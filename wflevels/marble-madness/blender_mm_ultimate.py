"""
blender_mm_ultimate.py — Build the MM Ultimate level from ROM data in Blender.

Run via Blender MCP (execute_blender_code) or headless:
    blender --background --python blender_mm_ultimate.py

Path layout (GAME_UNIT=0.05, SEG_LEN=2.5, PATH_HALF=2.0):
    Segs 0-1:   heading  2.81° (nearly East);  h_center=45-37 → Z=2.00-1.60m
    Segs 2-3:   heading  3.37° (nearly East);  h_center=38-39 → Z=1.65-1.70m
    Segs 4-5:   heading  4.00° (nearly East);  h_center=50-51 → Z=2.25-2.30m
    Seg  6:     heading  5.86° (nearly East);  h_center=56 → Z=2.55m
    Seg  7:     heading  5.86° (nearly East);  h_center=47 → Z=2.10m
    Segs 8-9:   heading 24.61° (NNE);          h_center=48-57 → Z=2.15-2.60m
    Segs 10-11: heading 26.02° (NNE);          h_center=52-53 → Z=2.35-2.40m
    Seg  12:    heading 24.19° (NNE, h_left=h_right=0 crowned); h_center=25 → Z=1.00m
    Segs 13-17: heading 25.31° (NNE);          h_center=58-55 → Z=2.65-2.50m
    Segs 18-22: goal platform (h_center=5 → Z=0)
    Path extent: X ~[-2,33], Y ~[-2,35]; walls up to ~5.05m
    Total XY span: ~30 m NE to goal
"""

import bpy
import addon_utils
import math
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
OAD_DIR    = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'mm_ultimate.lev')

def oad(name):
    return os.path.join(OAD_DIR, f'{name}.oad')


ROOM_POS        = (12.0, 12.0,  4.5)
ROOM_LOCAL_BBOX = (-20.5, -22.5, -10.5,  20.5, 22.5, 10.5)

SPAWN_POS    = ( 0.3,   0.3,  2.20)
CAMSHOT_POS  = (-6.0,  -8.0, 10.0)
TARGET1_POS  = ( 0.0,   0.0,  0.0)
TARGET2_POS  = (30.2,  32.6,  0.0)
LIGHT_POS    = (12.0,  12.0, 13.5)
CAMERA_POS   = (-5.7,  -7.7, 12.20)

DIRECTOR_SCRIPT = (
    r'\\ wf' '\n'
    r': init-game  INDEXOF_TIME read-mailbox 55 +  2 write-mailbox'
    r'  99 72 write-mailbox  0 70 write-mailbox ;' '\n'
    r'2 read-mailbox 0 = if init-game then' '\n'
    r'2 read-mailbox INDEXOF_TIME read-mailbox -  dup 71 write-mailbox'
    r'  0 <= if 1 INDEXOF_END_OF_LEVEL write-mailbox then' '\n'
    r'13 read-mailbox 0 <> if  0 13 write-mailbox'
    r'  72 read-mailbox 1 -  dup 72 write-mailbox'
    r'  0 <= if 1 INDEXOF_END_OF_LEVEL write-mailbox then  then' '\n'
    r'100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then' '\n'
    r' 99 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then' '\n'
    r' 98 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then' '\n'
)

PLAYER_SCRIPT = (
    r'\\ wf' '\n'
    r': cam-remap  0'
    r'  over 2048  & if 10240 | then'
    r'  over 4096  & if 20480 | then'
    r'  over 8192  & if 12288 | then'
    r'  over 16384 & if 18432 | then'
    r'  swap drop ;' '\n'
    r': respawn  0 INDEXOF_X_POS write-mailbox  0 INDEXOF_Y_POS write-mailbox'
    r'  3 INDEXOF_Z_POS write-mailbox'
    r'  0 INDEXOF_XSPEED write-mailbox  0 INDEXOF_YSPEED write-mailbox'
    r'  0 INDEXOF_ZSPEED write-mailbox  1 13 write-mailbox ;' '\n'
    r'INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox cam-remap INDEXOF_INPUT write-mailbox' '\n'
    r'INDEXOF_Z_POS read-mailbox -2 < if respawn then' '\n'
)


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block)
    addon_utils.enable("wf_blender", default_set=False, persistent=False)


def make_empty(name, pos, oad_name, props=None):
    obj = bpy.data.objects.new(name, None)
    obj.location = pos
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = oad(oad_name)
    if props:
        for k, v in props.items():
            obj[f'wf_{k}'] = v
    return obj


def make_box_empty(name, pos, bbox_local, oad_name, props=None):
    lx0, ly0, lz0, lx1, ly1, lz1 = bbox_local
    verts = [
        (lx0, ly0, lz0), (lx1, ly0, lz0), (lx1, ly1, lz0), (lx0, ly1, lz0),
        (lx0, ly0, lz1), (lx1, ly0, lz1), (lx1, ly1, lz1), (lx0, ly1, lz1),
    ]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    m = bpy.data.meshes.new(f'{name}_box')
    m.from_pydata(verts, [], faces)
    m.update()
    obj = bpy.data.objects.new(name, m)
    obj.location = pos
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = oad(oad_name)
    obj['wf_original_bbox'] = bbox_local
    if props:
        for k, v in props.items():
            obj[f'wf_{k}'] = v
    obj.display_type = 'WIRE'
    return obj


