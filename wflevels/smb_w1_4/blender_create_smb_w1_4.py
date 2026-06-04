"""
blender_create_smb_w1_4.py — SMB World 1-4 (Castle).

Phase 1: castle corridor geometry, lava sections, floating platforms, ? block.
Phase 2 (TODO): fire-bars (_build_firebar × 7).
Phase 3 (TODO): Fake Bowser, axe, hidden ? blocks.
See docs/plans/2026-06-03-build-faithful-smb-w1-4.md.

Run headlessly:
  blender --background --python wflevels/smb_w1_4/blender_create_smb_w1_4.py
then  bash wftools/wf_blender/build_level_binary.sh smb_w1_4
"""

import bpy
import os
import math
import addon_utils

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS  = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'smb_w1_4.lev')
OAD_DIR    = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')

# ── Layout ────────────────────────────────────────────────────────────────────
T            = 1.5        # NES tile size in WF metres
FLOOR_Z      = 0.0        # top surface of castle floor
GROUND_THICK = T
GROUND_Y     = T          # Y half-extent for slabs
CEILING_Z    = 8 * T      # 12.0 m — underside of ceiling
LAVA_SURF_Z  = -2 * T    # -3.0 m — lava surface
LAVA_VIS_Z   = LAVA_SURF_Z - GROUND_THICK  # -4.5 m — lava tile bottom

# Mario
MARIO_SPAWN_X = 2 * T
MARIO_SPAWN_Z = FLOOR_Z + T
MARIO_Z       = FLOOR_Z + T
MARIO_FEET_Z  = FLOOR_Z
SMB_MARIO_VIS = 1864

# Level extents
LEVEL_X0    = 0.0
LEVEL_X1    = 160 * T     # 240 m
SCENE_MID_X = LEVEL_X1 / 2

# Stepping platforms across lava pit 1 (cols 14-32). Sized so every gap — entry
# edge → A → B → C → corridor edge — is ≤3 tiles (≤4.5 m), comfortably jumpable
# with the established Mario tuning. (col_start, col_end) per platform.
LAVA1_PLATS = [(16, 19), (21, 24), (26, 29)]

# Boss bridge stand-in (surface at floor level — TODO Phase 2: collapsing bridge).
# Extends to col 154 so it meets the toad floor (cols 154-160) with no lava gap —
# the celebration walks Mario rightward off the bridge, so the run-off must be solid.
BRIDGE_X0, BRIDGE_X1 = 122 * T, 154 * T

# Powerup ? block above lava-pit-1 platform B (col 22), hit-from-below at 4T
POWERUP_COL = 22
POWERUP_Z   = FLOOR_Z + 4 * T    # 6 m above floor

# Axe at the right end of the bridge (col 152). The end-of-level "flagpole"
# celebration is staged in the toad room (col 156) so Mario finishes on solid
# ground — placing it at the axe (over lava) drops him in the lava mid-cutscene.
AXE_COL    = 152
FLAGPOLE_X = 156 * T   # 234 m — toad-room floor (cols 154-160)

# Mario tint colours
FIRE_TINT          = 0xF8F0E0
MARIO_DEFAULT_TINT = 0xFFFFFF
STAR_FLASH_A       = 0xFFE000
STAR_FLASH_B       = 0xFFFFFF

# Level confinement bounds for camera ratchet
GROUND_X0 = LEVEL_X0
GROUND_X1 = LEVEL_X1

# Camera
CAM_Y       = -30.0
CAMSHOT_POS = (MARIO_SPAWN_X, CAM_Y, MARIO_Z + 3.0)
LOOKAT_POS  = (MARIO_SPAWN_X, 0.0,   MARIO_Z)

# Director
TIMER_UNITS      = 300
TIMER_REAL_SECONDS = 100.0
NUM_MAILBOXES    = 100

# Castle colour
BG_COLOR  = 0x1C1C1C     # dark charcoal interior
FOG_COLOR = 0x1C1C1C

