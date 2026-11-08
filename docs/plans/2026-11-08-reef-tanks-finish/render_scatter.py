"""Blender renders of the W3b scatter prototype: several seeds, plus W3's fixed layout.

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/plans/2026-11-08-reef-tanks-finish/render_scatter.py -- OUTDIR fixed 11 2026 713

'fixed' renders the shipped W3 layout; each number renders scatter_prototype
with that seed. Front view (the game's wide camera direction) and a
three-quarter view, CPU Cycles, matte. Design mock-up, not engine captures.
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'wflevels/aquarium_thai_reef'), str(ROOT / 'wflevels/aquarium_tanks'), str(HERE)]
argv = sys.argv[sys.argv.index('--') + 1:]
OUT = Path(argv[0]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

from mesh import Mesh  # noqa: E402
from reef import atlas, corals, geometry, invertebrates, life, rockscape, sponges, uvmap  # noqa: E402
from reef.scene import anchor_map, worm_origin  # noqa: E402
import scatter_prototype  # noqa: E402


def to_blender(mesh, material, offset=(0, 0, 0)):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata([tuple(v[i] + offset[i] for i in range(3)) for v in mesh.vertices], [], mesh.faces)
    data.materials.append(material)
    uv = data.uv_layers.new(name='UVMap')
    for poly, face_uv in zip(data.polygons, uvmap.face_uvs(mesh)):
        for li, (u, v) in zip(poly.loop_indices, face_uv):
            uv.data[li].uv = (u, 1 - v)
    data.update()
    obj = bpy.data.objects.new(mesh.name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 20
scene.cycles.seed = 20261108
scene.cycles.use_denoising = False
world = bpy.data.worlds.new('water')
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Color'].default_value = (0.05, 0.22, 0.38, 1)
bg.inputs['Strength'].default_value = 1.0
scene.world = world
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (.32, -.38, -.25)
scene.collection.objects.link(sun)
scene.render.resolution_x, scene.render.resolution_y = 1440, 620
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam

path = OUT / 'atlas.tga'
atlas.write_atlas(path, style='realistic')
mat = bpy.data.materials.new('reef')
mat.use_nodes = True
tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(str(path))
tex.interpolation = 'Closest'
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 1.0
for name in ('Specular IOR Level', 'Specular'):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = 0.0

# Everything except the attached colonies is the shipped scene.
base = []
for group in ('left', 'right', 'arch'):
    m = Mesh('reef_' + group)
    rockscape.populate(m, group)
    base.append(m)
for builder in (corals.hard_corals, corals.soft_corals, sponges.populate):
    m = Mesh(builder.__name__)
    builder(m)
    base.append(m)
sand = Mesh('sand')
geometry._box(sand, (-6, -3, 0), (6, 3, .72), 'sand')
base.append(sand)
for m in base:
    to_blender(m, mat)
a = anchor_map()
for builder, anchor in ((life._sea_fan, 'sea_fan_left'), (life._feather_star, 'feather_star'),
                        (life.feather_dusters, 'feather_duster'), (corals.flowerpot, 'flowerpot'),
                        (corals.leather_coral, 'leather_coral'), (life._clam, 'giant_clam'),
                        (invertebrates.hermit_crab, 'hermit_crab'), (life._nudibranch, 'nudibranch')):
    m = Mesh(builder.__name__)
    builder(m, (0, 0, 0))
    to_blender(m, mat, a[anchor])
crowns = Mesh('crowns')
life.worm_crowns(crowns, worm_origin())
to_blender(crowns, mat, worm_origin())

VIEWS = {'front': ((0, -9.2, 3.0), (0, 0, 1.75), 32), 'three-quarter': ((-6.6, -6.2, 3.6), (-2.2, -.3, 1.6), 34)}
for variant in argv[1:]:
    m = Mesh('life')
    if variant == 'fixed':
        life.populate(m)
        counts = 'W3 fixed layout'
    else:
        counts = scatter_prototype.populate(m, int(variant))
    obj = to_blender(m, mat)
    print('variant', variant, counts)
    for view, (location, target, lens) in VIEWS.items():
        cam.location = location
        cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        scene.render.filepath = str(OUT / f'scatter-{variant}-{view}.png')
        bpy.ops.render.render(write_still=True)
        print('wrote', scene.render.filepath)
    bpy.data.objects.remove(obj)
