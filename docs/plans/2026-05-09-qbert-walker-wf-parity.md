# Plan — Q*bert walker WF-side parity (Phase E)

**Date:** 2026-05-09
**Status:** In progress — scaffolding complete and end-to-end run done (12 round-clears across L1–L4 + R1–R3 of L4, 30 state captures). Two follow-ups before this can land as a regression:
1. **Q*bert floats after round 1** — L1R1 captures place him correctly on apex (state-0) and on cube (1,0) (state-1). From L2R1 onward, every state-0 / state-1 PNG shows him drifting well above the pyramid. Suspect: `step-move` defaults to DL beyond step 30, so the existing 32-step Warnsdorff path keeps hopping DL once it falls off the table → off-pyramid → FALL_PHASE → Z ramps down → director's round-clear cleanup zeros FALL_PHASE but doesn't restore Z, and the ROUND_INITIALIZED handler that does restore Z races with something. Need to trace via debug bridge `set_mailbox` queries on mb[419]/INDEXOF_Z_POS during the L1R4→L2R1 transition.
2. **Diff sample points are off** — projected apex pixel-coord lands at y≈137 in the 640×640 PNG; actual apex top is at y≈250. Either the auto-projection's FOV/up-vector is wrong for WF's camera, or BungeeCameraHandler is doing something the projection math doesn't capture. Working fix: read the actual on-disk PNG once, hand-tune pixel coords, hardcode in the diff tool. Auto-projection from cube positions can land later when a `scene:get_actor_pos` op is available.
**Parent plan:** [2026-05-08-qbert-walker-rom-grounded.md](2026-05-08-qbert-walker-rom-grounded.md) (Phase E)

## Context

Phases A–D of the parent plan produced ROM-grounded MAME captures of cube colors for all 16 Q*bert rounds (15/16 in `qbert_walker.lua`, L4R1 via standalone `qbert_l4r1_walker.lua`). The MAME-side walker protocol is now fully specified: at each round entry, snap state-0 at apex, force a DR hop, force UL back to apex, snap state-1, advance round, repeat. Sample points `(120,56)` apex / `(137,80)` cube(1,1) / `(40,55)` HUD-target give a 3-pixel signature that distinguishes 1-step from 2-step rounds (see [scripts/research/mame/sample_cube_colors.py](../../scripts/research/mame/sample_cube_colors.py)).

Phase E mirrors the same protocol in WF so the two engines emit comparable image pairs. WF already has the pieces: an autopilot Forth director (`mb[430] AUTOPILOT_ON`), no Demo AI to fight, no HUD-update lag — the protocol is "trivial" on the WF side per the parent plan. What's missing: a way for the engine to dump a PNG at the moment the director reaches each capture point, plus host-side glue to drive the run and diff against MAME.

## Decisions

- **mb[432] CAPTURE_TRIGGER** — mb[431] is already AUTOPILOT_STEP ([blender_create_qbert.py:73](../../wflevels/qbert_practice/blender_create_qbert.py)).
- **PNG via vendored stb_image_write.h** — single public-domain header, ~1k LOC; no system dep.
- **Auto-derive sample points** from cube world positions projected via the WF camera; no hardcoded pixel coords.
- **Host scripts in `scripts/research/wf/`** — mirrors `scripts/research/mame/`; these are research/regression tools, not unit tests.

## Approach

### 1. Engine: PNG writer + `screenshot` op

**Vendor stb_image_write.h** at `engine/vendor/stb/stb_image_write.h` plus `engine/vendor/stb/stb_image_write_impl.cc` (one `#define STB_IMAGE_WRITE_IMPLEMENTATION` + `#include`). Add the impl TU to the engine CMake target.

**Add a `screenshot` op to [engine/debug_server.cc](../../engine/debug_server.cc)** following the existing `set_mailbox` pattern (dispatch in `handle_client` ~:304–459, drain in game thread `DrainQueue` ~:562, broadcast helper `send_all_locked` ~:288):

- New `PendingUpdate::SCREENSHOT { std::string filename; int reply_fd; }` enqueued by the JSON parser when it sees `{"op":"screenshot","filename":"..."}`.
- `DrainQueue` handles it on the game thread after the next frame finishes: `glReadPixels(GL_RGBA, GL_UNSIGNED_BYTE)` against the default framebuffer at the current viewport size, vertical-flip into a row-major top-left buffer, call `stbi_write_png(filename, w, h, 4, buf, w*4)`. Reply with `{"op":"screenshot_done","filename":"...","w":...,"h":...}` so the host knows it's flushed.

**No engine-side mailbox watcher for capture-trigger.** The host already gets `mb[432]` change events via the existing `watch` op + `BroadcastMailboxes` (~:952–982). Host watches `mb[432]`, and on each transition issues a `screenshot` op with the right filename. Keeps engine logic tiny and avoids tying screenshot semantics to a specific mailbox index.

### 2. Director script: emit `mb[432] CAPTURE_TRIGGER`

In [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) (DIRECTOR_SCRIPT at :616, autopilot block at :408–411, round-clear state machine at :731–750):

- Add **mb[432] CAPTURE_TRIGGER** to the mailbox-constant comment block at :72–76.
- Per round, woven into existing autopilot:
  1. Round entry, Q*bert at apex stable: `1 432 write-mailbox` (state-0). Hold ~30 frames.
  2. Force DR hop. Wait for landing.
  3. Force UL hop. Wait for `pos == apex`.
  4. `2 432 write-mailbox` (state-1). Hold ~30 frames.
  5. Resume normal Warnsdorff to clear the round.
  6. On round-clear latch (existing logic ~:731): `3 432 write-mailbox` (round-clear), then reset to 0 a few frames later so the next "1" is a real transition.
