# Plan: finish the two deferred items from web A/V

## Context

Web A/V (voice+video over browser WebRTC) shipped + merged to `2026-new-level` across 4
phases. Two items were deferred as "minor"; this finishes them:

1. **Audio-level meters** — `wfwebrtc_peer_level` returned a hardcoded 0, so the
   Collaborators-panel per-peer audio meter (`collab_panel.cc` `ImGui::ProgressBar(level…)`,
   fed by `VoiceChat::PeerLevel`) was always flat.
2. **web↔native media spot-check** — Phase 1 proved web↔native *connect* (SDP/ICE/transport
   interop). The open question is whether the browser's `RTCPeerConnection` and native
   libdatachannel actually exchange **media** (Opus PT-111 / VP8 PT-96 RTP).

**Device/privacy finding (changes the approach for #2):** this is Will's **live desktop**
(`:0`), and it *does* have a webcam (`/dev/video0`) + mic (ALSA `card 1` capture) + pipewire
— my earlier "no hardware" note was wrong. But `VideoChat::Start()` (video_track.cc)
**eagerly** opens the camera (`cam_enabled_.store(OpenCamera())`), so launching native A/V
would silently **activate Will's real webcam** (LED on, video sent to peers). The mic is
safer — `ma_device_start` only runs when unmuted (default muted). So a native media test must
**not** open the camera. `sudo` is not passwordless (can't load a `v4l2loopback` dummy cam).

## Approach

### Item 1 — audio-level meters (web)
Already wired (this session, pre-plan-mode): `wfwebrtc_peer_level` in
`engine/wf_edit/webrtc_web.cc` now returns the audio receiver's RFC-6464
`getSynchronizationSources()[0].audioLevel` (0..1) — no WebAudio graph, only populated while
packets arrive, so it reads ~0 on silence and rises with the peer's voice.
`VoiceChat::PeerLevel` already calls it; `collab_panel.cc` already renders it. No other change.

### Item 2 — web↔native media, non-intrusively (native receive-only)
Add a native env flag **`WF_COLLAB_NO_CAM=1`** that makes `VideoChat::Start()` skip
`OpenCamera()` (leave `cam_enabled_=false`) — native then joins a call as a **receive-only**
peer (no webcam activation; mic already idle while muted). This is also a generally useful
"join as a viewer/listener" affordance. Then verify the browser→native media direction (the
interop that matters), which needs no native capture:
- **Audio:** native receives the web peer's Opus → `VoiceChat::OnRemoteOpus` decodes;
  `WF_COLLAB_VOICE_DEBUG=1` already logs per-second `recv` counts → assert `recv_count > 0`.
- **Video:** native receives VP8 → `VideoChat::OnRemoteVP8Frame` decodes → `PeerTexture` non-zero;
  capture the native editor window (`--frames N --screenshot`) and confirm the web peer's
  (fake-camera) video thumbnail renders in the native Collaborators panel.

native→web (native *sending*) is the same RTP mechanism in reverse but requires activating
Will's real webcam/mic → left as a manual/consented real-hardware check (documented), not auto-run.

## Files

- `engine/wf_edit/webrtc_web.cc` — `wfwebrtc_peer_level` via `getSynchronizationSources()`
  (DONE; web-only `#if __EMSCRIPTEN__`).
- `engine/wf_edit/video_track.cc` — in `Start()`, honor `WF_COLLAB_NO_CAM` (skip `OpenCamera`,
  log "video: capture suppressed (WF_COLLAB_NO_CAM)"). Native-only file; tiny guard.

## Verification

1. **Level meters (web↔web, headless):** rebuild `task build-web-edit`; two headless-Chrome
   processes (`--use-fake-device-for-media-stream --use-fake-ui-for-media-stream`) +
   `WF_COLLAB_AV_AUTOSTART=1`, local `wf-relay`; via CDP `Runtime.evaluate` assert
   `wfwebrtc_peer_level(<peer>) > 0` on both (the fake beep drives a non-zero level). Reuses
   the existing `/tmp/av_*.mjs` CDP harness.
2. **web↔native media (non-intrusive):** `task build-wf-edit-fast`; run native
   `WF_COLLAB_NO_CAM=1 WF_COLLAB_VOICE_DEBUG=1 build-editor-fast/wf-edit
   --leveltree=…snowgoons-blender.lev --level=…snowgoons-standalone.iff --room=avx
   --relay=ws://localhost:PORT --frames 600 --screenshot /tmp/native_rx.ppm` on `:0` (transient
   window, **no webcam**); concurrently a web peer sending fake audio+video. Assert: native log
   `voice-dbg … recv` with count > 0 (browser→native audio), and the native screenshot shows the
   web peer's video thumbnail (browser→native video). Confirm native's stderr shows
   `video: capture suppressed` (no camera opened).
3. **No regression:** native (no-ASan) build links clean; web↔web A/V still passes.

## Branch / commit

Small polish — do it directly on `2026-new-level` (consistent with the session's other
direct commits; the A/V *feature* branch is already merged). Two commits: (a) web peer-level
meter; (b) native `WF_COLLAB_NO_CAM` + the verified web↔native media spot-check. Update the A/V
plan doc + manual (meter live; web↔native media verified browser→native; native→web noted as
hardware/consent). Push `2026-new-level`.
