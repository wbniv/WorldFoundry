#!/usr/bin/env python3
"""blender_create_swim_spike.py — aquarium Phase 1: a gravity-free Physics fish in an open box.

Plan: docs/plans/2026-09-30-aquarium-level.md § Verification, Phase 1 (steps 5–8).

Builds, at WORLD_SCALE (env, default 10; see aquarium_constants.py):
  * the tank as SEPARATE statplat slabs — bottom, sand, back, left, right — plus an
    INVISIBLE front collider (Plan B: no visible front pane). Separate slabs, not one shell:
    jolt_backend.cc JoltCharacterCreate ignores every static body whose world AABB encloses
    the character at spawn ("zone body"), and a one-piece tank encloses the fish.
    `-- shell=one` builds the one-piece variant instead, to demonstrate exactly that;
  * the fish: the `Player`, Physics, Falling Acceleration 0, Script Controls Input, Turn Rate 0,
    a body + a white tail so its heading reads in a capture; its Forth maps the joystick to
    X/Y/ZSPEED, clamps Z under the water line and writes ROTATION_C to face travel;
  * a parked camera outside the front (bungee rig: Follow = Target = Track Object = LookAt).

Run: WORLD_SCALE=10 blender --background --python-exit-code 1 --python <this> [-- shell=one] [fish=box]
     bash wftools/wf_blender/build_level_binary.sh aquarium_swim_spike
or   python3 wflevels/aquarium_swim_spike/run_swim_spike.py   (build + bridge-driven tests)
"""
import math
import os
import sys

import addon_utils
import bmesh
import bpy

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import aquarium_constants as C                                     # noqa: E402

REPO          = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OAD_DIR       = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
LEVEL_NAME    = 'aquarium_swim_spike'
OUT_LEV       = os.path.join(SCRIPT_DIR, LEVEL_NAME + '.lev')

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SHELL_ONE = 'shell=one' in ARGV
FISH_BOX = 'fish=box' in ARGV       # coarse fish; the 12×8 ellipsoid aborts the level at ×1
S = C.WORLD_SCALE
m = C.m

# ── Tank (inches → metres via C.m); origin = centre of the footprint, z = 0 = outer base ──
HX, HY = C.EXT_X / 2, C.EXT_Y / 2               # 24, 6.5
IX, IY = HX - C.WALL, HY - C.WALL               # 23.5, 6.0  (inner faces)
SLABS = {                                       # name: (x0, y0, z0, x1, y1, z1) in inches
    'tank-bottom': (-HX, -HY, 0.0,     HX,  HY, C.WALL),
    'sand':        (-IX, -IY, C.WALL,  IX,  IY, C.SAND_TOP),
    'tank-back':   (-HX,  IY, C.WALL,  HX,  HY, C.EXT_Z),
    'tank-left':   (-HX, -IY, C.WALL, -IX,  IY, C.EXT_Z),
    'tank-right':  ( IX, -IY, C.WALL,  HX,  IY, C.EXT_Z),
    'tank-front':  (-HX, -HY, C.WALL,  HX, -IY, C.EXT_Z),     # invisible collider (Plan B)
}
COLOURS = {'tank-bottom': (0.55, 0.75, 0.80), 'sand': (0.85, 0.78, 0.55),
           'tank-back': (0.10, 0.35, 0.55), 'tank-left': (0.55, 0.75, 0.80),
           'tank-right': (0.55, 0.75, 0.80), 'tank-front': (0.55, 0.75, 0.80)}

# ── Fish (inches) ────────────────────────────────────────────────────────────
FISH_BODY_L, FISH_W, FISH_H = 2.6, 1.0, 1.4     # ellipsoid body; tail adds 0.9 in → 3.5 in total
FISH_TAIL_L = C.FISH_LEN - FISH_BODY_L
FISH_SPAWN = (-16.0 * 0.39370, 0.0, 24.0 * 0.39370)   # plan: (−1.6, 0, 2.4) m at ×10 → inches
SWIM_SPEED = 12.0                               # in/s ≈ 0.3 m/s at ×1 (3 m/s at ×10)
Z_MARGIN = 0.25                                 # in: keep the fish's top this far under the water line

CAM_POS  = (0.0, -1.10 * S, m(C.EXT_Z) / 2)     # plan: y ≈ −11 at ×10
LOOK_POS = (0.0, 0.0, m(C.EXT_Z) / 2)

KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light', 'room', 'camshot',
                'target', 'player'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


def find_by_class(cn):
    return next((o for o in bpy.data.objects if get_class(o) == cn), None)


def attach_schema(obj, oad):
    obj['wf_schema_path'] = os.path.join(OAD_DIR, oad + '.oad')


