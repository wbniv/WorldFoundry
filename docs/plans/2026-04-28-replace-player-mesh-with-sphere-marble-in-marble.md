# Plan: Replace Player Mesh with Sphere (Marble) in marble-madness

**Status:** DONE — sphere mesh created and used by [`wflevels/marble-madness`](../../wflevels/marble-madness).

## Context
The marble-madness level currently uses `player.iff` (snowman model) as a placeholder for
the marble. The player mesh needs to be replaced with a sphere to match the Marble Madness
game shape. Physics properties also need tuning for marble-like behaviour.

All level work now happens via headless Blender scripts + build pipeline.

---

## Step 1 — Write plan doc to docs/plans/

File: `docs/plans/2026-04-28-marble-player-sphere.md`
Brief human-readable record of what this script does and why.

---

## Step 2 — Write headless Blender script

File: `wflevels/marble-madness/blender_update_player_sphere.py`

```python
"""Import marble-madness.lev, replace Player mesh with a 1-unit UV sphere,
update custom props and physics, export back out."""

import bpy, math, addon_utils, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEV = os.path.join(SCRIPT_DIR, 'marble-madness.lev')

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)

bpy.ops.wf.import_level(filepath=LEV)

player = bpy.data.objects.get("Player")

# Replace mesh with UV sphere radius=0.5, so world extents = [-0.5,-0.5,0..0.5,0.5,1]
old_mesh = player.data
sphere = bpy.data.meshes.new("SphereMesh")
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0,0,0.5))
sphere_tmp = bpy.context.active_object
player.data = sphere_tmp.data
player.data.name = "SphereMesh"
bpy.data.objects.remove(sphere_tmp, do_unlink=True)
if old_mesh and old_mesh.users == 0:
    bpy.data.meshes.remove(old_mesh)

# Assign same texture as ramp so it renders
import bpy
mat = bpy.data.materials.new("MarbleMat")
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(os.path.join(SCRIPT_DIR,'G_SnowyGrass1.tga'), check_existing=True)
mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
player.data.materials.clear()
player.data.materials.append(mat)

# Update WF custom properties
player['wf_original_mesh_name'] = 'sphere.iff'
player['wf_original_bbox'] = (-0.5, -0.5, 0.0, 0.5, 0.5, 1.0)

# Tune physics for marble
player['wf_Vertical Elasticity']   = 0.3
player['wf_Horizontal Elasticity'] = 0.7
player['wf_Running Acceleration']  = 15.0

bpy.ops.wf.export_level(filepath=LEV)
print("[sphere] Done")
```

---

## Step 3 — Run the script

```bash
cd wflevels/marble-madness
blender --background --python blender_update_player_sphere.py
```

Verify `marble-madness.lev` now references `sphere.iff` (grep "Mesh Name").

---

## Step 4 — Build

```bash
bash ../../wftools/wf_blender/build_level_binary.sh marble-madness
```

Expected: 24 576 bytes (or close — sphere has more verts than snowman so may differ).

---

## Step 5 — Smoke test

```bash
timeout 8 engine/wf_game -L wflevels/marble-madness-standalone.iff
```

Need standalone wrapper first:
- Write `wflevels/marble-madness/marble-madness-standalone.iff.txt`
- Compile it

Success: `GROUND` state, no crash, no `fell out of room`.

---

## Step 6 — Commit

Files to stage:
- `docs/plans/2026-04-28-marble-player-sphere.md`
- `wflevels/marble-madness/blender_update_player_sphere.py`
- `wflevels/marble-madness/marble-madness.lev` (updated)
- `wflevels/marble-madness/sphere.iff` (new mesh)
- `wflevels/marble-madness.iff` (rebuilt)
- `wflevels/marble-madness/marble-madness-standalone.iff.txt`
- `wflevels/marble-madness-standalone.iff`
- build outputs in marble-madness/

---

## Critical files
- `wflevels/marble-madness/marble-madness.lev` — level source, edited in-place
- `wftools/wf_blender/export_level.py` — exporter, writes sphere.iff via `_write_mesh_iff`
- `wftools/wf_blender/build_level_binary.sh` — build pipeline
- `engine/wf_game` — smoke test binary

## Key custom property names (from importer seeding)
- `wf_original_mesh_name` — filename exporter uses for the mesh .iff
- `wf_original_bbox` — 6-tuple (minX,minY,minZ,maxX,maxY,maxZ)
- `wf_Vertical Elasticity`, `wf_Horizontal Elasticity`, `wf_Running Acceleration`
