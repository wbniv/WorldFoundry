# Plan: `marble-madness-3d` — course-JSON → WF level pipeline

**Date:** 2026-09-22
**Branch:** `marble-madness-3d-fable`
**Parent plan:** [2026-09-21 Marble Madness true-3D reimplementation](2026-09-21-marble-madness-true-3d-reimplementation.md)
**Status:** Implemented + verified (see [README](../../wflevels/marble-madness-3d/README.md) § Verification)

## Goal

A **data-driven, course-agnostic** generator that turns a heightfield **course description
JSON** into a runnable standalone WF level: rolling marble player, fixed SW-isometric
follow camera, void/cliff/goal geometry. The real arcade course JSON is being
reverse-engineered separately and will be dropped in later; this effort delivers the
pipeline plus a synthetic test course that exercises every geometry case.

Nothing under `wflevels/marble-madness/`, `wflevels/marble-madness-2/` or
`wflevels/mm_practice*/` is read, copied or modified. Pipeline templates are the
**non-marble** levels: `pilot_demo` (minimal from-scratch level), `qbert_practice`
and `smb_w1_1` (infrastructure import/strip, materials, export).

## Visible surface

The visible surface is a 3D scene rendered by the WF engine. A self-contained HTML
mockup cannot represent it (lighting, backface culling and the perspective camera are
the things under test), so the mockup section is replaced by **in-engine frame capture**:
`WF_RECORD=1` → `ffmpeg` frame → `wflevels/marble-madness-3d/verify/*.png`, read back and
checked. That is the honest equivalent here.

## Contract — course description JSON

```json
{
  "name": "practice",
  "cell_size": 1.0,
  "cells": [ {"i": 3, "j": 7, "h": [z00, z10, z11, z01]} ],
  "spawn": [x, y, z],
  "goal": {"min": [x0,y0,z0], "max": [x1,y1,z1]},
  "kill_z": -3.0
}
```

`cells` is **sparse** — an absent cell is void. Cell `(i,j)` spans
`X ∈ [i·s, (i+1)·s]`, `Y ∈ [j·s, (j+1)·s]`; corner order is
`(i,j) (i+1,j) (i+1,j+1) (i,j+1)`. Z up (WF convention). `spawn` is the marble **centre**.

## Design

### Geometry (`course_geom.py`, pure Python, no `bpy`)

Separating geometry from Blender is deliberate: winding, diagonal choice and
degenerate-triangle rejection are the parts most likely to be wrong, and they are
testable without launching Blender.

| Feature | Rule |
|---|---|
| Floor | one quad per cell, split on the diagonal whose two triangles have the **smaller normal deviation** |
| Cliff wall | between adjacent cells whose shared-edge corner heights differ at either end; degenerate half dropped by area |
| Skirt | cell edge bordering void → vertical face down to `min(all heights) − 2.0` |
| Winding | authored Blender-CCW-from-outside (+Z for floors, out-of-solid for walls); the exporter flips to the engine's hand |
| Colour | flat Principled BSDF, no textures: checkerboard greys by `(i+j)%2`, dark walls, darker skirts, distinct goal |

**Rejected:** per-cell mesh actors (one statplat per cell). Simple, but N actors × N Jolt
bodies × N room-pool meshes — `qbert_practice` already had to collapse 1344 actors to 28
for exactly this reason. One merged mesh per chunk is the right unit.

**Chunking:** the exporter packs face vertex indices as `int16`
(`export_level.py:_write_mesh_iff`, `struct.pack('<hhhh', v1, v2, v3, mat_idx)`), so a
single mesh actor is hard-capped at **32767 vertices**. The generator partitions cells
into chunks under a conservative budget and emits one statplat per chunk, each face owned
by exactly one cell so shared walls are emitted once.

### Camera — exact SW-iso follow with no script

`SetCameraParametersFromShot` (`movecam.cc:247-405`) computes:

```
position  = (camShotPos − Follow.pos) + TrackObject.pos      [per-axis, when that axis is Relative]
direction = Target.pos − camShotPos                          [always absolute camShotPos]
```

The trap: with `Target = Player`, `direction` uses the **static** camshot position, so the
view direction swings as the marble travels away from spawn — the camera stops pointing
along the iso axis. The fix falls out of the same formula:

* `Target01` — a `target` actor at the **world origin**, used as both `Follow` and `Target`
* camshot actor at world position **= the offset itself**, `(−d, −d, +d)`
* `Track Object = Player`, all three `Position` axes `Relative`, `Rotation = Fixed`

⇒ `position = offset + playerPos` and `direction = 0 − offset = −offset`, **exactly
constant every frame, no script, no tick lag**.

**Rejected:** a Forth-driven camshot that writes its own `X/Y/Z_POS` each tick (the SMB
scroll pattern). Equivalent result but costs a script and one tick of lag.

Offset `(−22, −22, +22)`: horizontal distance `22√2 = 31.1 m`, elevation
`atan(22 / 31.1) = 35.26°` — **true isometric**, the closest a perspective camera gets to
the arcade's 2:1 view. FOV 28° at 38.1 m keeps perspective convergence small.

### Marble

`MarbleHandler` is selected by `Turn Rate == 0`. Input is applied **relative to actor
facing**: `fwd = currentDir() = (cos C, sin C, 0)` (`physicalobject.hpi:52` — the
`movement.cc:698` comment saying `(sin C, cos C, 0)` is wrong, per CLAUDE.md), and
`right = (fwd.Y, −fwd.X, 0)`. The documented `cam-remap` bit-rotation word assumes
`UP → +Y`, `RIGHT → +X`, which holds **only at `C = π/2`** — so the player's
`rotation_euler.z = π/2`.

Terminal speed on a slope under `MarbleHandler` is `v = a / (30 · RunningDeceleration)`
(frame-rate independent: the per-frame decay is `decel · dt · 30`). Tuned so a 5° grade
settles near 7 m/s.

### Spawn clearance — the zone-volume exclusion trap

`JoltCharacterCreate` (`jolt_backend.cc:686-704`) walks existing **static** bodies and
permanently ignores any whose world AABB fully contains the character's spawn AABB
("zone volume" heuristic). A terrain chunk's AABB contains a marble sitting on it unless
the marble sticks out of it somewhere — so the generator raises the spawn until
`spawn.z + R` strictly exceeds the max Z of every chunk that could enclose it. Verified by
the **absence** of `jolt: character N ignoring zone body` in the engine log.

## Deliverables

| Path | What |
|---|---|
| `wflevels/marble-madness-3d/course_geom.py` | pure-Python geometry + chunking |
| `wflevels/marble-madness-3d/gen_course.py` | headless Blender scene build + `.lev` export |
| `wflevels/marble-madness-3d/make_test_course.py` | writes `course-test.json` |
| `wflevels/marble-madness-3d/build.sh` | Blender step + `task build-level` |
| `wflevels/marble-madness-3d/marble-madness-3d-standalone.iff.txt` | L4 wrapper |
| `wflevels/marble-madness-3d/README.md` | contract, commands, numbers, gotchas, verification |
| `Taskfile.yml` | `build-mm3d`, `run-mm3d` |

## Verification

Numbered steps with raw output live in
[`wflevels/marble-madness-3d/README.md`](../../wflevels/marble-madness-3d/README.md)
§ Verification, per house convention. Summary of the recorded results (2026‑09‑22):

1. `course_geom.py --selftest` and `--check` on `course-test.json` — **PASS** (592 tris, 1 chunk, 355 verts).
2. Clean build → `marble-madness-3d-standalone.iff` (51200 bytes), Player exported before the course chunks — **PASS**.
3. 15 s run: 0 matches for `AssertMsg|zforth compile|fell out of room|ignoring zone body|terminate called` — **PASS**.
4. Rolls downhill with no input: `(1.15, 2.00, 8.15) → … → (27.34, 12.06, −3.900)` = floor(−4.4) + radius(0.5), at rest on the goal — **PASS**.
5. Frames inspected: floor visible under default backface culling, checkerboard/cliff/rim/goal legible, HUD live — **PASS**.
6. Real arcade `course.json` (1729 cells): `--check` PASS, 2 chunks, built to 147 KB, 22 s run with 0 asserts / 0 zone exclusions — **PASS**; end‑to‑end traversal with injected input is recorded in the [parent plan](2026-09-21-marble-madness-true-3d-reimplementation.md) § Verification step 5.
