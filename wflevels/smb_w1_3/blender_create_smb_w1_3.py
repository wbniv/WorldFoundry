"""
blender_create_smb_w1_3.py — create the smb_w1_3 level (SMB World 1-3, "Athletic").

W1-3 is the inverse of W1-1/W1-2: instead of continuous ground with a few pits, it is a
continuous BOTTOMLESS PIT spanned by green tree-top (mushroom) islands — the only footing.
Fall = death. Faithful per docs/smb-level-layouts.md §1-3 + MarioWiki:
  3 green Koopa Troopas, 2 green Koopa Paratroopas, 3 Goombas, 23 open-air coins,
  1 ? block (Mushroom/Fire-Flower), no pipes / no underground.

Moving platforms (1 lift + 2 horizontal movers) are STATIC stand-ins this pass — the Jolt
ground-velocity carry that would make them rideable is a tracked TODO (the level ships
complete and traversable; static stepping platforms stand in for the movers).
See docs/plans/2026-06-03-build-faithful-smb-w1-3.md.

Geometry: T = 1.5 m per NES tile. Ground surface Z=0. Camera: classic SMB side-scroll
(Director deadzone + one-way ratchet + edge clamp + lead → SMB_TARGET_CAM_X → CamShot).

Run headlessly:
  blender --background --python wflevels/smb_w1_3/blender_create_smb_w1_3.py
then  bash wftools/wf_blender/build_level_binary.sh smb_w1_3
"""

import bpy
import os
import math
import addon_utils

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS  = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'smb_w1_3.lev')
OAD_DIR    = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')

# ── Layout (T = NES tile size in WF metres) ───────────────────────────────────
T = 1.5
GROUND_TOP_Z  = 0.0
GROUND_THICK  = T
MARIO_Z       = GROUND_TOP_Z + T          # reference Mario body-centre height
MARIO_FEET_Z  = GROUND_TOP_Z
MARIO_SPAWN_Z = MARIO_FEET_Z + T
MARIO_SPAWN_X = 3 * T
FLAGPOLE_X    = 155 * T                    # 232.5 — faithful col ~155 (164-tile level)

# Mario tint colours the player script drives (Fire-Mario warm-white + Star flicker).
FIRE_TINT          = 0xF8F0E0
MARIO_DEFAULT_TINT = 0xFFFFFF
STAR_FLASH_A       = 0xFFE000
STAR_FLASH_B       = 0xFFFFFF

# ── Celebration mailboxes (flagpole end-of-level cutscene; same as W1-1/W1-2) ──
SMB_MARIO_VIS = 1864

# Ground: a small START strip (Mario spawns here) and an END strip (staircase + flagpole +
# castle). Everything between is open sky over a death pit — the tree-tops are the footing.
START_X0, START_X1 = -2 * T, 8 * T          # spawn strip
END_X0,   END_X1   = 135 * T, FLAGPOLE_X + 7 * T   # 202.5 .. 243 — staircase/flag/castle
GROUND_X0 = START_X0
GROUND_X1 = END_X1
GROUND_Y  = T

# One continuous bottomless pit between the two ground strips. A single invisible
# pit-death sensor under it (Z band [-15,-1]) costs a life on any fall — the level's
# defining hazard. (Standing on a tree-top lip, origin Z≈top_z+T, never overlaps the band.)
PIT_X0, PIT_X1 = START_X1, END_X0           # 12 .. 202.5

TIMER_UNITS        = 300                     # SMB W1-3 starts at 300
TIMER_REAL_SECONDS = 120.0
SCENE_MID_X = (GROUND_X0 + GROUND_X1) / 2

CAM_Y = -30.0
CAMSHOT_POS = (MARIO_SPAWN_X, CAM_Y, MARIO_Z + 3.0)
LOOKAT_POS  = (MARIO_SPAWN_X, 0.0,   MARIO_Z)
NUM_MAILBOXES = 100

