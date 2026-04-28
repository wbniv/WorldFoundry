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

# Add UV unwrap so the exporter has UV data
bpy.context.view_layer.objects.active = player
bpy.ops.object.select_all(action='DESELECT')
player.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
bpy.ops.object.mode_set(mode='OBJECT')

# Assign a basic textured material (reuse the ramp texture)
mat = bpy.data.materials.new("MarbleMat")
mat.use_nodes = True
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
tga_path = os.path.join(SCRIPT_DIR, 'G_SnowyGrass1.tga')
tex_node.image = bpy.data.images.load(tga_path, check_existing=True)
mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
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
