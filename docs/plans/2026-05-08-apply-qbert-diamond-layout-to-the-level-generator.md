# Plan: Apply Q*bert diamond layout to the level generator

**Status:** DONE 2026-05-08 (commits `c0b87a25`, `61457243`) — √2 scaling + 45° rotation diamond layout in the generator.

## Context

The user's interactive Blender experiments confirmed that the iconic Q*bert
look needs:

1. Each cube **rotated 45° about Z** (so it presents a diamond top, not a
   flat square top), and
2. Cube centres in XY **spread by √2** so adjacent diamond corners touch
   without overlapping.

The user has approved this look in the live `qbert_practice.blend` and now
wants the change baked into the source script
(`wflevels/qbert_practice/blender_create_qbert.py`) so the next run of
`blender --background --python blender_create_qbert.py` reproduces the
correct layout. The player must spawn on top of the apex cube, which means
the apex's new Y position (also scaled by √2) has to flow through to the
player spawn AND to the Forth `do-hop` formula that teleports the player
on each landed-on-cube.

## Files to modify

- `wflevels/qbert_practice/blender_create_qbert.py` — the only file that
  needs editing for this change. `gen_cube.py` (the per-cube IFF generator)
  is unaffected because cube *geometry* doesn't change — only its rotation
  and the per-actor location.

## Recommended approach

### 1. Add `SQRT2` constant near the pyramid-geometry section

```python
import math
SQRT2 = math.sqrt(2.0)
```

### 2. Update `cube_world_position(row, col)` to scale XY by √2

```python
def cube_world_position(row, col):
    world_x = SQRT2 * (col - row / 2.0) * CUBE_SIZE
    world_y = SQRT2 * (NUM_ROWS - 1 - row) * (CUBE_SIZE / 2.0)
    world_z = CUBE_BASE_Z + (NUM_ROWS - 1 - row) * CUBE_SIZE
    return (world_x, world_y, world_z)
```

Z is unchanged — the staircase rise stays at one CUBE_SIZE per row.

### 3. Update `APEX_X`, `APEX_Y`, `PLAYER_SPAWN_XYZ`

```python
APEX_X = 0.0
APEX_Y = SQRT2 * (NUM_ROWS - 1) * (CUBE_SIZE / 2.0)   # was 6.0 → ~8.485
APEX_Z = CUBE_BASE_Z + (NUM_ROWS - 1) * CUBE_SIZE      # unchanged (=13.0)
PLAYER_SPAWN_XYZ = (APEX_X, APEX_Y, APEX_Z + 1.5)
```

### 4. Rotate every cube actor 45° about Z when it's created

In the actor-creation loop (currently around line 715):

```python
obj = bpy.data.objects.new(obj_name, mesh_data)
obj.location = (wx, wy, wz)
obj.rotation_euler = (0.0, 0.0, math.pi / 4)   # NEW — 45° about Z
scene.collection.objects.link(obj)
```

The wf_blender exporter writes `rotation_euler` into the actor's `EULR`
Orientation chunk, so the engine receives the same rotation that's
visible in Blender.

### 5. Update the player's Forth `do-hop` to scale X/Y by √2

zForth's cell type is `float` (engine/stubs/scripting_zforth.cc:7) and
`zf_host_parse_num` parses float literals via `strtof`, so a `1.4142136`
literal multiplier is the simplest mechanism — no fixed-point shifts needed.

In the `wf_Script` literal under `# Player — Anchored, Q*bert hop state machine`:

- `over over swap 2 * swap - INDEXOF_X_POS write-mailbox`
  → `over over swap 2 * swap - 1.4142136 * INDEXOF_X_POS write-mailbox`
- `6 over - INDEXOF_Y_POS write-mailbox`
  → `6 over - 1.4142136 * INDEXOF_Y_POS write-mailbox`

Z math is unchanged. Make the same edits to the *off-edge re-clamp* branch
of `do-hop` so the predictive-fall position is consistent (only its Z is
written there, so no edits required for that branch in practice — verify
during implementation).

The same constant must also be applied to the Y values in the
restart/fall/round-clear `INDEXOF_Y_POS write-mailbox 6` calls, so the
player respawns at apex Y = 6·√2 instead of 6:

- `6 INDEXOF_Y_POS write-mailbox` → `6 1.4142136 * INDEXOF_Y_POS write-mailbox`
  (4 occurrences in the player Script: game-over restart, round-clear apex
   respawn, fall-end snap, Z<-2 safety net.)

### 6. Verify ROOM_BBOX_REL still encloses everything

After scaling, cube X extends ±6·√2 ≈ ±8.49 (was ±6) and cube Y extends
0..6·√2 ≈ 0..8.49 (was 0..6). Current `ROOM_BBOX_REL = (-15, -100, -45,
75, 15, 45)` already covers ±15 in X and -100..15 in Y, so no change is
required. Worth a sanity assertion in code, but not load-bearing.

## Verification

1. `blender --background --python wflevels/qbert_practice/blender_create_qbert.py`
   — should run clean and write `qbert_practice.blend` and `qbert_practice.lev`.
2. Open the .blend in Blender → confirm the diamond layout matches what's
   currently in the live scene (cubes rotated 45°, edge-to-edge with no
   overlap).
3. Build & run: from `engine/`, `./build_game.sh && cd
   ../wfsource/source/game && ./wf_game qbert_practice` (or whatever
   command the existing build doc lists).
4. In-game checks:
   - Player spawns visually centred on the apex diamond.
   - Hopping in each of the four diagonal directions lands the player
     centred on the neighbouring diamond (not offset by ~0.4 units).
   - Off-edge hops still trigger the fall animation correctly.
   - Round-clear apex respawn places the player back on the apex diamond.
5. If any landing looks off-centre, the most likely cause is a missed
   `1.4142136 *` insertion in either the X- or Y-position branch — diff
   the script against the plan before re-running.