def flat_material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def add_box(bm, x0, y0, z0, x1, y1, z1, mat_index=0):
    vs = [bm.verts.new(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                                    (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        face = bm.faces.new([vs[i] for i in f])
        face.material_index = mat_index


def finish(bm, me):
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # outward
    bm.to_mesh(me)
    bm.free()
    me.update()


def statplat(name, me, location=(0.0, 0.0, 0.0), visible=True):
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.location = location
    attach_schema(obj, 'statplat')
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Visibility Mailbox'] = 1 if visible else 0
    obj['wf_Mass'] = 0.0
    slug = name.replace('-', '_') + '.iff'
    obj['wf_Mesh Name'] = slug
    obj['wf_original_mesh_name'] = slug
    return obj


# 1. Scaffold: snowgoons stripped to one of each infrastructure class, survivors renamed.
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable('wf_blender', default_set=False, persistent=False)
scene = bpy.context.scene
bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)
for obj in list(bpy.data.objects):
    if get_class(obj) not in KEEP_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in seen:
        bpy.data.objects.remove(obj, do_unlink=True)
    else:
        seen.add(cn)
for cn, new in (('director', 'Director'), ('camera', 'Camera'), ('levelobj', 'LevelObj'),
                ('matte', 'Matte'), ('room', 'Room'), ('camshot', 'cs_front'),
                ('target', 'LookAt'), ('player', 'Player'), ('light', 'SunLight')):
    o = find_by_class(cn)
    assert o is not None, f'no {cn} in the snowgoons scaffold'
    o.name = new

# 2. The fish (Player). Built first among the new meshes; its actor index is fixed by the
#    scaffold order anyway (Player is imported before anything created here).
fme = bpy.data.meshes.new('fish')
fme.materials.append(flat_material('fish-orange', (0.95, 0.42, 0.05)))
fme.materials.append(flat_material('fish-white', (0.95, 0.95, 0.95)))
bm = bmesh.new()
if FISH_BOX:
    # Coarse box body: every triangle stays above the engine's minimum face area at ×1
    # (vector3.hpi:243 asserts |(v2−v0)×(v1−v0)| > 6.1e-5, i.e. area > ~3e-5 m²).
    add_box(bm, -m(FISH_BODY_L) / 2, -m(FISH_W) / 2, 0.0, m(FISH_BODY_L) / 2, m(FISH_W) / 2, m(FISH_H))
else:
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1.0)
    for v in bm.verts:                           # ellipsoid, nose at +X, base at local z = 0
        v.co.x *= m(FISH_BODY_L) / 2
        v.co.y *= m(FISH_W) / 2
        v.co.z = (v.co.z + 1.0) * m(FISH_H) / 2
# tail: a white wedge behind the body (−X), so heading is readable side-on
tx0, tx1 = -m(FISH_BODY_L) / 2 - m(FISH_TAIL_L), -m(FISH_BODY_L) / 2 + m(0.2)
add_box(bm, tx0, -m(0.15), m(0.1), tx1, m(0.15), m(FISH_H) - m(0.1), mat_index=1)
finish(bm, fme)
fme.update()

player = bpy.data.objects['Player']
player.data = fme
for key in ('wf_original_bbox', 'wf_had_authored_bbox'):      # else snowgoons' 2 m capsule wins
    if key in player:
        del player[key]
player.location = tuple(m(c) for c in FISH_SPAWN)
player.rotation_euler = (0.0, 0.0, 0.0)          # C = 0 → currentDir = +X (nose right)
player.scale = (1.0, 1.0, 1.0)
player['wf_Mobility']              = 'Physics'
player['wf_Mass']                  = 1.0
player['wf_Model Type']            = 'Mesh'
player['wf_Visibility Mailbox']    = 1
player['wf_Falling Acceleration']  = 0.0         # neutral buoyancy
player['wf_Script Controls Input'] = 'True'
player['wf_Turn Rate']             = 0.0
player['wf_Air Acceleration']      = 0.0
player['wf_Max Air Speed']         = m(2 * SWIM_SPEED)   # must not be 0 (troubleshooting: AirHandler cap)
player['wf_Horiz Air Drag']        = 2.0         # glide: v × (1 − 2·dt) per tick when no key is held
player['wf_Vert Air Drag']         = 2.0
player['wf_Running Acceleration']  = 0.0
player['wf_Running Deceleration']  = 0.05        # MarbleHandler friction = decel·dt·30 per tick; 0.85 zeroes XY at 20 fps
player['wf_Max Ground Speed']      = m(2 * SWIM_SPEED)
player['wf_Jumping Acceleration']  = 0.0

JOY = 'INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox'


def held(button):
    return f'{JOY} JOYSTICK_BUTTON_{button} & 0 <>'


V = m(SWIM_SPEED)
ZMAX = m(C.WATER_Z - FISH_H - Z_MARGIN)          # feet Z at which the top of the fish is at the margin
lines = [
    '\\ wf',
    '\\ aquarium swim spike: joystick → X/Y/ZSPEED; glide = air drag when released',
    '0 INDEXOF_INPUT write-mailbox',
    f'{held("RIGHT")} if {V:.4f} INDEXOF_XSPEED write-mailbox 0 INDEXOF_ROTATION_C write-mailbox then',
    f'{held("LEFT")} if {-V:.4f} INDEXOF_XSPEED write-mailbox 0.5 INDEXOF_ROTATION_C write-mailbox then',
    f'{held("UP")} if {V:.4f} INDEXOF_ZSPEED write-mailbox then',
    f'{held("DOWN")} if {-V:.4f} INDEXOF_ZSPEED write-mailbox then',
    f'{held("C")} if {V:.4f} INDEXOF_YSPEED write-mailbox then',
    f'{held("B")} if {-V:.4f} INDEXOF_YSPEED write-mailbox then',
    # water-line clamp: above ZMAX, no upward speed, and pin Z at ZMAX
    f'INDEXOF_Z_POS read-mailbox {ZMAX:.4f} > if 0 INDEXOF_ZSPEED write-mailbox {ZMAX:.4f} INDEXOF_Z_POS write-mailbox then',
]
player['wf_Script'] = '\n'.join(lines) + '\n'

# 3. Tank.
if SHELL_ONE:
    me = bpy.data.meshes.new('tank-shell')
    me.materials.append(flat_material('acrylic', COLOURS['tank-left']))
    bm = bmesh.new()
    for name, b in SLABS.items():
        if name not in ('sand', 'tank-front'):
            add_box(bm, *(m(v) for v in b))
    finish(bm, me)
    statplat('tank-shell', me)
    names = ['sand', 'tank-front']
else:
    names = list(SLABS)
for name in names:
    me = bpy.data.meshes.new(name)
    me.materials.append(flat_material(name + '-mat', COLOURS[name]))
    bm = bmesh.new()
    add_box(bm, *(m(v) for v in SLABS[name]))
    finish(bm, me)
    statplat(name, me, visible=(name != 'tank-front'))

# 4. Lights: Directional + Ambient.
sun = bpy.data.objects['SunLight']
sun.location = (0.0, -0.6 * S, 0.6 * S)
sun.rotation_euler = (0.0, -math.radians(40.0), math.radians(-90.0))   # from the camera side, above
sun['wf_lightType'] = 'Directional'
for ch in ('Red', 'Green', 'Blue'):
    sun[f'wf_light{ch}'] = 0.45
amb = sun.copy()
scene.collection.objects.link(amb)
amb.name = 'AmbientLight'
amb['wf_lightType'] = 'Ambient'
for ch in ('Red', 'Green', 'Blue'):
    amb[f'wf_light{ch}'] = 0.55

# 5. Parked camera outside the front. Bungee aim = Target − Follow + Track Object, so all three
#    are LookAt (docs/level-building.md § CamShot, 2026-09-30 correction).
look = bpy.data.objects['LookAt']
look.location = LOOK_POS
look['wf_Model Type'] = 'None'
look['wf_Script'] = ''
cs = bpy.data.objects['cs_front']
cs.location = CAM_POS
for axis in ('X', 'Y', 'Z'):
    cs[f'wf_Position {axis}'] = 'Absolute'
cs['wf_Rotation'] = 'Fixed'
cs['wf_Follow'] = 'LookAt'
cs['wf_Target'] = 'LookAt'
cs['wf_Track Object'] = 'LookAt'
cs['wf_Model Type'] = 'None'
cs['wf_Script'] = '\\ wf\nINDEXOF_ACTOR_INDEX read-mailbox INDEXOF_CAMSHOT write-mailbox\n'
cam = bpy.data.objects['Camera']
cam.location = CAM_POS
cam['wf_Model Type'] = 'None'
cam['wf_FoggingColor'] = 0x000000                # fog off in the spike
cam['wf_FoggingStartDistance'] = 999.0
cam['wf_FoggingCompleteDistance'] = 1000.0

# 6. Scaffold leftovers out of frame, behind the camera.
director = bpy.data.objects['Director']
director['wf_Script'] = ''
director.location = (-0.4 * S, -2.0 * S, 0.1 * S)
bpy.data.objects['LevelObj'].location = (0.4 * S, -2.0 * S, 0.1 * S)
matte = bpy.data.objects['Matte']
matte.location = (0.0, -2.0 * S, 0.1 * S)
matte['wf_Matte Type'] = 'Color'
matte['wf_Background Color'] = 0x000000
matte['wf_Model Type'] = 'None'
room = bpy.data.objects['Room']
room.location = (0.0, 0.0, 0.0)
room['wf_original_bbox'] = (-2.0 * S, -3.0 * S, -1.0 * S, 2.0 * S, 2.0 * S, 2.0 * S)

print(f'[swim_spike] WORLD_SCALE={S} shell={"one" if SHELL_ONE else "slabs"} fish={"box" if FISH_BOX else "ellipsoid"} '
      f'fish spawn {tuple(round(v, 3) for v in player.location)} ZMAX={ZMAX:.4f} V={V:.4f} '
      f'inner x ±{m(IX):.4f} y ±{m(IY):.4f} sand {m(C.SAND_TOP):.4f} water {m(C.WATER_Z):.4f}')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCRIPT_DIR, LEVEL_NAME + '.blend'))
bpy.ops.wf.export_level(filepath=OUT_LEV)
print('[swim_spike] done')
