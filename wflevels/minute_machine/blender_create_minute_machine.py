#!/usr/bin/env python3
"""Build the Minute Machine level (plan docs/plans/2026-11-21-sixty-second-chain-reaction.md).

Every dynamic piece is an actor whose pose the director script computes from the wall clock; the
table, rails, frame, hopper and display housing are static. Run through build.sh, in the Blender
container. Writes wflevels/minute_machine/minute_machine.lev and actor-map.json.
"""
import json
import math
import sys
from pathlib import Path

import addon_utils
import bpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import forth      # noqa: E402
import parts      # noqa: E402
import timeline as tl  # noqa: E402

OAD = REPO / 'wftools/wf_oad/tests/fixtures'
TAG = '[minute-machine]'
REFERENCE = 10 * 3600 + 8 * 60 + 22.0     # the pose the level starts from (the mockups' reading)
MATERIALS = {}


def material(key):
    if key not in MATERIALS:
        mt = bpy.data.materials.new('mm-' + key)
        mt.use_nodes = True
        rgb = (*parts.PALETTE[key], 1)
        mt.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = rgb
        mt.diffuse_color = rgb
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


def schema(obj, name):
    obj['wf_schema_path'] = str(OAD / (name + '.oad'))


def box_fields(obj, box):
    obj['wf_original_bbox'] = tuple(box)
    obj['wf_had_authored_bbox'] = True


def actor(name, mesh, pose=None, kind='platform'):
    obj = bpy.data.objects.new(name, blender_mesh(mesh))
    bpy.context.scene.collection.objects.link(obj)
    if pose is not None:
        obj.location = (pose.x, pose.y, pose.z)
        obj.rotation_euler = (pose.a * math.tau, pose.b * math.tau, pose.c * math.tau)
        obj.scale = (pose.sx, pose.sy, pose.sz)
    schema(obj, kind)
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1
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
    obj.location = (5.6, -15, 2.2)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj['wf_Mass'] = 0.0
    obj['wf_Model Type'] = 'None'
    obj['wf_Script'] = ''
    box_fields(obj, (-.1, -.1, -.1, .1, .1, .1))
assert seen == set(classes), seen

poses = tl.all_poses(REFERENCE)
for mesh in parts.static_meshes():
    actor(mesh.name, mesh, kind='statplat')
for name, mesh in parts.all_meshes().items():
    actor(name, mesh, poses[name])

sun = bpy.data.objects['SunLight']
sun.rotation_euler = (0, math.radians(40), math.radians(90))
sun['wf_lightType'] = 'Directional'
for ch, v in zip(('Red', 'Green', 'Blue'), (.80, .78, .72)):
    sun['wf_light' + ch] = v
amb = sun.copy()
amb.name = 'AmbientLight'
bpy.context.scene.collection.objects.link(amb)
amb['wf_lightType'] = 'Ambient'
for ch, v in zip(('Red', 'Green', 'Blue'), (.38, .39, .45)):
    amb['wf_light' + ch] = v

look = bpy.data.objects['LookAt']
look.location = (poses['camera_look'].x, poses['camera_look'].y, poses['camera_look'].z)
wide = bpy.data.objects['cs_wide']
wide.location = (poses['camera_proxy'].x, poses['camera_proxy'].y, poses['camera_proxy'].z)
for axis in 'XYZ':
    wide['wf_Position ' + axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow', 'Target', 'Track Object'):
    wide['wf_' + key] = 'LookAt'
bpy.data.objects['Camera'].location = wide.location
bpy.data.objects['Matte']['wf_Matte Type'] = 'Color'
bpy.data.objects['Matte']['wf_Background Color'] = 0x0b0c10
bpy.data.objects['Player'].location = (5.6, -3.0, 2.2)
box_fields(bpy.data.objects['Room'], (-40, -45, -8, 50, 12, 24))
bpy.data.objects['Room'].location = (0, 0, 0)

# This clock has no level-specific settings yet. The existing generic holder supplies
# the global settings sheet, so the phone's settings button remains available.
settings = bpy.data.objects.new('MinuteMachineSettings', None)
bpy.context.scene.collection.objects.link(settings)
settings['wf_schema_path'] = str(REPO / 'wfsource/source/oas/levelsettings.oad')
settings['wf_Editor Label'] = 'Minute Machine'
settings['wf_Mobility'] = 'Anchored'
settings['wf_Model Type'] = 'None'
settings['wf_Mass'] = 0.0
box_fields(settings, (-.1, -.1, -.1, .1, .1, .1))

objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name: i + 1 for i, o in enumerate(objects)}
for i in range(tl.DOMINO_COUNT - 1):
    assert indices[f'domino_{i + 1:02d}'] - indices[f'domino_{i:02d}'] == 1, 'dominoes must be contiguous'
for k in range(4):
    for c in range(tl.DRUM_SIZES[k] - 1):
        assert indices[f'card_{k}_{c + 1}'] - indices[f'card_{k}_{c}'] == 1, 'a drum\'s cards must be contiguous'
bpy.data.objects['Director']['wf_Script'] = forth.director_script(indices)

(HERE / 'actor-map.json').write_text(json.dumps(dict(indices=indices, reference=REFERENCE), indent=1) + '\n')
animated = len([n for n in parts.all_meshes()])
print(f'{TAG} {len(objects)} actors ({animated} animated, {len(parts.static_meshes())} static groups)')
bpy.ops.wf.export_level(filepath=str(HERE / 'minute_machine.lev'))
print(f'{TAG} done')
