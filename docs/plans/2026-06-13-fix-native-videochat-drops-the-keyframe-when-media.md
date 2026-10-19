# Fix: native VideoChat drops the keyframe when media beats presence

## Context

During the 2026‑06‑13 web↔native A/V spot‑check, a native peer received remote
VP8 but showed **blank video / avatar** instead of the remote camera. The cause
was filed as a bug in `TODO.md:14` and overlaps the existing **PLI TODO**
(`TODO.md:164`). This plan fixes the *decoder‑creation race* that is the actual
root cause; PLI remains a separate, complementary enhancement (see Out of scope).

### Root cause (confirmed by reading the code)

`VideoChat::OnRemoteVP8Frame` (`engine/wf_edit/video_track.cc:177‑187`) **silently
drops** a frame when the peer is not yet in `peer_video_`:

```cpp
auto it = peer_video_.find(peer_id);
if (it == peer_video_.end()) {
    static int s_miss = 0;
    if (++s_miss <= 3)
        std::fprintf(stderr, "video: VP8 frame for unknown peer %s\n", peer_id.c_str());
    return;                       // ← keyframe lost here
}
```

The per‑peer decoder is created **only** by the presence‑driven
`VideoChat::SyncPeers` (`video_track.cc:115‑152`), fed each frame from
`collab->Peers()` (`main.cc:~1914`). But a `PeerConnection` — and therefore
inbound media → `OnRemoteVP8Frame` — can be created *ahead of presence* by
`WebrtcSession::OnSignal` (`webrtc_session.cc:367‑404`), whose own comment says:

```cpp
// Answerer: create PeerState if we receive an offer before SyncPeers fires.
auto state = GetOrCreate(from_peer, is_offerer);
```

So media beats the presence‑driven decoder creation. If the dropped frame is the
**initial keyframe** and the sender is a browser (one keyframe, then relies on
RTCP PLI), the decoder stays `waiting_for_keyframe` forever → permanent blank.
Native↔native self‑heals in ~1 s via the periodic keyframe
(`kKeyframeInterval = 30`, `video_track.cc:44`) but still shows a brief blank.

Audio (`VoiceChat::OnRemoteOpus`, `voice_track.cc:223‑258`) has the *identical*
early‑return but tolerates it: every Opus packet is independently decodable, so
the next packet after `SyncPeers` registers the peer plays fine.

```
relay offer arrives ──► WebrtcSession::OnSignal ──► GetOrCreate(peer)      [media path, network thread]
                                                          │
                                            ICE/DTLS up, browser sends 1 KEYFRAME
                                                          │
                                                          ▼
                                      OnRemoteVP8Frame(peer)  ── peer ∉ peer_video_ ──►  DROP  ✗
presence beacon merges later ─► VideoChat::SyncPeers creates decoder   [too late: keyframe already gone]
                                                          │
                                       decoder stuck waiting_for_keyframe ──► blank video
```

## Fix — lazy‑create the per‑peer decoder on first media

Create the decoder *on demand* inside `OnRemoteVP8Frame` when the peer is
unknown, instead of dropping the frame, so the initial keyframe is decoded
immediately. Factor the creation logic (currently inlined in `SyncPeers`) into a
shared `EnsurePeer` helper so the presence path and the media path are identical
(DRY). Mirror the same change in audio for symmetry.

**Why lazy‑create over an eager WebRTC‑connect callback:** it touches only two
leaf files (no changes to `WebrtcSession`, `main.cc`, or the presence→decoder
ownership model), avoids a second owner of the peer map and the cross‑subsystem
lock‑ordering hazard that a callback from `GetOrCreate`/`onStateChange` would
introduce, and fully fixes the observed failure (the *first* frame is decoded on
arrival). The only thing eager‑create would buy is a decoder existing a few ms
earlier — irrelevant when the bug is the first frame being dropped.

