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

## Gold standard: what the 3ds Max exporter did

The legacy 3ds Max exporter (`wfmaxplugins/max2lvl/level.cc`, deleted in commit [`c5761ca`](https://github.com/wbniv/WorldFoundry/commit/c5761ca) "purge") is the closest thing to a known-correct reference. No real bugs have been reported against it in years. Reading the deleted source:

```cpp
// QLevel::CreateQObjectFromSceneNode — wfmaxplugins/max2lvl/level.cc:126–550

Matrix3 nodeTM   = thisNode->GetNodeTM(theTime);
Point3  location = nodeTM.GetTrans();             // (1) Position = node's WORLD translation

// ... rotation extraction, OAD load, path keyframes ...

QColBox collision;
objTM = thisNode->GetObjTMAfterWSM(theTime);
objTM.NoTrans();                                  // (2) strip translation
collision.Bound(*thisMesh, objTM, objOffsetPos);  //     bbox in OBJECT-LOCAL space

// ... thin-floor padding to avoid axis-degenerate bboxes ...

objects.push_back(new QObject(
    thisObjectName, typeIndex,
    Point3(location.x, location.y, location.z),   // Position field — node world pos
    Point3(1.0, 1.0, 1.0),                        // (3) Scale HARDCODED to identity
    rotEuler, collision, oadFlags, pathIndex, newobjOAD));
```

| Field | Max-exporter semantic |
|---|---|
| `Position` | Node's world-space translation (the pivot point a Max artist sees in the viewport). Never zero unless the artist actually placed the node at the origin. |
| `Scale` | Always `(1, 1, 1)`. The Max exporter does not pass per-actor scale into the level — geometry is authored at final scale, and any node-level scale is reflected only via the bounding-box derivation. |
| `Bounding Box` (`QColBox`) | The mesh AABB transformed by `objTM` with translation stripped — i.e., scale + rotation applied around the pivot, no world-position component. **Object-local extents.** A ground slab modelled as 73.5×3×1.5 m emits min=`(-36.75, -1.5, -0.75)` max=`(+36.75, +1.5, +0.75)`, regardless of where the node sits in world space. |
| Mesh data | Object-local vertices (Max's mesh data is in node-local space; the world pivot adds them up at render time). |

Together these mean the engine can always reconstruct the world extent as `Position + BBox` and the world vertex location as `Position + Rotation×Scale×MeshVert`. Any consumer downstream — Jolt collider construction, `actboxor` trigger overlap math, `INDEXOF_X_POS` script reads, debug picks, the `--debug-print-actors` log — sees a consistent picture.

The `add_box` Blender quirk breaks this on all three of (1)/(3)/bbox: `Position` collapses to `(0,0,0)`, the BOX3 collapses to world-extent (because the mesh-local verts are world-baked), and Jolt happens to build a collider from the world-baked mesh that lands in the right place by accident. The visual renders correctly because both the mesh and the (zero) actor transform agree, but the level data structure has lost the artist's intent.

## What other Blender levels do — Q*bert and Marble Madness already match Max

The Q*bert and Marble Madness Blender scripts predate SMB and **both independently arrive at the Max-correct pattern**. Neither hits the quirk. The two patterns:

### Q*bert pyramid cubes ([`wflevels/qbert_practice/blender_create_qbert.py:3452–3493`](../../wflevels/qbert_practice/blender_create_qbert.py))

```python
# Build one mesh datablock by hand — no primitive_cube_add, no transform_apply.
_cube_mesh = bpy.data.meshes.new('cube_mesh_shared')
_s = CUBE_SIZE / 2
_box_verts = [
    (-_s, -_s, -_s), ( _s, -_s, -_s), ( _s,  _s, -_s), (-_s,  _s, -_s),
    (-_s, -_s,  _s), ( _s, -_s,  _s), ( _s,  _s,  _s), (-_s,  _s,  _s),
]
_box_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
_cube_mesh.from_pydata(_box_verts, [], _box_faces)
_cube_mesh.update()

for row in range(NUM_ROWS):
    for col in range(row + 1):
        wx, wy, wz = cube_world_position(row, col)
        obj = bpy.data.objects.new(f"cube_{N:02d}", _cube_mesh)
        obj.location = (wx, wy, wz)                # ← world pivot, never re-applied
        obj.rotation_euler = (0.0, 0.0, math.pi / 4)
        scene.collection.objects.link(obj)
        obj['wf_schema_path'] = STATPLAT_OAD
        # ... obj['wf_Mesh Name'] etc.
```

Mesh-local verts at `±_s` around the mesh origin, `obj.location` set to the world pivot, no scale, no `transform_apply` ever called. All 28 cubes share one mesh datablock (Phase 1 cube consolidation). Export emits:
- `Position = (wx, wy, wz)` — true world pivot ✓
- `Scale` implied (1,1,1) ✓
- `BOX3 = (-_s, -_s, -_s) → (+_s, +_s, +_s)` — object-local ✓

### MM `mm_practice` ramp ([`wflevels/mm_practice/blender_create_mm_practice.py:149–163`](../../wflevels/mm_practice/blender_create_mm_practice.py))

Same shape, different vertex pattern:

```python
verts = [
    (-5, -10,  2), ( 5, -10,  2),
    ( 5,  10, -2), (-5,  10, -2),   # mesh-local quad coords
]
faces = [(0, 1, 2, 3)]
mesh_data = bpy.data.meshes.new("RampMesh")
mesh_data.from_pydata(verts, [], faces)
ramp_obj = bpy.data.objects.new("Ramp", mesh_data)
ramp_obj.location = (0, 10, 2)                     # ← world pivot
scene.collection.objects.link(ramp_obj)
```

### MM ROM-driven `make_box_empty` ([`wflevels/marble-madness/blender_mm_practice_rom.py:129–148`](../../wflevels/marble-madness/blender_mm_practice_rom.py))

The cleanest extraction of the pattern — a helper that takes an explicit `bbox_local` parameter and a world `pos`:

```python
def make_box_empty(name, pos, bbox_local, oad_name, props=None):
    lx0, ly0, lz0, lx1, ly1, lz1 = bbox_local
    verts = [
        (lx0, ly0, lz0), (lx1, ly0, lz0), (lx1, ly1, lz0), (lx0, ly1, lz0),
        (lx0, ly0, lz1), (lx1, ly0, lz1), (lx1, ly1, lz1), (lx0, ly1, lz1),
    ]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    m = bpy.data.meshes.new(f'{name}_box')
    m.from_pydata(verts, [], faces)
    m.update()
    obj = bpy.data.objects.new(name, m)
    obj.location = pos
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = oad(oad_name)
    obj['wf_original_bbox'] = bbox_local           # ← exporter override (export_level.py:924)
    # ...
```

Notable extra: it sets `obj['wf_original_bbox'] = bbox_local`. The exporter checks for this key first (export_level.py:924–927) and uses it verbatim as the BOX3 if present, bypassing `obj.bound_box` derivation entirely. This lets the author tighten / loosen the collision bbox away from the auto-derived visual AABB — a feature the SMB script would benefit from later for "forgiving Mario hitbox" tuning (see [`docs/investigations/2026-05-17-colspace-authoring.md`](2026-05-17-colspace-authoring.md) "Open questions").

### Why SMB regressed

SMB's [`add_box`](../../wflevels/smb_w1_1/blender_create_smb.py) is a newer authoring style — `primitive_cube_add` for the geometry, then `obj.scale = (sx, sy, sz)` + `transform_apply(scale=True)` to bake the cube to size. Cleaner-looking Blender code than building vertex tuples by hand, but it walks straight into the `transform_apply` location-baking quirk. None of the older levels happen to use this pattern.

### Coverage summary

| Level | Box-statplat construction | Hits the quirk? | Position in `.lev` |
|---|---|---|---|
| `qbert_practice` | `bpy.data.meshes.new` + `from_pydata` + `bpy.data.objects.new` | NO | true world pivot ✓ |
| `mm_practice` | same | NO | true world pivot ✓ |
| `marble-madness` (all five variants) | `make_box_empty` helper (same pattern) | NO | true world pivot ✓ |
| `snowgoons-blender` | — (no box statplats, all `Anchored` non-physical actors) | n/a | n/a |
| `smb_w1_1` | `primitive_cube_add` → `obj.scale = …` → `transform_apply(scale=True)` | **YES** | `(0, 0, 0)` ✗ |

So this is a one-level regression, not a systemic bug. Q*bert and MM are already correct and serve as the working reference. The fix is to either port SMB's `add_box` to the from_pydata pattern, or work around the `transform_apply` quirk in place (move-to-origin / apply / restore).

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