# Mailbox constants (Python-side; engine uses INDEXOF_ prefix)
SMB_PLAYER_HURT = 1804    # INDEXOF_SMB_PLAYER_HURT

# ── 1. Clean scene & enable addon ─────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# ── Shared SMB builders ────────────────────────────────────────────────────────
import sys as _sys
_sys.path.insert(0, os.path.join(SCRIPT_DIR, '..'))
import smb_common
smb_common.init(scene, OAD_DIR)
from smb_common import (make_mat, attach_schema, find_by_class, get_class,
    add_box, add_statplat, _room_bounds_mesh,
    _make_qblock_tga, _make_brick_tga, _make_grid_tile_tga,
    build_textured_ground_mesh, _build_mario)
from smb_common import (_make_coin_template, _make_popup_template,
    _make_powerup_template, _make_powerup_block, _add_qblock)
from smb_common import (_make_fireball_generator, _make_fireball_template)
from smb_common import (_make_bowser_fireball_template, _make_bowser_fireball_generator,
    koopa_mesh)
from smb_common import (POWERUP_SCRIPT, AXE_SCRIPT, fakebowser_script)
from smb_common import (mat_castle, mat_lava, mat_axe, mat_hard)

# ── 2. Import snowgoons for infrastructure ────────────────────────────────────
print(f"[smb_w1_4] Importing snowgoons from {SNOWGOONS}")
bpy.ops.wf.import_level(filepath=SNOWGOONS)

# ── 3. Strip gameplay; keep one of each infrastructure class ──────────────────
KEEP_CLASSES   = {'director', 'camera', 'levelobj', 'matte', 'light',
                  'room', 'camshot', 'target', 'actboxor', 'player'}
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile',
                  'tool', 'tool01', 'ground01', 'hp', 'gold', 'generator'}
for obj in list(bpy.data.objects):
    if get_class(obj) in DELETE_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in KEEP_CLASSES:
        if cn in seen:
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            seen.add(cn)
print("[smb_w1_4] Classes after strip:", sorted({get_class(o) for o in bpy.data.objects}))

# ── 4. Configure infrastructure actors ────────────────────────────────────────
director = find_by_class('director')
if director:
    director.location = (0, CAM_Y - 2, MARIO_Z)
    director['wf_Model Type'] = 'None'
    director['wf_Script'] = smb_common.director_script(
        {'FLAGPOLE_X': FLAGPOLE_X, 'TIMER_UNITS': TIMER_UNITS,
         'TIMER_REAL_SECONDS': TIMER_REAL_SECONDS})

levelobj = find_by_class('levelobj')
if levelobj:
    levelobj.location = (0, CAM_Y - 2, MARIO_Z)
    levelobj['wf_Number Of Mailboxes'] = NUM_MAILBOXES
    levelobj['wf_Model Type'] = 'None'

matte = find_by_class('matte')
if matte:
    matte.location = (SCENE_MID_X, CAM_Y - 2, MARIO_Z)
    matte['wf_Matte Type']         = 'Color'
    matte['wf_Background Color']   = BG_COLOR
    matte['wf_Visibility Mailbox'] = 1
    matte['wf_Model Type']         = 'None'

camera = find_by_class('camera')
if camera:
    camera.location = CAMSHOT_POS
    camera['wf_FoggingStartDistance']    = 150.0
    camera['wf_FoggingCompleteDistance'] = 250.0
    camera['wf_FoggingColor']            = FOG_COLOR
    camera['wf_Model Type']              = 'None'

light = find_by_class('light')
if light:
    light.location       = (SCENE_MID_X, CAM_Y + 8, MARIO_Z + 12)
    light.rotation_euler = (math.pi / 3, 0, 0)
    light.name = 'Light01'
    light['wf_lightType']  = 'Directional'
    light['wf_lightRed']   = 1.0
    light['wf_lightGreen'] = 1.0
    light['wf_lightBlue']  = 1.0