# ── 1. Clean scene & enable addon ─────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# ── Shared SMB builders (wflevels/smb_common.py — levels share, cannot drift) ──
import sys as _sys
_sys.path.insert(0, os.path.join(SCRIPT_DIR, '..'))
import smb_common
smb_common.init(scene, OAD_DIR)
from smb_common import (make_mat, attach_schema, find_by_class, get_class,
    add_box, add_statplat, add_treetop, _add_textured_box, _make_qblock_tga,
    _make_brick_tga, _make_grid_tile_tga, build_textured_ground_mesh, _room_bounds_mesh,
    _build_mario)
from smb_common import (_make_powerup_block, koopa_mesh, paratroopa_mesh)
from smb_common import (_make_coin_template, _make_powerup_template, _make_popup_template,
    _add_staircase)
from smb_common import (_apply_enemy_movement, _build_goomba, _make_target)
from smb_common import (KOOPA_SCRIPT, PARATROOPA_SCRIPT, COIN_PICKUP_SCRIPT, POWERUP_SCRIPT)

# ── 2. Import snowgoons for infrastructure ────────────────────────────────────
print(f"[smb_w1_3] Importing snowgoons from {SNOWGOONS}")
bpy.ops.wf.import_level(filepath=SNOWGOONS)

# ── 3. Strip gameplay; keep one of each infrastructure class ───────────────────
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
print("[smb_w1_3] Classes after strip:", sorted({get_class(o) for o in bpy.data.objects}))

# ── 4. Configure infrastructure actors ────────────────────────────────────────
director = find_by_class('director')
if director:
    director.location = (0, CAM_Y - 2, MARIO_Z)
    director['wf_Model Type'] = 'None'
    director['wf_Script'] = smb_common.director_script(
        {'FLAGPOLE_X': FLAGPOLE_X, 'TIMER_UNITS': TIMER_UNITS, 'TIMER_REAL_SECONDS': TIMER_REAL_SECONDS})

levelobj = find_by_class('levelobj')
if levelobj:
    levelobj.location = (0, CAM_Y - 2, MARIO_Z)
    levelobj['wf_Number Of Mailboxes'] = NUM_MAILBOXES
    levelobj['wf_Model Type'] = 'None'

matte = find_by_class('matte')
if matte:
    matte.location = (SCENE_MID_X, CAM_Y - 2, MARIO_Z)
    matte['wf_Matte Type'] = 'Color'
    matte['wf_Background Color'] = 0x5C94FC   # SMB daytime sky blue (overworld, not cave)
    matte['wf_Visibility Mailbox'] = 1
    matte['wf_Model Type'] = 'None'

camera = find_by_class('camera')
if camera:
    camera.location = CAMSHOT_POS
    camera['wf_FoggingStartDistance']    = 150.0
    camera['wf_FoggingCompleteDistance'] = 250.0
    camera['wf_FoggingColor']            = 0x5C94FC
    camera['wf_Model Type'] = 'None'

light = find_by_class('light')
if light:
    light.location       = (SCENE_MID_X, CAM_Y + 8, MARIO_Z + 12)
    light.rotation_euler = (math.pi / 3, 0, 0)
    light.name = 'Light01'
    light['wf_lightType']  = 'Directional'
    light['wf_lightRed']   = 1.0
    light['wf_lightGreen'] = 1.0
    light['wf_lightBlue']  = 1.0

# ── 5. Ground strips (start + end) + the continuous pit-death sensor ──────────
grid_tex_path = _make_grid_tile_tga(os.path.join(SCRIPT_DIR, 'grid_tile.tga'))
SMB_PLAYER_HURT = 1804   # INDEXOF_SMB_PLAYER_HURT

for _i, (_sx0, _sx1) in enumerate([(START_X0, START_X1), (END_X0, END_X1)]):
    seg_mesh = build_textured_ground_mesh(
        f'w1_3_ground_{_i}',
        _sx0, -GROUND_Y, GROUND_TOP_Z - GROUND_THICK,
        _sx1,  GROUND_Y, GROUND_TOP_Z,
        grid_tex_path)
    seg_obj = bpy.data.objects.new(f'ground_{_i}', seg_mesh)
    seg_obj.location = (0.0, 0.0, 0.0)
    scene.collection.objects.link(seg_obj)
    attach_schema(seg_obj, 'statplat')
    seg_obj['wf_Visibility Mailbox'] = 1
    seg_obj['wf_Model Type'] = 'Mesh'