**Safe against reaping (verified):** media only flows for a peer whose
`PeerConnection` is live; `WebrtcSession::SyncPeers` (`webrtc_session.cc:356‑362`)
tears down any peer not in the roster, and `main.cc` feeds the *same* roster to
`video->SyncPeers` and `webrtc->SyncPeers` each frame. So a peer that can deliver
media is a peer `VideoChat::SyncPeers` will **not** reap. The only reap of a
lazily‑created decoder happens in the same frame the connection is also torn down
(peer genuinely gone) — discarding its video is then correct, and
`UploadFrames` correctly skips GL‑texture deletion for a never‑uploaded peer
(`gl_tex == 0`).

**Thread‑safe (verified):** `vpx_codec_dec_init` / `opus_decoder_create`
initialise a self‑contained context (only process‑global *const* codec tables are
shared). The codebase already calls `vpx_codec_dec_init` on the network thread
today via `ResetDecoder` (`video_track.cc:168‑175`). Both lazy‑create paths run
under the existing `peers_mu_` the handlers already hold, serialising against
`SyncPeers`/`UploadFrames`/`Stop`.

### Edits

**`engine/wf_edit/video_track.h`** — add a private helper + a GL‑free test seam:
```cpp
// Return the PeerVideo for peer_id, creating its VP8 decoder on first use.
// Caller MUST hold peers_mu_. nullptr only if decoder init fails. Shared by
// SyncPeers (presence) and OnRemoteVP8Frame (media that beats the roster).
PeerVideo* EnsurePeer(const std::string& peer_id);
```
```cpp
// True if a decoded frame is pending upload for this peer (GL-free; mirrors
// VoiceChat::PeerLevel). Used by the headless video-race regression test.
bool PeerHasFrame(const std::string& peer_id);   // public
```

**`engine/wf_edit/video_track.cc`**
- Add `VideoChat::EnsurePeer` — body lifted verbatim from the `SyncPeers`
  add‑loop (`:120‑133`) so the two paths are byte‑identical.
