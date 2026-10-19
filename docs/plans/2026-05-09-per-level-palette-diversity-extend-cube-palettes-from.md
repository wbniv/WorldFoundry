# Per-level palette diversity: extend cube palettes from 4 to 16 rounds

**Status:** DONE (commit `9f104b28`) — 16-round cube-palette extension shipped.

## Context

Q*bert arcade has 4 levels × 4 rounds = 16 distinct cube colour palettes.
Today `wflevels/qbert_practice/gen_cube.py` only ships 4 (L1R1..L1R4), and
`blender_create_qbert.py` cycles `cur_pal = round_num % 4`, so after R3 the
practice level loops the L1 palette set rather than progressing through
L2/L3/L4 colours. The investigation
`docs/investigations/qbert_cube_face_colors.md` already lists all 16
canonical (top, target_top, lit_side, shadow_side) entries from MAME
captures. This change makes the visible cube colours match the arcade for
every round of the practice level. User-facing.

## Critical constraint discovered during planning

Going from 4→16 rounds with the existing actor-per-`(cube, round, state)`
visibility model bumps the visibility mailbox range to:

```
INDEXOF_VIS_BASE + (NUM_ROUNDS-1)*84 + 27*3 + 2
= 440 + 15*84 + 81 + 2
= 1783
```

That exceeds `GLOBAL_USER_MAX = 999` (and the 950-workaround per
`memory/project_followup_mailbox_999_crash.md`). We must pick a strategy
before implementing — see "Open question" at the bottom.

## Files to modify

- `wflevels/qbert_practice/gen_cube.py` — extend `ROUND_COLORS` to 16
  entries (canonical (top, target_top, lit_side, shadow_side) tuples
  drawn from `docs/investigations/qbert_cube_face_colors.md`). Loop
  already does `enumerate(ROUND_COLORS)` so no other changes here; output
  grows from 12 to 48 source IFFs (`cube_state{0,1,2}_r{0..15}.iff`).
- `wflevels/qbert_practice/blender_create_qbert.py`:
  - line 79: `NUM_ROUNDS = 4` → `NUM_ROUNDS = 16`
  - line 714 Forth: `"425 read-mailbox 4 % "` → `"425 read-mailbox "`
    (drop modulo so `cur_pal == round_num`)
  - line 718 Forth: `"12 0 do "` → `"48 0 do "` (inner loop is
    `NUM_ROUNDS * 3`)
  - line 764 Forth: `"336 0 do …"` → `"1344 0 do …"` (vis-zero loop is
    `TOTAL_CUBES * 3 * NUM_ROUNDS`)
  - line 767 Forth: `"440 425 read-mailbox 4 % 84 * + "` →
    `"440 425 read-mailbox 84 * + "`
  - lines 778, 785, 850 already reference `NUM_ROUNDS`; they scale
    automatically.
- The 16 ROUND_COLORS entries source from
  `docs/investigations/qbert_cube_face_colors.md`. Two arcade rounds
  (L2R4, L4R2) are documented as flat-shaded with sides equal to the
  top — preserve that authentically (sides = 0x000000 in the doc means
  "no lit/shadow split"; will look correct because all faces are the
  same RGB).

## Reused functions / patterns

- `gen_cube.py:build_modl(top_rgb, lit_side_rgb, shadow_side_rgb)` —
  no changes needed; already takes per-round colours.
- `blender_create_qbert.py:cube_index`, `cube_world_position`, the
  per-cube actor-creation loop and the post-export IFF copy loop —
  all already iterate over `range(NUM_ROUNDS)`.
- The Forth `INDEXOF_VIS_BASE + r*84 + N*3 + s` mailbox layout — kept
  identical, only the upper bound on `r` changes.

## Round counter clamp (pin at 15)

`425 read-mailbox 1 + 425 write-mailbox` (line 759) increments the round
counter forever. With `cur_pal = round_num` (no mod), once it passes 15
the visibility fan-out finds no matching combo and every cube becomes
invisible. Pin at 15 to match arcade L4R4-forever behaviour:

```
425 read-mailbox dup 15 < if 1 + then 425 write-mailbox
```

## Verification

1. `python3 -m py_compile wflevels/qbert_practice/gen_cube.py
   wflevels/qbert_practice/blender_create_qbert.py` — must pass before
   reload (per memory `feedback_py_compile_check.md`).
2. `python3 wflevels/qbert_practice/gen_cube.py
   wflevels/qbert_practice/` — verifies 48 source IFFs are produced
   (4 per round × 16 rounds, but actually 3 states × 16 = 48).
3. Run the level once through `engine/build_game.sh` (per
   `memory/project_wf_game_build.md`); each round-clear should show a
   visibly different palette. Spot-check L1R1 (purple/yellow), L2R1
   (blue/green sides retain orange/dark-orange), L3R1 (blue→navy with
   olive sides), L4R1 (green→blue) — these are the four "first-round-
   of-level" entries with the most distinctive shifts.
4. Watch mailbox 425 in MAME-side capture and confirm wraparound at 16.

## Engine change: raise GLOBAL_USER_MAX

Per user decision, raise `GLOBAL_USER_MAX` from 999 to ~2000 to fit the
1344-slot vis range (440..1783) plus headroom. Tasks:

- Locate `GLOBAL_USER_MAX` definition in engine source (grep needed
  during implementation; `wfsource/source/`).
- Bump value to 2048 (round number, gives ~265 slot headroom).
- Audit and unwind the 950-workarounds noted in
  `memory/project_followup_mailbox_999_crash.md`. Search:
  `grep -rn '\b95[0-9]\b\|GLOBAL_USER_MAX' scripts/research/mame/
  wfsource/`.
- The off-by-one crash on mailbox-at-cap is a separate latent bug; not
  required for this task but worth re-testing after the bump (this is
  the trigger condition the follow-up memory references).
- Rebuild via `engine/build_game.sh`.
