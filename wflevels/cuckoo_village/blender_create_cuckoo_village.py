#!/usr/bin/env python3
"""Build the Cuckoo Village level, Classic mode (plan docs/plans/2026-11-21-cuckoo-village.md).

The art is the layout prototype's, unchanged: this script runs wflevels/cuckoo_village_layout/generate.py up to its
review-render section (hillside terrain, lanes, cottages, the carved glockenspiel tower with four pivoted figures and
the bird), so a change to that art flows straight into this level. It then checks that the tower is where
timeline.py assumes, wires the actors, poses everything from timeline.py at the reference time, writes the director
script and exports. Run through build.sh, in the Blender container.

Writes cuckoo_village.lev and actor-map.json.
"""
import json
import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LAYOUT = ROOT / 'wflevels/cuckoo_village_layout'
sys.path.insert(0, str(HERE))
import forth                 # noqa: E402
import timeline as tl        # noqa: E402
import candles as cd         # noqa: E402
sys.path.insert(0, str(ROOT / 'wflevels/cuckoo_village_assets'))
import flowers as fw         # noqa: E402

TAG = '[cuckoo-village]'
REFERENCE = 10 * 3600 + 8 * 60 + 22.0       # the pose the level starts from: 10:08
GLOW_CELL0, BIRD_CELL = 200, 213

source = (LAYOUT / 'generate.py').read_text()
cut = source.index('scene=bpy.context.scene')       # everything after this is the layout's review render and export
scope = {'__file__': str(LAYOUT / 'generate.py'), '__name__': 'cuckoo_village_layout'}
exec(compile(source[:cut], str(LAYOUT / 'generate.py'), 'exec'), scope)

# The packer finds textures beside the level: bring in the layout's two (git-ignored copies, regenerated every build).
import shutil
for texture in ('village_atlas.tga', 'tower-carved-wood.tga'):
    shutil.copyfile(LAYOUT / texture, HERE / texture)

objs = bpy.data.objects

# The prototype's hand meshes are bars offset sideways from their object origin (the hour bar sits +0.11 right of it,
# the minute bar -0.14 left), so rotating the object swings each hand around a point that is not the dial centre and
# the face reads wrong at almost every time (Will, 2026-11-21: "hands on village clock not correct"). Recentre each
# bar on its pivot; the tail (below the pivot) and the length are kept. Directions were already right: 3:00 has the
# minute hand up and the hour hand right.
for hand_name in ('hour_hand', 'minute_hand'):
    hand = objs[hand_name]
    hand.data = hand.data.copy()
    xs = [v.co.x for v in hand.data.vertices]
    centre = (min(xs) + max(xs)) / 2
    for v in hand.data.vertices:
        v.co.x -= centre
    hand.data.update()
    xs = [v.co.x for v in hand.data.vertices]
    assert abs(min(xs) + max(xs)) < 1e-6 and max(xs) - min(xs) < 0.1, f'{hand_name} is not centred on its pivot'

assert abs(scope['tower_z'] - tl.TZ) < 1e-3, f"tower height {scope['tower_z']} differs from timeline TZ {tl.TZ}"


def near(a, b, what, tol=1e-3):
    assert all(abs(x - y) <= tol for x, y in zip(a, b)), f'{what}: scene has {tuple(round(v, 4) for v in a)}, timeline assumes {tuple(round(v, 4) for v in b)}'


for i, name in enumerate(tl.FIG_NAMES):
    near(objs[name].location, (tl.FIG_X[i], tl.FIG_HOME_Y, tl.FIG_Z0), name)
near(objs[tl.BIRD_NAME].location, tl.BIRD_REST, tl.BIRD_NAME)
near(objs['hour_hand'].location, tl.DIAL, 'hour_hand')
assert [n for n in (f'cottage_light_{i + 1:02}' for i in range(tl.HOUSES)) if n not in objs] == [], 'cottage light actors changed'

# Christmas candles (docs/plans/2026-11-21-cuckoo-village.md): all the sticks in one mesh, and each tree's flames in their own, so
# every tree glows on its own stagger. Static meshes (never posed): the director only switches their visibility mailboxes.
assert [n for n in (f'pine_{i + 1:02}' for i in range(tl.TREES)) if n not in objs] == [], 'the pine trees changed'
mesh_actor = scope['mesh_actor']          # the layout's helper: an anchored platform mesh actor from vertices, faces and an atlas tile
stick_parts = []
for i in range(tl.TREES):
    tree = objs[f'pine_{i + 1:02}']
    sticks, flames = cd.tree_candles(i, tuple(tree.location), tree.rotation_euler.z, tree.scale.x)
    stick_parts += sticks
    flame_verts, flame_faces = cd.merge(flames)
    mesh_actor(f'candle_flames_{i + 1:02}', flame_verts, flame_faces, cd.FLAME_TILE)['wf_Visibility Mailbox'] = tl.FLAME_CELL0 + i