# Single pit-death sensor spanning the whole middle (invisible ActBox, Z band [-15,-1]).
_pcx = (PIT_X0 + PIT_X1) / 2.0
_phx = (PIT_X1 - PIT_X0) / 2.0 + 0.5
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(_pcx, 0.0, -8.0))
pit = bpy.context.object
pit.name = 'pit_death_0'; pit.data.name = 'w1_3_pit_death_0'
pit.scale = (_phx, GROUND_Y, 7.0)   # half-extents → Z band [-15, -1]
bpy.ops.object.transform_apply(scale=True)
attach_schema(pit, 'actbox')
pit['wf_MailBox']            = SMB_PLAYER_HURT
pit['wf_MailBoxValue']       = 1
pit['wf_Activated By Actor'] = 'Player'
pit['wf_Activated Actor Mailbox'] = 4005

# ── 6. Mario ──────────────────────────────────────────────────────────────────
player = find_by_class('player')
if player:
    player.name = 'Player'
    player.location = (MARIO_SPAWN_X, 0.0, MARIO_SPAWN_Z)
    player['wf_Mobility'] = 'Physics'
    player['wf_Mass']     = 1.0
    player['wf_Model Type'] = 'Mesh'
    player['wf_Visibility Mailbox'] = SMB_MARIO_VIS
    player['wf_Moves Between Rooms'] = 'True'
    # SMB-feel physics (identical tuning to W1-1/W1-2; see those scripts for the derivation).
    player['wf_Running Acceleration']  = 60.0
    player['wf_Running Deceleration']  = 0.18    # steady ≈ 11.1 m/s
    player['wf_Max Ground Speed']      = 32.0
    player['wf_Jumping Acceleration']  = 60.0
    player['wf_Falling Acceleration']  = 12.0
    player['wf_Air Acceleration']      = 0.0
    player['wf_Max Air Speed']         = 32.0
    player['wf_Horiz Air Drag']        = 3.0
    player['wf_Turn Rate']             = 0.0
    player.rotation_euler.z            = math.pi / 2   # C=π/2 → faces +Y, strafes ±X
    player['wf_Script'] = smb_common.player_script(
        {'CR_ENTRY_X': 0.0, 'CR_ENTRY_Z': -100.0, 'FIRE_TINT': FIRE_TINT, 'FLAGPOLE_X': FLAGPOLE_X,
         'GROUND_X0': GROUND_X0, 'GROUND_X1': GROUND_X1, 'GROUND_Y': GROUND_Y,
         'MARIO_DEFAULT_TINT': MARIO_DEFAULT_TINT, 'MARIO_SPAWN_X': MARIO_SPAWN_X,
         'MARIO_SPAWN_Z': MARIO_SPAWN_Z, 'STAR_FLASH_A': STAR_FLASH_A, 'STAR_FLASH_B': STAR_FLASH_B})
    mario_mesh = _build_mario()
    old = player.data
    player.data = mario_mesh.data
    bpy.data.objects.remove(mario_mesh, do_unlink=True)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

# ── 7. Flagpole + castle + fireworks + triggers (shared celebration) ──────────
# NEXT_LEVEL_INDEX = 3 → advance to W1-4 (cd.iff level 3). The loop is now
# W1-1(0)→W1-2(1)→W1-3(2)→W1-4(3)→W1-1(0); W1-4's axe writes 0 to close it.
smb_common.celebration({'FLAGPOLE_X': FLAGPOLE_X, 'NEXT_LEVEL_INDEX': 3})

# ── 8. CamShot + Targets + surface camera zone ────────────────────────────────
camshot = find_by_class('camshot')
if camshot:
    camshot.location = CAMSHOT_POS
    camshot.name = 'cs_side'
    camshot['wf_Position X'] = 'Absolute'
    camshot['wf_Position Y'] = 'Absolute'
    camshot['wf_Position Z'] = 'Absolute'
    camshot['wf_Rotation']   = 'Fixed'
    camshot['wf_FOV']                 = 35.0
    camshot['wf_Pan Time In Seconds'] = 0.1
    camshot['wf_Model Type']          = 'None'
    camshot['wf_Track Object'] = 'Player'
    camshot['wf_Target']       = 'Target02'
    camshot['wf_Follow']       = 'Target02'
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

