# Plan: Voice + Video (A/V) for the browser editor (`wf_edit_web`)

> Status: approved 2026-06-13. Feature branch `2026-web-av` off `2026-new-level`.
> Brings back the voice/video deferred in [2026-06-12-wf-edit-in-the-browser.md](2026-06-12-wf-edit-in-the-browser.md).

## Context

The web editor v1 shipped co-edit + presence + text chat but **deferred voice/video** — the
native A/V stack (libdatachannel + Opus + libvpx + V4L2 + miniaudio) doesn't port to wasm. This
brings A/V back to the **web** build. Key realisation: the browser already has **native WebRTC**
(`RTCPeerConnection`, `getUserMedia`, built-in Opus/VP8/H264, DTLS-SRTP, ICE/STUN/TURN), so the
web build needs **none** of those native libs — the browser does capture, encode, transport,
decode and playback. Our C++ becomes a thin coordinator shuttling SDP/ICE JSON between the
**already-working** relay `CH_SIGNAL` (0x05) path and a per-peer JS `RTCPeerConnection`. Because
the signaling wire + offerer rule are shared with the native editor, a browser peer and a native
`wf-edit` peer interoperate in the same relay room.

The relay path is already correct for web: `main.cc` CollabDrain (~866) routes a `0x05` frame to
`webrtc->OnSignal(from, json)`; the frame loop (~1908-1935) calls `webrtc->SyncPeers(...)` and
sends `[0x05][to\0 json]` from `webrtc->DrainSignaling()`. Today those calls hit the web stub.

## Architecture (one sentence)

Preserve the native C++ interfaces (`WebrtcSession`/`VoiceChat`/`VideoChat`); implement them for
web by delegating to a JS `RTCPeerConnection` shim — the same shape as `ws_client_emscripten.cc`
(native interface, browser async-callback implementation). **No changes to `main.cc`'s shared
integration block** — keeping it byte-identical is what makes web↔native interop free.

## Files

**Create**
- `engine/wf_edit/webrtc_web.cc` — real web `WebrtcSession`/`VoiceChat`/`VideoChat` +
  `ResolveIceConfig`/`WebrtcCleanup`, `#if defined(__EMSCRIPTEN__)`. Same headers as native;
  bodies call JS; holds the outgoing-signal queue `DrainSignaling()` returns.
- `web/wf_webrtc.js` — Emscripten `--js-library`: `Map<peer_id, RTCPeerConnection>`,
  `getUserMedia` lifecycle, `ontrack`→`<video>`/`<audio>`, video-overlay layout, the C++-called
  functions; calls back via exported `_wfwebrtc_queue_signal`.

**Modify**
- `engine/wf_edit/collab_stub_web.cc` — remove `VoiceChat`/`VideoChat`/`WebrtcSession`/
  `ResolveIceConfig`/`WebrtcCleanup` (→ `webrtc_web.cc`); keep `CollabSession` + `MonoNow`.
- `CMakeLists.txt` (`wf_edit_web` ~1390-1501) — add `webrtc_web.cc`; add
  `"SHELL:--js-library web/wf_webrtc.js"`; `-sEXPORTED_FUNCTIONS=...,_wfwebrtc_queue_signal`.
- `engine/wf_edit/collab_panel.cc` — `#if __EMSCRIPTEN__` hook computing per-peer + self thumbnail
  screen rects (`ImGui::GetCursorScreenPos()` + `kThumbW/H`, → canvas CSS px via
  `io.DisplayFramebufferScale`) → `wfwebrtc_layout_video`/`wfwebrtc_layout_self`.
- `web/shell-edit.html` — a positioned `<div id="wf-video-layer">` over the canvas. ICE env vars
  already flow via `?wfenv=KEY=VAL`.

**Unchanged (the contract):** `webrtc_session.h`, `voice_track.h`, `video_track.h`,
`collab_session.h`, `main.cc` integration block.

## C++ ↔ JS bridge (payloads are C strings — same as the relay wire)

**C++ → JS:** `wfwebrtc_set_self(peer_id)`, `wfwebrtc_create_peer(peer_id, is_offerer, ice_json)`,
`wfwebrtc_on_signal(peer_id, json)`, `wfwebrtc_close_peer(peer_id)`, `wfwebrtc_set_mic(en)`,
`wfwebrtc_set_cam(en)`, `wfwebrtc_connected_count()`, `wfwebrtc_peer_level(peer_id)`,
`wfwebrtc_layout_video(peer_id,x,y,w,h,vis)`, `wfwebrtc_layout_self(x,y,w,h,vis)`.

**JS → C++** (reentrant callback, `EMSCRIPTEN_KEEPALIVE` + exported):
`wfwebrtc_queue_signal(to_peer_id, json)` — JS `onicecandidate` + post-`setLocalDescription`
callbacks push `{to,json}` onto `pending_signals_`; `DrainSignaling()` ships it next frame. This
is the **async→sync adapter**, identical in shape to native's `QueueSignal`
(webrtc_session.cc:210-227). JSON fields must match native exactly: offer/answer `{type,sdp,from}`,
candidate `{type,candidate,sdpMid,from}`; `from` = `our_peer_id`.

## Per-method mapping (highlights)

