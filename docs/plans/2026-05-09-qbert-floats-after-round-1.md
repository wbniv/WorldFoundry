# Plan — Q*bert floats after round 1

## Context

The walker-wf-parity Phase E end-to-end run ([docs/plans/2026-05-09-qbert-walker-wf-parity.md](../../home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-09-qbert-walker-wf-parity.md)) captured 32 PNGs across all 16 rounds. **L1R1 captures correctly place Q*bert on apex (state-0) and on cube (1,0) (state-1). From L2R1 onward, every state-0 / state-1 PNG shows him drifting well above the pyramid.** This is the regression blocker preventing the walker-parity plan from landing.

The fix must hold across all 15 round-clear transitions (L1R1→L1R2 … L4R3→L4R4), not just the first one. Authoritative test = re-running `scripts/research/wf/qbert_wf_walker.py` and visually scanning the 32 emitted PNGs.

## What's actually known vs. assumed

**Known from screenshots:**
- L1R1 state-0 / state-1 are correct.
- L2R1+ state-0 / state-1 show Q*bert above the pyramid in Z.

**Plan-doc hypothesis (untested):** `step-move` defaults beyond step 30 → off-pyramid hop → FALL_PHASE → director zeros FALL_PHASE without restoring Z → race with player respawn handler.

**Static-read findings that complicate the hypothesis:**
1. `step-move` actually defaults to `(1, 0)` = DR, not DL ([blender_create_qbert.py:333](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py)).
2. Round-clear countdown is 90 ticks; fall animation is 30 ticks — fall completes well within countdown, and the fall-snap at line 401 already writes `Z=15`.
3. Director clears `mb[419] FALL_PHASE` (line 761) and then sets `mb[426]=1`; player's respawn at line 386 explicitly writes `Z=15`. There is no code path that sets Z *higher* than 15 — every Z-write either uses the `(6−row)*2+3` formula, decrements (fall ramp), or hardcodes `15`.

So the real cause is not obviously visible from the source. **Phase A is mandatory** before committing to a fix — the `set_mailbox`/`watch` bridge ops (already shipped, see memory `project_keyboard_focus_fix.md` siblings) are the right tool.

## Approach

### Phase A — instrument & reproduce (no code change in level, only the harness)

Use the already-landed debug bridge ops (`watch`, `set_mailbox`, `screenshot`) from a small ad-hoc Python script under `scripts/research/wf/qbert_float_trace.py`. The script:

1. Connects to `localhost:7777`.
2. `watch` adds: `mb[419]` (FALL_PHASE), `mb[431]` (AUTOPILOT_STEP), `mb[400]` (ROW), `mb[401]` (COL), `mb[424]` (ROUND_CLEAR_TIMER), `mb[425]` (ROUND_NUMBER), `mb[413]` (ROUND_CLEAR), `mb[426]` (round-respawn-pending), `mb[432]` (CAPTURE_TRIGGER).
3. INDEXOF_Z_POS isn't a mailbox — it's an engine position slot. Cheapest probe: extend `watch` to include the player-actor `INDEXOF_Z_POS` if the existing op already supports per-actor mailboxes (per the keyboard-focus memory; debug-bridge Phase A landed `set_mailbox` *with* per-actor support — the `watch` side likely matches). If not, add a thin `get_pos` op modelled on the existing `screenshot` drain pattern at `engine/debug_server.cc:562` — read `Position3D` of the player actor, reply `{op:"pos",x:...,y:...,z:...}`. Poll every frame from the host. Don't merge this op; it's a debugging aid for the duration of Phase A.
4. Sets `mb[430] AUTOPILOT_ON = 1`.
5. Logs a CSV row per change event with frame counter (already in broadcasts) so we can reconstruct the L1R4→L2R1 boundary tick-by-tick.
6. After L4R4, dump CSV to `docs/investigations/2026-05-09-qbert-float-trace.csv` and the matching PNGs.

Read the CSV around the round transition we already know is broken. Likely diagnoses:

- **(a) FALL_PHASE re-arms inside countdown**: an extra autopilot hop during the 90-tick window sets `mb[419]=1`, and the fall ramp is interrupted by the director's `0 419 write-mailbox` *mid-ramp*, leaving Z low instead of restored. Player's `mb[426]=1` handler writes `Z=15` next tick — but if the engine's actor-update order puts the cube-actor render between the director and the player tick, the screenshot fires with stale Z. Less likely (capture is gated on `mb[432]` transition, which the director sets only after writing mb[426]=1), but observable from the trace.
- **(b) Z accumulates above 15 from somewhere unexpected**: would falsify everything in the static read. Possible if `bpy.ops.wf.export_level` is silently appending to a Forth word, or if the room/camera transform shifts after the first round-clear.
- **(c) Capture fires before respawn**: `mb[432]` write happens in the autopilot step-0 block at line 422 right after step `dup 0 = if`. If `mb[431]` got cleared by player respawn but `INDEXOF_Z_POS` write at line 386 hasn't taken effect yet (same-tick ordering), the screenshot captures pre-respawn pose.

