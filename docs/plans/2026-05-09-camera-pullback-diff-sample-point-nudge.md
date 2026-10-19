# Camera pullback + diff sample-point nudge

**Status:** DONE (commit `f67774fc`) — camera pull-back landed (screenshot proof in the SMB plans).

User reported Q*bert's head is clipped at the top of the framebuffer. Current `CAMSHOT_POS = (0.0, -15.0, 19.0)` / `CAMSHOT_LOOKAT = (0.0, 3.0, 8.5)` puts the look-direction (0, 18, -10.5) magnitude ~20.85 from camera to lookat. Pull the camera back ~35% along that vector to give head/foot margin: new `CAMSHOT_POS ≈ (0.0, -22.0, 23.0)` keeps the same lookat point and roughly the same down-tilt angle (atan((23-8.5)/(3-(-22))) = atan(0.58) = 30.1° vs the documented 30°).

Edit in [wflevels/qbert_practice/blender_create_qbert.py:113](../../WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py).

Then regen + relaunch + walker re-run; the diff sample point will land somewhere different from before (different pixel coords). That's a separate edit on `qbert_walker_diff.py` after we see the new framing.

# Old: Diff sample-point nudge (superseded — camera change moves these too)

Trivial fix in `scripts/research/wf/qbert_walker_diff.py`: `WF_APEX_TOP = (320, 240)` is hitting the apex cube's shadow side. Pixel scan of `wf_walker_L1R1_state0.png` at x=320 shows the diamond-top band sits at y≈211..223 (round-0 state-0 colour `#5545ED`), with shadow side starting at y=225. New value: `(320, 217)` — middle of the top band.

For `WF_CUBE10_TOP = (290, 285)`: this works for state-1 (now that cubes flip correctly), but worth re-eyeballing on a state-1 PNG to make sure it's mid-top-diamond rather than near an edge. Tweak only if visibly off.

Re-run `python3 scripts/research/wf/qbert_walker_diff.py` after the edit; expect L?R1 state-0 cells to now read R0 top colour `#5645ED` (matching the WF render of `gen_cube.py` ROUND_COLORS[0][0] = `0x5646EF`).

# Cube-color-on-landing — root-cause + fix (DONE, commit 5cf6883)

## Context

Phase E walker landed and produced 30 state captures + a side-by-side composite that revealed the issue the user actually cares about: when Q*bert lands on a cube in WF, it doesn't transition to its "flipped" colour. Instead it goes BLACK / disappears. The captures' state-1 column reads `#000000` for most rounds in [scripts/research/wf/qbert_walker_diff.py](../../WorldFoundry.2026-new-level/scripts/research/wf/qbert_walker_diff.py) output. The state-0 (round-start) palette is fine — colours match author intent. The bug is on the state transition specifically.

## What we know

The architecture is **one actor per (cube_N, round_r, state_s)** = 336 actors, each with `wf_Mesh Name = cube_state{s}_r{r}.iff` and `wf_Visibility Mailbox = 440 + r*84 + N*3 + s`. The 12 mesh IFFs exist with distinct contents and correct authored colours per round/state (verified via `xxd` — `cube_state2_r0.iff` MATL block shows `de de 00` = 0xDEDE00 = the canonical L1R1 state-2 yellow). Initially only `(r==0, s==0)` actors are visible.

The director's per-frame fan-out at [blender_create_qbert.py:708–735](../../WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) computes `vis_addr = 440 + r*84 + N*3 + s` for each (combo_r, combo_s) and writes 1 to the address whose (r, s) matches `(cur_palette, cube_state[N])`, 0 elsewhere. The math matches what each actor's Visibility Mailbox is wired to.

The cube-state advance on landing at [blender_create_qbert.py:692–695](../../WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py) is:

```forth
411 read-mailbox 0 <> if
    400 read-mailbox dup 1 + * 2 / 401 read-mailbox + 200 +
    dup read-mailbox 0 = if 2 swap write-mailbox else drop then
    0 411 write-mailbox
then
```

It hardcodes `cube_state := 2` when player lands on a cube whose state was 0 (skips state 1 entirely, even for 2-step rounds where state 1 is the intermediate yellow). For 1-step rounds where state 1 == state 2, that's fine; for 2-step rounds it skips an intermediate frame.

## Hypotheses for "cube goes black"

