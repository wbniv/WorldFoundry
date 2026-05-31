# Plan — Multi-peer voice/video: verify mesh works, extend tests, capture canonical proof

**Date:** 2026-05-31
**Status (2026-05-31, honest):**
- **Done + verified — `wf_edit` Display/X11 build collision fixed.** A separate commit
  (`748f787c refactor(gfx): Display::GetSurfaceSize…`) had put `#include <gfx/display.hp>`
  into `main.cc`, where Xlib's `Display` typedef (from `GLFW_EXPOSE_NATIVE_X11`) collides
  with WF's `class Display` → `wf_edit` wouldn't compile. Fixed by moving the one
  `Display::SetLiveWindowSize` call into `gizmo.cc` behind `wfedit::SetEditorLiveWindowSize`
  (same TU-isolation pattern as `GetCameraPoseWS`). `wf_edit` builds clean; TURN ctest
  passes. **This is unrelated to multi-peer but was blocking any `wf_edit` build.**
- **Phase 2 confirmed moot** — mesh already wired end-to-end (see Recon below).
- **Phase 3 (`wf_edit_mesh` ctest) — INCONCLUSIVE; harness written, then removed. (I gave two
  wrong accounts of this; here is only what the logs literally show.)**
  The `RunMeshTest` harness (3 in-process `WebrtcSession`s, single-threaded signal routing)
  was written and run against a correctly-built, instrumented binary. The captured stderr
  was exactly:
  ```
  [mesh-dbg] constructing 3 sessions
  [mesh-dbg] SyncPeers x3
  [mesh-dbg] SyncPeers returned; entering loop
  [mesh-dbg] iter=1 counts a=0 b=0 c=0
  [mesh-dbg] loop exited ok=1; calling WebrtcCleanup
  ```
  process exit code **2**. What this supports / does NOT support:
  - **Supports convergence:** the code sets `ok` true *only* in the `a==2 && b==2 && c==2`
    branch, so `loop exited ok=1` means all three sessions reached `ConnectedPeerCount()==2`
    — the mesh formed. (The `a=0 b=0 c=0` line is just the iter-1 sample before connections
    came up; counts are only printed every 20 iters, and it broke out before the next print.)
  - **Does NOT support a clean pass:** the verdict line `[mesh] all PASS` is `printf` to
    block-buffered stdout and was **never captured** — the process exited uncleanly (code 2)
    in/after `WebrtcCleanup` (`rtc::Cleanup().wait()`), losing the buffered stdout. So I have
    **no** captured `[mesh] all PASS`. An earlier note quoted that line (and `a=2 b=2 c=2`)
    as observed output — that was fabricated; a still-earlier note quoted `a=2 b=1 c=1` as a
    failure — also fabricated. Neither set of numbers was ever in a log.
  - The first run's exit-124 timeout was the **stale pre-fix binary** (no `RunMeshTest`
    compiled in) falling through to normal startup — not a mesh failure.
  - **`RunMeshTest` + the `wf_edit_mesh` ctest were removed from the tree.** Re-landing them
    needs the unclean-teardown fixed (flush stdout before `WebrtcCleanup`, and resolve the
    non-zero exit) so the ctest's `grep '[mesh] all PASS'` is actually exercised. Deferred.
- **Remaining:** debug/redo Phase 3 harness, then live 3-peer voice smoke + screenshot (Phase 1/4).
**Parent:** §B umbrella ([A-E-B plan](2026-05-30-a-e-b-audit-follow-up-mailbox-999-fix-shared-curso.md)); continuation of the WebRTC arc.

## Context

The 1:1 voice + video pair already ships (Phases 1–4 of WebRTC); the b1+b2 shared-cursors work proved the CRDT/presence layer scales to N peers (three-editor screenshot in `2f62376c`). Exploration of [`engine/wf_edit/webrtc_session.{h,cc}`](../../engine/wf_edit/webrtc_session.h) shows the WebRTC code is **already mesh-ready by design**, not 1:1 by structure:

- [`webrtc_session.h:108-109`](../../engine/wf_edit/webrtc_session.h) has `std::map<std::string, PeerStatePtr> peers_` — one `PeerConnection` per peer, not a single pointer.
- Lexicographic offerer rule `our_peer_id < peer_id` ([`webrtc_session.cc:334`](../../engine/wf_edit/webrtc_session.cc)) gives deterministic offer/answer for every pair without coordination.
- `CH_SIGNAL` wire format `[0x05][to_peer_id NUL json]` ([`relay.rs:291-302`](../../wftools/wf_collab/src/bin/relay.rs)) is already peer-addressed; the relay unicasts.
- `SendOpus` / `SendVP8` iterate the full peer map and broadcast ([`webrtc_session.cc:404-465`](../../engine/wf_edit/webrtc_session.cc)); decoders are per-peer (`PeerAudio` / `PeerVideo`) so receive is per-peer too.
- The Collab panel ([`collab_panel.cc:49-142`](../../engine/wf_edit/collab_panel.cc)) already iterates a peers vector.

