"""
blender_update_player_sphere.py — replace Player mesh with a marble sphere.

Run:
  blender --background --python blender_update_player_sphere.py
"""

import bpy
import os
import addon_utils

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LEV = os.path.join(SCRIPT_DIR, 'marble-madness.lev')

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)

print(f"[sphere] Importing {LEV}")
bpy.ops.wf.import_level(filepath=LEV)

player = bpy.data.objects.get("Player")
assert player, "Player object not found after import"

# Spawn inside Room01 (world BOX3 maxZ=5): position Z=4.5 puts the
# player bbox [4.5,5.5] overlapping the room, so levcomp assigns it
# to RM0 rather than PERM (which is outside the room render list).
player.location.z = 4.5

# Replace mesh: add UV sphere at origin (radius=0.5, centre Z=0.5 → sits on ground)
old_mesh = player.data
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 0.5))
sphere_tmp = bpy.context.active_object
new_mesh = sphere_tmp.data
new_mesh.name = "SphereMesh"
player.data = new_mesh
bpy.data.objects.remove(sphere_tmp, do_unlink=True)
if old_mesh and old_mesh.users == 0:
    bpy.data.meshes.remove(old_mesh)

# Solid-colour material: yellow, flags=0 (FLAT_SHADED|SOLID_COLOR)
mat = bpy.data.materials.new("MarbleMat")
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 0.0, 1.0)
player.data.materials.clear()
player.data.materials.append(mat)

# Update WF custom properties
player['wf_original_mesh_name'] = 'sphere.iff'
player['wf_original_bbox'] = (-0.5, -0.5, 0.0, 0.5, 0.5, 1.0)

# Marble physics
player['wf_Vertical Elasticity']   = 0.3
player['wf_Horizontal Elasticity'] = 0.7
player['wf_Running Acceleration']  = 15.0

# Always visible (mailbox 1 is permanently true)
player['wf_Visibility Mailbox'] = 1

print(f"[sphere] Player mesh → SphereMesh, mesh_name=sphere.iff, bbox={player['wf_original_bbox']}")

print(f"[sphere] Exporting to {LEV}")
bpy.ops.wf.export_level(filepath=LEV)
print("[sphere] Done")
