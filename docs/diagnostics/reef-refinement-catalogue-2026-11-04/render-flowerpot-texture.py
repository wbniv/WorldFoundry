"""Render the same flowerpot-coral view from a selected reef source snapshot.

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
from reef import corals, atlas

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mesh = Mesh('flowerpot restoration')
corals.flowerpot(mesh, (0, 0, 0))
data = bpy.data.meshes.new('flowerpot restoration')
data.from_pydata(mesh.vertices, [], mesh.faces)
data.update()
obj = bpy.data.objects.new('flowerpot restoration', data)
scene.collection.objects.link(obj)
atlas_file = Path('/tmp') / (output.stem + '.atlas.tga')
atlas.write_atlas(atlas_file, style='realistic')
mat = bpy.data.materials.new('reef atlas')
mat.use_nodes = True
texture = mat.node_tree.nodes.new('ShaderNodeTexImage')
texture.image = bpy.data.images.load(str(atlas_file))
mat.node_tree.links.new(texture.outputs['Color'], mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
data.materials.append(mat)
data.update()
uv = data.uv_layers.new(name='UVMap')
bounds = [(min(v.co[axis] for v in data.vertices), max(v.co[axis] for v in data.vertices)) for axis in range(3)]
for poly in data.polygons:
    axis = max(range(3), key=lambda i: abs(poly.normal[i]))
    axes = ((1, 2), (0, 2), (0, 1))[axis]
    for li in poly.loop_indices:
        co = data.vertices[data.loops[li].vertex_index].co
        if output.stem.endswith('before'):
            values = ((co.x*.37 + co.y*.11) % 1, (co.z*.37 + co.y*.11) % 1)
        else:
            values = tuple((co[i]-bounds[i][0])/(bounds[i][1]-bounds[i][0]) if bounds[i][1]>bounds[i][0] else .5 for i in axes)
        u=(1+.04+.92*values[0])/4
        v=(1+.04+.92*values[1])/2
        uv.data[li].uv=(u, 1-v)
center, size = Vector((0, 0, .20)), 1.05
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
