"""Render the same clam view from a selected reef source snapshot.

Run in Blender with `-- <source-parent> <output.png>`; source-parent contains
the `reef` package. The camera, lighting, mesh generation and framing match.
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

source, output = (Path(value) for value in sys.argv[sys.argv.index('--') + 1:])
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(source))
sys.path.insert(0, str(root / 'wflevels/aquarium_tanks'))
from mesh import Mesh
from reef import life, invertebrates

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mesh = Mesh('clam ribs restoration')
invertebrates.banded_shrimp(mesh, (0,0,0))
data = bpy.data.meshes.new('clam ribs restoration')
data.from_pydata(mesh.vertices, [], mesh.faces)
data.update()
obj = bpy.data.objects.new('clam ribs restoration', data)
scene.collection.objects.link(obj)
colors = list(dict.fromkeys(mesh.colors))
palette = {'fish_dark': (.015,.018,.022,1), 'sponge': (.65,.28,.11,1), 'rock': (.3,.27,.22,1), 'sand': (.72,.64,.46,1), 'clam': (.08,.47,.52,1), 'fish_white': (.9,.9,.83,1)}
for name in colors:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = palette.get(name, (.45, .35, .3, 1))
    mat.use_nodes = True
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = mat.diffuse_color
    obj.data.materials.append(mat)
for polygon, color in zip(data.polygons, mesh.colors):
    polygon.material_index = colors.index(color)
center, size = Vector((0, 0, .04)), .45
camera_data = bpy.data.cameras.new('Camera')
camera = bpy.data.objects.new('Camera', camera_data)
scene.collection.objects.link(camera)
camera.location = center + Vector((size*1.1, -size*2.9, size*1.15))
camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = size*1.65
scene.camera = camera
light_data = bpy.data.lights.new('Key', 'AREA')
light_data.energy = 700*size*size
light_data.shape = 'DISK'
light_data.size = size*3
light = bpy.data.objects.new('Key', light_data)
scene.collection.objects.link(light)
light.location = center + Vector((-size, -size*2, size*3))
light.rotation_euler = (center-light.location).to_track_quat('-Z', 'Y').to_euler()
scene.world = bpy.data.worlds.new('World')
scene.world.color = (.12, .12, .12)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 960, 720
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(output)
bpy.ops.render.render(write_still=True)
