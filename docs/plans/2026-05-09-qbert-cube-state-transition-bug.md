# Plan — Cube goes black on landing (state-transition bug)

**Date:** 2026-05-09
**Status:** ✅ Fixed (commit `5cf6883`). Root cause: zForth `i 3 /` in the visibility fan-out is float division — combo_r came out 0.667 / 1.667 / 2.667 instead of integers, so the `combo_r = cur_pal` comparison silently failed for every state-1 / state-2 combo. Fix: cast via `i dup 3 % - 3 /` in both the comparison and the address calculation. Verified end-to-end: 12 round-clears, state-1 cubes render the correct authored colour (e.g. L1R1 cube top reads #DCDC00 vs the canonical MAME #DEDE00 — diff of 2). Diagnostic via debug-bridge `set_mailbox(201, 2)` to force `cube_state[1]=2` then probe vis mailboxes — mb[529] (cube_01_r1_s2 vis) stayed 0 instead of going to 1.
**Surfaced by:** [2026-05-09-qbert-walker-wf-parity.md](2026-05-09-qbert-walker-wf-parity.md) Phase E captures

## Context

The Phase E walker captured 30 state-pair PNGs across L1R1..L4R3 and surfaced a real authoring bug the user has called out:

1. **Cube goes BLACK / disappears when Q*bert lands on it** — instead of flipping from state-0 colour to the round's state-2 colour.
2. **The cube top doesn't show the level-correct colour** when it does flip — secondary symptom of the same wiring issue.

The state-0 (round-start) colours are fine; the bug is on the state transition specifically. Reading [scripts/research/wf/qbert_walker_diff.py](../../scripts/research/wf/qbert_walker_diff.py) output, the WF state-1 column reads `#000000` for most rounds, with three rounds (L3R3, L4R2, L4R3) showing some non-canonical colour — all 32 cells fail the diff vs MAME.

## What we know

The architecture is **one actor per (cube_N, round_r, state_s)** = 28 × 4 × 3 = 336 actors, each with `wf_Mesh Name = cube_state{s}_r{r}.iff` and `wf_Visibility Mailbox = 440 + r*84 + N*3 + s` ([blender_create_qbert.py:798–807](../../wflevels/qbert_practice/blender_create_qbert.py)). The 12 mesh IFFs exist with distinct contents; verified via xxd that `cube_state2_r0.iff` MATL block contains `de de 00` = 0xDEDE00 = the canonical L1R1 state-2 yellow. Initially only `(r==0, s==0)` actors are visible.

The director's per-frame fan-out at [blender_create_qbert.py:708–735](../../wflevels/qbert_practice/blender_create_qbert.py) computes `vis_addr = 440 + r*84 + N*3 + s` for each (combo_r, combo_s) and writes 1 to the address whose (r, s) matches `(cur_palette, cube_state[N])`, 0 elsewhere. The math matches each actor's wired Visibility Mailbox.

The cube-state advance on landing at [blender_create_qbert.py:692–695](../../wflevels/qbert_practice/blender_create_qbert.py) hardcodes `cube_state := 2` when player lands on a cube whose state was 0 (skips state 1 entirely). For 1-step rounds where state 1 == state 2 that's fine; for 2-step rounds it skips an intermediate frame. Not the bug we're chasing — even with the skip, state-2 should render the round's state-2 colour, not black.

## Hypotheses

1. **`s2` actors aren't loaded into the engine.** The mesh file references go through the export pipeline; the scene has the actor, but maybe its mesh isn't resolved at level load (asset bundle indexing, or `wf_Mesh Name` not honoured when the actor starts invisible). When visibility flips on later, the engine has no mesh to render → black.
2. **Visibility mailbox writes don't propagate to `s2` actors.** Maybe the Visibility Mailbox property gets dropped during export for non-`s0` actors, so writing `mb[vis_addr]=1` is a no-op against the engine's internal flag.
3. **Material binding regression on visibility flip.** Mesh loads, but the s2 IFF's MATL chunk isn't honoured on a hot visibility flip — material stays at the s0 default (or worse, uninitialised → black). Less likely given `wf_Mesh Name` is per-actor not per-mesh-instance, but possible.

## Diagnostic plan (read-only, ~10 min)

A. **Bridge-query the visibility mailbox before and after a hop.** Run the engine with the walker; on state-0 capture, send `set_mailbox` to query `mb[440 + 0*84 + 1*3 + 0]` (= cube_01 r0 s0) and `mb[440 + 0*84 + 1*3 + 2]` (= cube_01 r0 s2). Expect (1, 0) before hop, (0, 1) after. If the mb values DO flip, the script side is fine; the engine isn't honouring them.

B. **Force-show all `s2` actors at level start.** Temporarily edit the director's startup to write `1` to every `s2` vis mailbox (in addition to `s0`). If we see overlapping s0+s2 cubes (z-fighting on top, mixed colours visible), the s2 actors render fine and the bug is in the transition logic. If we see only s0 cubes (or pure black at cube tops), the s2 actors aren't loadable.

C. **xxd a few exported actors in the .lev** to confirm `wf_Visibility Mailbox` is set on s2 actors. Grep the .lev for `cube_01_r0_s2` and verify the Visibility Mailbox value matches `440 + 0*84 + 1*3 + 2 = 445`.

After A/B/C we'll know which hypothesis applies. The fix follows the diagnosis:

- **(A) shows mb correctly flipping but cube stays black** → investigate the engine's actor visibility code (the consumer of `wf_Visibility Mailbox` in `wfsource/source/`). Likely a single-flag check that only listens at level-load, not per-frame.
- **(B) shows s2 invisible always** → s2 mesh/material isn't loaded at level start. Fix: a "preload meshes for all visibility states" step, or change initial visibility to a tiny non-zero value that forces mesh resolution, or set `initial_vis = 1` for all states then immediately have the director hide all but s0 on its first frame.
- **(C) shows wf_Visibility Mailbox missing on s2 actors** → the Blender export drops the property for actors with `initial_vis=0`. Fix in the exporter.

## Critical files

| File | Section | Why |
|---|---|---|
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | :692–695 (state advance) | hardcoded 0→2; not the cause of black but worth noting |
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | :708–735 (vis fan-out) | computes `vis_addr` from (cur_pal, cube_state) |
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | :771–810 (cube creation) | sets `wf_Mesh Name`, `wf_Visibility Mailbox`, `initial_vis` |
| [wflevels/qbert_practice/gen_cube.py](../../wflevels/qbert_practice/gen_cube.py) | :150–175 (ROUND_COLORS) | per-(round, state) authored colours; verified to land in IFFs |
| [wflevels/qbert_practice/qbert_practice.lev](../../wflevels/qbert_practice/qbert_practice.lev) | (generated) | grep here to verify `wf_Visibility Mailbox` survived export |
| `wfsource/source/` (TBD) | actor visibility consumer | engine side — find via grep `Visibility Mailbox` and trace |

## Verification

Once fix lands:

1. `blender --background --python wflevels/qbert_practice/blender_create_qbert.py` then `wftools/wf_blender/build_level_binary.sh qbert_practice` then iffcomp the standalone.
2. Launch `wf_game -L<...>.iff --debug-port 7777`.
3. Run `scripts/research/wf/qbert_wf_walker.py --max-rounds 4` (one level).
4. Inspect `wf_walker_L1R1_state1.png` — cube (1,0) top at sample point (290, 285) should be 0xDEDE00 (yellow), not 0x000000.
5. Re-run `qbert_walker_diff.py`: state-1 column for L1R1..L1R4 should match each round's `state2_top` from `gen_cube.py:ROUND_COLORS` within the threshold.
6. Side-by-side composite (`scripts/research/wf/qbert_walker_composite.py`) — WF state-1 column should look distinct from state-0 (cube tops differ), with the cube-(1,0) crosshair landing on a non-black colour for every round.

## Out of scope (separate workstreams)

- **Per-level palette diversity.** WF cycles 4 round palettes (cur_pal = round_num % 4); MAME has 16 distinct (level, round) palettes. Fix lives in `gen_cube.py` extending ROUND_COLORS to 16 and changing the cur_pal formula. Track separately once this transition bug is fixed.
- **State increment 0→1→2 vs 0→2.** For 2-step rounds, the intermediate state-1 frame is skipped. Visible only briefly during the hop animation; not a blocker for the regression baseline.
