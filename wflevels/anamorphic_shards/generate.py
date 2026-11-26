"""Build a live, depth-fragmented clock using the baseline scene contract."""
import json
import math
import subprocess
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT / 'wftools'), str(HERE)]
import wf_blender
import wf_core
from wf_blender.export_level import _seed_defaults
import model

OAS = ROOT / 'wfsource/source/oas'
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()


def actor(name, cls, data=None, pos=(0, 0, 0), fields=None, bounds=None):
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS / (cls + '.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    values = {'Mobility': 'Anchored', 'Mass': 0.0, 'Model Type': 'Mesh' if data else 'None',
              'Visibility Mailbox': 1 if data else 0, 'Script': '', 'Script Controls Input': 'False',
              'Moves Between Rooms': 'False', 'Number Of Local Mailboxes': 0}
    values.update(fields or {})
    for key, value in values.items(): obj['wf_' + key] = value
    if data:
        obj['wf_Mesh Name'] = name + '.iff'
        obj['wf_original_mesh_name'] = name + '.iff'
    if bounds or not data:
        obj['wf_original_bbox'] = tuple(bounds or (-.05, -.05, -.05, .05, .05, .05))
        obj['wf_had_authored_bbox'] = True
    return obj


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*color, 1)
    mat['wf_prelit'] = True
    mat['wf_double_sided'] = True
    return mat


gold = material('shards-gold', (.95, .72, .37))
white = material('overlay-ivory', (.94, .96, 1.0))


def mesh(name, polys, mat):
    verts, faces = [], []
    for poly in polys:
        base = len(verts)
        # Give every fragment a real thickness instead of a coplanar texture.
        verts.extend(poly)
        verts.extend((x, y + .045, z) for x, y, z in poly)
        faces.extend(((base, base+1, base+2, base+3), (base+7, base+6, base+5, base+4)))
        faces.extend((base+i, base+(i+1)%4, base+(i+1)%4+4, base+i+4) for i in range(4))
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.materials.append(mat)
    data.update()
    return data


actor('Level', 'levelobj')
actor('Room', 'room', bounds=(-35, -35, -20, 35, 35, 25))
director = actor('Director', 'director')
actor('Player', 'player', pos=(0, 8, 0))
actor('Camera', 'camera', pos=(0, model.CAMERA_Y, model.CAMERA_Z), fields={
    'Mobility': 'Camera', 'Moves Between Rooms': 'True', 'FoggingColor': 0x101828,
    'FoggingStartDistance': 900.0, 'FoggingCompleteDistance': 1000.0})
actor('LookAt', 'target', pos=(0, 0, model.CAMERA_Z))
actor('cs_wide', 'camshot', pos=(0, model.CAMERA_Y, model.CAMERA_Z), fields={
    'Follow': 'LookAt', 'Target': 'LookAt', 'Track Object': 'LookAt', 'Rotation': 'Fixed',
    'Position X': 'Absolute', 'Position Y': 'Absolute', 'Position Z': 'Absolute',
    'Hither': 1.0, 'Yon': 200.0, 'FOV': 50.0, 'Pan Time In Seconds': 0.0})
actor('SunLight', 'light', fields={'lightType': 'Ambient', 'lightRed': 1., 'lightGreen': 1., 'lightBlue': 1.})
actor('Background', 'matte', fields={'Matte Type': 'Color', 'Background Color': 0x101828})
actor('AnamorphicShardsSettings', 'anamorphicshardssettings', fields={'Editor Label': 'Anamorphic Shards'})

for d in range(4):
    for s in range(7):
        name = f'shard_{d}_{s}'
        actor(name, 'platform', mesh(name, model.fragments(d, s), gold), fields={'Visibility Mailbox': 600+d*7+s})
        # The readout sits behind the near plane and stays in view throughout
        # the camera's excursion, without moving cached meshes every frame.
        x0,z0,x1,z1 = model.SEGMENTS[s]
        x = .50 + d * .31 + (.12 if d >= 2 else 0)
        poly = ((x0*.88,0,z0*.88), (x1*.88,0,z0*.88),
                (x1*.88,0,z1*.88), (x0*.88,0,z1*.88))
        name = f'overlay_{d}_{s}'
        actor(name, 'platform', mesh(name, [poly], white), pos=(x*4,0,6.28),
              fields={'Visibility Mailbox': 600+d*7+s})