actboxor = find_by_class('actboxor')
if actboxor:
    bpy.data.objects.remove(actboxor, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(SCENE_MID_X, 0.0, 8.0))
abs_ = bpy.context.object
abs_.name = 'abor_surface'; abs_.data.name = 'w1_3_abor_surface'
abs_.scale = ((GROUND_X1 - GROUND_X0)/2 + 6.0, GROUND_Y + 2.0, 16.0)   # tall: covers the high tree-tops
bpy.ops.object.transform_apply(scale=True)
attach_schema(abs_, 'actboxor')
abs_['wf_MailBox']            = 1921
abs_['wf_Object']             = 'cs_side'
abs_['wf_Activated By Actor'] = 'Player'
abs_['wf_Model Type']         = 'None'

# ── 9. Room bbox (single room; tree-tops reach ~9T so Z spans high) ───────────
ROOM_CENTRE = (SCENE_MID_X, 0.0, 8.0)
_half_span  = (GROUND_X1 - GROUND_X0) / 2 + 5
ROOM_BBOX_REL = (-_half_span, -35.0, -23.0, _half_span, 10.0, 22.0)   # Z world [-15,30]
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

# ══════════════════════════════════════════════════════════════════════════════
# W1-3 POPULATION — tree-top islands over the pit (docs/smb-level-layouts.md §1-3).
# Island spec: (centre_col, width_tiles, top_z_tiles). Gaps kept ≤ ~4 tiles (jumpable).
# ══════════════════════════════════════════════════════════════════════════════
BSIZE = T / 2
qblock_tex = _make_qblock_tga(os.path.join(SCRIPT_DIR, 'qblock_tex.tga'))
smb_common.set_textures(qblock=qblock_tex)
brick_tex  = _make_brick_tga(os.path.join(SCRIPT_DIR, 'brick_tex.tga'))   # generated for pipeline parity
smb_common.set_textures(brick=brick_tex)
mat_hard = smb_common.mat_hard()

# ── Templates (one each, parked off-screen / template-flagged — never rendered) ──
_make_coin_template()
_make_popup_template()
mat_powerup = make_mat('powerup_red', (0.85, 0.16, 0.12))
_make_powerup_template('powerup_template', mat_powerup, POWERUP_SCRIPT, 0.0, -55.0)
_coin_mesh = bpy.data.meshes['coin_template']
_coin_n = [0]


def _add_coin(x, z):
    """Open-air collectible: Anchored Enemy disc sharing the coin_template datablock; spins
    and self-collects on player proximity (+200 score, despawn). No parking, no per-coin
    global — COIN_PICKUP_SCRIPT reads the SMB_PLAYER_X/Z broadcasts and latches via the
    per-actor SMB_COIN_TAKEN_L. See project_smb_parked_helper_visibility."""
    c = bpy.data.objects.new(f'coin_{_coin_n[0]:02d}', _coin_mesh)
    _coin_n[0] += 1
    scene.collection.objects.link(c)
    c.location = (x, 0.0, z)
    attach_schema(c, 'enemy')
    c['wf_Mobility']                  = 'Anchored'
    c['wf_Model Type']                = 'Mesh'
    c['wf_Visibility Mailbox']        = 1     # visible until collected; pickup despawns (ALIVE=0)
    c['wf_Number Of Local Mailboxes'] = 20    # SMB_COIN_TAKEN_L = 2019
    c['wf_Script']                    = COIN_PICKUP_SCRIPT
    return c


_koopa_n = [0]