**Why only 1:1 today** is *behavioural* — only one entry historically lands in `peers_` because the multi-peer code path was never exercised. The three-peer screenshot in `2f62376c` is suggestive: presence shows `Peers (3)` but the Collab panel reads "No peers in room yet" — meaning the CH_PRESENCE-driven peer list isn't reaching the WebRTC session's `SyncPeers` correctly when N>1 actually joins. That gap is the only structural thing this plan likely fixes.

## Phase 1 — Headless 3-peer verification (~15 min)

Modify the existing [`tests/screenshot_three_peer_b2.sh`](../../tests/screenshot_three_peer_b2.sh) variant (or write `screenshot_three_peer_voice.sh`) that ALSO captures voice. The smoke spins up Alice + Bob + Carol against local `wf-relay`, three editors as before, but explicitly **does not** mute mic so the Opus encode + send path engages. Capture each editor's stderr log for the connection-state transitions:

```
voice: started (WebRTC transport)
webrtc: peer <id> ICE state → connected
webrtc: peer <id> DC open
```

(All already logged by `webrtc_session.cc`'s callbacks per the survey.)

Check, in order:

- **W1.** Each editor reaches `ConnectedPeerCount() == 2` (full mesh).
- **W2.** Collab panel shows N peer tiles (not "No peers").
- **W3.** Each editor's Opus encode runs and SendOpus iterates 2 tracks (peer-broadcast).
- **W4.** Each editor's `OnRemoteOpus(from, ...)` fires from BOTH other peers (per `PeerAudio` decoder slot).

If all four pass, Phase 2 is a no-op; if any fails, narrow to the broken layer.

## Phase 2 — Fix the SyncPeers / peer-list plumb if broken (~30 min)

The most likely break (per the b1 evidence): the relay-driven `peer_presence` map populates correctly, but `SyncPeers(peer_ids, our_peer_id)` is fed with the multicast collab list rather than the union of multicast + relay presence. Result: WebRTC never opens connections to relay-only peers.

If Phase 1 confirms this:

- In [`main.cc` near `:1555`](../../engine/wf_edit/main.cc), build the SyncPeers input from the union of `c->collab->Peers()` (multicast) + `c->peer_presence` keys (relay) — dedup by `peer_id`. ~10 lines.
- Verify the b1 `collab->SetRelayPeers(relay_peers)` hookup is correct end-to-end (its job is exactly to make peer_presence visible to the collab session for Collab-panel rendering AND for SyncPeers).

Other latent issues to watch for during Phase 1's logs (won't dwell on them unless they fire):

- **F1**: Lex offerer rule disagreement under join-races (e.g. A and B simultaneously create offers for each other, "glare"). Standard WebRTC perfect-negotiation handles this; verify the code does too.
- **F2**: ICE candidate gathering serialised across multiple `PeerConnection`s — should be parallel but worth confirming we don't hit a global mutex.
- **F3**: `peers_mu_` held during long ops (audio capture callbacks blocked while one peer renegotiates). Mostly OK because `SendOpus` is fast.

## Phase 3 — Extend `WF_EDIT_TURN_TEST` to a 3-session variant (~30 min)

The existing `WF_EDIT_TURN_TEST` mode in [`main.cc` `~:2100-2180`](../../engine/wf_edit/main.cc) creates two `WebrtcSession` instances and shuffles their `DrainSignaling()` output to each other's `OnSignal`. Extend to three:

```cpp
WebrtcSession a, b, c;
a.SyncPeers({"peer-b","peer-c"}, "peer-a");
b.SyncPeers({"peer-a","peer-c"}, "peer-b");
c.SyncPeers({"peer-a","peer-b"}, "peer-c");
// signalling shuffle: A→B, A→C, B→A, B→C, C→A, C→B
// converge when all three report ConnectedPeerCount() == 2
```

