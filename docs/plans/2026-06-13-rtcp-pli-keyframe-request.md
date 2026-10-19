# RTCP PLI — fast keyframe recovery for native WebRTC video

## Context

Native wf-edit video recovered from a lost/corrupt keyframe only at the next
*periodic* keyframe — up to ~1 s (`kKeyframeInterval = 30` @ 30 fps,
[`video_track.cc`](../../engine/wf_edit/video_track.cc)). Worse, a **browser
sender resends a keyframe only on RTCP PLI**, so a native receiver that missed a
keyframe from a browser peer could stay blank indefinitely — the
genuinely-lost-keyframe half left open by the decoder-creation fix
([`1c7aeafd`](https://github.com/wbniv/WorldFoundry/commit/1c7aeafd)). This adds
RTCP **Picture Loss Indication** so recovery drops to one round-trip. Two halves:

- **(A) Honor** an incoming PLI → force our next encoded frame to be a keyframe.
  A browser *receiver* already sends PLI automatically; native↔native too.
- **(B) Send** a PLI → when our receiver's decoder is stuck/corrupt, ask the
  sender for a keyframe. Recovers native-receiving-from-browser and native↔native.

The web path (`webrtc_web.cc`) gets this free — the browser's media stack does PLI
both directions. This work is native-only.

## Confirmed facts (libdatachannel v0.21.2, vendored `build-editor/_deps/libdatachannel-src`)

The code hand-rolls RTP over `rtc::Track` (no `MediaHandler`). With no handler:
- **Inbound RTCP is delivered to `onMessage` as `rtc::binary`** (`impl/track.cpp:169-171`);
  `dispatchMedia` (`impl/peerconnection.cpp:528-610`) fans a PLI to the **video**
  track (both its SSRCs map there). The old `size()<=13` guard silently dropped the
  12-byte PLI — adding an `rtc::IsRtcp()` guard is also a latent-bug cleanup (compound
  RTCP could otherwise be misparsed as VP8).
- **Outbound `track->send(binary)` auto-retags as Control when `IsRtcp()` matches**
  (`impl/track.cpp:163-171`) → a raw 12-byte PLI goes out over SRTCP. No
  `make_message`/`RtcpPli` struct needed (and `RtcpPli::preparePacket` sets both SSRC
  fields to the same value — wrong for us). `rtc::binary` is `std::vector<std::byte>`.
- **PLI wire format** (RFC 4585 §6.3.1, 12 bytes): `0x81, 206, 0x00, 0x02,
  sender_ssrc[4], media_ssrc[4]`. `media_ssrc` is the **sender's** SSRC → captured
  from inbound RTP header bytes 8–11. Honor PT=206 with FMT∈{1=PLI, 4=FIR}.
  ⚠ Byte 1 is the **full** RTCP packet type (206) — do *not* mask with `0x7f` (that's
  `IsRtcp`'s 64..95 range heuristic, not the exact PT). [caught by the test, below]

## Design

### Part A — honor an incoming PLI (force a keyframe)
- `VideoChat` gains `std::atomic<bool> force_keyframe_`, `RequestKeyframe()`,
  `HasPendingKeyframe()`, and a pure `static DecideForceKey(flag, frames_since_key,
  interval)` used by `CaptureThread` (preserves the post-increment cadence; the
  `exchange` coalesces a PLI burst into one keyframe and resets the counter).
- `webrtc_session.cc` video `onMessage`: `rtc::IsRtcp` branch *before* any RTP field
  access → `IsPliPacket` → `vd_->RequestKeyframe()`. Audio `onMessage`: `IsRtcp→return`.
  Capture the remote video SSRC from inbound RTP into `PeerState`.

### Part B — send a PLI on loss (main-loop pump, not a network-thread callback)
A callback from `OnRemoteVP8Frame` (holding `VideoChat::peers_mu_` + `PeerState::vp8_mu`)
into `WebrtcSession::SendPli` (needs `WebrtcSession::peers_mu_`) creates an ABBA risk
against `SendVP8`. Instead poll on the main thread, where the two `peers_mu_` never nest:
- `PeerVideo` gains `last_vp8_frame_mono` / `last_pli_mono`; `OnRemoteVP8Frame` stamps
  arrival **at entry, before the waiting-for-keyframe gate** (so an inter-only-while-
  waiting stream still counts as active).
- `VideoChat::TakePliRequests(now)` returns peers `waiting_for_keyframe && active(<2 s)
  && throttled(≥0.25 s)`, stamping the throttle.
- `WebrtcSession::SendPli(pid)` builds `MakePliPacket(video_ssrc_, remote_video_ssrc)`
  and sends on the video track (no-op if `!connected` or SSRC unknown).
- `main.cc` collab tick: `for (pid : video->TakePliRequests(now)) webrtc->SendPli(pid);`

### Shared helpers
`WebrtcSession::MakePliPacket`/`IsPliPacket` — public, pure, `std::vector<std::byte>`
(== `rtc::binary`, feeds `Track::send` directly), unit-testable without a connection.

PLI send/receive logs are gated behind `WF_COLLAB_VIDEO_DEBUG` (mirrors `WF_COLLAB_VOICE_DEBUG`).

## Files changed

`engine/wf_edit/webrtc_session.{h,cc}` (helpers, `PeerState.remote_video_ssrc`, onMessage
branches, `SendPli`, debug flag) · `engine/wf_edit/video_track.{h,cc}` (`force_keyframe_`,
`RequestKeyframe`/`HasPendingKeyframe`/`DecideForceKey`/`TakePliRequests`, `PeerVideo`
timestamps, stamp + `DecideForceKey` use) · `engine/wf_edit/main.cc` (PLI pump, `RunPliTest`,
dispatch) · `CMakeLists.txt` (`wf_edit_pli`).

## Verification

### 1. Build
```
$ task build-wf-edit
[100%] Built target wf_edit
✓ wf-edit built → build-editor/wf-edit
```
**PASS**

### 2. Test bites
The `wf_edit_pli` test caught a real regression on the first run — `IsPliPacket`
masked the RTCP packet-type byte with `0x7f` (`206 & 0x7f = 78 ≠ 206`):
```
[pli] PASS — MakePliPacket bytes + big-endian SSRCs
[pli] FAIL — IsPliPacket parses its own PLI (media SSRC)
[pli] FAIL — FIR (FMT=4) recognised as keyframe request
[pli] FAIL
```
After removing the mask (byte 1 is the full RTCP PT):
```
[pli] all PASS
```
**PASS** (test discriminates correct from incorrect behavior).

### 3. ctest sweep
```
$ ctest --test-dir build-editor -R 'wf_edit_(pli|video_race|mesh|turn|connect_retry)'
      Start 17: wf_edit_connect_retry ... Passed
      Start 18: wf_edit_turn ............ Passed
      Start 19: wf_edit_mesh ............ Passed
      Start 20: wf_edit_video_race ...... Passed
      Start 21: wf_edit_pli ............. Passed
100% tests passed, 0 tests failed out of 5
```
**PASS**

### 4. Manual end-to-end (needs a display — OPEN)
Two `wf-edit` peers (or native + browser fake-media) with `WF_COLLAB_VIDEO_DEBUG=1`:
confirm a `video: PLI ->` / `video: PLI from peer …` log pair and remote video resyncs
in ~one RTT, not ~1 s; native-sender → browser-receiver now honors the browser's
automatic PLI. **Not yet run** (no display this session).

## Out of scope
Live SRTCP round-trip in CI (flaky; two PCs + camera) — manual above. NACK / REMB /
SR-RR / FEC. Per-peer simulcast (`RequestKeyframe` is encoder-global, correct for the
single-stream design).