# ── 5. Castle geometry ────────────────────────────────────────────────────────
# Floor tiles use build_textured_ground_mesh (bakes scale into vertices) so the
# Jolt MESH_STATIC body has correct world-space geometry.  add_statplat leaves
# mesh vertices at ±0.5 local space; the resulting MESH body only covers a 1 m³
# cube and the character falls through despite the correct BOX body.
castle_tile_tex = _make_grid_tile_tga(
    os.path.join(SCRIPT_DIR, 'grid_tile.tga'),
    bg=(70, 70, 78), fg=(40, 40, 46))   # dark gray castle stone (not overworld brown)

def _castle_floor(name, col_start, col_end):
    """Solid textured gray floor slab, top surface at FLOOR_Z."""
    mesh = build_textured_ground_mesh(
        f'w1_4_{name}_floor',
        col_start * T, -GROUND_Y, FLOOR_Z - GROUND_THICK,
        col_end   * T,  GROUND_Y, FLOOR_Z,
        castle_tile_tex)
    obj = bpy.data.objects.new(f'floor_{name}', mesh)
    obj.location = (0.0, 0.0, 0.0)
    scene.collection.objects.link(obj)
    attach_schema(obj, 'statplat')
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Model Type'] = 'Mesh'

def _actbox_death(name, x0, x1, z_top=LAVA_SURF_Z):
    """Death ActBox spanning x0..x1 below z_top → SMB_PLAYER_HURT."""
    cx = (x0 + x1) / 2.0
    hx = (x1 - x0) / 2.0 + 0.5
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(cx, 0.0, z_top - 5.0))
    sensor = bpy.context.object
    sensor.name = name
    sensor.data.name = f'w1_4_{name}'
    sensor.scale = (hx, GROUND_Y + 1.0, 7.5)
    bpy.ops.object.transform_apply(scale=True)
    attach_schema(sensor, 'actbox')
    sensor['wf_Visibility Mailbox']      = 1
    sensor['wf_MailBox']                 = SMB_PLAYER_HURT
    sensor['wf_MailBoxValue']            = 1
    sensor['wf_Activated By Actor']      = 'Player'
    sensor['wf_Activated Actor Mailbox'] = 4005

def _lava_section(name, col_start, col_end):
    """Orange lava visual + death ActBox. Mario falls into lava → SMB_PLAYER_HURT."""
    add_statplat(f'w1_4_{name}_lava',
                 col_start * T, -GROUND_Y, LAVA_VIS_Z,
                 col_end   * T,  GROUND_Y, LAVA_SURF_Z,
                 mat_lava())
    _actbox_death(f'{name}_death', col_start * T, col_end * T)

# Floor sections — textured ground mesh (baked scale → correct Jolt MESH body)
_castle_floor('entry', 0,   14)
_castle_floor('corr',  32, 120)
_castle_floor('toad', 154, 160)

# Full-level fallback death sensor: catches Mario anywhere he falls below floor.
# z_top = -3 (2 tiles below floor) so feet at Z=0 are safe; triggers when feet < -0.5.
_actbox_death('fallback_death', LEVEL_X0, LEVEL_X1, z_top=-3.0)

# Ceiling spans the entire castle (single unbroken slab). Kept INVISIBLE — it is a
# jump barrier (collision), not scenery; rendered, its lit underside washed the
# mid-level view bright. The dark matte reads as the castle interior overhead.
_ceil = add_statplat('w1_4_ceil',
                     LEVEL_X0, -GROUND_Y, CEILING_Z,
                     LEVEL_X1,  GROUND_Y, CEILING_Z + GROUND_THICK,
                     mat_castle())
_ceil['wf_Visibility Mailbox'] = 0

# Lava sections (visual + per-section death sensor)
_lava_section('pit1',  14,  32)
_lava_section('boss', 120, 154)

