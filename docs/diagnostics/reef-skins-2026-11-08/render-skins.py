"""Before/after Blender renders of the Thai reef creature skins (plan W2).

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/diagnostics/reef-skins-2026-11-08/render-skins.py -- OUTDIR {after|before REEF_TREE}

after   builds the creatures with the current reef modules and reef/uvmap.py.
before  imports the reef package from REEF_TREE (a copy of reef/*.py at an
        older commit) and applies the UV rule generate.py used then: flat
        texels for fish_dark/fish_white, otherwise the world-projected tile
        (0.37 cycles/unit, 1.1 for the polyp tile).
Renders two line-ups per style, mobile animals and sessile life, with CPU
Cycles and the static bake's sun. Shows texture and colour, not engine light.
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
reef_atlas = importlib.import_module('reef.atlas')
invertebrates = importlib.import_module('reef.invertebrates')
life = importlib.import_module('reef.life')
fishes = importlib.import_module('reef.fishes')

OLD_SWATCH = {'rock': 4, 'sand': 3, 'coralline': 0, 'polyp': 1, 'zoanthid': 5, 'sponge': 2,
              'clam': 6, 'fish': 7}


def old_uvs(mesh):
    """The generator's UV rule before W2 (16-cell atlas, world projection)."""
    out = []
    for face, key in zip(mesh.faces, mesh.colors):
        pts = [mesh.vertices[i] for i in face]
        if key in ('fish_dark', 'fish_white'):
            x, y = reef_atlas.FISH_DARK if key == 'fish_dark' else reef_atlas.FISH_WHITE
            out.append([(x / 1024, y / 1024)] * len(pts))
            continue
        tile = OLD_SWATCH[key]
        f = 1.1 if tile == 1 else .37
        out.append([((tile % 4 + .04 + .92 * ((x * f + y * .11) % 1)) / 4,
                     (tile // 4 + .04 + .92 * ((z * f + y * .11) % 1)) / 4) for x, y, z in pts])
    return out


def face_uvs(mesh):
    if MODE == 'before':
        return old_uvs(mesh)
    return importlib.import_module('reef.uvmap').face_uvs(mesh)


def to_blender(mesh, material, offset):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata([tuple(v[i] + offset[i] for i in range(3)) for v in mesh.vertices], [], mesh.faces)
    data.materials.append(material)
    uv = data.uv_layers.new(name='UVMap')
    for poly, face_uv in zip(data.polygons, face_uvs(mesh)):
        for li, (u, v) in zip(poly.loop_indices, face_uv):
            uv.data[li].uv = (u, 1 - v)        # Blender image v runs bottom-up
    data.update()
    obj = bpy.data.objects.new(mesh.name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def material_for(style):
    path = OUT / f'atlas-{MODE}-{style}.tga'
    reef_atlas.write_atlas(path, style=style)
    mat = bpy.data.materials.new(f'reef-{style}')
    mat.use_nodes = True
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = bpy.data.images.load(str(path))
    node.interpolation = 'Closest'
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    # Matte, like the engine's diffuse-only lighting: Cycles' default specular
    # turns dark surfaces grey-white at grazing angles.
    bsdf.inputs['Roughness'].default_value = 1.0
    for name in ('Specular IOR Level', 'Specular'):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    return mat


def built(builder):
    m = Mesh(builder.__name__)
    builder(m, (0, 0, 0))
    return m


def humbug(_mesh=None, _c=None):
    return fishes.humbug(Mesh)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
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
scene.render.resolution_x, scene.render.resolution_y = 1200, 500
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam

animals = [(lambda: built(invertebrates.guard_crab), (0, 0, 0)),
           (lambda: built(invertebrates.banded_shrimp), (.75, 0, 0)),
           (lambda: built(invertebrates.hermit_crab), (1.55, 0, 0)),
           (lambda: built(life._nudibranch), (2.35, 0, 0)),
           (lambda: fishes.humbug(Mesh), (3.25, 0, .15))]
sessile = [(lambda: built(life.feather_dusters), (0, 0, .2)),
           (lambda: built(life._zoanthids), (1.35, .1, 0)),
           (lambda: built(life._sea_fan), (2.55, .3, -.2)),
           (lambda: built(life._feather_star), (3.95, .3, .05))]

for style in ('realistic', 'anime'):
    mat = material_for(style)
    nudibranch = [(lambda: built(life._nudibranch), (0, 0, 0))]
    for name, row, target, distance, lens in (('animals', animals, (1.55, 0, .08), 4.6, 42),
                                              ('sessile', sessile, (2.0, 0, .35), 5.0, 45),
                                              ('nudibranch', nudibranch, (0, 0, .03), 1.5, 50),
                                              ('nudibranch-game', nudibranch, (0, 0, .03), 0, 50)):
        objs = [to_blender(make(), mat, offset) for make, offset in row]
        if name == 'nudibranch-game':
            # Same direction as the game's wide camera, (0, -7.5, 2.75), sees the
            # slug at (-4.0, -1.65, 1.05): a grazing ~16 degree view.
            d = Vector((4.0, -5.85, 1.7)).normalized() * 1.6
            cam.location = (target[0] + d.x, target[1] + d.y, target[2] + d.z)
        else:
            cam.location = (target[0], target[1] - distance, target[2] + distance * .28)
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        scene.render.filepath = str(OUT / f'{MODE}-{style}-{name}.png')
        bpy.ops.render.render(write_still=True)
        print('wrote', scene.render.filepath)
        for obj in objs:
            bpy.data.objects.remove(obj)
