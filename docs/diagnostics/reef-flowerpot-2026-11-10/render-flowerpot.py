"""Prototype render for the flowerpot-coral fix: today's coral beside the proposed one.

Usage (Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/diagnostics/reef-flowerpot-2026-11-10/render-flowerpot.py -- OUTDIR

Today: a purple ellipsoid body (32x16) with the zoanthid flower tile projected flat
over it, and 20 long polyps. Proposed (Goniopora): a cheaper body (16x8) in the
corallite tile, almost hidden under ~100 polyps covering the dome down to its equator,
each a column with a small crown and a ring of five tentacles. CPU Cycles,
matte, the production atlas. Design mock-up, not an engine capture.
"""
import math
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
from reef import atlas, corals, uvmap  # noqa: E402

RX, RY, RZ = .48, .34, .28          # today's body radii
# Small-object skins (the zoanthid approach): existing atlas tiles at a dense
# per-key frequency instead of the rock-scale world projection.
uvmap.SKINS['fp_body'] = (1, (0, 0, 256, 256), 5.0, 'project')    # corallite tile
uvmap.SKINS['fp_polyp'] = (0, (0, 0, 256, 256), 7.0, 'project')   # mottled column
uvmap.SKINS['fp_crown'] = (5, (0, 0, 256, 256), 9.0, 'project')   # flower-head tile
POLYPS = 100


def proposed(mesh, center):
    """Goniopora: a dome covered by short polyps; the body mostly hidden."""
    x, y, z = center
    mesh.ellipsoid((x, y, z), (RX, RY, RZ), 'fp_body', 16, 8)
    golden = math.pi * (3 - math.sqrt(5))
    placed = 0
    i = 0
    while placed < POLYPS and i < 4 * POLYPS:
        # Fibonacci points over the upper part of the ellipsoid (polar angle < ~70 deg).
        k = i + .5
        cz = 1 - k / (1.05 * POLYPS)
        i += 1
        if cz < .02:
            break
        r = math.sqrt(max(0.0, 1 - cz * cz))
        a = golden * i
        nx, ny, nz = r * math.cos(a), r * math.sin(a), cz
        base = (x + RX * nx, y + RY * ny, z + RZ * nz)
        # Outward normal of the ellipsoid at that point.
        gx, gy, gz = nx / RX, ny / RY, nz / RZ
        gl = math.sqrt(gx * gx + gy * gy + gz * gz)
        gx, gy, gz = gx / gl, gy / gl, gz / gl
        h = .13 + .05 * math.sin(i * 2.7)
        tip = (base[0] + gx * h, base[1] + gy * h, base[2] + gz * h)
        mesh.swept_tube([base, tip], .022, 'fp_polyp', 5)
        mesh.ellipsoid(tip, (.026, .026, .018), 'fp_crown', 5, 2)
        for petal in range(5):
            t = math.tau * petal / 5 + i
            # Two perpendicular vectors to the normal for the tentacle ring.
            ux, uy, uz = (-gy, gx, 0) if abs(gz) < .9 else (1, 0, 0)
            ul = math.sqrt(ux * ux + uy * uy + uz * uz)
            ux, uy, uz = ux / ul, uy / ul, uz / ul
            vx, vy, vz = gy * uz - gz * uy, gz * ux - gx * uz, gx * uy - gy * ux
            d = (math.cos(t) * ux + math.sin(t) * vx, math.cos(t) * uy + math.sin(t) * vy,
                 math.cos(t) * uz + math.sin(t) * vz)
            end = tuple(tip[j] + .05 * d[j] + .012 * (gx, gy, gz)[j] for j in range(3))
            mesh.swept_tube([tip, end], .008, 'fp_crown', 3)
        placed += 1
    return placed


def to_blender(mesh, material, offset):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata([tuple(v[k] + offset[k] for k in range(3)) for v in mesh.vertices], [], mesh.faces)
    data.materials.append(material)
    uv = data.uv_layers.new(name='UVMap')
    for poly, face_uv in zip(data.polygons, uvmap.face_uvs(mesh)):
        for li, (u, v) in zip(poly.loop_indices, face_uv):
            uv.data[li].uv = (u, 1 - v)
    data.update()
    obj = bpy.data.objects.new(mesh.name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def tris(mesh):
    return sum(len(f) - 2 for f in mesh.faces)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.seed = 20261110
scene.cycles.use_denoising = False
world = bpy.data.worlds.new('water')
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Color'].default_value = (0.05, 0.22, 0.38, 1)
scene.world = world
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (.5, -.3, -.4)
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

today = Mesh('flowerpot_today')
corals.flowerpot(today, (0, 0, 0))
new = Mesh('flowerpot_proposed')
n = proposed(new, (0, 0, 0))
to_blender(today, mat, (-.75, 0, 0))
to_blender(new, mat, (.75, 0, 0))
print(f'TRIS today {tris(today)} proposed {tris(new)} polyps {n}')

for view, loc in (('front', (0, -3.1, .55)), ('above', (0, -2.2, 1.9))):
    cam.location = loc
    cam.rotation_euler = (Vector((0, 0, .25)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 40
    scene.render.filepath = str(OUT / f'flowerpot-{view}.png')
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath)