clear_scene()

make_box_empty(
    'Room01', ROOM_POS, ROOM_LOCAL_BBOX, 'room',
    props={'Adjacent Room 1': '', 'Adjacent Room 2': '', 'Room Loaded Mailbox': 0}
)

make_empty('LevelObj', ROOM_POS, 'levelobj',
    props={'Mobility': 'Anchored', 'MovementClass': 15, 'Model Type': 'Box'})

make_empty('Matte', ROOM_POS, 'matte',
    props={
        'Mobility':           'Anchored',
        'MovementClass':      11,
        'Model Type':         'Box',
        'Matte Type':         'Color',
        'Background Color':   0,
        'Visibility Mailbox': 1,
    })

_light = make_empty('Light01', LIGHT_POS, 'light',
    props={'Mobility': 'Anchored', 'MovementClass': 23, 'Model Type': 'None'})
_light.rotation_euler = (math.pi / 2, 0, 0)

make_empty(
    'Director', ROOM_POS, 'director',
    props={
        'Mobility':              'Anchored',
        'MovementClass':         20,
        'Script':                DIRECTOR_SCRIPT,
        'Script Controls Input': 'False',
        'Model Type':            'None',
    }
)

make_empty('Camera', CAMERA_POS, 'camera',
    props={'Mobility': 'Camera', 'MovementClass': 13, 'Model Type': 'Box'})

make_empty('Target01', TARGET1_POS, 'target',
    props={'Mobility': 'Anchored', 'MovementClass': 3, 'Model Type': 'Box'})
make_empty('Target02', TARGET2_POS, 'target',
    props={'Mobility': 'Anchored', 'MovementClass': 3, 'Model Type': 'Box'})

make_empty(
    'CamShot01', CAMSHOT_POS, 'camshot',
    props={
        'Mobility':           'Anchored',
        'MovementClass':      16,
        'Target':             'Player',
        'Follow':             'Target01',
        'Track Object':       'Player',
        'Rotation':           'Track',
        'Position X':         'Relative',
        'Position Y':         'Relative',
        'Position Z':         'Relative',
        'FOV':                60.0,
        'Climb Rate':         5.0,
        'Elasticity':         10.0,
        'Pan Time In Seconds': 1.0,
        'Hither':             0.1,
        'Yon':                1000.0,
        'Model Type':         'Box',
        'Visibility Mailbox': 1,
    }
)

make_box_empty(
    'ActBoxOR', ROOM_POS, ROOM_LOCAL_BBOX, 'actboxor',
    props={
        'Mobility':     'Anchored',
        'MovementClass': 17,
        'Model Type':   'None',
        'MailBox':      100,
        'Object':       'CamShot01',
        'Activated By': 'Player',
    }
)

player = make_empty(
    'Player', SPAWN_POS, 'player',
    props={
        'Mobility':              'Physics',
        'MovementClass':         22,
        'Moves Between Rooms':   'True',
        'Turn Rate':             0.0,
        'Running Acceleration':  15.0,
        'Running Deceleration':  0.0,
        'Max Ground Speed':      15.0,
        'Air Acceleration':      10.0,
        'Horiz Air Drag':        0.0,
        'Vert Air Drag':         0.0,
        'Max Air Speed':         50.0,
        'Falling Acceleration':  9.8,
        'Vertical Elasticity':   0.3,
        'Horizontal Elasticity': 0.7,
        'Step Size':             0.25,
        'Mass':                  75.0,
        'Surface Friction':      0.3,
        'hp':                    32767.0,
        'Number Of Local Mailboxes': 6,
        'Script':                PLAYER_SCRIPT,
        'Script Controls Input': 'True',
        'Mesh Name':             'sphere.iff',
        'Model Type':            'Mesh',
        'Visibility Mailbox':    1,
    }
)
player['wf_original_bbox'] = (-0.33, -0.33, 0.0, 0.33, 0.33, 0.66)

_rtb_path = os.path.join(SCRIPT_DIR, 'rom_to_blender.py')
_rtb_ns   = {'__file__': _rtb_path, '__name__': 'rom_to_blender', 'bpy': bpy}
exec(open(_rtb_path).read(), _rtb_ns)
_rtb_ns['build_path_mesh']('Ultimate', _rtb_ns['load_levels']())

print(f'[ultimate] Exporting to {OUT_LEV}')
try:
    bpy.ops.wf.export_level(filepath=OUT_LEV)
except AttributeError:
    import importlib.util as _ilu
    _addon_dir = os.path.expanduser('~/.config/blender/4.0/scripts/addons/wf_blender')
    _spec = _ilu.spec_from_file_location('wf_blender.export_level',
                                          os.path.join(_addon_dir, 'export_level.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ok, msg = _mod.export_scene_to_lev(bpy.context, OUT_LEV)
    if not ok:
        raise RuntimeError(f'export_scene_to_lev failed: {msg}')
    print(f'Info: Exported to {OUT_LEV}')
print(f'[ultimate] Done. Objects in scene:')
for o in bpy.data.objects:
    print(f'  {o.name} @ {tuple(round(x,2) for x in o.location)}')
