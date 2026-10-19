# Q✱bert diamond cube layout

**Status:** ✅ Complete (2026-05-08, commit `c0b87a2`). All 5 steps
implemented in `blender_create_qbert.py`: cubes rotated 45° about Z
(line 801), `cube_world_position` scales XY by `SQRT2` (lines 97–99),
`APEX_Y` / `PLAYER_SPAWN_XYZ` updated to the new apex (lines 107–108),
player Forth `do-hop` and respawn paths multiply target X/Y by
`1.4142136` (lines 336/337/374/386/400/440), `ROOM_BBOX_REL` widened
to encompass the scaled extents (line 137). Verified live — the level
runs, Q✱bert lands centred on each diamond, off-edge hops trigger
fall (subsequent floating-after-round-1 issue tracked in
[walker-wf-parity](2026-05-09-qbert-walker-wf-parity.md)).

Bake the iconic Q✱bert diamond presentation into
`wflevels/qbert_practice/blender_create_qbert.py`:

1. Rotate every cube actor 45° about Z (`rotation_euler.z = π/4`).
2. Spread cube centres in XY by `√2` so adjacent diamond corners touch
   without overlapping. Z (staircase rise) unchanged.
3. Update `APEX_Y` and `PLAYER_SPAWN_XYZ` to the new √2-scaled apex.
4. Update the player Forth `do-hop` and respawn paths to multiply X/Y
   by `1.4142136` (zForth cell type is `float`).
5. `ROOM_BBOX_REL` already encloses the new extents (±8.49 vs ±15 cap).

Full reasoning + verification steps:
[~/.claude/plans/great-the-cubes-look-reflective-hearth.md].

## Verification

- `blender --background --python wflevels/qbert_practice/blender_create_qbert.py`
- Inspect `qbert_practice.blend` — diamonds, edge-touching.
- Build & run engine; confirm player lands centred on each diamond and
  off-edge hops trigger the fall animation.
