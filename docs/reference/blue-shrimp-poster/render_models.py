"""Render the exported shrimp meshes for the A3 poster, using Blender.

blender --background --python-exit-code 1 --python docs/reference/blue-shrimp-poster/render_models.py
"""
from pathlib import Path
import sys
import bpy
import addon_utils
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEVEL = ROOT/'wflevels/aquarium_blue_shrimp'
sys.path.insert(0, str(LEVEL))
from geometry import PARTS, OFFSETS
addon_utils.enable('wf_blender', default_set=False, persistent=False)
from wf_blender.export_level import _load_mesh_iff, _make_blender_material

for variety, prefix in [('blue-jelly', 'jelly_'), ('blue-dream', 'shrimp_')]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 650
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new('Studio')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.20,.25,.27,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .6
    for part, offset in zip(PARTS, OFFSETS):
        name = prefix+part.replace('-', '_')
        vertices, faces, uvs, slots, materials = _load_mesh_iff(str(LEVEL/(name+'.iff')))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        uv = mesh.uv_layers.new(name='UVMap')
        for poly in mesh.polygons:
            poly.material_index = slots[poly.index]
            for loop in poly.loop_indices:
                uv.data[loop].uv = uvs[mesh.loops[loop].vertex_index]
        for i, info in enumerate(materials):
            texture = str(LEVEL/'blue_jelly.tga') if info['tex'] else None
            mat = _make_blender_material(f'{name}-{i}', info, texture)
            mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .65
            mesh.materials.append(mat)
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.location = offset
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-.025))
    floor = bpy.context.object
    mat = bpy.data.materials.new('Neutral checker backdrop')
    mat.use_nodes = True
    checker = mat.node_tree.nodes.new('ShaderNodeTexChecker')
    checker.inputs['Color1'].default_value = (.18,.24,.25,1)
    checker.inputs['Color2'].default_value = (.55,.59,.57,1)
    checker.inputs['Scale'].default_value = 3
    coords = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mat.node_tree.links.new(coords.outputs['Object'],checker.inputs['Vector'])
    mat.node_tree.links.new(checker.outputs['Color'],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
    floor.data.materials.append(mat)
    bpy.ops.object.light_add(type='AREA', location=(1,-3,4))
    bpy.context.object.data.energy = 220
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = 4
    bpy.ops.object.camera_add(location=(1.0,-3.2,1.15))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((.1,0,.23))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 2.3
    scene.camera = camera
    scene.view_settings.view_transform = 'Standard'
    scene.render.filepath = str(HERE/(variety+'-blender.png'))
    bpy.ops.render.render(write_still=True)