def _build_koopa(name, col, top_tiles):
    """Green Koopa Troopa resting on a canopy at `col`. Physics → it walks left (KOOPA_SCRIPT)
    and, like a real 1-3 green Koopa, can stroll off a narrow tree-top edge into the pit."""
    ko = koopa_mesh(name, red=False)
    ko.location = (col*T, 0.0, GROUND_TOP_Z + top_tiles*T + 0.5*T)   # drop onto the canopy
    attach_schema(ko, 'enemy')
    _apply_enemy_movement(ko)
    ko['wf_Script']           = KOOPA_SCRIPT
    ko['wf_Max Ground Speed'] = 16.0
    ko['wf_Number Of Local Mailboxes'] = 19   # per-actor shell state (SMB_KOOPA_STATE_L 2018)
    return ko


def _build_paratroopa(name, col, z=None):
    """Green Koopa Paratroopa hovering over a gap: Anchored, bounces vertically in place
    (PARATROOPA_SCRIPT). Stomp defeats it; a side touch hurts Mario."""
    if z is None:
        z = MARIO_Z + 2.0*T
    pa = paratroopa_mesh(name)
    pa.location = (col*T, 0.0, z)
    attach_schema(pa, 'enemy')
    pa['wf_Mobility']                  = 'Anchored'
    pa['wf_Model Type']                = 'Mesh'
    pa['wf_Visibility Mailbox']        = 1
    pa['wf_Number Of Local Mailboxes'] = 18   # SMB_PIRANHA_UP_L (2016) phase flag
    pa['wf_Script']                    = PARATROOPA_SCRIPT
    return pa


# ── Tree-top islands (centre_col, width_tiles, top_tiles) ─────────────────────
add_treetop('tree_a',  14, GROUND_TOP_Z + 2*T, 5)    # launch pad
add_treetop('tree_b1', 22, GROUND_TOP_Z + 4*T, 4)    # Koopa #1
add_treetop('tree_b2', 29, GROUND_TOP_Z + 4*T, 4)    # 3 coins above
add_treetop('tree_c1', 37, GROUND_TOP_Z + 3*T, 4)
add_treetop('tree_c2', 45, GROUND_TOP_Z + 5*T, 5)    # tallest: 2 Goombas
add_treetop('tree_c3', 53, GROUND_TOP_Z + 3*T, 4)
add_treetop('tree_d',  60, GROUND_TOP_Z + 2*T, 4)    # short tree under the ? block
add_treetop('tree_e',  75, GROUND_TOP_Z + 6*T, 5)    # tall tree, 4 coins above
add_treetop('tree_f1', 94, GROUND_TOP_Z + 3*T, 4)    # small/medium tree
add_treetop('tree_f2', 102, GROUND_TOP_Z + 4*T, 6)   # wide/tall: Koopa #2
add_treetop('tree_g',  110, GROUND_TOP_Z + 3*T, 4)   # Goomba #3
add_treetop('tree_h',  118, GROUND_TOP_Z + 3*T, 4)   # 3 coins above
add_treetop('tree_i1', 125, GROUND_TOP_Z + 3*T, 4)   # Koopa #3
add_treetop('tree_i2', 131, GROUND_TOP_Z + 3*T, 4)

# ── Static stand-ins for the moving platforms (TODO: real Path/Jolt-carry movers) ──
# Lift bay (step 6): two stone steps gaining height up to the tall tree_e.
add_statplat('lift_step_0', 66*T - T, -GROUND_Y, GROUND_TOP_Z + 3*T - 0.5,
             66*T + T,       GROUND_Y, GROUND_TOP_Z + 3*T, mat_hard)
add_statplat('lift_step_1', 70*T - T, -GROUND_Y, GROUND_TOP_Z + 5*T - 0.5,
             70*T + T,       GROUND_Y, GROUND_TOP_Z + 5*T, mat_hard)
# Two horizontal movers (step 7): static stone platforms with a jumpable gap, coins above.
add_statplat('mover_0', 82*T - 1.5*T, -GROUND_Y, GROUND_TOP_Z + 4*T - 0.5,
             82*T + 1.5*T,  GROUND_Y, GROUND_TOP_Z + 4*T, mat_hard)
add_statplat('mover_1', 87*T - 1.5*T, -GROUND_Y, GROUND_TOP_Z + 4*T - 0.5,
             87*T + 1.5*T,  GROUND_Y, GROUND_TOP_Z + 4*T, mat_hard)

