"""Before/after Blender renders of the Goniopora flowerpot (option 1, 2026-11-10), in its scene.

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/diagnostics/reef-flowerpot-2026-11-10/render-flowerpot-scene.py -- OUTDIR LABEL [REEF_TREE]

LABEL names the output files ('before' or 'after'). REEF_TREE is a directory holding a
reef/ package (default: the current wflevels/aquarium_thai_reef); for 'before', extract
the earlier commit, e.g. git archive <rev> wflevels/aquarium_thai_reef/reef | tar -x -C
build-docker/reef-tiles-before, and pass build-docker/reef-tiles-before/wflevels/aquarium_thai_reef.
Builds the Fixed layout's rock masses, static coral and life groups, the sand bed and the
attached actors (flowerpot, leather coral, clam, sea fan, feather star, dusters) with that
tree's atlas and UVs, in both styles, and renders a wide view plus close-ups of the left
rock and a close view of the flowerpot. CPU Cycles, matte, the static
bake's sun; no anime outline hulls. Shows texture, not engine lighting.
"""
import importlib
import sys
from pathlib import Path

import bpy
from mathutils import Vector

if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__)
    sys.exit(0)
ROOT = Path(__file__).resolve().parents[3]
argv = sys.argv[sys.argv.index('--') + 1:]
OUT, LABEL = Path(argv[0]).resolve(), argv[1]
TREE = Path(argv[2]).resolve() if len(argv) > 2 else ROOT / 'wflevels/aquarium_thai_reef'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(TREE), str(ROOT / 'wflevels/aquarium_tanks')]
from mesh import Mesh  # noqa: E402
atlas = importlib.import_module('reef.atlas')
uvmap = importlib.import_module('reef.uvmap')
geometry = importlib.import_module('reef.geometry')
life = importlib.import_module('reef.life')
corals = importlib.import_module('reef.corals')
scene_mod = importlib.import_module('reef.scene')

ACTORS = {'SeaFan': (life._sea_fan, 'sea_fan_left'), 'FeatherStar': (life._feather_star, 'feather_star'),
          'FeatherDusters': (life.feather_dusters, 'feather_duster'),
          'FlowerpotCoral': (corals.flowerpot, 'flowerpot'), 'LeatherCoral': (corals.leather_coral, 'leather_coral'),
          'GiantClam': (life._clam, 'giant_clam')}


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


def material_for(style):
    path = OUT / f'atlas-{LABEL}-{style}.tga'
    atlas.write_atlas(path, style=style)
    mat = bpy.data.materials.new(f'reef-{style}')
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
    return mat


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 20
scene.cycles.seed = 20261110
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
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
anchors = scene_mod.anchor_map()
VIEWS = {   # name: (camera location, target, lens); the wide view is the game's wide camera
    'wide': ((0, -7.5, 2.75), (0, 0, 1.9), 30),
    'left-rock': ((-3.2, -3.4, 2.6), (-3.7, -.4, 2.0), 40),
    'flowerpot': ((-3.75, -1.85, 2.75), (-4.15, -.39, 2.3), 50),
}
for style in ('realistic', 'anime'):
    mat = material_for(style)
    objs = []
    for name, m in geometry.build_groups(Mesh).items():
        if name != 'reef_shell':
            objs.append(to_blender(m, mat))
    sand = Mesh('sand')
    geometry._box(sand, (-6, -3, 0), (6, 3, .72), 'sand')
    objs.append(to_blender(sand, mat))
    for name, (builder, anchor) in ACTORS.items():
        m = Mesh(name)
        builder(m, (0, 0, 0))
        objs.append(to_blender(m, mat, anchors[anchor]))
    for view, (location, target, lens) in VIEWS.items():
        cam.location = location
        cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        scene.render.filepath = str(OUT / f'{LABEL}-{style}-{view}.png')
        bpy.ops.render.render(write_still=True)
        print('wrote', scene.render.filepath)
    for obj in objs:
        bpy.data.objects.remove(obj)
