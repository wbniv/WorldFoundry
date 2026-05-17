# Statplat actor `Position` is silently `(0,0,0)` in the `.lev`

**Date:** 2026-05-17
**Author:** Will Norris + Claude
**Status:** investigation — root cause identified; fix proposed but not landed.

## TL;DR

The 2026-05-17 [`--debug-print-actors`](../level-building.md#-debug-print-actors-debug-builds-only) flag exposed a long-standing quirk: every static-platform actor in `wflevels/smb_w1_1/` reports `pos=(0.00, 0.00, 0.00)` at `Actor::Actor` construction, even though the ground, `?` blocks, and `flagpole_flag` are visibly placed at non-origin world coordinates. The flagpole **pole** is the only statplat that reports a real position (`63.00, 0.00, 7.50`).

Root cause: the Blender script's [`add_box` helper](../../wflevels/smb_w1_1/blender_create_smb.py) calls `bpy.ops.object.transform_apply(scale=True)` on a cube whose `obj.location` is non-origin. Empirically, when `obj.location ≠ (0,0,0)` at apply time, Blender bakes the **translation** into the mesh vertices as a side effect — even though only `scale=True` was requested — and resets `obj.location` to `(0,0,0)`. The `.lev` exporter then reads `obj.matrix_world.to_translation()` and writes the zeroed value as the actor's `Position` field. The cylinder-/plane-based primitives (`flagpole_pole`, `flagpole_flag` after the script's later transform_apply, and Mario himself) don't hit this because they're authored differently.

It quietly hasn't been a visible bug because:
- The world-baked mesh renders at the right pixels regardless of actor position.
- Jolt's static-body collider for statplats is built from the **mesh AABB**, which still spans the correct world coordinates.

It becomes visible the moment anything reads the actor's `Position` field — which `--debug-print-actors` just made trivially observable, but also affects runtime script reads (`INDEXOF_X_POS` etc.) and any future tooling that joins bridge `idx` to authored placement.

## Reproduction

A minimal Blender script:

```python
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(10, 20, 30))
obj = bpy.context.object
print(obj.location, obj.data.vertices[0].co)
# (10.0, 20.0, 30.0)  (-0.5, -0.5, -0.5)   ← expected: loc set, verts mesh-local at ±0.5

obj.scale = (4, 2, 1)
bpy.ops.object.transform_apply(scale=True)
print(obj.location, obj.scale, obj.data.vertices[0].co)
# (0.0, 0.0, 0.0)  (1.0, 1.0, 1.0)  (8.0, 19.0, 29.5)
#  ^^^^^^^^^^^^^                     ^^^^^^^^^^^^^^^
#  silently zeroed                    world-baked instead of mesh-local-scaled (-2, -1, -0.5)
```

The mesh-local vertex coordinate `(8.0, 19.0, 29.5)` is the cube corner's full **world** position — exactly what `obj.location + (scaled mesh-local)` would have been before the apply. Blender re-distributed the transform so the world appearance is identical and the operation looks like a "no-op from the user's perspective", but the data structure that downstream consumers (exporters, scripts, debuggers) read is now misleading.

## Empirical evidence from `wflevels/smb_w1_1/smb_w1_1.lev`

Parsing each `Position` field alongside the following `Class Name`:

| Position (auth-time intent) | Class | `Position` in `.lev` |
|---|---|---|
| `(33.75, 0, 5)` (centre of room) | `room` | `(33.75, 0, 5)` ✓ |
| `(4.5, -20, 4.5)` (`CAMSHOT_POS`) | `camera` / `camshot` | `(4.5, -20, 4.5)` ✓ |
| `(4.5, 0, 1.5)` (`MARIO_SPAWN_X, 0, MARIO_Z`) | `player` | `(4.5, 0, 1.5)` ✓ |
| `(33, 0, 1.5)` (`GOOMBA_X, 0, MARIO_Z`) | `enemy` (goomba) | `(33, 0, 1.5)` ✓ |
| `(42, 0, 1.5)` (`KOOPA_X, 0, MARIO_Z`) | `enemy` (koopa) | `(42, 0, 1.5)` ✓ |
| `(63, 0, 7.5)` (flagpole midheight) | `statplat` (`flagpole_pole`) | `(63, 0, 7.5)` ✓ |
| `(33.75, 0, -0.75)` (ground centre) | `statplat` (`ground`) | **`(0, 0, 0)`** ✗ |
| `(12, 0, 6.75)` (`?` block) | `statplat` (`qblock_00`) | **`(0, 0, 0)`** ✗ |
| `(21, 0, 6.75)` | `statplat` (`qblock_01`) | **`(0, 0, 0)`** ✗ |
| `(25.5, 0, 6.75)` | `statplat` (`qblock_02`) | **`(0, 0, 0)`** ✗ |
| `(41, 0, 9)` (flag offset from pole) | `statplat` (`flagpole_flag`) | **`(0, 0, 0)`** ✗ |
| `(0, 0, 0)` (level origin marker) | `target` (`Target01`) | `(0, 0, 0)` (semantically correct) |

The `(0, 0, 0)` cases are **all** the actors that went through `add_box → transform_apply(scale=True)`. Every other actor went through `primitive_cylinder_add` or `primitive_plane_add` with a non-unit `obj.scale` already baked into the primitive's `depth`/`radius` parameters — no separate scale-apply step, no side-effect location zeroing.

Parsing `wflevels/smb_w1_1/ground.iff` confirms the mesh-local verts span world coordinates `X: −3.0 → +70.5, Y: ±1.5, Z: −1.5 → 0` — i.e., **world-baked**, not the expected `±36.75, ±1.5, ±0.75` mesh-local-around-origin.

## Why it's stayed invisible

| Consumer | Reads from | Effect |
|---|---|---|
| `RenderActor3DAnimates` (visual) | mesh-local verts × `actor.matrix_world` | world-baked verts × identity matrix = correct world position |
| `JoltMakeStaticMesh` | mesh-local verts as Jolt mesh shape | Jolt body sits at the right world coordinates |
| Per-frame physics tick | Jolt body | unaffected (Jolt has correct collision) |
| Bridge `{"op":"state","idx":N,"pos":[…]}` for statplats | actor's `_physicalAttributes.Position()` → `(0,0,0)` | wrong but no one was looking; today's `--debug-print-actors` surfaced it |
| `INDEXOF_X_POS` mailbox read from script | actor position | would return `0` — and SMB has no scripts on statplats, so nobody noticed |
| Future "where is this actor?" debug pick | actor position | would mislead |
| `actboxor` overlap queries | actor `ColSpace.UnExpMin(pos) … UnExpMax(pos)` | uses actor position as origin → bbox shifted to origin → incorrect overlap region |

Of these, **the `actboxor` consumer is the silent landmine.** If anyone ever puts an actboxor trigger volume on or near a statplat for collision detection, the trigger zone is computed relative to (0,0,0) instead of the visible position. Hasn't bitten yet because every committed level either (a) doesn't use statplat triggers, or (b) uses single-cube statplats whose `obj.location` was already (0,0,0).

## Proposed fix

### (1) Patch `add_box` in `blender_create_smb.py` to preserve `obj.location`

Move-to-origin, apply, restore:

```python
def add_box(mesh_name, x0, y0, z0, x1, y1, z1, mat):
    cx, cy, cz = (x0+x1)/2, (y0+y1)/2, (z0+z1)/2
    sx, sy, sz = x1-x0, y1-y0, z1-z0
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    obj = bpy.context.object
    obj.name      = mesh_name
    obj.data.name = mesh_name

    # transform_apply(scale=True) silently bakes location too when obj.location
    # is non-origin (Blender quirk — see
    # docs/investigations/2026-05-17-statplat-zero-position-quirk.md). Move the
    # object to origin, apply scale around there, then restore the location so
    # mesh-local verts stay ±sx/2 etc. and obj.location is preserved.
    loc_backup = obj.location.copy()
    obj.location = (0, 0, 0)
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.location = loc_backup
    bpy.context.view_layer.update()

    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    return obj
```

After the fix:
- mesh-local verts: `(±sx/2, ±sy/2, ±sz/2)` (mesh-local around origin)
- `obj.location`: `(cx, cy, cz)`
- `obj.matrix_world.to_translation()`: `(cx, cy, cz)` ← what the exporter writes as `Position`
- Renders identically (visual is unchanged)
- Jolt static body still correct (mesh AABB unchanged in world space)
- `--debug-print-actors` now reports the real centre

The `view_layer.update()` is to refresh `matrix_world` after the manual `obj.location` write, so the exporter sees the restored translation.

### (2) Add an `add_box`-style helper to `wftools/wf_blender/`

`add_box` is reinvented per level (Q*bert and Marble Madness will hit the same quirk if they author cube primitives the same way). Move the helper into a shared module:

```python
# wftools/wf_blender/scripting_helpers.py
def add_box(mesh_name, mn, mx, mat, *, scene=None):
    """Add an axis-aligned cube statplat spanning min..max corners.
    Preserves obj.location through scale-apply (works around the Blender
    transform_apply(scale=True) location-zeroing quirk)."""
```

Then SMB / Q*bert / MM Blender scripts import it instead of re-defining.

### (3) Add a regression check to `wf_blender` export

Print a warning (or hard error in CI) when an actor with a non-trivial mesh AABB has `Position == (0, 0, 0)` and a `Class Name` of `statplat`. Catches the quirk automatically in any future level that re-introduces the pattern.

## Out of scope (deferred)

- The empirical-test-script `WORLD` computation showing `(-2, -1, -0.5)` instead of `(8, 19, 29.5)` after the workaround is a depsgraph staleness artifact — `matrix_world` doesn't update until the scene re-evaluates. The exporter calls `matrix_world.to_translation()` after the script has fully run (when the scene IS evaluated), so this isn't a problem at export time. Confirmed by the actual export path: actboxor / room / camera / player / enemies all get correct `Position` written even though they're authored across many lines.
- Whether `transform_apply` should be changed in Blender itself is a discussion for upstream Blender. The behaviour appears to be intentional ("apply the named transforms, but preserve world appearance") — but it's underdocumented and surprising.

## Files touched / proposed

| File | Status | Change |
|---|---|---|
| `wflevels/smb_w1_1/blender_create_smb.py` | proposed | `add_box` move-to-origin / apply / restore (fixes SMB W1-1 statplats) |
| `wftools/wf_blender/scripting_helpers.py` | proposed (new) | Shared `add_box` helper for future levels |
| `wftools/wf_blender/export_level.py` | proposed | Warn on `Position == (0,0,0)` for statplat with non-trivial AABB |
| `docs/level-building.md` | proposed | Add a "Box statplats" subsection under "Physics-mobility actor authoring rules" pointing here |

## Related

- [`docs/investigations/2026-05-17-colspace-authoring.md`](2026-05-17-colspace-authoring.md) — the OAD `Global Bounding Box` is auto-derived from the visual mesh AABB; the world-baked-mesh quirk explains why statplat bboxes show world coordinates instead of mesh-local extents in the `.lev`.
- [`docs/level-building.md`](../level-building.md) `--debug-print-actors` — the flag that surfaced this.
