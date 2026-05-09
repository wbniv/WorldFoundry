# Q*bert diamond cube layout

**Status:** In progress (2026-05-08).

Bake the iconic Q*bert diamond presentation into
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