- `SyncPeers` add‑loop (`:120‑134`) collapses to `for (const auto& pi : peers) EnsurePeer(pi.peer_id);` (reap loop `:136‑151` unchanged).
- `OnRemoteVP8Frame` miss block (`:181‑187`) → `PeerVideo* pv = EnsurePeer(peer_id); if (!pv || !pv->decoder) return;` (delete the `s_miss` drop counter — it was the bug's symptom). Everything from `:193` down is unchanged.
- Add `PeerHasFrame` (locks `peers_mu_` then `frame_mu`; returns `frame_dirty && !rgb.empty()`).

**`engine/wf_edit/voice_track.h` / `voice_track.cc`** — mirror exactly:
`VoiceChat::EnsurePeer` lifted from the `SyncPeers` add‑loop (`:191‑200`),
`SyncPeers` collapsed, `OnRemoteOpus` miss (`:227‑228`) → lazy‑create. (Keep the
`opus_decoder_create(48000, 1, &err)` literals inline — they are the existing
unnamed Opus rate/channel contract; naming them is out of scope.)

All edits stay in the local `wfedit` desktop‑tool idiom (`std::map`, `std::mutex`,
`std::printf`) — `docs/coding-conventions.md` is scoped to the `wfsource/`
runtime, not `engine/wf_edit/`. The carried‑over rules (DRY, pre‑increment, no new
magic numbers) are honoured; the net diff is ~+24/−18 and the handlers get shorter.

### Add a one‑line cross‑reference comment
At the lazy‑create site, note this fixes the *decoder‑creation* race and is
distinct from the *lost‑keyframe* PLI work in `TODO.md:164`, so a future reader
doesn't conflate them.

## Regression test (same commit)

Follow the established env‑gated headless self‑test pattern
(`WF_EDIT_MESH_TEST`/`WF_EDIT_TURN_TEST` in `main.cc`; registered via `add_test`
in `CMakeLists.txt`). No GL, no camera, no network — a pure in‑process call into
the function under test. `libvpx`/`libopus` are already linked into `wf_edit`.

**`RunVideoRaceTest()` (env `WF_EDIT_VIDEO_RACE_TEST`), added to `main.cc` dispatch:**
1. Construct a `VideoChat` (do **not** call `Start()` — no capture thread/camera).
2. Encode one real VP8 **keyframe** with libvpx (320×240 synthetic I420, `VPX_EFLAG_FORCE_KF`; assert `VPX_FRAME_IS_KEY`) — mirrors `OpenCamera`/`EncodeAndSend`.
3. Call `OnRemoteVP8Frame("ghost-peer", buf, len, true)` **without ever calling `SyncPeers`** — the exact bug condition.
4. Assert `PeerHasFrame("ghost-peer") == true`. **Fails on `master` today** (frame dropped, peer never created); **passes after the fix**.
5. **Negative control:** feed a *delta* frame to a second unregistered peer; assert `PeerHasFrame == false` (lazy‑created decoder still correctly waits for a keyframe — proves the gate isn't blindly accepting garbage).
6. **Audio mirror (cheap):** encode one Opus frame, `OnRemoteOpus("ghost-peer", …)` for an unregistered peer, assert `PeerLevel("ghost-peer") > 0` (existing GL‑free accessor).
7. Print `[video-race] all PASS` / `FAIL`; `fflush(stdout)`; return 0/1.

**`CMakeLists.txt`** — register beside the other A/V tests:
```cmake
add_test(NAME wf_edit_video_race
    COMMAND sh -c "WF_EDIT_VIDEO_RACE_TEST=1 $<TARGET_FILE:wf_edit> 2>&1 | tee /dev/stderr | grep -q '\\[video-race\\] all PASS'"
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})
```

## Out of scope

- **RTCP PLI (`TODO.md:164`)** — sender‑side keyframe‑on‑request via libdatachannel
  RTCP feedback. That is the complementary fix for a *genuinely lost* keyframe
  (transit loss, decoder corruption reset), not the decoder‑creation race fixed
  here. Leave the TODO; update its note to record that the creation‑race half is
  now closed so the two aren't conflated.

## Files

| File | Change |
|------|--------|
| `engine/wf_edit/video_track.cc` | `EnsurePeer`; lazy‑create in `OnRemoteVP8Frame`; `SyncPeers` collapse; `PeerHasFrame` |
| `engine/wf_edit/video_track.h`  | declare `EnsurePeer` (private), `PeerHasFrame` (public) |
| `engine/wf_edit/voice_track.cc` | `EnsurePeer`; lazy‑create in `OnRemoteOpus`; `SyncPeers` collapse |
| `engine/wf_edit/voice_track.h`  | declare `VoiceChat::EnsurePeer` (private) |
| `engine/wf_edit/main.cc`        | `RunVideoRaceTest()` + env dispatch |
| `CMakeLists.txt`                | register `wf_edit_video_race` `add_test` |
| `docs/plans/2026-06-13-native-video-keyframe-race.md` | project plan doc (per SRC convention) |
| `TODO.md`                       | mark `:14` fixed → done section; annotate `:164` (PLI) that the creation‑race half is closed |

## Verification

1. **Build the editor**
   ```
   task build-wf-edit            # or: cmake --build build-editor --target wf_edit -j
   ```
   PASS = compiles clean (`wf_edit`/`wf-edit`).

2. **Regression test fails before the fix, passes after** (proves it bites)
   ```
   # on master (or stash the video_track.cc fix): expect FAIL / no PASS line
   WF_EDIT_VIDEO_RACE_TEST=1 ./build-editor/wf-edit 2>&1 | grep -c '\[video-race\] all PASS'
   # with the fix applied: expect "1"
   ```
   PASS = `0` before the fix, `1` after.

3. **CTest registration**
   ```
   cd build-editor && ctest -R wf_edit_video_race --output-on-failure
   ```
   PASS = `1/1 Passed`.

4. **No regression in existing A/V self‑tests**
   ```
   cd build-editor && ctest -R 'wf_edit_(mesh|turn|connect_retry)' --output-on-failure
   ```
   PASS = all pass.

5. **End‑to‑end (manual, the original repro):** start a web peer with fake media
   and a native receive‑only peer
   ```
   WF_COLLAB_NO_CAM=1 ./build-editor/wf-edit -L <level>.iff
   ```
   Confirm the remote camera renders in the Collaborators panel (no
   "video: VP8 frame for unknown peer" stuck state). PASS = remote video visible.
