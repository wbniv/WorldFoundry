"""Mock-up renders for W5: seeded rock layouts with a user-chosen rock count.

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/plans/2026-11-08-reef-tanks-finish/render_rock_layouts.py -- OUTDIR

Imitates what the proposed Forth layout would do with a baked module kit:
for (count, seed) it picks modules, spaces them along the sand with seeded
gaps and jitter, and mirrors some. The modules here are clusters of the
production rock blobs (reef.rockscape.rock_blob); the real kit would carry
baked light, colliders and attachment sites. Rocks and sand only.
"""
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'wflevels/aquarium_thai_reef'), str(ROOT / 'wflevels/aquarium_tanks')]
argv = sys.argv[sys.argv.index('--') + 1:]
OUT = Path(argv[0]).resolve()
OUT.mkdir(parents=True, exist_ok=True)

from mesh import Mesh  # noqa: E402
from reef import atlas, geometry, uvmap  # noqa: E402
from reef.rockscape import rock_blob  # noqa: E402

# A small kit: each module is a list of (dx, dz, rx, ry, rz) blobs about its foot.
KIT = {
    'boulder-mass': [(0, .9, 1.2, .9, .95), (-.6, 1.5, .7, .7, .6), (.5, 1.6, .8, .7, .55)],
    'tall-mass': [(0, 1.1, .8, .8, 1.2), (.3, 2.2, .55, .6, .5)],
    'low-ledge': [(0, .75, 1.4, .8, .5), (.7, 1.0, .6, .6, .45)],
    'twin-pillars': [(-.45, 1.2, .5, .6, 1.1), (.45, 1.0, .5, .6, .9)],
    'arch': None,      # the existing arch, a hero module (cave + cleaner station)
}


def build_module(mesh, kind, x, mirror, rng):
    if kind == 'arch':
        from reef.scene import from_mockup
        pts = [from_mockup(px, py, .15) for px, py in
               ((625, 665), (680, 520), (760, 430), (855, 430), (945, 520), (1000, 660))]
        cx = sum(p[0] for p in pts) / len(pts)
        mesh.swept_tube([(p[0] - cx + x, p[1], p[2]) for p in pts], .36, 'rock', 10)
        for leg in (pts[0], pts[-1]):
            rock_blob(mesh, (leg[0] - cx + x, .5, .9), (.6, .9, .75), rng)
        return
    for dx, dz, rx, ry, rz in KIT[kind]:
        s = rng.uniform(.85, 1.15)
        rock_blob(mesh, (x + (-dx if mirror else dx), .5 + rng.uniform(-.15, .15), dz * s),
                  (rx * s, ry * s, rz * s), rng)


def layout(count, seed):
    """Seeded module choice and spacing along the 10.4-unit sand front."""
    rng = random.Random(seed)
    kinds = ['arch'] + rng.sample([k for k in KIT if k != 'arch'], k=min(count - 1, 4))
    while len(kinds) < count:
        kinds.append(rng.choice([k for k in KIT if k != 'arch']))
    rng.shuffle(kinds)
    width = 10.4 / count
    return [(k, -5.2 + width * (i + .5) + rng.uniform(-.2, .2) * width, rng.random() < .5)
            for i, k in enumerate(kinds)], rng


def to_blender(mesh, material):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata(mesh.vertices, [], mesh.faces)
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
scene.cycles.samples = 16
scene.cycles.seed = 20261108
scene.cycles.use_denoising = False
world = bpy.data.worlds.new('water')
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Color'].default_value = (0.05, 0.22, 0.38, 1)
scene.world = world
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (.32, -.38, -.25)
scene.collection.objects.link(sun)
scene.render.resolution_x, scene.render.resolution_y = 1440, 560
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, -9.2, 3.0)
cam.rotation_euler = (Vector((0, 0, 1.6)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 32
path = OUT / 'atlas.tga'
atlas.write_atlas(path, style='realistic')
mat = bpy.data.materials.new('reef')
mat.use_nodes = True
tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(str(path))
bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 1.0
for name in ('Specular IOR Level', 'Specular'):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = 0.0
sand = Mesh('sand')
geometry._box(sand, (-6, -3, 0), (6, 3, .72), 'sand')
to_blender(sand, mat)

for count, seed in ((2, 5), (3, 11), (3, 2026), (5, 713)):
    modules, rng = layout(count, seed)
    m = Mesh(f'rocks-{count}-{seed}')
    for kind, x, mirror in modules:
        build_module(m, kind, x, mirror, rng)
    obj = to_blender(m, mat)
    scene.render.filepath = str(OUT / f'rocks-{count}-seed{seed}.png')
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath, [k for k, _, _ in modules])
    bpy.data.objects.remove(obj)
