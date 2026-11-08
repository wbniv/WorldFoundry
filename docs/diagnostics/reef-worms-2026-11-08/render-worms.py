"""Blender render of the rebuilt Christmas tree worms on their Porites boulder.

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh \
    blender --background --python docs/diagnostics/reef-worms-2026-11-08/render-worms.py -- OUTDIR

Builds the left rock mass, the boulder (reef_hard, which now carries the worm
collars and opercula) and the WormCrowns mesh with the reef generator's own
modules, UV-maps them with the generator's formulas (world-projected tiles for
static parts, explicit cell UVs for the crowns) and textures them with each
style's real reef atlas. Renders, per style, open and retracted (each crown
scaled to 0.02 about its tube mouth, as the DFRM curve scale does), from the
game's wide-camera position zoomed onto the boulder, plus one close 3/4 view.
CPU Cycles with the static bake's sun and a water-blue sky: this shows model,
texture, colour and placement, not the engine's lighting.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'wflevels/aquarium_thai_reef'), str(ROOT / 'wflevels/aquarium_tanks')]
from mesh import Mesh  # noqa: E402
from reef import life, rockscape  # noqa: E402
from reef.atlas import write_atlas  # noqa: E402
from reef.geometry import build_groups  # noqa: E402
from reef.scene import worm_mouths, worm_origin  # noqa: E402

OUT = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
SWATCH = {'rock': 4, 'porites': 1, 'pocillopora': 1, 'pocillopora_tip': 1, 'acropora': 1,
          'sand': 3, 'coralline': 0, 'polyp': 1, 'zoanthid': 5, 'sponge': 2, 'scroll': 0}


def to_blender(mesh, material, offset=(0, 0, 0)):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata([tuple(v[i] + offset[i] for i in range(3)) for v in mesh.vertices], [], mesh.faces)
    data.materials.append(material)
    uv = data.uv_layers.new(name='UVMap')
    explicit = getattr(mesh, 'face_uvs', {})
    for index, (poly, key) in enumerate(zip(data.polygons, mesh.colors)):
        if index in explicit:
            for li, value in zip(poly.loop_indices, explicit[index]):
                uv.data[li].uv = (value[0], 1 - value[1])   # image v runs bottom-up in Blender
            continue
        tile = SWATCH.get(key, 4)
        frequency = 1.1 if tile == 1 else .37
        for li in poly.loop_indices:
            x, y, z = data.vertices[data.loops[li].vertex_index].co
            u = (tile % 4 + .04 + .92 * ((x * frequency + y * .11) % 1)) / 4
            v = (tile // 4 + .04 + .92 * ((z * frequency + y * .11) % 1)) / 4
            uv.data[li].uv = (u, 1 - v)
    data.update()
    obj = bpy.data.objects.new(mesh.name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def material_for(style):
    path = OUT / f'atlas-{style}.tga'
    write_atlas(path, style=style)
    mat = bpy.data.materials.new(f'reef-{style}')
    mat.use_nodes = True
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = bpy.data.images.load(str(path))
    node.interpolation = 'Closest'
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    return mat


def crowns(retract):
    mesh = Mesh('wormcrowns')
    ranges = []
    origin = worm_origin()
    life.worm_crowns(mesh, origin, ranges)
    if retract:
        for r in ranges:
            m = r['mouth']
            for i in range(r['start'], r['end']):
                v = mesh.vertices[i]
                mesh.vertices[i] = tuple(m[k] + (v[k] - m[k]) * .02 for k in range(3))
    return mesh, origin


def render(name, location, target, lens):
    scene = bpy.context.scene
    cam = scene.camera
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.filepath = str(OUT / f'{name}.png')
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.seed = 20261108
scene.cycles.use_denoising = False
world = bpy.data.worlds.new('water')
world.use_nodes = True
background = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
background.inputs['Color'].default_value = (0.05, 0.22, 0.38, 1)
background.inputs['Strength'].default_value = .9
scene.world = world
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (.32, -.38, -.25)      # the static bake's sun (reef/bake.py)
scene.collection.objects.link(sun)
scene.render.resolution_x, scene.render.resolution_y = 1200, 750
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam

groups = build_groups(Mesh)
target = worm_origin()
for style in ('realistic', 'anime'):
    mat = material_for(style)
    static = [to_blender(groups['reef_left'], mat), to_blender(groups['reef_hard'], mat)]
    for retract in (False, True):
        mesh, origin = crowns(retract)
        obj = to_blender(mesh, mat, origin)
        state = 'retracted' if retract else 'open'
        # The game's wide camera sits at (0, -7.5, 2.75); same direction, zoomed in.
        render(f'{style}-{state}', (0, -7.5, 2.75), target, 150)
        if not retract:
            render(f'{style}-close', (target[0] + .9, target[1] - 1.6, target[2] + .55), target, 60)
        bpy.data.objects.remove(obj)
    for obj in static:
        bpy.data.objects.remove(obj)