stick_verts, stick_faces = cd.merge(stick_parts)
mesh_actor('candle_sticks', stick_verts, stick_faces, cd.STICK_TILE)['wf_Visibility Mailbox'] = tl.CANDLE_CELL

# The window boxes (docs/plans/2026-11-22-cuckoo-village-flowers.md). The 13 cottages share one mesh, `standard_house`, which today
# carries the blocky plants of its two front window boxes. They come out of it into their own actor, `cottage_flower_blocks` (all
# 26 boxes, the village atlas, shown when Detailed flowers is Off), and the new flowers go into one more actor, `cottage_flowers`
# (all 26 boxes, ten flat-coloured materials, no texture, shown when it is On). The director shows exactly one of them.
import bmesh                      # noqa: E402
from mathutils import Vector      # noqa: E402

bpy.context.view_layer.update()                 # matrix_world is stale in a headless run until the dependency graph has been evaluated
COTTAGES = [objs[f'cottage_{i + 1:02}'] for i in range(tl.HOUSES)]
HOUSE = COTTAGES[0]                  # the layout deletes its template object, so the shared mesh is reached through any cottage
assert all(c.data is HOUSE.data for c in COTTAGES), 'the cottages no longer share one mesh'
BOX_TOP, BOX_X, BOX_Y = 1.655, (-0.78, 0.78), -1.12                  # the boxes' middle of the top, in the house mesh's own frame
OLD_PLANT_TRIANGLES = 328                                            # two boxes of seven posts and seven blocks, measured in the plan


def is_old_plant(face):
    c = face.calc_center_median()
    return c.y < -1.07 and BOX_TOP + 0.005 < c.z < 1.90 and 0.4 < abs(c.x) < 1.2


bm = bmesh.new(); bm.from_mesh(HOUSE.data)
doomed = [f for f in bm.faces if is_old_plant(f)]
assert sum(len(f.verts) - 2 for f in doomed) == OLD_PLANT_TRIANGLES, 'the cottage art changed: the old plant faces are not the 328 triangles the plan measured'
uv_layer = bm.loops.layers.uv.active
old_verts, old_faces, old_uvs = [], [], []
for f in doomed:                                                     # keep a copy, with its atlas coordinates, for the blocks actor
    base = len(old_verts)
    old_verts += [tuple(l.vert.co) for l in f.loops]
    old_uvs += [tuple(l[uv_layer].uv) for l in f.loops]
    old_faces.append(tuple(range(base, base + len(f.loops))))