# Floating platforms over lava — textured mesh for correct Jolt body.
# 3 stepping stones across lava pit 1 + the wide boss bridge stand-in.
_PLATFORMS = [(f'plat1_{_i}', c0 * T, c1 * T) for _i, (c0, c1) in enumerate(LAVA1_PLATS)]
_PLATFORMS.append(('boss_bridge', BRIDGE_X0, BRIDGE_X1))
for _pname, _px0, _px1 in _PLATFORMS:
    _pmesh = build_textured_ground_mesh(
        f'w1_4_{_pname}',
        _px0, -GROUND_Y, FLOOR_Z - GROUND_THICK,
        _px1,  GROUND_Y, FLOOR_Z,
        castle_tile_tex)
    _pobj = bpy.data.objects.new(f'plat_{_pname}', _pmesh)
    _pobj.location = (0.0, 0.0, 0.0)
    scene.collection.objects.link(_pobj)
    attach_schema(_pobj, 'statplat')
    _pobj['wf_Visibility Mailbox'] = 1
    _pobj['wf_Model Type'] = 'Mesh'

# ── 6. Mario ──────────────────────────────────────────────────────────────────
player = find_by_class('player')
if player:
    player.name = 'Player'
    player.location = (MARIO_SPAWN_X, 0.0, MARIO_SPAWN_Z)
    player['wf_Mobility']              = 'Physics'
    player['wf_Mass']                  = 1.0
    player['wf_Model Type']            = 'Mesh'
    player['wf_Visibility Mailbox']    = SMB_MARIO_VIS
    player['wf_Turn Rate']             = 0.0
    player.rotation_euler.z            = math.pi / 2
    player['wf_Script'] = smb_common.player_script(
        {'CR_ENTRY_X': 0.0, 'CR_ENTRY_Z': -100.0,
         'FIRE_TINT': FIRE_TINT, 'FLAGPOLE_X': FLAGPOLE_X,
         'GROUND_X0': GROUND_X0, 'GROUND_X1': GROUND_X1, 'GROUND_Y': GROUND_Y,
         'MARIO_DEFAULT_TINT': MARIO_DEFAULT_TINT,
         'MARIO_SPAWN_X': MARIO_SPAWN_X, 'MARIO_SPAWN_Z': MARIO_SPAWN_Z,
         'STAR_FLASH_A': STAR_FLASH_A, 'STAR_FLASH_B': STAR_FLASH_B})
    mario_mesh = _build_mario()
    old = player.data
    player.data = mario_mesh.data
    bpy.data.objects.remove(mario_mesh, do_unlink=True)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

# ── 7. Templates ──────────────────────────────────────────────────────────────
qblock_tex = _make_qblock_tga(os.path.join(SCRIPT_DIR, 'qblock_tex.tga'))
smb_common.set_textures(qblock=qblock_tex)
brick_tex  = _make_brick_tga(os.path.join(SCRIPT_DIR, 'brick_tex.tga'))
smb_common.set_textures(brick=brick_tex)

_make_coin_template()
_make_popup_template()
mat_powerup = make_mat('powerup_red', (0.85, 0.16, 0.12))
_make_powerup_template('powerup_template', mat_powerup, POWERUP_SCRIPT, 0.0, -55.0)
_make_fireball_template()
SMB_FIREBALL_FIRE_R, SMB_FIREBALL_FIRE_L = 1823, 1824
_make_fireball_generator('fireball_gen_r', SMB_FIREBALL_FIRE_R,  12.0)   # Fire Mario fires right
_make_fireball_generator('fireball_gen_l', SMB_FIREBALL_FIRE_L, -12.0)   # Fire Mario fires left

# ── 8. Powerup block (above lava pit 1 platform) ──────────────────────────────
# Mushroom if Small, Fire Flower if Super — same self-determining powerup_template as W1-1/W1-2.
_make_powerup_block('w14_powerup', POWERUP_COL * T, 'powerup_template', 0.0, z=POWERUP_Z)