- `WebrtcSession::SyncPeers` → diff; new peer ⇒ `create_peer(pid, our_peer_id<pid, ice_json)`
  (**same lower-id-offers rule as native**, webrtc_session.cc:351); departed ⇒ `close_peer`.
- `OnSignal` → `wfwebrtc_on_signal` (JS lazily creates the PC). `DrainSignaling`/`ConnectedPeerCount`
  → `pending_signals_` / `wfwebrtc_connected_count()`.
- `VoiceChat` thin shim: `SetMuted`→`set_mic` (first unmute = `getUserMedia({audio})` in the panel
  user gesture); `OnRemoteOpus`/`OnCapture`/`OnPlayback`/`Tick` = no-ops (browser `<audio>` plays
  remote; PCM never enters C++); `PeerLevel` → optional WebAudio AnalyserNode.
- `VideoChat` thin shim: `SetCameraEnabled`→`set_cam`; `OnRemoteVP8Frame` = no-op; `PeerTexture`
  returns 0 (panel → initials avatar, leaving a rect the overlay `<video>` fills).
- **No renegotiation:** `create_peer` adds audio+video `sendrecv` transceivers up front, `replaceTrack`
  on enable — matches native's "tracks from the first offer" SDP (Opus PT-111 / VP8 PT-96).

## Video display: HTML `<video>` overlay

Absolutely-positioned `<video>` over the WebGL2 canvas (in `#wf-video-layer`), not per-frame
`<video>`→canvas→`texImage2D`. Preserves hardware decode, far less code, no per-frame copy;
self-preview = `video.srcObject = localStream`. Panel-rect tracking (drag/dock/scroll/collapse) is
driven from `collab_panel.cc` (hide on collapse/clip). Fallback if occlusion is unacceptable: the
GL-texture path (`PeerTexture` signature kept), throttled + single scratch canvas.

## ICE config

`ResolveIceConfig` (web) reads the same `WF_COLLAB_STUN/TURN[:port]/TURN_USER/PASS/TLS/FORCE_RELAY`
env (fed by `?wfenv=`), serializes to an `iceServers` JSON → `new RTCPeerConnection(...)`. 1:1 with
native's `BuildRtcConfig`. Default `stun:stun.l.google.com:19302`.

## Phases (each independently verifiable; headless where possible)

Headless Chrome fakes media: `--use-fake-device-for-media-stream --use-fake-ui-for-media-stream`
(auto-grant + test-pattern video + beep). Verify via the established CDP driver pattern (two
**separate** Chrome processes — background `createTarget` tabs pause rAF — asserting
`Runtime.consoleAPICalled`). Add console affordances (`webrtc: connected peers=N`,
`ontrack audio|video from <peer>`) + a `WF_COLLAB_AV_AUTOSTART=1` env hook (enable mic+cam on first
connect, for headless).

1. **Signaling + PC connect, no media.** `WebrtcSession` + `wf_webrtc.js` PC lifecycle +
   `_wfwebrtc_queue_signal`; up-front transceivers. Verify web↔web (`connected peers=1`) + web↔native.
2. **Audio.** `set_mic` (getUserMedia audio, `replaceTrack`, `ontrack`→`<audio>`). Verify web↔web
   (fake mic + autostart: `ontrack audio`, track live) + web↔native (Opus both directions).
3. **Video.** `set_cam`, overlay + `collab_panel.cc` rect hook, self-preview. Verify web↔web (fake
   video: `videoWidth>0`, overlay positioned, screenshot) + web↔native.
4. **UI polish + robustness.** Panel-button permission prompts (real path), AnalyserNode meters,
   overlay hide-on-collapse, teardown on peer-leave/`beforeunload`, PC-failed→recreate. 3-peer mixed
   mesh (2 web + 1 native).

## Verification (end-to-end)

- **web↔web** (two Chrome processes, fake media, local `wf-relay`): primary headless CI — per-phase
  console-log + CDP `Runtime.evaluate` assertions (connected count, track readyState, videoWidth,
  overlay rect) + a Phase-3 screenshot.
- **web↔native** (browser + native `wf-edit`, same relay room): the critical interop check that the
  browser's `RTCPeerConnection` and native libdatachannel exchange media. Run every phase.
- **3-peer mixed mesh** in Phase 4.

## Risks

1. **Autoplay/permission UX** — gate mic/cam on the panel buttons (user gesture); retry remote
   `<audio>.play()` on first gesture. Headless bypasses via `--use-fake-ui-for-media-stream`.
2. **Secure context** — `getUserMedia` needs https/localhost (deployed HTTPS; dev localhost).
3. **Overlay z-order/occlusion** — drive rect from the panel; hide on collapse/clip; partial
   occlusion is a v1 limitation; texture path is the fallback.
4. **web↔native SDP drift** — transceivers up front (no renegotiation), JSON fields byte-identical,
   web↔native interop in CI every phase.
5. **Mobile Safari** — `playsinline`/`muted`; VP8-vs-H264 note (out of scope for desktop-Chrome CI).
6. **TURN/symmetric NAT** — wired via `WF_COLLAB_TURN*`/`?wfenv=`; `force_relay` testable headlessly.
7. **JS↔C string lifetime / symbol stripping** — copy strings on entry; `EMSCRIPTEN_KEEPALIVE` +
   `-sEXPORTED_FUNCTIONS` for `_wfwebrtc_queue_signal`.
