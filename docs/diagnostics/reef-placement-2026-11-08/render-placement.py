"""Before/after renders of reef placement (plan W3): what floated, and where it sits now.

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/diagnostics/reef-placement-2026-11-08/render-placement.py -- OUTDIR {after|before REEF_TREE}

Builds the rock masses, the static coral and life groups and the attached or
ground-dwelling actors with the reef modules of the chosen tree, textured
with that tree's atlas and UVs. 'before' uses the actor positions generate.py
hard-coded before W3; 'after' uses the resolved anchor table. Renders side
elevations (looking along x, so depth shows) and a three-quarter view, with
CPU Cycles and a matte material. Shows placement, not engine lighting.
"""
import importlib
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
argv = sys.argv[sys.argv.index('--') + 1:]
OUT, MODE = Path(argv[0]).resolve(), argv[1]
OUT.mkdir(parents=True, exist_ok=True)
tree = Path(argv[2]).resolve() if MODE == 'before' else ROOT / 'wflevels/aquarium_thai_reef'
sys.path[:0] = [str(tree), str(ROOT / 'wflevels/aquarium_tanks')]
from mesh import Mesh  # noqa: E402
atlas = importlib.import_module('reef.atlas')
uvmap = importlib.import_module('reef.uvmap')
geometry = importlib.import_module('reef.geometry')
life = importlib.import_module('reef.life')
corals = importlib.import_module('reef.corals')
invertebrates = importlib.import_module('reef.invertebrates')
scene_mod = importlib.import_module('reef.scene')

BEFORE_POSITIONS = {   # generate.py at 5030e6cd, before W3
    'SeaFan': (-4.45, -.55, 2.82), 'FeatherStar': (1.75, -.35, 2.8),
    'Nudibranch': (-4.0, -1.65, 1.05), 'FeatherDusters': (-1.96, .15, 2.05),
    'FlowerpotCoral': (-4.15, -.85, 2.42), 'LeatherCoral': (4.0, -.72, 2.76),
    'GiantClam': (1.82, -1.15, .82), 'HermitCrab': (1.295, -1.0, .444),
    'ShrimpOne': (-.7, -.15, 1.885),
}
AFTER_ANCHORS = {'SeaFan': 'sea_fan_left', 'FeatherStar': 'feather_star', 'Nudibranch': 'nudibranch',
                 'FeatherDusters': 'feather_duster', 'FlowerpotCoral': 'flowerpot',
                 'LeatherCoral': 'leather_coral', 'GiantClam': 'giant_clam',
                 'HermitCrab': 'hermit_crab', 'ShrimpOne': 'cleaner_station'}
BUILDERS = {'SeaFan': life._sea_fan, 'FeatherStar': life._feather_star, 'Nudibranch': life._nudibranch,
            'FeatherDusters': life.feather_dusters, 'FlowerpotCoral': corals.flowerpot,
            'LeatherCoral': corals.leather_coral, 'GiantClam': life._clam,
            'HermitCrab': invertebrates.hermit_crab, 'ShrimpOne': invertebrates.banded_shrimp}


def position(name):
    if MODE == 'before':
        return BEFORE_POSITIONS[name]
    return scene_mod.anchor_map()[AFTER_ANCHORS[name]]


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
scene.render.resolution_x, scene.render.resolution_y = 1200, 700
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam

path = OUT / f'atlas-{MODE}.tga'
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

groups = geometry.build_groups(Mesh)
for name, m in groups.items():
    if name != 'reef_shell':
        to_blender(m, mat)
sand = Mesh('sand')
geometry._box(sand, (-6, -3, 0), (6, 3, .72), 'sand')
to_blender(sand, mat)
for name, builder in BUILDERS.items():
    m = Mesh(name)
    builder(m, (0, 0, 0))
    to_blender(m, mat, position(name))

VIEWS = {   # name: (camera location, target, lens)
    'left-side': ((-7.2, -.55, 1.9), (-3.4, -.55, 1.7), 40),
    'right-side': ((7.2, -.55, 1.6), (3.0, -.55, 1.4), 40),
    'three-quarter': ((-6.6, -6.2, 3.6), (-2.6, -.4, 1.5), 38),
}
for view, (location, target, lens) in VIEWS.items():
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.filepath = str(OUT / f'{MODE}-{view}.png')
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath)