# ── ? block (single power-up: Mushroom if Small, Fire Flower if Super) over tree_d ──
_make_powerup_block('w13_powerup', 60*T, 'powerup_template', 0.0, z=GROUND_TOP_Z + 4*T)

# ── Stone platform before the flagpole + staircase up to it ───────────────────
add_statplat('stone_plat', 138*T - 2*T, -GROUND_Y, GROUND_TOP_Z,
             138*T + 2*T,   GROUND_Y, GROUND_TOP_Z + 1*T, mat_hard)
_add_staircase('w13_stairs', base_col=146, steps=8)   # rises to the flagpole at col 155

# ── Enemies ───────────────────────────────────────────────────────────────────
_build_koopa('koopa_green_0', 22, 4)     # Koopa #1 on tree_b1
_build_koopa('koopa_green_1', 102, 4)    # Koopa #2 on the wide tree_f2
_build_koopa('koopa_green_2', 125, 3)    # Koopa #3 on tree_i1

# 3 Goombas (2 on the tallest tree_c2, 1 on tree_g). Shared 'goomba' datablock.
_goomba_body = _build_goomba()
_goomba_data = _goomba_body.data
bpy.data.objects.remove(_goomba_body, do_unlink=True)
GOOMBAS = [(44, 5), (47, 5), (110, 3)]   # (col, canopy_top_tiles)
for _gi, (_gc, _gt) in enumerate(GOOMBAS):
    _go = bpy.data.objects.new(f'goomba_{_gi:02d}', _goomba_data)
    scene.collection.objects.link(_go)
    _go.location = (_gc*T, 0.0, GROUND_TOP_Z + _gt*T + 0.5*T)
    attach_schema(_go, 'enemy')
    _apply_enemy_movement(_go)

# 2 green Paratroopas hovering over gaps (so the bounce stays clear of canopies).
_build_paratroopa('paratroopa_0', 107)   # over the tree_f2 → tree_g gap
_build_paratroopa('paratroopa_1', 121)   # over the tree_h → tree_i1 gap

# ── Coins (23 open-air) ───────────────────────────────────────────────────────
# 2 scattered above tree_a
_add_coin(13*T, GROUND_TOP_Z + 3.0*T); _add_coin(16*T, GROUND_TOP_Z + 3.0*T)
# 3 above tree_b2 (canopy top 4T)
for _cx in (28, 29, 30):
    _add_coin(_cx*T, GROUND_TOP_Z + 5.0*T)
# 3 scattered in the jump arc tree_c3 → tree_d
_add_coin(55*T, GROUND_TOP_Z + 4.0*T); _add_coin(57*T, GROUND_TOP_Z + 4.7*T); _add_coin(59*T, GROUND_TOP_Z + 4.0*T)
# 4 above the tall tree_e (canopy top 6T)
for _cx in (73, 74.5, 76, 77.5):
    _add_coin(_cx*T, GROUND_TOP_Z + 7.0*T)
# 8 above the two movers (two rows)
for _cx in (81, 83, 85, 87):
    _add_coin(_cx*T, GROUND_TOP_Z + 5.5*T)
for _cx in (82, 84, 86, 88):
    _add_coin(_cx*T, GROUND_TOP_Z + 7.0*T)
# 3 above tree_h (canopy top 3T)
for _cx in (117, 118, 119):
    _add_coin(_cx*T, GROUND_TOP_Z + 4.0*T)

print(f"[smb_w1_3] coins placed: {_coin_n[0]} (target 23)")

# ── 10. Export ────────────────────────────────────────────────────────────────
SMB_MESH_DIR = os.path.join(REPO, 'wflevels', 'smb')
print(f"[smb_w1_3] Exporting to {OUT_LEV} (meshes → {SMB_MESH_DIR})")
bpy.ops.wf.export_level(filepath=OUT_LEV, mesh_dir=SMB_MESH_DIR)
print("[smb_w1_3] Objects in scene:", len(bpy.data.objects))
print(f"[smb_w1_3] Done — {OUT_LEV}")