- The protocol replaces (not augments) the first 2 hops of the autopilot path; subsequent rounds reuse it.

### 3. Host harness: `scripts/research/wf/qbert_wf_walker.py`

Pure-stdlib socket client (model on [tests/debug_bridge_client.py](../../tests/debug_bridge_client.py)):

1. Connect to `localhost:7777`. Read engine hello.
2. `watch` for `mb[432]` (CAPTURE_TRIGGER) and `mb[425]` (ROUND_NUMBER).
3. User starts the engine separately (`task build && cd wfsource/source/game && ./wf_game cd_qbert.iff`). Harness assumes engine is already up; subprocess.Popen can come later.
4. `set_mailbox` to set `mb[430] AUTOPILOT_ON = 1`.
5. Loop: when `mb[432]` transitions to {1,2,3}, derive `state ∈ {state0, state1, clear}`, current `(L,R)` from `mb[425]`, send `screenshot` op with `filename = "docs/investigations/wf-screenshots/wf_walker_L{L}R{R}_{state}.png"`, await `screenshot_done`. Stop after L4R4 round-clear or timeout.
6. Output dir: `docs/investigations/wf-screenshots/` (mirrors `mame-screenshots/`); gitignore the PNGs initially.

### 4. Diff: `scripts/research/wf/qbert_walker_diff.py`

Sample points must be derived per-engine from object positions, not hardcoded:

- **MAME side**: existing `scripts/research/mame/sample_cube_colors.py` already hardcodes (120,56), (137,80), (40,55) — those ARE the MAME framebuffer coords. Keep as-is.
- **WF side**: query the bridge for the world-space center-top of apex cube and cube(1,1) (use `scene:get_transform` if it exists; else add a lightweight `scene:get_actor_pos`). Project via the WF camera's view-projection matrix to pixel coords. WF has no arcade HUD, so drop the third sample for WF and diff only the 2 cube samples (apex + cube(1,1)).

Per round, the diff:
- Load `mame-screenshots/qbert_L{L}R{R}.png` (state-0) and `wf-screenshots/wf_walker_L{L}R{R}_state0.png`. Read pixel at (120,56) on MAME side, at projected apex coord on WF side. Compute `ΔE` (or simple max-channel-diff) between the two RGB triples. Pass = ΔE < threshold (e.g. 16/255 per channel).
- Same for state-1 with `qbert_hop_L{L}R{R}.png` ↔ `wf_walker_L{L}R{R}_state1.png` at the cube(1,1) sample point.
- Print a 16-row pass/fail table.

### Determinism

The parent plan's NVRAM-clear note doesn't apply to WF (no NVRAM). WF determinism comes from director + autopilot replay. Note in the harness: any dt-driven physics randomness must be controlled — if a hop drops, the protocol retries the same direction (mirror the MAME walker behaviour).

## Critical files

| File | Action |
|---|---|
| `engine/vendor/stb/stb_image_write.h` | new (vendored, ~1k LOC) |
| `engine/vendor/stb/stb_image_write_impl.cc` | new (~5 LOC) |
| `engine/CMakeLists.txt` | add vendor TU to engine target |
| `engine/debug_server.cc` | new `screenshot` op (parser ~:450, drain handler ~:562) |
| `wflevels/qbert_practice/blender_create_qbert.py` | DIRECTOR_SCRIPT (:616) + mailbox constants (:72–76) — add mb[432] writes around the dance |
| `scripts/research/wf/qbert_wf_walker.py` | new host harness |
| `scripts/research/wf/qbert_walker_diff.py` | new diff tool |
| `docs/investigations/wf-screenshots/` | new output dir |
| `.gitignore` | exclude `docs/investigations/wf-screenshots/*.png` initially |

## Verification

End-to-end pass:

1. `task build && cd wfsource/source/game && ./wf_game cd_qbert.iff` boots Q*bert level.
2. `python3 scripts/research/wf/qbert_wf_walker.py` connects, drives autopilot, dumps 32 PNGs (16 rounds × 2 states) plus 16 round-clear markers. Run completes well under 10 minutes.
3. `ls docs/investigations/wf-screenshots/wf_walker_L*R*_state*.png | wc -l` → 32.
4. `python3 scripts/research/wf/qbert_walker_diff.py` prints a 16-row table with ≥ 15/16 passing on both state-0 and state-1 columns. (L4R1 is the known edge case; investigate if it fails specifically on that row.)
5. Smoke: re-running step 2 produces byte-identical PNGs (replay determinism).

## Risks

- **Camera projection math wrong** — WF cube(1,1) sample point lands on background instead of cube top. Mitigation: dump projected coords with a tiny crosshair overlay during a debug run; eyeball-correct before locking in.
- **glReadPixels alignment / FBO oddness** — if default framebuffer pack alignment causes garbage rows at non-multiple-of-4 widths, set `GL_PACK_ALIGNMENT = 1` before the read.
- **Director Forth gets too large** — Forth dictionary already substantial; if the new state machine pushes past zForth's limits, factor the dance into a sub-word.
- **mb[432] race with autopilot step** — autopilot writes mb[431] every step; per-frame `BroadcastMailboxes` will see mb[432] transitions cleanly because they're written by the same Forth thread, sequentially. Add a frame-counter to the broadcast payload during bring-up if events look out of order.

## Out of scope

- L4R1 multi-round edge case in MAME (Phase D shipped a workaround; WF side has no equivalent issue).
- Replacing the existing Warnsdorff coverage path — this plan inserts the dance + capture trigger; existing 32-step coverage stays.
- Generalizing the `screenshot` op for non-qbert use (it'll be reusable as-is; no doc/marketing for that here).