bmesh.ops.delete(bm, geom=doomed, context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(HOUSE.data); bm.free(); HOUSE.data.update()


def static_actor(name, verts, faces, face_material, materials, uvs, cell):
    """An anchored platform mesh actor from several parts joined: one mesh, one material slot per entry of `materials`."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces); mesh.update()
    for m in materials:
        mesh.materials.append(m)
    for poly, mi in zip(mesh.polygons, face_material):
        poly.material_index = mi; poly.use_smooth = False
    layer = mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[li]
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = str(ROOT / 'wfsource/source/oas/platform.oad')
    obj['wf_Mobility'] = 'Anchored'; obj['wf_Model Type'] = 'Mesh'; obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = cell
    obj['wf_Mesh Name'] = name + '.iff'; obj['wf_original_mesh_name'] = name + '.iff'
    return obj


def to_world(cottage, local):
    return tuple(cottage.matrix_world @ Vector(local))


# The blocks: the removed faces, once for each cottage, in the atlas material they always had.
block_verts, block_faces, block_uvs = [], [], []
for cottage in COTTAGES:
    base = len(block_verts)
    block_verts += [to_world(cottage, v) for v in old_verts]
    block_uvs += old_uvs
    block_faces += [tuple(i + base for i in f) for f in old_faces]
static_actor('cottage_flower_blocks', block_verts, block_faces, [0] * len(block_faces), [bpy.data.materials['village_atlas']],
             block_uvs, tl.BLOCKS_CELL)

# The flowers: 26 boxes (cottage k has box 2k on the left and 2k + 1 on the right), petunia and geranium boxes by box_kind, one
# mesh with a flat-coloured material slot for each of the ten colours. Thin petals and leaves are double-sided (flag 8).
flower_materials = {}
for name_, rgb in fw.MATERIALS.items():
    m = bpy.data.materials.new(name_); m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    if name_ in fw.DOUBLE_SIDED:
        m['wf_double_sided'] = True
    flower_materials[name_] = m
boxes = []
for k, cottage in enumerate(COTTAGES):
    for side, bx in enumerate(BOX_X):
        index = 2 * k + side
        boxes.append(fw.placed(fw.box_flowers(index, 'full'), to_world(cottage, (bx, BOX_Y, BOX_TOP)), cottage.rotation_euler.z, cottage.scale.x))
joined = fw.merge(boxes)
f_verts, f_faces, f_mat, f_names = [], [], [], list(joined)
for mi, name_ in enumerate(f_names):
    verts_, faces_ = joined[name_]
    base = len(f_verts)
    f_verts += verts_
    f_faces += [tuple(i + base for i in face) for face in faces_]
    f_mat += [mi] * len(faces_)
used = [n for n in f_names if joined[n][1]]
assert len(f_faces) == fw.triangle_count(joined) and len(boxes) == 2 * tl.HOUSES
static_actor('cottage_flowers', f_verts, f_faces, f_mat, [flower_materials[n] for n in f_names], [(0.0, 0.0)] * (3 * len(f_faces)), tl.FLOWERS_CELL)
print(f'{TAG} window boxes: {len(f_faces)} flower triangles in {len(used)} materials, {len(sum(len(f) - 2 for f in block_faces)} block triangles')

# window glow: one visibility mailbox per cottage; the bird is shown only during the hourly calls
for i in range(tl.HOUSES):
    objs[f'cottage_light_{i + 1:02}']['wf_Visibility Mailbox'] = GLOW_CELL0 + i
objs[tl.BIRD_NAME]['wf_Visibility Mailbox'] = BIRD_CELL

poses = tl.all_poses(REFERENCE)
for name, p in poses.items():
    if name in ('cs_wide', 'LookAt'):
        continue
    o = objs[name]
    o.location = p[:3]
    o.rotation_euler = (p[3] * math.tau, p[4] * math.tau, p[5] * math.tau)
objs['LookAt'].location = poses['LookAt'][:3]
wide = objs['cs_wide']
wide.location = poses['cs_wide'][:3]
for axis in 'XYZ':
    wide['wf_Position ' + axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow', 'Target', 'Track Object'):
    wide['wf_' + key] = 'LookAt'
objs['Camera'].location = wide.location
objs['Matte']['wf_Matte Type'] = 'Color'
objs['Matte']['wf_Background Color'] = 0x0b1115
objs['Player'].location = (0, -3, 1)

# The user-controlled settings object: an empty carrying the CuckooVillageSettings schema (no model, no mass).
# The director reads each field with property@ using the settings actor's index and the catalog's field index.
import subprocess
settings = bpy.data.objects.new('CuckooVillageSettings', None)
bpy.context.scene.collection.objects.link(settings)
settings['wf_schema_path'] = str(ROOT / 'wfsource/source/oas/cuckoovillagesettings.oad')
settings['wf_Model Type'] = 'None'
settings['wf_Mass'] = 0.0
settings['wf_original_bbox'] = (-.1, -.1, -.1, .1, .1, .1)
settings['wf_had_authored_bbox'] = True
catalog = json.loads(subprocess.check_output([str(ROOT / 'wftools/wf_attr_edit/target/release/catalog'), settings['wf_schema_path']], text=True))
settings_fields = {f['key']: f['index'] for f in catalog['fields'] if f['width'] and f['key'] in tl.SETTINGS_DEFAULTS}
assert set(settings_fields) == set(tl.SETTINGS_DEFAULTS), settings_fields

scene = bpy.context.scene
objects = [o for o in scene.objects if o.get('wf_schema_path')]
indices = {o.name: i + 1 for i, o in enumerate(objects)}
for a, b in zip(tl.FIG_NAMES, tl.FIG_NAMES[1:]):
    assert indices[b] - indices[a] == 1, 'the four figures must be contiguous'
objs['Director']['wf_Script'] = forth.director_script(indices, settings_fields)
(HERE / 'actor-map.json').write_text(json.dumps(dict(indices=indices, reference=REFERENCE), indent=1) + '\n')
print(f'{TAG} {len(objects)} actors')
bpy.ops.wf.export_level(filepath=str(HERE / 'cuckoo_village.lev'))
print(f'{TAG} done')