1. **`s2` actors aren't actually loaded into the engine.** The mesh file references go through the export pipeline; the scene has the actor, but maybe its mesh isn't resolved at level load (cd.iff/asset bundle indexing, or `wf_Mesh Name` not honored when the actor starts invisible). When visibility flips on, the engine has no mesh to render → black.
2. **Visibility mailbox writes don't propagate to `s2` actors.** Maybe the Visibility Mailbox property gets dropped during export for non-`s0` actors, so writing `mb[vis_addr]=1` is a no-op against the engine's internal flag.
3. **Material binding regression.** Mesh loads, but the s2 IFF's MATL chunk isn't honored on a hot visibility flip — material stays at the s0 default. Less likely given the IFF reference is per-actor, not per-mesh-instance, but possible.

We'd need to disambiguate before fixing.

## Diagnostic plan (read-only, ~10 min)

A. **Bridge-query the visibility mailbox before and after a hop.** Run the engine with the walker; on state-0 capture, send `set_mailbox` to query mb[440 + 0*84 + 1*3 + 0] (= cube_01 r0 s0) and mb[440 + 0*84 + 1*3 + 2] (= cube_01 r0 s2). Expect (1, 0) before hop, (0, 1) after. If the mb values DO flip, the script side is fine; the engine isn't honouring them.

B. **Force-show all `s2` actors at level start.** Temporarily edit the director's startup code to write `1` to every `s2` vis mailbox (in addition to `s0`). If we see overlapping s0+s2 cubes (probably z-fighting on top, mixed colours visible), the s2 actors render fine and the bug is in the transition logic. If we see only s0 cubes (or pure black at cube tops), the s2 actors aren't loadable.

C. **xxd a few exported actors in the .lev** to confirm `wf_Visibility Mailbox` is set on s2 actors. Grep the .lev for `cube_01_r0_s2` and verify the Visibility Mailbox value matches `440 + 0*84 + 1*3 + 2 = 445`.

After A/B/C we'll know which of the three hypotheses applies. The fix follows the diagnosis:

- **If (A) shows mb correctly flipping but cube stays black:** investigate the engine's actor visibility code (`wf_Visibility Mailbox` consumer in `wfsource/source/`). Likely there's a single-flag check that only listens at level-load, not per-frame.
- **If (B) shows s2 invisible always:** the s2 actor's mesh/material isn't loaded at level start. Fix: add a "preload meshes for all visibility states" step, or change initial visibility to a tiny non-zero value that forces mesh resolution.
- **If (C) shows wf_Visibility Mailbox missing on s2 actors:** the Blender export drops the property for actors with `initial_vis=0`. Fix in the exporter.

## After diagnosis — focused fix

The diagnostic step costs nothing (10 min, read-only) and tells us exactly where to invest. Without it, any fix is guesswork.

If diagnostic confirms hypothesis (B) and the fix is "make all 336 cubes initial-visible then have the director hide all but s0 on its first frame", the change is one block in the director script and shouldn't risk anything else.

## Out of scope (separate workstream)

- **Per-level palette diversity.** WF's 4 round palettes cycle (r0..r3) regardless of level — `cur_pal = round_num % 4` at [blender_create_qbert.py:761](../../WorldFoundry.2026-new-level/wflevels/qbert_practice/blender_create_qbert.py). MAME has 16 distinct (level, round) palettes. Fix lives in `gen_cube.py` (extend `ROUND_COLORS` to 16) + change the cur_pal formula. Not what the user asked for right now.
- **Cube-state increment 0→1→2 vs 0→2.** Not what the user is asking about; their issue is the state-2 cube going black, not state-1 being skipped.

## Verification

1. Run `blender --background --python wflevels/qbert_practice/blender_create_qbert.py` then `wftools/wf_blender/build_level_binary.sh qbert_practice` then iffcomp the standalone.
2. Launch `wf_game -L<...>.iff --debug-port 7777`.
3. Run the walker (`scripts/research/wf/qbert_wf_walker.py --max-rounds 4` for one level).
4. Check `wf_walker_L1R1_state1.png` — cube (1,0) top should show 0xDEDE00 (yellow) at the (290, 285) sample point, not 0x000000.
5. Re-run the diff: state-1 column for L1R1..L1R4 should match each round's `state2_top` from `gen_cube.py:ROUND_COLORS` (within the threshold).
