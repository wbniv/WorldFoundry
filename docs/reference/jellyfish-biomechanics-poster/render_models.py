"""Render the actual exported bell and arms, including their OPAC materials."""
from pathlib import Path
import bpy
import addon_utils
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
addon_utils.enable('wf_blender', default_set=False, persistent=False)
from wf_blender.export_level import _load_mesh_iff, _make_blender_material

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.render.resolution_x = 1200
scene.render.resolution_y = 760
scene.render.resolution_percentage = 100
scene.world = bpy.data.worlds.new('Studio')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.23,.32,.35,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .7
for name in ['bell', 'arms']:
    vertices, faces, uvs, slots, materials = _load_mesh_iff(str(ROOT/'wflevels/aquarium_jellyfish'/(name+'.iff')))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for poly in mesh.polygons:
        poly.material_index = slots[poly.index]
    for i, info in enumerate(materials):
        mesh.materials.append(_make_blender_material(f'{name}-{i}', info, None))
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-1.2))
floor = bpy.context.object
mat = bpy.data.materials.new('Checker backdrop shows transmission')
mat.use_nodes = True
checker = mat.node_tree.nodes.new('ShaderNodeTexChecker')
checker.inputs['Color1'].default_value = (.15,.25,.28,1)
checker.inputs['Color2'].default_value = (.46,.60,.62,1)
checker.inputs['Scale'].default_value = 2
coords = mat.node_tree.nodes.new('ShaderNodeTexCoord')
mat.node_tree.links.new(coords.outputs['Object'],checker.inputs['Vector'])
mat.node_tree.links.new(checker.outputs['Color'],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
floor.data.materials.append(mat)
bpy.ops.object.light_add(type='AREA', location=(1,-3,4))
bpy.context.object.data.energy = 300
bpy.context.object.data.size = 4
bpy.ops.object.camera_add(location=(1,-2.4,1.2))
camera = bpy.context.object
camera.rotation_euler = (Vector((0,0,-.26))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.1
scene.camera = camera
scene.view_settings.view_transform = 'Standard'
scene.render.filepath = str(HERE/'jellyfish-blender.png')
bpy.ops.render.render(write_still=True)