# ── Phase 2: Fire-Bars ─────────────────────────────────────────────────────────
# A fire-bar = 1 small hard-block pivot + N orbiting lava-cube segments. Each
# segment is an Anchored 'enemy' running firebar_segment_script (symplectic-Euler
# orbit around the pivot + lethal proximity). All segments share one mesh datablock.
N_SEGS         = 5
SEG_SPACING_T  = 0.4          # tiles between segments → max radius N*0.4 = 2T
SEG_HALF       = 0.2 * T      # segment cube half-extent (≈ spacing → continuous bar)
FIREBAR_OMEGA  = 2.4          # rad/s → ~2.6 s per revolution (faithful NES cadence)

# Build one shared fire-segment datablock (small orange lava cube).
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
_seg = bpy.context.object
_seg.scale = (SEG_HALF, SEG_HALF, SEG_HALF)
bpy.ops.object.transform_apply(scale=True)
_seg.data.materials.clear()
_seg.data.materials.append(mat_lava())
for _p in _seg.data.polygons:
    _p.material_index = 0
_seg.name = 'firebar_seg'; _seg.data.name = 'firebar_seg'
_firebar_seg_data = _seg.data
bpy.data.objects.remove(_seg, do_unlink=True)
_firebar_n = [0]


def _build_firebar(name, pivot_col, pivot_z_tiles, omega, initial_angle_deg=0.0,
                   n_segs=N_SEGS):
    """Place a fire-bar: a solid pivot block + n_segs orbiting lava segments."""
    px = pivot_col * T
    pz = pivot_z_tiles * T
    # Pivot — small solid hard block marking the hub (faithful: fire-bar centres
    # are solid blocks Mario must navigate around).
    add_box(f'{name}_pivot',
            px - 0.4 * T, -GROUND_Y, pz - 0.4 * T,
            px + 0.4 * T,  GROUND_Y, pz + 0.4 * T,
            mat_hard())
    script = smb_common.firebar_segment_script(px, pz, omega)
    theta0 = math.radians(initial_angle_deg)
    for k in range(1, n_segs + 1):
        r  = k * SEG_SPACING_T * T
        sx = px + r * math.cos(theta0)
        sz = pz + r * math.sin(theta0)
        seg = bpy.data.objects.new(f'{name}_seg{k}', _firebar_seg_data)
        scene.collection.objects.link(seg)
        seg.location = (sx, 0.0, sz)
        attach_schema(seg, 'enemy')
        seg['wf_Mobility']                  = 'Anchored'
        seg['wf_Model Type']                = 'Mesh'
        seg['wf_Visibility Mailbox']        = 1
        seg['wf_Number Of Local Mailboxes'] = 0      # pivot baked in script; uses globals
        seg['wf_Script']                    = script
        _firebar_n[0] += 1


# 7 fire-bars (col, pivot_z_tiles, omega, initial_angle_deg). Floor/platform bars
# pivot at Z=2T (sweep 0..4T, lower arc grazes the floor); ceiling bars at Z=6T
# (sweep 4..8T, upper arc tucks into the ceiling). Alternate spin + start angle so
# the seven don't beat in unison.
_FIREBARS = [
    ('fb1', 22, 2,  FIREBAR_OMEGA,   0.0),   # lava-pit-1 platform
    ('fb2', 42, 2, -FIREBAR_OMEGA,  90.0),   # corridor floor
    ('fb3', 50, 6,  FIREBAR_OMEGA,   0.0),   # corridor ceiling
    ('fb4', 58, 2,  FIREBAR_OMEGA,  45.0),   # corridor floor
    ('fb5', 66, 6, -FIREBAR_OMEGA, 135.0),   # corridor ceiling
    ('fb6', 76, 2,  FIREBAR_OMEGA,   0.0),   # fire-bar room low
    ('fb7', 84, 6, -FIREBAR_OMEGA,  90.0),   # fire-bar room high
]
for _fbname, _fbcol, _fbz, _fbom, _fbang in _FIREBARS:
    _build_firebar(_fbname, _fbcol, _fbz, _fbom, _fbang)