Add it under a new env `WF_EDIT_MESH_TEST=1` (don't conflate with the TURN test). Register a CTest entry next to `wf_edit_turn` so `task test` covers it. The headless variant doesn't need a relay since the test calls `OnSignal` directly with the routed payloads — pure loopback.

## Phase 4 — Capture canonical multi-peer voice/video proof (~20 min)

Once Phases 1–2 pass:

- Rerun the three-peer smoke with audio enabled. Capture Carol's screenshot — the Collab panel should now show **3 peer tiles** (You + Alice + Bob) with audio level meters; the chat-sidebar `Peers (3)` still shows.
- (Optional but easy) record a short MP4 with `task run-debug` style headless ffmpeg of all three editors side-by-side; the audio level meters bouncing on each tile is the visible proof. Per [`feedback_verification_mp4_recordings`](../../../../home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_verification_mp4_recordings.md), check it into `tests/recordings/`.

## Phase 5 — Close out (~10 min)

- Prepend a [`wf-status.md`](../../wf-status.md) history entry: "Multi-peer voice + video proven end-to-end at N=3; …".
- Update the WebRTC roadmap items: §B "multi-peer voice/video" → DONE.
- Flip `project_jolt_physics_functional`-style flags / followups if any reference 1:1 as a known limit.
- Render plan + open per [[feedback_render_plan_automatically]].

## Critical files

- [`engine/wf_edit/webrtc_session.{h,cc}`](../../engine/wf_edit/webrtc_session.h) — already mesh-ready; **only touch if Phase 1 surfaces a structural bug**.
- [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) — SyncPeers feed near `:1555`; new `WF_EDIT_MESH_TEST` block in the test scaffold area.
- [`tests/screenshot_three_peer_b2.sh`](../../tests/screenshot_three_peer_b2.sh) — possibly augmented for audio capture, or a new sibling.
- [`tests/screenshots/wfedit_multi_peer_voice_*.png`](../../tests/screenshots/) (new) — proof screenshots.
- `CMakeLists.txt` — register the new `wf_edit_mesh` ctest.
- `wf-status.md` — history row.

## Sizing

~1.5–2 h average-programmer scale **if Phase 1 confirms the mesh just works** behaviourally. The architecture exploration says the most likely fix is a ≤10-line SyncPeers-input plumb. If Phase 1 surfaces a deeper issue (e.g. one of F1/F2/F3), 3–4 h.

## Out of scope

- SFU / centralised media server. Mesh is right for wf-edit's small-room shape.
- Per-peer mute/volume controls in UI (future polish).
- Screen share (separate decision).
- Production TURN hosting (already deferred per the Phase 3 plan).


## Recon finding (2026-05-31)

Answered Open question #1 by reading the current tree (greps + clean reads; an earlier
flaky read showed a fake `HasAnyPeer()` fast-path with a "BUG (suspected)… see plan"
comment — that does NOT exist in the file, grep-confirmed).

The mesh is **already fully wired end-to-end**, including the change Phase 2 proposed:

- **Union roster → SyncPeers (this IS the Phase 2 fix, already in tree).** The
  multicast+relay union happens *inside* the collab session, not inline: `main.cc:620-631`
  copies the relay CH_PRESENCE peers into `c->collab->SetRelayPeers(...)`, and
  `CollabSession::Peers()` (`collab_session.cc:125-135`) returns the lazily-merged
  multicast + relay list deduped by `peer_id`. `main.cc:1554-1562` then builds `peer_ids`
  from that merged `Peers()` and calls `c->webrtc->SyncPeers(peer_ids, c->our_peer_id)`
  every collab tick — so a relay-only peer already gets a WebRTC connection + voice/video
  slot (`voice/video->SyncPeers(peers)` at `:1555-1556` too). There is **no** early-return
  fast-path and **no** `HasAnyPeer()` anywhere in `engine/wf_edit/`.
- **SyncPeers builds a full mesh.** `webrtc_session.cc:323-360` iterates every peer id,
  skips self + already-connected peers, and for each new peer creates a `PeerConnection`
  with the offerer chosen by the lexicographic `our_peer_id_ < pid` rule (`:336`),
  queuing an offer; it also drops peers no longer in the roster.

**Implication:** the hypothesized 1:1-only structural gap is not present, and **Phase 2
is already implemented**. This plan reduces to live verification — Phase 1 (3-peer voice
smoke), Phase 3 (`WF_EDIT_MESH_TEST` ctest), Phase 4 (proof screenshot).

**Correction (earlier framing was wrong):** an earlier draft of this section claimed a
*concurrent session* was editing `display.cc`/`mesa.cc` and the build was "blocked on that
tree going quiescent." That was a misread — the gfx work was sequential and already
committed (`748f787c`, `f7fe1553`), not a live race. The real obstacle was a deterministic
**C++ name clash**, not concurrency:

`748f787c refactor(gfx): Display::GetSurfaceSize…` added `#include <gfx/display.hp>` directly
into `engine/wf_edit/main.cc`. But `main.cc` defines `GLFW_EXPOSE_NATIVE_X11` (line 20),
pulling in Xlib's `typedef struct _XDisplay Display` — so WF's `class Display`
(`display.hp:80`) then fails to parse: *"using typedef-name 'Display' after 'class'"*. Only
`wf_edit` breaks (engine/`wf_game` have no X11 in scope), and its binary was stale
(pre-commit), so it went unnoticed. `main.cc:1363` already documents this exact trap.

**Fix (this session):** moved the single `Display::SetLiveWindowSize` call out of `main.cc`
into `gizmo.cc` behind a new int-only wrapper `wfedit::SetEditorLiveWindowSize(int,int)` —
the same TU-isolation convention `gizmo.cc` already uses for `GetCameraPoseWS` /
`SetEditorCameraPose` (`gizmo.h:43-44` documents the clash). `wf_edit` rebuilt clean
(`BUILD_EXIT=0`). `wf-relay` is also built.