# Two separator pieces share the same alignment projection and are always visible.
def separator(x, z, size, depth):
    return tuple(model.unproject(x+dx, model.CAMERA_Z+z+dz, depth)
                 for dx,dz in ((-size,-size),(size,-size),(size,size),(-size,size)))
actor('shard_colon', 'platform', mesh('shard_colon',
      [separator(0, .37*model.DISPLAY_SCALE, .09*model.DISPLAY_SCALE, -1.5),
       separator(0, -.37*model.DISPLAY_SCALE, .09*model.DISPLAY_SCALE, 4.0)], gold))
overlay_dots = [tuple((x*4,0,z*4) for x,z in ((-.02,.06),(.02,.06),(.02,.10),(-.02,.10))),
                tuple((x*4,0,z*4) for x,z in ((-.02,-.10),(.02,-.10),(.02,-.06),(-.02,-.06)))]
actor('overlay_colon', 'platform', mesh('overlay_colon', overlay_dots, white), pos=(4.1,0,6.28))

bpy.context.view_layer.update()
objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name: i+1 for i,o in enumerate(objects)}
catalog = json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),
                                                str(OAS/'anamorphicshardssettings.oad')], text=True))
drift = next(f for f in catalog['fields'] if f['key'] == 'Camera drift')
assert drift['live']

def show_expr(d, s):
    valid = [i for i, mask in enumerate(model.MASKS) if mask & (1 << s)]
    return ' '.join(f'{d} sh-digit {n} =' for n in valid) + ' ' + ' |' * (len(valid)-1)

lines = [r'\ Anamorphic Shards: wall-clock-driven visibility and camera.',
         ': sh-mod over over / floor * - ;',            # floored, with the engine's floor (docs/forth-math-words.md)
         ': sh-digit ( k -- d )',
         '  dup 0 = if drop INDEXOF_WALL_HOUR read-mailbox 10 / floor else',
         '  dup 1 = if drop INDEXOF_WALL_HOUR read-mailbox 10 sh-mod else',
         '  dup 2 = if drop INDEXOF_WALL_MINUTE read-mailbox 10 / floor else',
         '  drop INDEXOF_WALL_MINUTE read-mailbox 10 sh-mod then then then ;',
         ': sh-tick',
         f'  {indices["AnamorphicShardsSettings"]} {drift["index"]} property@ if 0 <> else drop 0 then',
         '  if 0 else INDEXOF_WALL_SECOND read-mailbox 4 - 0 max 56 / cos-rev negate 1 + 1.35 * then',
         f'  dup INDEXOF_X_POS {indices["cs_wide"]} write-actor-mailbox',
         f'  INDEXOF_X_POS {indices["LookAt"]} write-actor-mailbox']
# The zero-amplitude deformer keeps the interleaved meshes on the dynamic draw
# path. Without it the PC capture loses pieces off-axis or after a time change.
for d in range(4):
    for s in range(7):
        lines.append(f'  0 0 {indices[f"shard_{d}_{s}"]} fish-deform')
        lines.append(f'  0 0 {indices[f"overlay_{d}_{s}"]} fish-deform')
lines.append(f'  0 0 {indices["overlay_colon"]} fish-deform')
for d in range(4):
    for s in range(7): lines.append(f'  {show_expr(d,s)} {600+d*7+s} write-mailbox')
lines.append(';\nsh-tick\n')
director['wf_Script'] = '\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices': indices, 'depths': model.DEPTHS,
                                                'camera_drift_field': drift['index']}, indent=2)+'\n')
bpy.ops.wf.export_level(filepath=str(HERE/'anamorphic_shards.lev'))