print(f"[smb_w1_4] fire-bar segments placed: {_firebar_n[0]} "
      f"(7 bars × {N_SEGS} = {7 * N_SEGS})")

# ── Phase 3: Hidden-chamber coin blocks, Fake Bowser, axe ────────────────────
# 6 coin ? blocks in the chamber before the boss (cols 94-109, hit from below).
# (True invisible-until-bump is deferred; these are visible coin blocks for now.)
for _hc in (94, 97, 100, 103, 106, 109):
    _add_qblock(f'w14_coinblk_{_hc}', _hc * T, z=FLOOR_Z + 5 * T)

# Fake Bowser — big Physics boss patrolling the boss bridge (cols 122-152). Reuses
# the koopa_green datablock at 2× scale. Walks + lobs fireballs + 5 HP; defeated by
# the axe or 5 Mario fireballs. Bridge rails inset 2 tiles from each bridge end.
BOWSER_COL = 138
BRIDGE_L_RAIL = (122 + 2) * T
BRIDGE_R_RAIL = (152 - 2) * T
bowser = koopa_mesh('bowser', red=False)
bowser.location = (BOWSER_COL * T, 0.0, FLOOR_Z)
bowser.scale = (2.0, 2.0, 2.0)                       # 2× — render + collision (OAS Scale)
attach_schema(bowser, 'enemy')
bowser['wf_Mobility']                  = 'Physics'
bowser['wf_Mass']                      = 4.0
bowser['wf_Turn Rate']                 = 0.0   # → MarbleHandler: carries the script's XSPEED
bowser['wf_Running Deceleration']      = 0.0   # frictionless so the walk velocity isn't bled off
bowser['wf_Max Air Speed']             = 50.0  # don't let the speed cap zero gravity (marble bug)
bowser['wf_Falling Acceleration']      = 12.0
bowser['wf_Model Type']                = 'Mesh'
bowser['wf_Visibility Mailbox']        = 1
bowser['wf_Max Ground Speed']          = 8.0
bowser['wf_Number Of Local Mailboxes'] = 23          # LOCAL_BOWSER_HP/HIT_COOL/FIRE_T (2020-2022)
bowser['wf_Script'] = fakebowser_script(BRIDGE_L_RAIL, BRIDGE_R_RAIL,
                                        walk_speed=2.0, fire_interval=2.5)

# Bowser's fireball template + a fixed generator at the bridge centre.
_make_bowser_fireball_template()
_make_bowser_fireball_generator('bowser_fb_gen', BOWSER_COL * T, FLOOR_Z + 0.8 * T)

# The axe at the right end of the bridge (col 152). A gold box; Anchored + script
# so Mario passes through it. Touch → SMB_CELEBRATE → celebration → level end.
_axe_half = 0.35 * T
_axe_z = FLOOR_Z + 1.0 * T
_axe = add_box('w14_axe',
               AXE_COL * T - _axe_half, -GROUND_Y, _axe_z - _axe_half,
               AXE_COL * T + _axe_half,  GROUND_Y, _axe_z + _axe_half,
               smb_common.mat_axe())
attach_schema(_axe, 'enemy')
_axe['wf_Mobility']           = 'Anchored'
_axe['wf_Model Type']         = 'Mesh'
_axe['wf_Visibility Mailbox'] = 1
_axe['wf_Script']             = AXE_SCRIPT

# ── 9. Celebration ────────────────────────────────────────────────────────────
# SMB_CELEBRATE fires when the axe is touched (Phase 3). The Director's celebration
# sequencer then runs the cutscene and writes END_OF_LEVEL after ~4.5 s.
# NEXT_LEVEL_INDEX=0 → loops back to W1-1 (W1-5 doesn't exist yet).
smb_common.celebration({'FLAGPOLE_X': FLAGPOLE_X, 'NEXT_LEVEL_INDEX': 0})

