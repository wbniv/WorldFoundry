#!/usr/bin/env python3
"""Build one Tide Harbour spike level (variant a, b, c, d, n, v or g from SPIKE_VARIANT); see spike.py for what each tests.

Run through build.sh, in the Blender container. Writes wflevels/tide_spike_<v>/tide_spike_<v>.lev and actor-map.json.
Throwaway: it exists to answer the plan's Phase 0 questions on cast1, and is deleted or folded into Phase 2.
"""
import json
import math
import os
import sys
from pathlib import Path

import addon_utils
import bpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import spike as sp  # noqa: E402

V = os.environ.get('SPIKE_VARIANT', 'c')
assert V in sp.VARIANTS, V
OUT = REPO / 'wflevels' / f'tide_spike_{V}'
OUT.mkdir(exist_ok=True)
OAD = REPO / 'wftools/wf_oad/tests/fixtures'
TAG = f'[tide-spike-{V}]'
MATERIALS = {}


def material(key):
    if key not in MATERIALS:
        mt = bpy.data.materials.new('ts-' + key)
        mt.use_nodes = True
        rgb = (*sp.PALETTE[key], 1)
        mt.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = rgb
        mt.diffuse_color = rgb
        if key in sp.VEIL_OPACITY:
            mt['wf_opacity'] = sp.VEIL_OPACITY[key]            # the exporter turns this into the mesh's OPAC chunk
        MATERIALS[key] = mt
    return MATERIALS[key]


def blender_mesh(mesh):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata(mesh.vertices, [], mesh.faces)
    keys = list(dict.fromkeys(mesh.colors))
    for key in keys:
        data.materials.append(material(key))
    for poly, key in zip(data.polygons, mesh.colors):
        poly.material_index = keys.index(key)
    data.update()
    return data


def box_fields(obj, box):
    obj['wf_original_bbox'] = tuple(box)
    obj['wf_had_authored_bbox'] = True


def actor(name, mesh, pos, kind='platform', visibility=1):
    obj = bpy.data.objects.new(name, blender_mesh(mesh))
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    obj['wf_schema_path'] = str(OAD / (kind + '.oad'))
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = visibility
    filename = mesh.name + '.iff'
    assert len(filename) <= 30, filename
    obj['wf_Mesh Name'] = filename
    obj['wf_original_mesh_name'] = filename
    return obj


bpy.ops.wm.read_factory_settings(use_empty=True)
assert addon_utils.enable('wf_blender', default_set=False, persistent=False), 'wf_blender unavailable'
bpy.ops.wf.import_level(filepath=str(REPO / 'wflevels/snowgoons-blender/snowgoons-blender.lev'))
classes = {'director': 'Director', 'camera': 'Camera', 'levelobj': 'LevelObj', 'matte': 'Matte',
           'light': 'SunLight', 'room': 'Room', 'camshot': 'cs_wide', 'target': 'LookAt', 'player': 'Player'}
seen = set()
for obj in list(bpy.context.scene.objects):
    cls = Path(obj.get('wf_schema_path', '')).stem
    if cls not in classes or cls in seen:
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    seen.add(cls)
    obj.name = classes[cls]
    obj.location = (0, -10, 3)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj['wf_Mass'] = 0.0
    obj['wf_Model Type'] = 'None'
    obj['wf_Script'] = ''
    box_fields(obj, (-.1, -.1, -.1, .1, .1, .1))
assert seen == set(classes), seen

for mesh in sp.static_meshes():
    actor(mesh.name, mesh, (0.0, 0.0, 0.0) if mesh.name != 'dial' else sp.DIAL, kind='statplat')
for grp in sp.groups(V).values():
    for name, mesh, pos in grp:
        actor(name, mesh, pos)
if V in sp.FEATURES:
    if sp.FEATURES[V]['veils']:
        for i, (name, mesh, pos) in enumerate(sp.veil_actors()):
            actor(name, mesh, pos, visibility=sp.VEIL_MAILBOX + i)
    if sp.FEATURES[V]['glows']:
        for i, (name, mesh, pos) in enumerate(sp.glow_actors()):
            actor(name, mesh, pos, visibility=sp.GLOW_MAILBOX + i)

sun = bpy.data.objects['SunLight']
# Measured 2026-11-21 (wflevels/tide_spike/shots, five settings, four faces of known normal): with outward-wound faces a directional
# light travels along (cos B cos C, cos B sin C, -sin B), so B = +alt tilts it downward and C is the bearing it travels toward. A face is lit
# when its normal opposes that vector. B=50, C=70 lights tops, camera-facing fronts and left sides: the sun is behind the camera.
_B, _C = (float(x) for x in os.environ.get('TANK_SPIKE_SUN', '50,70').split(','))       # degrees; see docs/level-building.md, Lighting
sun.rotation_euler = (0, math.radians(_B), math.radians(_C))
sun['wf_lightType'] = 'Directional'
for ch, v in zip(('Red', 'Green', 'Blue'), (.80, .78, .72)):
    sun['wf_light' + ch] = v
amb = sun.copy()
amb.name = 'AmbientLight'
bpy.context.scene.collection.objects.link(amb)
amb['wf_lightType'] = 'Ambient'
for ch, v in zip(('Red', 'Green', 'Blue'), (.50, .52, .56)):
    amb['wf_light' + ch] = v

look = bpy.data.objects['LookAt']
look.location = sp.LOOK_AT
wide = bpy.data.objects['cs_wide']
wide.location = sp.CAMERA
for axis in 'XYZ':
    wide['wf_Position ' + axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow', 'Target', 'Track Object'):
    wide['wf_' + key] = 'LookAt'
bpy.data.objects['Camera'].location = wide.location
cam = bpy.data.objects['Camera']
cam['wf_FoggingColor'] = 0xbfdcf2                       # a mild haze toward the horizon colour; the baseline camera's grey fog hid everything past ~30 m
cam['wf_FoggingStartDistance'] = 150.0
cam['wf_FoggingCompleteDistance'] = 500.0
bpy.data.objects['Matte']['wf_Matte Type'] = 'Color'
bpy.data.objects['Matte']['wf_Background Color'] = 0x6fabe0
bpy.data.objects['Player'].location = (-10, -5, 2.2)       # over the pier deck, so it has a floor to stand on
box_fields(bpy.data.objects['Room'], (-320, -80, float(os.environ.get('TANK_SPIKE_ROOMZ', '-90')), 320, 120, 160))      # the sun and moon dip to z = -44: stay inside the room
bpy.data.objects['Room'].location = (0, 0, 0)

objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name: i + 1 for i, o in enumerate(objects)}
for grp in sp.groups(V).values():
    names = [n for n, _m, _p in grp]
    for a, b in zip(names, names[1:]):
        assert indices[b] - indices[a] == 1, f'{a} and {b} must be contiguous'
bpy.data.objects['Director']['wf_Script'] = sp.director_script(V, indices)

(OUT / 'actor-map.json').write_text(json.dumps(dict(indices=indices, variant=V), indent=1) + '\n')
posed = sum(len(g) for g in sp.groups(V).values())
print(f'{TAG} {len(objects)} actors ({posed} posed)')
bpy.ops.wf.export_level(filepath=str(OUT / f'tide_spike_{V}.lev'))
print(f'{TAG} done')
