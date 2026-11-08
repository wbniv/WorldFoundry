"""Close Blender renders of the reef fish pair (humbug -> Dascyllus reticulatus, D10).

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/diagnostics/reef-humbug-swap-2026-11-09/render-pair.py -- OUTDIR LABEL [REEF_TREE]

LABEL    'before' or 'after'; names the output files.
REEF_TREE  a directory holding a reef/ package (default: the current
           wflevels/aquarium_thai_reef). For 'before', extract the reef package
           at the earlier commit, e.g.
           git archive <rev> wflevels/aquarium_thai_reef/reef | tar -x -C build-docker/reef-humbug-before
Renders the two-fish pair as generate.py places it (second fish offset by
(.5, .1, -.2)), with each style's real atlas and the exported UVs (reef/uvmap.py),
matte, CPU Cycles, the static bake's sun. Same approach as
docs/diagnostics/reef-skins-2026-11-08/render-skins.py. Shows texture and colour,
not engine light. Writes LABEL-{realistic,anime}-{side,three-quarter}.png.
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
reef_atlas = importlib.import_module('reef.atlas')
fishes = importlib.import_module('reef.fishes')
uvmap = importlib.import_module('reef.uvmap')


def to_blender(mesh, material, offset):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata([tuple(v[i] + offset[i] for i in range(3)) for v in mesh.vertices], [], mesh.faces)
    data.materials.append(material)
    uv = data.uv_layers.new(name='UVMap')
    for poly, face_uv in zip(data.polygons, uvmap.face_uvs(mesh)):
        for li, (u, v) in zip(poly.loop_indices, face_uv):
            uv.data[li].uv = (u, 1 - v)        # Blender image v runs bottom-up
    data.update()
    obj = bpy.data.objects.new(mesh.name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def material_for(style):
    path = OUT / f'atlas-{LABEL}-{style}.tga'
    reef_atlas.write_atlas(path, style=style)
    mat = bpy.data.materials.new(f'reef-{style}')
    mat.use_nodes = True
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = bpy.data.images.load(str(path))
    node.interpolation = 'Closest'
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 1.0
    for name in ('Specular IOR Level', 'Specular'):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    return mat


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.seed = 20261109
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
scene.render.resolution_x, scene.render.resolution_y = 1000, 600
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam

target = Vector((.25, .05, -.1))
views = {'side': Vector((0, -1.55, .25)), 'three-quarter': Vector((.9, -1.2, .45))}
for style in ('realistic', 'anime'):
    mat = material_for(style)
    objs = [to_blender(fishes.humbug(Mesh), mat, (0, 0, 0)),
            to_blender(fishes.humbug(Mesh), mat, (.5, .1, -.2))]
    for view, d in views.items():
        cam.location = target + d
        cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = 50
        scene.render.filepath = str(OUT / f'{LABEL}-{style}-{view}.png')
        bpy.ops.render.render(write_still=True)
        print('wrote', scene.render.filepath)
    for obj in objs:
        bpy.data.objects.remove(obj)