# ── 10. CamShot + Targets + actboxor ──────────────────────────────────────────
camshot = find_by_class('camshot')
if camshot:
    camshot.location = CAMSHOT_POS
    camshot.name = 'cs_side'
    camshot['wf_Position X']          = 'Absolute'
    camshot['wf_Position Y']          = 'Absolute'
    camshot['wf_Position Z']          = 'Absolute'
    camshot['wf_Rotation']            = 'Fixed'
    camshot['wf_FOV']                 = 35.0
    camshot['wf_Pan Time In Seconds'] = 0.1
    camshot['wf_Model Type']          = 'None'
    camshot['wf_Track Object']        = 'Player'
    camshot['wf_Target']              = 'Target02'
    camshot['wf_Follow']              = 'Target02'
    camshot['wf_Script'] = (
        "\\ wf\n"
        "INDEXOF_SMB_TARGET_CAM_X read-mailbox INDEXOF_X_POS write-mailbox\n"
    )

targets = [o for o in bpy.data.objects if get_class(o) == 'target']
while len(targets) < 2:
    tn = bpy.data.objects.new(f'Target_new_{len(targets)}', None)
    scene.collection.objects.link(tn)
    attach_schema(tn, 'target')
    targets.append(tn)
targets[0].location = (0.0, 0.0, 0.0); targets[0].name = 'Target01'; targets[0]['wf_Model Type'] = 'None'
targets[1].location = LOOKAT_POS;       targets[1].name = 'Target02'; targets[1]['wf_Model Type'] = 'None'

# Camera zone (actboxor) activates cs_side when Mario is anywhere in the castle
actboxor = find_by_class('actboxor')
if actboxor:
    bpy.data.objects.remove(actboxor, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(SCENE_MID_X, 0.0, CEILING_Z / 2))
abs_ = bpy.context.object
abs_.name = 'abor_surface'; abs_.data.name = 'w1_4_abor_surface'
abs_.scale = (LEVEL_X1 / 2 + 6.0, GROUND_Y + 2.0, CEILING_Z / 2 + 4.0)
bpy.ops.object.transform_apply(scale=True)
attach_schema(abs_, 'actboxor')
abs_['wf_MailBox']            = 1921   # INDEXOF_SMB_CAMSHOT
abs_['wf_Object']             = 'cs_side'
abs_['wf_Activated By Actor'] = 'Player'
abs_['wf_Model Type']         = 'None'

# ── 11. Room bbox ──────────────────────────────────────────────────────────────
ROOM_CENTRE   = (SCENE_MID_X, 0.0, CEILING_Z / 2)
_hx = LEVEL_X1 / 2 + 5.0
ROOM_BBOX_REL = (-_hx, -35.0, -15.0, _hx, 10.0, CEILING_Z + 5.0)
room = find_by_class('room')
if room:
    room.name = 'room_surface'
    room.location = ROOM_CENTRE
    room['wf_original_bbox'] = ROOM_BBOX_REL
    old = room.data
    room.data = _room_bounds_mesh('RoomBounds', ROOM_BBOX_REL)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)
    room['wf_Adjacent Room 1'] = ''
    room['wf_Adjacent Room 2'] = ''

# ── 12. Export ────────────────────────────────────────────────────────────────
SMB_MESH_DIR = os.path.join(REPO, 'wflevels', 'smb')
print(f"[smb_w1_4] Exporting to {OUT_LEV} (meshes → {SMB_MESH_DIR})")
bpy.ops.wf.export_level(filepath=OUT_LEV, mesh_dir=SMB_MESH_DIR)
print("[smb_w1_4] Objects in scene:", len(bpy.data.objects))
print(f"[smb_w1_4] Done — {OUT_LEV}")