The CSV will pick the right one. Don't write any of the (a)/(b)/(c) fix code until it does.

### Phase B — fix, scoped by Phase A finding

Most-likely fix (case (a) or (c)) — **defensive layering, all in `wflevels/qbert_practice/blender_create_qbert.py`:**

1. **Gate autopilot on no-fall AND no-countdown.** At [line 420](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) (`430 read-mailbox 0 <> if`), add `419 read-mailbox 0 = if 424 read-mailbox 0 = if … then then` so the 32-step path can't advance while the engine is in fall or round-clear states. This kills the "extra hop during countdown" path that case (a) needs.

2. **Restore Z atomically with FALL_PHASE clear in the director.** At [line 761](../../home/will/WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py), after `0 419 write-mailbox`, append `15 INDEXOF_Z_POS write-mailbox 0 INDEXOF_X_POS write-mailbox 6 1.4142136 * INDEXOF_Y_POS write-mailbox`. This makes round-clear cleanup self-sufficient — the player respawn handler (line 386) becomes a redundant safety net rather than load-bearing.

3. **Reset autopilot step on round-clear in the director.** Append `0 431 write-mailbox` to the director's countdown-zero block (line 760-770). Today only the player respawn handler does this (line 387) — moving it earlier makes the player handler purely positional.

These three are independent and can land together as a single commit: belt-and-braces against same-tick ordering ambiguity. Net diff is ~6 Forth tokens.

If Phase A surfaces case (b) (Z value > 15 actually getting written somewhere), the fix moves into engine territory — pause and re-plan.

### Phase C — verify

1. `task build` (`engine/build_game.sh` per memory `project_wf_game_build.md`).
2. Re-run blender_create_qbert.py inside Blender via the running MCP — re-export `.lev`, repack via `wftools/wf_blender/build_level_binary.sh qbert_practice`, copy the standalone bundle.
3. Re-run `scripts/research/wf/qbert_wf_walker.py`. 32 PNGs in `docs/investigations/wf-screenshots/`.
4. **Visual scan** all 32 — every state-0 has Q*bert centred on apex, every state-1 has him on cube (1,0). If any round still floats, return to Phase A with a narrowed window.
5. Run `qbert_walker_diff.py` — should now reach the 15/16 pass threshold (the existing sample-points caveat from follow-up #2 may still suppress some passes; that's a separate plan).

## Critical files

| File | Phase | Action |
|---|---|---|
| `scripts/research/wf/qbert_float_trace.py` | A | new (~60 LOC, throwaway after fix lands) |
| `engine/debug_server.cc` | A (maybe) | new `get_pos` op if `watch` doesn't already cover player-actor position |
| `wflevels/qbert_practice/blender_create_qbert.py:420,761,770` | B | autopilot fall/countdown gate, Z restore in director, mb[431]=0 in director |
| `docs/plans/2026-05-09-qbert-walker-wf-parity.md` | C | flip the float-bug follow-up to ✅ once the 32 PNGs are clean |
| `wf-status.md` | C | one-sentence summary paragraph at top per the rolling-summary convention |

## Reuse

- Existing debug-bridge ops (`watch`, `set_mailbox`, `screenshot`) — Phase A1/B1/B2 all landed already.
- `tests/debug_bridge_client.py` for the socket boilerplate.
- Existing `scripts/research/wf/qbert_wf_walker.py` for the regression run; Phase A's tracer can borrow its watcher loop.

## Verification

End-to-end: re-running `qbert_wf_walker.py` produces 32 PNGs; manual scan shows Q*bert on apex (state-0) and on cube (1,0) (state-1) for every round, not just L1R1. Smoke-rerun is byte-identical (replay determinism). Plan and wf-status.md updated, commit per phase per memory `feedback_commit_after_each_phase.md`.

## Risks

- **Bug is in engine actor-update ordering, not Forth.** If Phase A shows position is being written correctly but the framebuffer reads stale geometry, the fix is in `wfsource/source/game/`'s tick loop — out of this plan's scope and we replan.
- **L4R1 special case.** Parent walker plan called out L4R1 as the round needing a hand-tuned MAME walker. WF side has no equivalent issue per the parent plan, but if the float symptom turns out to be L4R1-specific too, scope grows.
- **Re-running blender_create_qbert.py via Blender MCP regenerates 1344 cube IFFs.** That's a big diff. Consider running gen_cube.py + manual shutil refresh + iffcomp repack (the path used in the per-round-state-1 commit `a863791`) to keep the diff small if only the Forth changes.
