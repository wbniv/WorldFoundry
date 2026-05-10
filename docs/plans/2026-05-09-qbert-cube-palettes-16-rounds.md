# Per-level palette diversity: extend cube palettes from 4 to 16 rounds

**Status:** ✅ Complete (2026-05-09, commits `0048211` + `a863791`).
`gen_cube.py` now ships 16 round entries pixel-sampled from MAME (5-tuple
`(s0, s1, s2, lit, shadow)` — state-1 added 2026-05-09 in follow-up
commit `a863791` with per-round mid-hop colors for L2/L4 and
state-1≡state-2 for L1/L3); `blender_create_qbert.py` cycles through all
16 (`NUM_ROUNDS=16`, vis fan-out inner loop 12→48, vis-zero range
336→1344) and clamps `425` at 15 (L4R4-forever after the 16th clear).
Engine-side budgets bumped to fit 1344 actors:
`GLOBAL_USER_MAX 999→1900` (system range shifted to 1901–1922),
`maxAsset 1000→4000`, `ASMP buffer 16→64` sectors,
`cbHalLmalloc 16MB→64MB`, OBJD/ROOM in standalone iff.txt up to
`4000000l`/`8000000l`. The 950-mailbox workaround audit and the
mailbox-at-cap crash retest both deferred to follow-ups.

## Context

Q*bert arcade has 4 levels × 4 rounds = 16 distinct cube colour palettes.
Today [`wflevels/qbert_practice/gen_cube.py`](../../wflevels/qbert_practice/gen_cube.py)
only ships 4 (L1R1..L1R4), and
[`blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py)
cycles `cur_pal = round_num % 4`, so after R3 the practice level loops
the L1 palette set rather than progressing through L2/L3/L4 colours. The
investigation [qbert_cube_face_colors.md](../investigations/qbert_cube_face_colors.md)
already lists all 16 canonical (top, target_top, lit_side, shadow_side)
entries from MAME captures. This change makes the visible cube colours
match the arcade for every round of the practice level. User-facing.

## Critical constraint

Going from 4→16 rounds with the existing actor-per-`(cube, round, state)`
visibility model bumps the visibility mailbox range to:

```
INDEXOF_VIS_BASE + (NUM_ROUNDS-1)*84 + 27*3 + 2
= 440 + 15*84 + 81 + 2
= 1783
```

That exceeds `GLOBAL_USER_MAX = 999`. Resolution (decided): raise
`GLOBAL_USER_MAX` to 2048. See "Engine change" section below.

## Files to modify

- [`wflevels/qbert_practice/gen_cube.py`](../../wflevels/qbert_practice/gen_cube.py)
  — extend `ROUND_COLORS` to 16 entries (canonical
  `(state0_top, state2_top, lit_side, shadow_side)` tuples drawn from
  [qbert_cube_face_colors.md](../investigations/qbert_cube_face_colors.md)).
  The loop already does `enumerate(ROUND_COLORS)` so no other changes
  here; output grows from 12 to 48 source IFFs
  (`cube_state{0,1,2}_r{0..15}.iff`). Two arcade rounds (L2R4, L4R2)
  are documented as flat-shaded with sides == top — preserve that
  authentically.
- [`wflevels/qbert_practice/blender_create_qbert.py`](../../wflevels/qbert_practice/blender_create_qbert.py):
  - line 79: `NUM_ROUNDS = 4` → `NUM_ROUNDS = 16`
  - line 714 Forth: `"425 read-mailbox 4 % "` → `"425 read-mailbox "`
    (drop modulo so `cur_pal == round_num`)
  - line 718 Forth: `"12 0 do "` → `"48 0 do "` (inner loop =
    `NUM_ROUNDS * 3`)
  - line 759 Forth: replace
    `"425 read-mailbox 1 + 425 write-mailbox "` with the clamp
    `"425 read-mailbox dup 15 < if 1 + then 425 write-mailbox "`
    (pin at 15 — arcade-faithful L4R4-forever)
  - line 764 Forth: `"336 0 do …"` → `"1344 0 do …"` (vis-zero loop =
    `TOTAL_CUBES * 3 * NUM_ROUNDS`)
  - line 767 Forth: `"440 425 read-mailbox 4 % 84 * + "` →
    `"440 425 read-mailbox 84 * + "`
  - lines 778, 785, 850 already reference `NUM_ROUNDS` and scale
    automatically.

## Reused functions / patterns

- `gen_cube.py:build_modl(top_rgb, lit_side_rgb, shadow_side_rgb)` —
  unchanged; already takes per-round colours.
- `blender_create_qbert.py:cube_index`, `cube_world_position`, the
  per-cube actor-creation loop and the post-export IFF copy loop —
  all already iterate over `range(NUM_ROUNDS)`.
- The Forth `INDEXOF_VIS_BASE + r*84 + N*3 + s` mailbox layout —
  kept identical, only the upper bound on `r` changes.

## Engine change: raise GLOBAL_USER_MAX

Per user decision, raise `GLOBAL_USER_MAX` from 999 to 2048 to fit the
1344-slot vis range (440..1783) plus headroom.

- Locate `GLOBAL_USER_MAX` definition in `wfsource/source/` (grep at
  implementation time).
- Bump value to 2048.
- Audit and unwind the 950-workarounds. Search:
  `grep -rn '\b95[0-9]\b\|GLOBAL_USER_MAX' scripts/research/mame/ wfsource/`.
- The off-by-one crash on mailbox-at-cap (the trigger documented in the
  mailbox-999 follow-up) is a separate latent bug — re-test after the
  bump but it is not required to land this task.
- Rebuild via `engine/build_game.sh`.

## Verification

1. `python3 -m py_compile wflevels/qbert_practice/gen_cube.py
   wflevels/qbert_practice/blender_create_qbert.py` — must pass before
   reload in Blender.
2. `python3 wflevels/qbert_practice/gen_cube.py wflevels/qbert_practice/`
   — confirm 48 source IFFs produced (3 states × 16 rounds).
3. Re-run `blender_create_qbert.py` inside Blender; confirm 1344 cube
   actor objects + 1344 per-cube IFFs in `wflevels/qbert_practice/`.
4. Build the engine with the raised `GLOBAL_USER_MAX`, then run the
   level via `engine/build_game.sh`. Each round-clear should show a
   visibly different palette. Spot-check L1R1 (purple/yellow), L2R1
   (blue start with orange sides), L3R1 (blue→navy, olive sides), L4R1
   (green→blue) — the four "first-round-of-level" entries with the most
   distinctive shifts. Confirm round counter pins at 15 (L4R4 displays
   forever after the 16th clear).
5. Watch mailbox 425 via MAME-side capture/Forth diagnostics during a
   long play to confirm the clamp.
