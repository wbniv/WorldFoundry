"""
blender_create_smb.py — create smb_w1_1 validation level.

Super Mario Bros. W1-1 first-pass validation scene (brief §Verification steps 1–10):
  - Flat ground platform (brown)
  - Three ? blocks at tile-row 4 height (gold)
  - Mario placeholder (red/blue figure, Physics mobility)
  - Goomba placeholder (brown mushroom, static)
  - Koopa Troopa placeholder (green shell, static)
  - Flagpole at level end (grey pole + green flag)
  - Side-scrolling camera (Y=-30, looking in +Y at X-Z gameplay plane)

Geometry: T = 1.5 m per NES tile. Ground surface Z=0. Mario centre Z=T when standing.
? blocks centre Z = 4*T + T/2 (4 tiles above ground, block centred in its tile).

Camera: classic SMB scroll via Director + signal-mailbox pattern.  CamShot's
X position is driven by a Forth Director script that reads Mario's X each
tick, applies a 1-tile deadzone + one-way ratchet + level-edge clamp + 1-tile
forward lead, and routes the target X through global mailbox 1801; the
CamShot's own script consumes that mailbox and writes its INDEXOF_X_POS.
Y/Z stay Absolute at (-20, MARIO_Z+3). Inherent 1-tick lag (16 ms @ 60 Hz,
invisible). See docs/plans/2026-05-17-smb-scrolling-camera.md.

Run via Blender MCP execute_blender_code, or headlessly:
  blender --background --python blender_create_smb.py
"""

import bpy
import os
import math
import addon_utils

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS  = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'smb_w1_1.lev')
OAD_DIR    = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')

# ── Layout (T = NES tile size in WF metres) ───────────────────────────────────
T = 1.5

GROUND_TOP_Z  = 0.0
GROUND_THICK  = T                         # 1-tile-thick slab
MARIO_Z       = GROUND_TOP_Z + T         # reference "Mario height" — body centre for camera framing, etc.
# Player actor.pos = feet (WF convention). Spawn 1 tile above ground so the fall is visible.
MARIO_FEET_Z  = GROUND_TOP_Z
MARIO_SPAWN_Z = MARIO_FEET_Z + T
BLOCK_Z       = GROUND_TOP_Z + 4*T + T/2 # ? block centre (4 tiles above ground)

# W1-1 landmark X positions (tile counts × T) — faithful 224-tile original
MARIO_SPAWN_X = 3  * T
QBLOCK_XS     = [21*T, 107*T]            # coin ? blocks at faithful cols 21, 107
KOOPA_X       = 113 * T                  # col 113 (was 32*T)
FLAGPOLE_X    = 210 * T                  # 315 m — faithful (was 42*T)

# 16 Goombas at reference positions (docs/smb-level-layouts.md §1-1)
GOOMBA_XS = [
    22*T,                                # col 22 — first enemy
    32*T, 34*T,                          # between pipes 1–2
    42*T, 44*T,                          # between pipes 2–3
    50*T,                                # lone Goomba mid-level
    80*T, 83*T,                          # near post-pit ? block
    88*T, 92*T, 95*T, 99*T,             # overhead block row area
    128*T, 133*T,                        # near pyramid A
    143*T, 147*T,                        # near pyramid B
]

GROUND_X0 = -2 * T
GROUND_X1 = FLAGPOLE_X + 5*T
GROUND_Y  = T                             # half-depth of ground slab in Y

# Pits (bottomless gaps in the ground) — faithful W1-1 positions.
# See docs/plans/2026-05-25-smb-pit-death-and-level-timer.md.
PITS = [(77*T, 81*T),   # cols 77-80: mid-level gap
        (118*T, 122*T)] # cols 118-121: late gap before pyramids

# Level countdown timer (Director script). SMB starts at 400 "time units"; we
# drain them over TIMER_REAL_SECONDS of wall-clock so 100-left lines up with the
# faithful tempo-change point. display = TIMER_UNITS - elapsed * (UNITS/SECONDS).
TIMER_UNITS        = 400
TIMER_REAL_SECONDS = 150.0

SCENE_MID_X = (GROUND_X0 + GROUND_X1) / 2

# ── Underground coin room (pipe-warp target) ──────────────────────────────────
# A genuine SECOND room, placed straight below the surface with a DISJOINT bbox
# (Z gap -36..-10) so leaving the surface room's bbox triggers a real room switch
# (ActiveRooms::UpdateRoom loops all rooms — no adjacency needed; hard-switch =
# the W1-2 "unload surface / load underground" behaviour). The point is to prove
# WF's room-to-room transition path. See docs/plans/2026-05-25-smb-pipe-warp-coin-room.md.
SMB_AT_PIPE  = 1809               # INDEXOF_SMB_AT_PIPE (mailbox.inc) — entry ActBox sets 1 on the pipe mouth
SMB_COIN_0, SMB_COIN_1, SMB_COIN_2 = 1811, 1812, 1813   # coin-room coin visibility mailboxes (mailbox.inc)
SMB_COIN_3, SMB_COIN_4, SMB_COIN_5, SMB_COIN_6 = 1846, 1847, 1848, 1849  # coins 3-6
SMB_COIN_7, SMB_COIN_8, SMB_COIN_9 = 1850, 1851, 1852                     # coins 7-9
SMB_COIN_10, SMB_COIN_11, SMB_COIN_12, SMB_COIN_13 = 1853, 1854, 1855, 1856  # coins 10-13
SMB_COIN_14, SMB_COIN_15, SMB_COIN_16, SMB_COIN_17, SMB_COIN_18 = 1857, 1858, 1859, 1860, 1861  # coins 14-18
# Fire Mario fireball globals (mailbox.inc 1820-1827). The generators' Activation
# MailBox needs the literal index here (an OAS int field); scripts use INDEXOF_ names.
SMB_FIREBALL_FIRE_R, SMB_FIREBALL_FIRE_L = 1823, 1824
# Celebration extension (mailbox.inc 1864-1871): Mario hides into the castle + radial fireworks.
SMB_MARIO_VIS = 1864                          # Player visibility mailbox (1=show, 0=hide)
# 6 firework-generator activation mailboxes; generator n throws a spark burst in its window
# iff n < SMB_FIREWORK_COUNT (the faithful 1/3/6 last-digit count, latched at celebration start).
SMB_FIREWORK = [1865, 1866, 1867, 1868, 1869, 1870]
SMB_FIREWORK_COUNT = 1871
ENTRY_PIPE_X = 47 * T             # = 70.5, center of cols 46-47 (was 12*T)
CR_FLOOR_TOP = -48.0              # coin-room floor top
CR_X0, CR_X1 = 0.0, 24.0         # coin-room play span (16 tiles, faithful W1-1)
CR_MID        = (CR_X0 + CR_X1) / 2  # = 12.0
CR_ENTRY_X   = 3.0               # entry-warp drop point (left side)
CR_ENTRY_Z   = CR_FLOOR_TOP + T  # = -46.5, feet drop-in (mirrors surface MARIO_SPAWN_Z)

# Camera: fixed side-view, Y=-30, looking toward +Y at Mario's spawn position.
# SCENE_MID_X (33.75) is the level midpoint, but the player starts at MARIO_SPAWN_X
# (4.5). Centering on MARIO_SPAWN_X keeps Mario in frame at game start.
CAM_Y = -30.0
CAMSHOT_POS = (MARIO_SPAWN_X, CAM_Y, MARIO_Z + 3.0)
LOOKAT_POS  = (MARIO_SPAWN_X, 0.0,   MARIO_Z)

NUM_MAILBOXES = 100   # minimal for validation level

# ── 1. Clean scene & enable addon ─────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# ── Shared SMB builders (extracted to wflevels/smb_common.py so levels cannot drift).
#    See docs/plans/2026-06-02-smb-common-extraction-and-mesh-sharing.md (Phase P1a).
import sys as _sys
_sys.path.insert(0, os.path.join(SCRIPT_DIR, '..'))
import smb_common
smb_common.init(scene, OAD_DIR)
from smb_common import (make_mat, attach_schema, find_by_class, get_class,
    add_box, add_statplat, _add_textured_box, _make_qblock_tga, _make_brick_tga,
    _make_grid_tile_tga, build_textured_ground_mesh, _room_bounds_mesh, _build_mario)
from smb_common import (_add_brick, _make_powerup_block)
from smb_common import (_make_coin_template, _make_debris_template, _make_spark_template, _make_fireball_template, _make_powerup_template, _add_pyramid, _add_staircase)
from smb_common import (_apply_enemy_movement, _build_goomba, _make_target, _make_popup_template, _make_fireball_generator)
from smb_common import (
    QBLOCK_SCRIPT, DEBRIS_SCRIPT, SPARK_SCRIPT, BRICK_SCRIPT, POPUP_SCRIPT, ENEMY_SCRIPT, KOOPA_SCRIPT, POWERUP_BLOCK_SCRIPT, POWERUP_SCRIPT, STAR_SCRIPT, ONEUP_SCRIPT, FIREBALL_SCRIPT, FIREBALL_GEN_SCRIPT)

# ── 2. Import snowgoons for infrastructure ────────────────────────────────────
print(f"[smb] Importing snowgoons from {SNOWGOONS}")
bpy.ops.wf.import_level(filepath=SNOWGOONS)

# ── 3. Strip gameplay objects; keep one of each infrastructure class ──────────
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

print("[smb] Classes after strip:", sorted({get_class(o) for o in bpy.data.objects}))


# ── 4. Configure infrastructure actors ───────────────────────────────────────
director = find_by_class('director')
if director:
    director.location = (0, CAM_Y - 2, MARIO_Z)
    director['wf_Model Type'] = 'None'
    # SMB scroll Director — runs after every main-loop actor each tick
    # (level.cc:881-888). Reads INDEXOF_SMB_PLAYER_X, applies deadzone +
    # one-way ratchet + edge clamp + 1-tile lead, writes
    # INDEXOF_SMB_TARGET_CAM_X for the CamShot to consume next tick.
    # INDEXOF_SMB_MAX_CAM_X holds the ratchet state; 0 means uninitialised
    # → seed to SPAWN_CAM_X=4.5.
    # Edge bounds: X_MIN+HALF_FRUSTUM = -3.0+12.0 = 9.0;
    #              X_MAX-HALF_FRUSTUM = FLAGPOLE_X-12.0 = 303.0.
    # Deadzone test uses (delta < 1.5) — true for both in-deadzone AND
    # Mario-behind-camera cases (the one-way ratchet falls out for free).
    _cam_x_max = FLAGPOLE_X - 12.0
    director['wf_Script'] = (
        "\\ wf\n"
        "INDEXOF_SMB_MAX_CAM_X read-mailbox not if "
        "4.5 INDEXOF_SMB_MAX_CAM_X write-mailbox then\n"
        "INDEXOF_SMB_PLAYER_X read-mailbox 1.5 +\n"
        "dup INDEXOF_SMB_MAX_CAM_X read-mailbox -\n"
        "1.5 <\n"
        "if drop INDEXOF_SMB_MAX_CAM_X read-mailbox\n"
        "else 1.5 - "
        "dup 9.0 < if drop 9.0 then "
        f"dup {_cam_x_max:.1f} > if drop {_cam_x_max:.1f} then "
        "dup INDEXOF_SMB_MAX_CAM_X write-mailbox\n"
        "then\n"
        "INDEXOF_SMB_TARGET_CAM_X write-mailbox\n"
        # ── level countdown timer ───────────────────────────────────────────
        # display = TIMER_UNITS - elapsed*RATE (clamped >=0) -> HUD_TIMER slot.
        # SMB_TIMER_START anchors the current life; reaching 0 = "TIME UP" fires
        # SMB_PLAYER_HURT (Mario dies, loses a life via the player respawn) and
        # restarts the clock. The player respawn also re-anchors it on every death.
        # ── celebration sequencer (gates on SMB_CELEBRATE) OR normal countdown ──
        # On SMB_CELEBRATE: seed START once, then phase off elapsed = TIME-START.
        #   phase D (elapsed>1.5): drain HUD_TIMER toward 0 (visual; the player already
        #     credited HUD_TIMER*50 to the score on the rising edge).
        #   phase E (elapsed>=3.5): fire END_OF_LEVEL -> meta-loop loads the next level.
        # While celebrating the normal countdown is suspended (it also owns HUD_TIMER).
        "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
        "  INDEXOF_SMB_CELEBRATE_START read-mailbox not if "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START write-mailbox then\n"
        # Frame the flag + the castle to its right (overrides the scroll target, which
        # clamps at the pole and would leave the castle off the right edge).
        f"  {FLAGPOLE_X:.1f} INDEXOF_SMB_TARGET_CAM_X write-mailbox\n"
        "  INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox -\n"   # elapsed
        "  dup 1.5 > if "                                       # phase D: drain the timer
        "INDEXOF_HUD_TIMER read-mailbox 250.0 INDEXOF_DELTA_TIME read-mailbox * - "
        "dup 0 < if drop 0 then INDEXOF_HUD_TIMER write-mailbox then\n"
        "  4.5 > if 1 INDEXOF_END_OF_LEVEL write-mailbox then\n"  # phase G: finale (after the last firework burst ~4.35)
        "else\n"
        "  INDEXOF_SMB_TIMER_START read-mailbox not if "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox then\n"
        f"  {TIMER_UNITS} INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START read-mailbox - "
        f"{TIMER_UNITS / TIMER_REAL_SECONDS:.5f} * -\n"        # 400 - elapsed*RATE
        "  dup 0 <= if "
        "1 INDEXOF_SMB_PLAYER_HURT write-mailbox "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox "
        "drop 0 then\n"                                        # clamp display to 0
        "  INDEXOF_HUD_TIMER write-mailbox\n"
        "then\n"
    )

levelobj = find_by_class('levelobj')
if levelobj:
    levelobj.location = (0, CAM_Y - 2, MARIO_Z)
    levelobj['wf_Number Of Mailboxes'] = NUM_MAILBOXES
    levelobj['wf_Model Type'] = 'None'

matte = find_by_class('matte')
if matte:
    matte.location = (SCENE_MID_X, CAM_Y - 2, MARIO_Z)
    matte['wf_Matte Type'] = 'Color'
    matte['wf_Background Color'] = 0x5C94FC   # NES overworld sky blue
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
    light.rotation_euler = (math.pi / 3, 0, 0)   # sun ~60° above horizon
    light.name = 'Light01'
    light['wf_lightType']  = 'Directional'
    light['wf_lightRed']   = 1.0
    light['wf_lightGreen'] = 1.0
    light['wf_lightBlue']  = 1.0

# ── Helpers ───────────────────────────────────────────────────────────────────
# ── 5. Ground platform ────────────────────────────────────────────────────────
# Texture-mapped 1-unit grid on top of the ground so screenshots can be read
# off the floor (e.g. camera at X=9 sits at the 9th grid line from origin).
# Single 32×32 tile, single mesh quad on top, UV scaled so 1 UV unit = 1
# world metre (relies on GL_REPEAT — see TODO.md § SCRIPTING ENGINES for
# the atlas-UV-uint8-overflow bug that may bite at high UV).
grid_tex_path = _make_grid_tile_tga(os.path.join(SCRIPT_DIR, 'grid_tile.tga'))
SMB_PLAYER_HURT = 1804   # INDEXOF_SMB_PLAYER_HURT (wfsource/source/mailbox/mailbox.inc)

# Build the ground as solid slabs around the pits (the gaps in PITS are skipped,
# leaving real holes the player can fall through).
_solid_spans = []
_cursor = GROUND_X0
for _pl, _pr in sorted(PITS):
    if _pl > _cursor:
        _solid_spans.append((_cursor, _pl))
    _cursor = max(_cursor, _pr)
if _cursor < GROUND_X1:
    _solid_spans.append((_cursor, GROUND_X1))

for _i, (_sx0, _sx1) in enumerate(_solid_spans):
    seg_mesh = build_textured_ground_mesh(
        f'ground_{_i}',
        _sx0, -GROUND_Y, GROUND_TOP_Z - GROUND_THICK,
        _sx1,  GROUND_Y, GROUND_TOP_Z,
        grid_tex_path)
    seg_obj = bpy.data.objects.new(f'ground_{_i}', seg_mesh)
    seg_obj.location = (0.0, 0.0, 0.0)
    scene.collection.objects.link(seg_obj)
    attach_schema(seg_obj, 'statplat')
    seg_obj['wf_Visibility Mailbox'] = 1
    seg_obj['wf_Model Type'] = 'Mesh'

# Pit-death sensors: an invisible ActBox below each gap. A falling Player enters
# the band -> SMB_PLAYER_HURT=1 -> the player script's existing respawn fires
# (-1 life, back to spawn). Positioned below ground (Z band [-15, -1]) so a Mario
# standing at the lip doesn't trigger it; only a fall does. Mirrors the flagpole
# ActBox composition (see §10b).
for _i, (_pl, _pr) in enumerate(PITS):
    _cx = (_pl + _pr) / 2.0
    _hx = (_pr - _pl) / 2.0 + 0.5
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(_cx, 0.0, -8.0))
    pit = bpy.context.object
    pit.name      = f'pit_death_{_i}'
    pit.data.name = f'pit_death_{_i}'
    pit.scale = (_hx, GROUND_Y, 7.0)   # half-extents -> Z band [-15, -1]
    bpy.ops.object.transform_apply(scale=True)
    attach_schema(pit, 'actbox')
    pit['wf_MailBox']            = SMB_PLAYER_HURT
    pit['wf_MailBoxValue']       = 1
    pit['wf_Activated By Actor'] = 'Player'
    pit['wf_Activated Actor Mailbox'] = 4005   # scratch slot (don't care who fell in)

# ── 6. ? Blocks ───────────────────────────────────────────────────────────────
# Each ? block is ONE Generator actor: solid visible mesh + 3-state self-detect
# Forth script + per-actor activation mailbox. The block IS the generator.
# See docs/plans/2026-05-19-smb-block-generator-coin.md.
mat_coin = smb_common.mat_coin()
BSIZE = T / 2  # half-side of a 1-tile block
qblock_tex = _make_qblock_tga(os.path.join(SCRIPT_DIR, 'qblock_tex.tga'))
smb_common.set_textures(qblock=qblock_tex)
COIN_X = T * 0.25   # half-width:  NES 8px/16px → 50% of block → 0.375 m
COIN_Z = T * 0.5    # half-height: NES 16px/16px → 100% of block → 0.75 m
COIN_T = 0.2        # Y-depth: ≥ ~0.2 m to render from side-camera (Y=-20).
                    # 0.04 was below the renderer's camera-depth threshold; see
                    # docs/level-design-troubleshooting.md § "Object too thin…".

# Per-actor local mailbox slots (same index on every block instance; no cross-talk
# because local mailboxes 2000-2099 are per-actor). Must match mailbox.inc.
MB_SMB_QBLOCK_ACTIVATE = 2010
MB_SMB_QBLOCK_USED     = 2011
MB_SMB_QBLOCK_DIE      = 2012

# Tan (used-block) color packed as 0xRRGGBB for FACE_COLOR_TOP write-mailbox.
# (0.78*255, 0.49*255, 0.18*255) = (199, 125, 46) = 0xC77D2E.
QBLOCK_TAN = 0xC77D2E

# Tint colors written via FACE_COLOR_TOP (3037 = override material[0]). Fire Mario
# wears white/red; the Star flicker alternates yellow<->white; MARIO_DEFAULT_TINT
# (white) restores Mario when leaving Fire or when the Star window closes. Verified
# 2026-05-26: this tints the multi-material player mesh AND fully recolors a single-
# material collectible box (every face is material[0]).
FIRE_TINT          = 0xF8F0E0   # warm white (Fire Mario)
MARIO_DEFAULT_TINT = 0xFFFFFF   # neutral restore
STAR_FLASH_A       = 0xFFE000   # yellow
STAR_FLASH_B       = 0xFFFFFF   # white
FLOWER_TINT        = 0xF2731A   # orange (fire flower) — repaints the power-up box when Super+

# 3-state self-detect script (NORMAL → ACTIVE → USED).
# State: SMB_QBLOCK_DIE = window-close time (first_hit+4.0); 0 = NORMAL.
#        SMB_QBLOCK_USED = 1 → permanently dead.
# Hit-from-below gate: COLLISION_NORMAL_Z > 0. JoltContactDispatch passes the
# same normal vector to both actor and struck body; bump-from-below is +Z for
# both (direction Mario pushes the surface). Matches the engine change in
# docs/plans/2026-05-19-smb-block-generator-coin.md step 8.
# Activation pulse is one tick (Generator spawn-check at top, script clear at
# bottom of Generato::update) → exactly one coin per distinct bump.
# `not` used instead of `0=` (zForth defines `not` as `: not 0 = ;` but
# doesn't expose `0=` as a named word; `0<>` and `>` are both available).

COIN_SCRIPT = "\\ wf\nINDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"

# Coin template — Gold collectible class (pickup-driven despawn via
# Gold::Collision + SetPendingRemove; spins via ROTATION_C each frame).
import bmesh as _bmesh
_make_coin_template()

for i, bx in enumerate(QBLOCK_XS):
    blk = _add_textured_box(f'qblock_{i:02d}',
                             bx - BSIZE, -BSIZE, BLOCK_Z - BSIZE,
                             bx + BSIZE,  BSIZE, BLOCK_Z + BSIZE,
                             qblock_tex)
    attach_schema(blk, 'generator')
    blk['wf_Mobility']           = 'Anchored'
    blk['wf_Model Type']         = 'Mesh'
    blk['wf_Visibility Mailbox'] = 1
    blk['wf_Number Of Local Mailboxes'] = 13  # LOCAL_USER_START+0..+12 covers 2000-2012
    blk['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
    blk['wf_Object To Throw']    = 'coin_template'
    blk['wf_Generation Rate']    = 10.0
    blk['wf_Object X Velocity']  = 1.5   # slight rightward drift (+X = screen-right)
    blk['wf_Object Y Velocity']  = 0.0
    blk['wf_Object Z Velocity']  = 6.0
    blk['wf_Script']             = QBLOCK_SCRIPT

# ── 6b. Power-up collectibles — mushroom / fire flower / star ─────────────────
# All three REUSE the `gold` collectible class as a "coin worth 0": Gold::update runs
# the actor's wf_Script (proximity pickup raises a signal) and the C++ pickup removes
# the actor on contact. They are NOT coins — taxonomy debt logged in TODO §69. The
# gold/CharacterVirtual collision profile lets Mario walk THROUGH to collect while still
# landing/sliding on the floor. The mushroom & flower are now ONE self-determining
# template (see below). See docs/plans/2026-05-26-smb-powerup-block-and-star-reversal.md.
MUSH_X = T * 0.40   # half-width
MUSH_Z = T * 0.40   # half-height
MUSH_T = 0.25       # Y-depth (>= ~0.2 m so it renders from the side camera at Y=-20)

# One-shot power-up block — a Generator that throws exactly ONE collectible on the first
# bump-from-below, then latches USED (tan). Mirrors the qblock authoring but without
# the 4-second multi-coin window: set the activate pulse on the first bump; the tick
# after the Generator consumes it, latch USED so no second item can spawn.

MUSHROOM_BLOCK_X = 16 * T  # 24.0 — col 16, faithful W1-1 mushroom ? block
mblk = _add_textured_box('mushroom_block',
                         MUSHROOM_BLOCK_X - BSIZE, -BSIZE, BLOCK_Z - BSIZE,
                         MUSHROOM_BLOCK_X + BSIZE,  BSIZE, BLOCK_Z + BSIZE,
                         qblock_tex)
attach_schema(mblk, 'generator')
mblk['wf_Mobility']           = 'Anchored'
mblk['wf_Model Type']         = 'Mesh'
mblk['wf_Visibility Mailbox'] = 1
mblk['wf_Number Of Local Mailboxes'] = 13   # 2000..2012, same as the qblocks
mblk['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
mblk['wf_Object To Throw']    = 'powerup_template'   # state-aware: mushroom while Small
mblk['wf_Generation Rate']    = 10.0
mblk['wf_Object X Velocity']  = 1.5   # pops out drifting right (the mushroom slides)
mblk['wf_Object Y Velocity']  = 0.0
mblk['wf_Object Z Velocity']  = 6.0   # and upward, like the coin
mblk['wf_Script']             = POWERUP_BLOCK_SCRIPT

# ── 6b. Fire Flower + Star power-ups ───────────────────────────────────────────
# Both reuse the gold class (Gold Value 0) like the mushroom — they are NOT coins;
# their pickup scripts signal the player state machine. Logged as taxonomy debt
# (TODO §69). See docs/plans/2026-05-26-smb-fire-flower-and-star.md.
#
# Shared collectible-template factory (the mushroom keeps its own fn, untouched, to
# avoid perturbing its export). Same gold/CharacterVirtual collision profile: walks
# through the player to be collected, lands + slides/rests on the floor.
# Power-up dispensing block: a one-shot Generator (bump from below -> throw one
# collectible -> latch tan), using POWERUP_BLOCK_SCRIPT.
# Mushroom-or-flower: ONE self-determining power-up. A Generator's Object To Throw is
# fixed at load (generator.cc:84), so rather than two templates the single
# `powerup_template` reads SMB_MARIO_STATE LIVE and BECOMES the right item: Small (0)
# stays the red mushroom that slides; Super+ (>0) repaints orange and forces stationary
# (the flower). On pickup it raises the signal for Mario's current tier (mushroom ->
# Super, flower -> Fire) = the existing player handlers. One-shot blocks mean Mario's
# tier can't change between bump and catch, so the live read always matches the item.
mat_powerup = make_mat('powerup_red', (0.85, 0.16, 0.12))   # base colour = mushroom red
_make_powerup_template('powerup_template', mat_powerup, POWERUP_SCRIPT, 0.0, -55.0)
# @15: throws straight up (X vel 0) so the flower sits; by here you've grabbed the
# mushroom from the @9 block and are Super, so this dispenses a flower. One-shot.
FIREFLOWER_BLOCK_X = 23 * T   # 34.5 — col 23, faithful W1-1 flower ? block
_make_powerup_block('fireflower_block', FIREFLOWER_BLOCK_X, 'powerup_template', 0.0)

# Star — BOUNCES rightward and reverses off walls. Running Decel 0 keeps the slide; the
# per-tick script re-launches ZSPEED on a real floor contact (COLLISION_NORMAL_Z < 0,
# landing normal points down), so it is ground-aware (falls into pits) without engine
# restitution (TODO: PHYSICS), and flips XSPEED on a side contact (|NORMAL_X| ~ 1). The
# stomp-bounce proves ZSPEED writes on a CharacterVirtual work.
mat_star = make_mat('star_yellow', (0.98, 0.85, 0.10))
_make_powerup_template('star_template', mat_star, STAR_SCRIPT, 0.0, -59.0)
STAR_BLOCK_X = 99 * T   # 148.5 — col 99, faithful W1-1 starman block
_make_powerup_block('star_block', STAR_BLOCK_X, 'star_template', 1.5)

# 1UP mushroom — green mushroom that grants +1 life on proximity pickup.
# Same gold-class template pattern as powerup/star (GoldValue=0, gold.cc despawns on
# proximity); the script raises SMB_ONEUP_PICKUP; player script grants the life.
mat_oneup = make_mat('smb_oneup', (0.05, 0.75, 0.05))   # bright green body
_make_powerup_template('oneup_template', mat_oneup, ONEUP_SCRIPT, 0.0, -65.0)

# ── 6c. Fire Mario fireball — first runtime-positioned spawn ───────────────────
# WF's first spawn at a runtime-chosen position, with ZERO engine code: rather than
# a new `spawn-template` primitive, two hidden pool Generators self-park on a point
# Mario publishes each tick and fire a Missile when he pulses their (global)
# Activation MailBox. Two generators (left/right) cover the Generator's baked-velocity
# limit (Object X Velocity is fixed at load). See:
#   docs/plans/2026-05-26-fire-mario-fireball-pooled-generator.md  (Approach A)
#   docs/investigations/2026-05-26-spawn-template-forth-primitive.md
#
# Why a Missile and not a gold-worth-0 clone (the mushroom/flower/star idiom): the
# COLTABLE has (Player,Missile,CI_NOTHING,CI_SPECIAL) — Mario neither collects nor
# blocks it (a gold collectible would be self-collected the instant it spawns on him),
# Missile is Physics + a template by default, and Explosion Delay gives a built-in TTL
# despawn. CI_SPECIAL vs Enemy is the Phase-2 defeat hook.
FIREBALL_SPEED = 12.0
FB = 0.2   # fireball half-extent (small, so it spawns clear of Mario's body)
mat_fireball = smb_common.mat_fireball()

# Phase 2 (docs/plans/2026-05-27-smb-fireball-defeats-enemies.md): a live fireball
# broadcasts its position + a freshness deadline each tick so enemies can self-defeat
# by proximity (Missile<->Enemy are both CharacterVirtuals -> no Jolt contact dispatch,
# same reason enemies track the player by proximity). When no fireball is alive nobody
# refreshes LIVE_UNTIL, so the stale LIVE_X/Z are ignored. Missile::update ends in
# Actor::update(), so this script runs each tick.

_make_fireball_template()

# Self-park: each tick copy Mario's published spawn point onto our own position. The
# generators are Anchored (no Jolt character body) so this same-actor X/Y/Z_POS write
# sticks. Generato::update spawns from currentPos() BEFORE Actor::update() runs this
# script, so a fireball appears at Mario's previous-tick point — sub-pixel at frame rate.

_make_fireball_generator('fireball_gen_r', SMB_FIREBALL_FIRE_R,  FIREBALL_SPEED)
_make_fireball_generator('fireball_gen_l', SMB_FIREBALL_FIRE_L, -FIREBALL_SPEED)

# ── 7. Mario placeholder ──────────────────────────────────────────────────────
player = find_by_class('player')
if player:
    player.name = 'Player'   # CamShot Track Object references this name
    player.location = (MARIO_SPAWN_X, 0.0, MARIO_SPAWN_Z)
    # Physics mobility = engine handles gravity, ground collision, jump.
    # Mobility value 1 = "Physics" (Anchored|Physics|Path|Camera|Follow).
    player['wf_Mobility'] = 'Physics'  # restored for diagnosis
    player['wf_Mass']     = 1.0
    player['wf_Model Type'] = 'Mesh'
    player['wf_Visibility Mailbox'] = SMB_MARIO_VIS   # 1=visible; celebration sets 0 (enters castle)
    # Survive the coin-room warp: with MovesBetweenRooms the player's mesh binds to
    # PERM (always loaded), not the surface room's transient slot that unloads on
    # the room switch. Without this Mario vanishes the instant he warps underground.
    player['wf_Moves Between Rooms'] = 'True'
    # Physics movement parameters — tuned for SMB feel.
    # OAS custom-prop keys mirror the schema's field.key, which preserves
    # spaces (e.g. "Running Acceleration"), NOT a WikiWord form.
    player['wf_Running Acceleration']  = 60.0
    # Steady ground speed = RunningAccel / (RunningDecel * 30). The doom-stick player
    # (Turn Rate=0) runs MarbleHandler when grounded [movement.cc:575-579 routes
    # TurnRate==0 -> MarbleHandler]: accel at :717, decay at :689. GroundHandler (:318/:233)
    # is the identical-on-flat-ground twin for steered actors. Same formula either way.
    # 60/(0.85*30) ≈ 2.35 m/s was far too slow — Mario fell ~5 m short of brick_1up
    # on the entry_pipe→brick→pipe_64 hop. Max Ground Speed is NOT the limiter once it
    # exceeds the steady value, so prior MaxGroundSpeed bumps (6→12→24→32) were inert.
    # Trajectory traces: a launch of ~9-10 m/s lands ON the brick (X 84.75-86.25, top Z=7.5);
    # ~8.5 m/s passes UNDER it (bottom Z=6.0); ~10.5+ overshoots. 60/(0.18*30) = 11.1 m/s top,
    # so the 3 m pipe-top runway can build ~9.5-10 m/s — but jumping too early stays short and
    # too late overshoots, so the hop is achievable with practice, not first-try (design intent:
    # somewhat difficult, never impossible). docs/plans/2026-05-31-smb-tall-pipe-hop-physics.md.
    player['wf_Running Deceleration']  = 0.18
    player['wf_Max Ground Speed']      = 32.0
    player['wf_Jumping Acceleration']  = 60.0
    player['wf_Falling Acceleration']  = 12.0
    player['wf_Air Acceleration']      = 0.0
    player['wf_Max Air Speed']         = 32.0
    # Air "sustain" (movement.cc:872-895): with Air Acceleration=0, holding RIGHT while
    # moving +X sets hDrag=1, so takeoff momentum persists for the whole jump (the hop holds
    # RIGHT throughout, so this knob does not bite on it). It only decays velocity on frames
    # where RIGHT is released — kept at 3.0 for a slight let-go float, same as before.
    player['wf_Horiz Air Drag']        = 3.0
    # TurnRate=0 → doom-stick LEFT/RIGHT strafe instead of rotate.
    # currentDir() = (cos C, sin C, 0) [physicalobject.hpi:52].
    # C=π/2 → currentDir=(0,1,0)=+Y; StepRight=(sin C,-cos C,0)=(1,0,0)=+X ✓
    player['wf_Turn Rate']             = 0.0
    player.rotation_euler.z            = math.pi / 2  # C=π/2 → faces +Y, strafes ±X
    # Feed joystick bits to INPUT (3024), also adding kBtnStepLeft/Right (bits 6/7)
    # when LEFT/RIGHT arrows are pressed. AirHandler doom-stick with TurnRate=0
    # ignores EJ_BUTTONF_LEFT/RIGHT (rotation by zero), but DOES process
    # kBtnStepLeft/Right as ±X strafe. MarbleHandler uses EJ_BUTTONF_LEFT/RIGHT
    # directly, so keeping those bits ensures ground movement also works.
    # LEFT  (bit14=0x4000) → add StepLeft  (bit6=0x40):  0x4000/256 = 0x40
    # RIGHT (bit13=0x2000) → add StepRight (bit7=0x80):  0x2000/64  = 0x80
    player['wf_Script'] = (
        "\\ wf\n"
        "1 INDEXOF_SMB_MARIO_VIS write-mailbox\n"   # default visible; celebration hides Mario in the castle
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox "
        "dup 16384 & 256 / over 8192 & 64 / | | "
        "INDEXOF_INPUT write-mailbox\n"
        "INDEXOF_X_POS read-mailbox INDEXOF_SMB_PLAYER_X write-mailbox\n"
        "INDEXOF_Z_POS read-mailbox INDEXOF_SMB_PLAYER_Z write-mailbox\n"   # enemies use proximity
        # ── Confine the player to the level box (ends + sides) ───────────────
        # Fixed walls at the level's ENDS (X: left edge GROUND_X0, right edge GROUND_X1)
        # and SIDES (Y: the ground half-depth ±GROUND_Y). Z stays free so pits + tubes/
        # warps still work. The X clamp is surface-only (z > -8; the coin room has its own
        # walls + X range). Without this you run/jump off the ends or sides of the level.
        "INDEXOF_Z_POS read-mailbox -8.0 > if\n"
        f"  INDEXOF_X_POS read-mailbox {GROUND_X0:.2f} < if {GROUND_X0:.2f} INDEXOF_X_POS write-mailbox 0 INDEXOF_XSPEED write-mailbox then\n"
        f"  INDEXOF_X_POS read-mailbox {GROUND_X1:.2f} > if {GROUND_X1:.2f} INDEXOF_X_POS write-mailbox 0 INDEXOF_XSPEED write-mailbox then\n"
        "then\n"
        f"INDEXOF_Y_POS read-mailbox {-GROUND_Y:.2f} < if {-GROUND_Y:.2f} INDEXOF_Y_POS write-mailbox 0 INDEXOF_YSPEED write-mailbox then\n"
        f"INDEXOF_Y_POS read-mailbox {GROUND_Y:.2f} > if {GROUND_Y:.2f} INDEXOF_Y_POS write-mailbox 0 INDEXOF_YSPEED write-mailbox then\n"
        # seed lives once (guarded so game-over at LIVES=0 never re-seeds)
        "INDEXOF_SMB_LIVES_INIT read-mailbox not if "
        "3 INDEXOF_LIVES write-mailbox 1 INDEXOF_SMB_LIVES_INIT write-mailbox then\n"
        # bounce up when we stomped an enemy this frame; award 100 pts
        "INDEXOF_SMB_STOMP read-mailbox 0<> if\n"
        "  8.0 INDEXOF_ZSPEED write-mailbox\n"
        "  INDEXOF_SMB_SCORE read-mailbox 100 + INDEXOF_SMB_SCORE write-mailbox\n"
        "  0 INDEXOF_SMB_STOMP write-mailbox\n"
        "then\n"
        # Super Mushroom pickup -> grow to Super. Small(0)->Super(1) only; already-Super
        # stays Super. Visual scale only (hitbox-resize deferred); the feet-origin mesh
        # scales up cleanly from the floor. `not` = state == 0.
        "INDEXOF_SMB_MUSHROOM_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_SMB_MARIO_STATE read-mailbox not if\n"
        "    1 INDEXOF_SMB_MARIO_STATE write-mailbox\n"
        "    1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox "
        "1.9 INDEXOF_Z_SCALE write-mailbox\n"
        "  then\n"
        "  0 INDEXOF_SMB_MUSHROOM_PICKUP write-mailbox\n"
        "then\n"
        # Fire Flower -> Fire (state 2). From Small OR Super, jump to Fire + super-size
        # (faithful: a flower picked up small makes you big + fire directly). >=Fire stays.
        "INDEXOF_SMB_FIREFLOWER_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_SMB_MARIO_STATE read-mailbox 2 < if\n"
        "    2 INDEXOF_SMB_MARIO_STATE write-mailbox\n"
        "    1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox "
        "1.9 INDEXOF_Z_SCALE write-mailbox\n"
        f"    0x{FIRE_TINT:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "  then\n"
        "  0 INDEXOF_SMB_FIREFLOWER_PICKUP write-mailbox\n"
        "then\n"
        # Star -> ~10 s invincibility. Orthogonal to size: do NOT touch state/scale.
        # Reuse the existing INVULN gate for damage-immunity (no edit to the hurt logic);
        # SMB_STAR_UNTIL drives the enemy defeat-on-touch + the flicker.
        "INDEXOF_SMB_STAR_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_TIME read-mailbox 10.0 + INDEXOF_SMB_STAR_UNTIL write-mailbox\n"
        "  INDEXOF_TIME read-mailbox 10.0 + INDEXOF_SMB_INVULN_UNTIL write-mailbox\n"
        "  0 INDEXOF_SMB_STAR_PICKUP write-mailbox\n"
        "then\n"
        # Flicker Mario's tint while the Star window is open; restore once when it closes.
        # `%` casts to int in zForth; (TIME*8)%2 -> 0/1 toggle.
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_STAR_UNTIL read-mailbox < if\n"
        f"  INDEXOF_TIME read-mailbox 8.0 * 2 % if 0x{STAR_FLASH_A:06X} else 0x{STAR_FLASH_B:06X} then "
        "INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "  1 INDEXOF_SMB_STAR_FLICKER_LATCH write-mailbox\n"
        "else\n"
        "  INDEXOF_SMB_STAR_FLICKER_LATCH read-mailbox 0<> if\n"
        f"    INDEXOF_SMB_MARIO_STATE read-mailbox 2 = if 0x{FIRE_TINT:06X} else 0x{MARIO_DEFAULT_TINT:06X} then "
        "INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "    0 INDEXOF_SMB_STAR_FLICKER_LATCH write-mailbox\n"
        "  then\n"
        "then\n"
        # enemy side-hit -> if Super, power down to Small (no life lost); if Small, lose
        # a life + respawn at spawn. Both gated on i-frames (unless still invulnerable).
        "INDEXOF_SMB_PLAYER_HURT read-mailbox 0<> if\n"
        "  INDEXOF_TIME read-mailbox INDEXOF_SMB_INVULN_UNTIL read-mailbox > if\n"
        "    INDEXOF_SMB_MARIO_STATE read-mailbox 0 > if\n"
        # Super (or Fire) -> drop one power level; keep the life, brief i-frames.
        # Scale-aware: Fire->Super stays big (1.25/1.9); Super->Small shrinks to 1.0.
        # `dup` keeps newstate on the stack to branch the scale; clear the fire tint either way.
        "      INDEXOF_SMB_MARIO_STATE read-mailbox 1 - dup INDEXOF_SMB_MARIO_STATE write-mailbox\n"
        "      0 > if\n"
        "        1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox "
        "1.9 INDEXOF_Z_SCALE write-mailbox\n"
        "      else\n"
        "        1.0 INDEXOF_X_SCALE write-mailbox 1.0 INDEXOF_Y_SCALE write-mailbox "
        "1.0 INDEXOF_Z_SCALE write-mailbox\n"
        "      then\n"
        f"      0x{MARIO_DEFAULT_TINT:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "      INDEXOF_TIME read-mailbox 1.5 + INDEXOF_SMB_INVULN_UNTIL write-mailbox\n"
        "    else\n"
        # Small -> die: lose a life + respawn at spawn.
        "      INDEXOF_LIVES read-mailbox 1 - INDEXOF_LIVES write-mailbox\n"
        f"      {MARIO_SPAWN_X} INDEXOF_X_POS write-mailbox\n"
        "      0 INDEXOF_Y_POS write-mailbox\n"
        f"      {MARIO_SPAWN_Z} INDEXOF_Z_POS write-mailbox\n"
        "      0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox "
        "0 INDEXOF_ZSPEED write-mailbox\n"
        # restart the countdown for the new life (any death resets the timer, SMB-faithful)
        "      INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox\n"
        "      INDEXOF_TIME read-mailbox 2.0 + INDEXOF_SMB_INVULN_UNTIL write-mailbox\n"
        "      INDEXOF_LIVES read-mailbox 1 < if 1 INDEXOF_END_OF_LEVEL write-mailbox then\n"
        "    then\n"
        "  then\n"
        "  0 INDEXOF_SMB_PLAYER_HURT write-mailbox\n"
        "then\n"
        # pipe warp: standing on a pipe mouth (entry ActBox set SMB_AT_PIPE) AND
        # pressing Down -> drop into the underground coin room. Reuses the proven
        # respawn teleport (X/Y/Z_POS write + zero velocity); 4096 = EJ_BUTTONF_DOWN.
        "INDEXOF_SMB_AT_PIPE read-mailbox 0<> if\n"
        "  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox 4096 & 0<> if\n"
        f"    {CR_ENTRY_X} INDEXOF_X_POS write-mailbox\n"
        "    0 INDEXOF_Y_POS write-mailbox\n"
        f"    {CR_ENTRY_Z} INDEXOF_Z_POS write-mailbox\n"
        "    0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox "
        "0 INDEXOF_ZSPEED write-mailbox\n"
        "  then\n"
        "then\n"
        # 1UP mushroom pickup: raise +1 life, clear signal
        "INDEXOF_SMB_ONEUP_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_LIVES read-mailbox 1 + INDEXOF_LIVES write-mailbox\n"
        "  0 INDEXOF_SMB_ONEUP_PICKUP write-mailbox\n"
        "then\n"
        # Flagpole celebration — fires on SMB_CELEBRATE's rising edge (the flag ActBox
        # sets it). One-shot height+time bonus, then pin Mario at the pole for the show.
        # Height tiers: Z≥9→5000, ≥6→2000, ≥4.5→800, ≥3→400, ≥1.5→200, else→100.
        # Time bonus: HUD_TIMER remaining × 50 (read once, before the Director drains it —
        # the player runs in the main loop, the Director runs last).
        # EOL_LATCH guards the credit so it fires once across the multi-second celebration.
        "INDEXOF_SMB_CELEBRATE read-mailbox 0<> if\n"
        # Seed SMB_CELEBRATE_START here (the player runs before the flag enemies), so the
        # flag/castle-flag scripts read a valid START the same frame and animate from
        # elapsed≈0 instead of snapping to the end (the Director also seeds it, but runs
        # last, so on frame 1 the flags would otherwise see START=0 → elapsed=TIME → frac=1).
        "  INDEXOF_SMB_CELEBRATE_START read-mailbox not if "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START write-mailbox then\n"
        "  INDEXOF_SMB_EOL_LATCH read-mailbox not if\n"
        "    1 INDEXOF_SMB_EOL_LATCH write-mailbox\n"
        "    INDEXOF_Z_POS read-mailbox\n"
        "    dup 9.0 > if drop 5000\n"
        "    else dup 6.0 > if drop 2000\n"
        "    else dup 4.5 > if drop 800\n"
        "    else dup 3.0 > if drop 400\n"
        "    else dup 1.5 > if drop 200\n"
        "    else drop 100\n"
        "    then then then then then\n"
        "    INDEXOF_SMB_SCORE read-mailbox + INDEXOF_SMB_SCORE write-mailbox\n"
        "    INDEXOF_HUD_TIMER read-mailbox 50 *\n"
        "    INDEXOF_SMB_SCORE read-mailbox + INDEXOF_SMB_SCORE write-mailbox\n"
        # Faithful firework count: last digit of the remaining timer, but only 1/3/6 give
        # fireworks (else none). Latched here, once, BEFORE the Director drains HUD_TIMER.
        "    INDEXOF_HUD_TIMER read-mailbox 10 %\n"   # `%` casts to int → last digit 0..9
        "    dup 1 = if drop 1 else dup 3 = if drop 3 else dup 6 = if drop 6 else drop 0 then then then\n"
        "    INDEXOF_SMB_FIREWORK_COUNT write-mailbox\n"
        "  then\n"
        # Walk Mario into the castle, then hide him (the SMB "enters the castle door" beat):
        #   elapsed < 0.9  → hold at the pole (clamp overshoot; the flag is sliding);
        #   0.9 – 1.6      → walk right FLAGPOLE_X → FLAGPOLE_X+2 (the castle door), visible;
        #   ≥ 1.6          → entered → hide (SMB_MARIO_VIS=0) + hold at the door.
        # Writing X_POS each frame overrides input; the 2 m walk is gentle so the bungee tracks.
        "  INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox -\n"   # elapsed
        f"  dup 0.9 < if drop INDEXOF_X_POS read-mailbox {FLAGPOLE_X:.1f} > if "
        f"{FLAGPOLE_X:.1f} INDEXOF_X_POS write-mailbox then\n"
        "  else dup 1.6 < if "
        f"0.9 - 1.42857 * dup 1.0 > if drop 1.0 then 2.0 * {FLAGPOLE_X:.1f} + INDEXOF_X_POS write-mailbox\n"
        f"  else drop 0 INDEXOF_SMB_MARIO_VIS write-mailbox {FLAGPOLE_X + 2.0:.1f} INDEXOF_X_POS write-mailbox\n"
        "  then then\n"
        "then\n"
        # coin-room coins: seed visible once, then proximity pickup. The Z test
        # (player z near -46) disambiguates the coin room from the surface, where
        # the same X range exists but z ~ 1.5. dup* = squared distance (no abs).
        # 19 coins in 3 rows — faithful W1-1 layout (SMBDIS.ASM L_UndergroundArea3).
        # Pickup is X-only per column; three stacked coins at the same column are
        # all collected in the same pass (by design — no per-height check needed).
        "INDEXOF_SMB_COIN_INIT read-mailbox not if\n"
        "  1 INDEXOF_SMB_COIN_0 write-mailbox 1 INDEXOF_SMB_COIN_1 write-mailbox "
        "1 INDEXOF_SMB_COIN_2 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_3 write-mailbox 1 INDEXOF_SMB_COIN_4 write-mailbox "
        "1 INDEXOF_SMB_COIN_5 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_6 write-mailbox 1 INDEXOF_SMB_COIN_7 write-mailbox "
        "1 INDEXOF_SMB_COIN_8 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_9 write-mailbox 1 INDEXOF_SMB_COIN_10 write-mailbox "
        "1 INDEXOF_SMB_COIN_11 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_12 write-mailbox 1 INDEXOF_SMB_COIN_13 write-mailbox "
        "1 INDEXOF_SMB_COIN_14 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_15 write-mailbox 1 INDEXOF_SMB_COIN_16 write-mailbox "
        "1 INDEXOF_SMB_COIN_17 write-mailbox 1 INDEXOF_SMB_COIN_18 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_INIT write-mailbox\n"
        "then\n"
        # coin-room pickup: TRUE XZ contact (dx^2+dz^2 < 1.0, == gold.cc
        # kGoldPickupRadius^2) against each coin's real row Z. No underground-band
        # gate -- the per-coin Z test subsumes it (surface is z~1.5, far from any
        # coin row at z~-35..-41). Player poke (a coin can't write the player's GOLD).
        "INDEXOF_SMB_COIN_0 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 6.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_0 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_1 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 8.25 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_1 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_2 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 9.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_2 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_3 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 11.25 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_3 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_4 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 12.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_4 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_5 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 14.25 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_5 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_6 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 15.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_6 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_7 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 6.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_7 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_8 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 8.25 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_8 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_9 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 9.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_9 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_10 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 11.25 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_10 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_11 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 12.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_11 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_12 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 14.25 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_12 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_13 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 15.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_13 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_14 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 8.25 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_14 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_15 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 9.75 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_15 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_16 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 11.25 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_16 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_17 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 12.75 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_17 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_18 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 14.25 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_18 write-mailbox\n"
        "  then then\n"
        # Coin delta scoring + 100-coin 1UP.
        # delta = GOLD − LAST_GOLD catches both gold.cc coin pickups and coin-room
        # script pickups. Score 200 pts per coin. At each 100-coin boundary (GOLD
        # crosses a multiple of 100, edge-detected via LAST_GOLD mod), grant +1 life.
        "INDEXOF_GOLD read-mailbox INDEXOF_SMB_LAST_GOLD read-mailbox -\n"  # delta
        "dup 0 > if\n"
        "  INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
        "  INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
        "  1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
        "  200 * INDEXOF_SMB_SCORE read-mailbox + INDEXOF_SMB_SCORE write-mailbox\n"
        "  INDEXOF_GOLD read-mailbox 100 % not if\n"            # GOLD now a multiple of 100
        "    INDEXOF_SMB_LAST_GOLD read-mailbox 100 % 0<> if\n"  # LAST_GOLD was not
        "      INDEXOF_GOLD read-mailbox 0 > if\n"               # skip the initial 0
        "        INDEXOF_LIVES read-mailbox 1 + INDEXOF_LIVES write-mailbox\n"
        "      then\n"
        "    then\n"
        "  then\n"
        "else\n"
        "  drop\n"
        "then\n"
        "INDEXOF_GOLD read-mailbox INDEXOF_SMB_LAST_GOLD write-mailbox\n"
        # HUD score: display the accumulated SMB_SCORE (coins×200 + bonus points).
        "INDEXOF_SMB_SCORE read-mailbox INDEXOF_HUD_SCORE write-mailbox\n"
        # ── Fire Mario fireball ───────────────────────────────────────────────
        # docs/plans/2026-05-26-fire-mario-fireball-pooled-generator.md
        # Facing latch: RIGHT -> +1, LEFT -> -1, else keep (seed +1 while still 0).
        "INDEXOF_SMB_MARIO_FACING read-mailbox not if "
        "1 INDEXOF_SMB_MARIO_FACING write-mailbox then\n"
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_RIGHT & 0<> if "
        "1 INDEXOF_SMB_MARIO_FACING write-mailbox then\n"
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_LEFT & 0<> if "
        "-1 INDEXOF_SMB_MARIO_FACING write-mailbox then\n"
        # Publish the spawn point each tick so the generators self-park on it:
        #  X: own X + facing*1.8 — well in front, so the missile's box reliably clears Mario's
        #     body. (1.2 was marginal: Mario's slow +X idle drift intermittently closed the gap,
        #     so the spawn pre-check rejected the fireball inside Mario ~2/3 of the time.)
        #  Z: own Z + 0.8 (waist height) — clears the ground slab (top at 0), else the
        #     spawn pre-check rejects the missile for touching the floor; also where a
        #     fireball should come from. (Mario's origin is at his feet, Z_POS ~ 0 at rest.)
        "INDEXOF_X_POS read-mailbox INDEXOF_SMB_MARIO_FACING read-mailbox 1.8 * + "
        "INDEXOF_SMB_FIREBALL_X write-mailbox\n"
        "INDEXOF_Y_POS read-mailbox INDEXOF_SMB_FIREBALL_Y write-mailbox\n"
        "INDEXOF_Z_POS read-mailbox 0.8 + INDEXOF_SMB_FIREBALL_Z write-mailbox\n"
        # Clear both activation pulses every tick; set one only on the firing tick so
        # the Generator sees a one-tick pulse and throws exactly one fireball.
        "0 INDEXOF_SMB_FIREBALL_FIRE_R write-mailbox "
        "0 INDEXOF_SMB_FIREBALL_FIRE_L write-mailbox\n"
        # Fire: Fire state (2) + B held + not already latched + cooldown elapsed.
        "INDEXOF_SMB_MARIO_STATE read-mailbox 2 = if\n"
        "  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_B & 0<> if\n"
        "    INDEXOF_SMB_FIRE_LATCH read-mailbox not if\n"
        "      INDEXOF_TIME read-mailbox INDEXOF_SMB_FIRE_COOLDOWN read-mailbox > if\n"
        "        INDEXOF_SMB_MARIO_FACING read-mailbox 0 > if\n"
        "          1 INDEXOF_SMB_FIREBALL_FIRE_R write-mailbox\n"
        "        else\n"
        "          1 INDEXOF_SMB_FIREBALL_FIRE_L write-mailbox\n"
        "        then\n"
        "        1 INDEXOF_SMB_FIRE_LATCH write-mailbox\n"
        "        INDEXOF_TIME read-mailbox 0.5 + INDEXOF_SMB_FIRE_COOLDOWN write-mailbox\n"
        "      then\n"
        "    then\n"
        "  then\n"
        "then\n"
        # Release the latch when B is up -> one fireball per distinct press.
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_B & not if "
        "0 INDEXOF_SMB_FIRE_LATCH write-mailbox then\n"
    )

    mario_mesh = _build_mario()
    old = player.data
    player.data = mario_mesh.data
    bpy.data.objects.remove(mario_mesh, do_unlink=True)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

# ── 8. Goomba (walks left) ───────────────────────────────────────────────────
# Enemies walk via the coin-slide pattern: Physics + Turn Rate 0 (→ MarbleHandler)
# + Running Deceleration 0 (carries velocity), and a per-tick script that forces a
# constant leftward XSPEED. Stomp + hurt branches are added in later phases.
ENEMY_WALK_SPEED = 4.0

# ── Koopa shell-kick (docs/plans/2026-05-27-smb-koopa-shell-kick.md) ──────────────
# 3-state machine on SMB_KOOPA_STATE: 0=walk (like the goomba), 1=shell at rest,
# 2=shell sliding. Stomp retracts (walk->rest, slide->rest) instead of killing; a
# side touch of a resting shell KICKS it away into a fast slide; a sliding shell
# reverses off walls (Starman idiom), broadcasts SMB_SHELL_LIVE so the goomba dies
# to it, and hurts Mario on a side hit.
SHELL_SPEED = 14.0


_goomba_body = _build_goomba()
_goomba_data = _goomba_body.data
bpy.data.objects.remove(_goomba_body, do_unlink=True)
for _gi, _gx in enumerate(GOOMBA_XS):
    _go = bpy.data.objects.new(f'goomba_{_gi:02d}', _goomba_data)
    scene.collection.objects.link(_go)
    _go.location = (_gx, 0.0, MARIO_Z)
    attach_schema(_go, 'enemy')
    _apply_enemy_movement(_go)

# ── 9. Koopa Troopa placeholder (static visual) ───────────────────────────────
# Geometry shared via smb_common.koopa_mesh — one green Koopa datablock (the same
# build W1-2's Koopas use; single source, build-once-instance-many). Also fixes the
# old inline `objects.new(name)`-while-name-taken trick that produced koopa_00.001.iff.
koopa_obj = smb_common.koopa_mesh('koopa_00')
koopa_obj.location = (KOOPA_X, 0.0, MARIO_Z)
attach_schema(koopa_obj, 'enemy')
_apply_enemy_movement(koopa_obj)
# Koopa runs the shell-kick state machine, not the shared goomba walk-and-die script.
# A kicked shell slides at SHELL_SPEED (14) — raise the ground-speed cap above it (the
# shared cap is 8, which would clamp the slide).
koopa_obj['wf_Script']           = KOOPA_SCRIPT
koopa_obj['wf_Max Ground Speed'] = 16.0
koopa_obj['wf_Number Of Local Mailboxes'] = 19   # per-actor shell state at SMB_KOOPA_STATE_L (2018)

# ── 10. Flagpole ──────────────────────────────────────────────────────────────
mat_pole = make_mat('smb_pole', (0.72, 0.72, 0.72))
mat_flag = make_mat('smb_flag', (0.10, 0.65, 0.16))

POLE_HEIGHT = 10 * T
POLE_RADIUS = 0.18 * T   # 0.27 m — a real round pole, not a thin sliver from the side cam

# Pole — a proper round cylinder (16 sides) from ground to 10 tiles high
bpy.ops.mesh.primitive_cylinder_add(
    vertices=16, radius=POLE_RADIUS, depth=POLE_HEIGHT,
    location=(FLAGPOLE_X, 0, POLE_HEIGHT / 2))
pole_obj = bpy.context.object
pole_obj.name      = 'flagpole_pole'
pole_obj.data.name = 'flagpole_pole'
pole_obj.data.materials.clear()
pole_obj.data.materials.append(mat_pole)
attach_schema(pole_obj, 'statplat')
pole_obj['wf_Visibility Mailbox'] = 1
pole_obj['wf_Model Type'] = 'Mesh'

# Flag — flat plane near the pole top. A scriptable Anchored 'enemy' (statplats can't
# tick a script) so it SLIDES DOWN the pole during the celebration: phase A
# (elapsed 0–0.5 s) lerps its Z from the top to the base. Before SMB_CELEBRATE it sits
# at the authored top. Anchored = no Jolt body, no collision; the script owns its Z.
FLAG_TOP_Z  = POLE_HEIGHT - T        # 13.5 — authored start (near pole top)
FLAG_BASE_Z = T * 0.7                # ~1.05 — slide target (pole base, the "grab")
# Thin VERTICAL slab (a flat plane lies in XY → edge-on/invisible to the side camera).
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(FLAGPOLE_X - T, 0, FLAG_TOP_Z))
flag_obj = bpy.context.object
flag_obj.name      = 'flagpole_flag'
flag_obj.data.name = 'flagpole_flag'
flag_obj.scale = (0.5 * T, 0.03, 0.4 * T)   # 1.5 m wide × 1.2 m tall, thin in Y; faces the camera
bpy.ops.object.transform_apply(scale=True)
flag_obj.data.materials.clear()
flag_obj.data.materials.append(mat_flag)
attach_schema(flag_obj, 'enemy')
flag_obj['wf_Mobility'] = 'Anchored'
flag_obj['wf_Model Type'] = 'Mesh'
flag_obj['wf_Visibility Mailbox'] = 1
flag_obj['wf_Script'] = (
    "\\ wf\n"
    "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
    "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox - 1.1 *\n"  # frac = elapsed/0.9
    "dup 1.0 > if drop 1.0 then\n"
    f"{FLAG_TOP_Z - FLAG_BASE_Z:.2f} * {FLAG_TOP_Z:.2f} swap - INDEXOF_Z_POS write-mailbox\n"  # Z = top - span*frac
    "then\n"
)

# ── 10a. Castle + rising castle flag + door + fireworks (celebration) ─────────
# A small stone castle just past the flagpole. Mario walks into its door and vanishes
# (Player phases B/D); its rooftop flag RAISES (phase C, 0.8–1.4 s — the "flag which
# raises" beat); then 3 fireworks pop above it (phase F, staggered 2.4/2.9/3.4 s). The
# flags + fireworks are scriptable Anchored 'enemy' actors driving their own Z /
# visibility off the celebration clock (elapsed = TIME − SMB_CELEBRATE_START).
mat_castle = make_mat('smb_castle', (0.60, 0.55, 0.50))
CASTLE_X0, CASTLE_X1 = FLAGPOLE_X + 1.5 * T, FLAGPOLE_X + 4.5 * T   # 317.25 .. 321.75 (on the ground)
CASTLE_TOP   = 3 * T                                               # 4.5 m tall
CASTLE_MID_X = (CASTLE_X0 + CASTLE_X1) / 2
add_statplat('castle', CASTLE_X0, -GROUND_Y, GROUND_TOP_Z, CASTLE_X1, GROUND_Y, CASTLE_TOP, mat_castle)
add_statplat('castle_pole', CASTLE_MID_X - 0.1, -0.1, CASTLE_TOP,
             CASTLE_MID_X + 0.1, 0.1, CASTLE_TOP + 2 * T, mat_pole)

CFLAG_BASE_Z = CASTLE_TOP                          # 4.5 — authored low (rooftop base)
CFLAG_TOP_Z  = CASTLE_TOP + 2.0 * T - 0.35 * T     # flag TOP (not center) meets the pole top 7.5
# Thin VERTICAL slab (same reason as the pole flag — a flat plane is edge-on to the camera).
# X so the flag's right edge overlaps the pole centre (CASTLE_MID_X) — attached, not floating beside it.
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(CASTLE_MID_X - 0.45 * T, 0, CFLAG_BASE_Z))
cflag = bpy.context.object
cflag.name      = 'castle_flag'
cflag.data.name = 'castle_flag'
cflag.scale = (0.45 * T, 0.03, 0.35 * T)   # 1.35 m wide × 1.05 m tall, thin in Y
bpy.ops.object.transform_apply(scale=True)
cflag.data.materials.clear()
cflag.data.materials.append(mat_flag)
attach_schema(cflag, 'enemy')
cflag['wf_Mobility'] = 'Anchored'
cflag['wf_Model Type'] = 'Mesh'
cflag['wf_Visibility Mailbox'] = 1
cflag['wf_Script'] = (
    "\\ wf\n"
    "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
    "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox - 0.8 -\n"  # elapsed - 0.8 (phase C)
    "dup 0.0 < if drop 0.0 then 1.667 *\n"   # frac = (elapsed-0.8)/0.6, clamped >=0
    "dup 1.0 > if drop 1.0 then\n"
    f"{CFLAG_TOP_Z - CFLAG_BASE_Z:.2f} * {CFLAG_BASE_Z:.2f} + INDEXOF_Z_POS write-mailbox\n"  # Z = base + span*frac
    "then\n"
)

# Castle door — a dark face on the castle's left/front where Mario walks in (he stops at
# FLAGPOLE_X+2 ≈ the door, then SMB_MARIO_VIS=0 hides him → "entered the castle").
mat_door = make_mat('smb_castle_door', (0.05, 0.04, 0.06))
add_statplat('castle_door', CASTLE_X0 + 0.15, -GROUND_Y - 0.06, GROUND_TOP_Z,
             CASTLE_X0 + 1.35, -GROUND_Y - 0.02, GROUND_TOP_Z + 2.2, mat_door)

# ── Radial spark-burst fireworks (debris idiom, replaces the flat slabs) ──────
# A parked Physics `spark_template` is THROWN by 6 invisible `generator` actors arranged
# in an arc in the open sky above the castle (clear of the flag at Z 7.5). Each generator
# pulses its global activation mailbox during a staggered elapsed window, but ONLY if its
# index < SMB_FIREWORK_COUNT — the faithful SMB count (remaining-timer last digit 1/3/6,
# else 0) the Player latches at celebration start. The generator's up-launch (Object Z
# Velocity) + gravity arc the sparks; SPARK_SCRIPT fans XSPEED by actor index for the
# radial spread; the spark despawns once it falls back below the burst height.
# LOCAL_SYSTEM mailboxes only on the template (a LOCAL_USER write on a default-sized
# template overflows its array → crash); no Random Displacement (Scalar::Random() asserts)
# — the fan is deterministic via the fragment's actor index, like the brick debris.
mat_spark = smb_common.mat_spark()
SPARK_H = 0.16                                          # ~0.32 m spark cube
SPARK_DESPAWN_Z = CASTLE_TOP + 1.5                     # 6.0 — fallen back below the burst → vanish


_make_spark_template()

# 6 invisible generators in an arc in the open sky above the castle. Burst n fires in its
# window iff n < SMB_FIREWORK_COUNT, so a count of 1/3/6 lights 1/3/6 bursts.
FW_SKY_Z = CASTLE_TOP + 5.0   # 9.5 — burst origins above the flag (7.5), in open sky
FW_ARC = [   # (x, z) arc above the castle, centre highest
    (CASTLE_MID_X - 3.0 * T, FW_SKY_Z - 0.5 * T),
    (CASTLE_MID_X - 1.8 * T, FW_SKY_Z + 0.3 * T),
    (CASTLE_MID_X - 0.6 * T, FW_SKY_Z + 0.8 * T),
    (CASTLE_MID_X + 0.6 * T, FW_SKY_Z + 0.8 * T),
    (CASTLE_MID_X + 1.8 * T, FW_SKY_Z + 0.3 * T),
    (CASTLE_MID_X + 3.0 * T, FW_SKY_Z - 0.5 * T),
]
for _i, (_fx, _fz) in enumerate(FW_ARC):
    _t0 = 2.0 + _i * 0.35   # staggered; 0.6 s window → last burst ends ~4.35 (finale 4.5)
    _t1 = _t0 + 0.6
    g = bpy.data.objects.new(f'firework_gen_{_i}', None)   # Empty → meshless, non-solid spawner
    scene.collection.objects.link(g)
    attach_schema(g, 'generator')
    g.location = (_fx, 0.0, _fz)
    g['wf_Mobility']           = 'Anchored'
    g['wf_Model Type']         = 'None'              # invisible
    g['wf_Visibility Mailbox'] = 0
    g['wf_Activation MailBox'] = SMB_FIREWORK[_i]    # global; the script pulses it in-window
    g['wf_Object To Throw']    = 'spark_template'
    g['wf_Generation Rate']    = 10.0               # generator.oas cap; ~6 sparks over the 0.6 s window
    g['wf_Object X Velocity']  = 0.0
    g['wf_Object Y Velocity']  = 0.0                # OAS default 1.0 drifts into +Y — zero it
    g['wf_Object Z Velocity']  = 4.0               # up-launch; gravity arcs the sparks back down
    g['wf_Script'] = (
        "\\ wf\n"
        f"0 INDEXOF_SMB_FIREWORK_{_i} write-mailbox\n"            # default: don't spawn
        "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
        f"  {_i} INDEXOF_SMB_FIREWORK_COUNT read-mailbox < if\n"  # this burst enabled by the count?
        "    INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox -\n"   # elapsed
        f"    dup {_t0:.2f} > swap {_t1:.2f} < & if 1 INDEXOF_SMB_FIREWORK_{_i} write-mailbox then\n"
        "  then\n"
        "then\n"
    )

# ── 10b. Flagpole end-of-level trigger ────────────────────────────────────────
# Composition, NOT a class: an invisible ActBox sensor volume over the flagpole.
# On Player overlap it writes SMB_CELEBRATE=1 → the Director runs the end-of-level
# celebration (pole-flag slide, castle flag raise, timer→score drain) and fires
# END_OF_LEVEL itself at the end. No script, no coordinate baked into a script (the
# box's placement IS the trigger region). See docs/plans/2026-05-31-smb-flagpole-
# celebration.md + 2026-05-25-smb-flagpole-end-of-level.md.
END_OF_LEVEL  = 1905  # INDEXOF_END_OF_LEVEL (wfsource/source/mailbox/mailbox.inc:31)
SMB_CELEBRATE = 1862  # INDEXOF_SMB_CELEBRATE — flag touch starts the celebration cutscene
# Flag-driven level advance: a SECOND ActBox at the flag writes LEVEL_TO_RUN, the
# persistent mailbox the meta-loop reads to pick the next level. shell.fth only seeds
# it on first boot, so the value persists across the reload. mailbox.inc:247 documents
# 5000 as "written by a flagpole ActBox to advance"; a level-side write to 5000 routes
# to WFGame::WriteSystemMailbox (mailbox.cc:90-102) -> _desiredLevelNum (game.cc:705).
# See docs/plans/2026-05-31-smb-flag-next-level-transition-and-w1-2-scaffold.md.
LEVEL_TO_RUN     = 5000   # INDEXOF_LEVEL_TO_RUN (wfsource/source/mailbox/mailbox.inc:247)
NEXT_LEVEL_INDEX = 1      # W1-1 is bundle level 0 -> advance to W1-2 (level 1)

bpy.ops.mesh.primitive_cube_add(size=2.0, location=(FLAGPOLE_X, 0.0, 2 * T))
flagtrig = bpy.context.object
flagtrig.name      = 'flagpole_trigger'
flagtrig.data.name = 'flagpole_trigger'
flagtrig.scale = (1.5, T, 2.5 * T)   # half-extents X±1.5, Y±T, Z±3.75 (centre Z=3): covers Mario at the pole
bpy.ops.object.transform_apply(scale=True)
attach_schema(flagtrig, 'actbox')
flagtrig['wf_MailBox']            = SMB_CELEBRATE  # start the celebration (Director fires END_OF_LEVEL at the end)
flagtrig['wf_MailBoxValue']       = 1
flagtrig['wf_Activated By Actor'] = 'Player'       # ActivatedBy defaults to 1 (Actor)
# ActBox::activate unconditionally writes the activator's index to "Activated Actor
# Mailbox"; its default 0 is a RESERVED mailbox (mailbox.cc asserts >= 2) → abort.
# We don't need the activator, so send it to a scratch slot (SCRATCH_USER_START=4005).
flagtrig['wf_Activated Actor Mailbox'] = 4005
# ActBox DEFAULT_VISIBILITY=0 → invisible; bbox (activation volume) comes from the cube mesh.

# ── 10c. Flagpole ADVANCE trigger (invisible ActBox → next level) ─────────────
# Second ActBox at the SAME volume as flagpole_trigger. On Player overlap it writes
# LEVEL_TO_RUN = NEXT_LEVEL_INDEX so the meta-loop loads the next level after this one
# unloads. Same bbox as the END_OF_LEVEL trigger so both fire on the same frame; order
# is irrelevant because the meta-loop reads _desiredLevelNum only after RunLevel()
# returns. Death sets END_OF_LEVEL without touching LEVEL_TO_RUN, so dying restarts the
# same level — only the flag advances.
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(FLAGPOLE_X, 0.0, 2 * T))
flagadv = bpy.context.object
flagadv.name      = 'flagpole_advance'
flagadv.data.name = 'flagpole_advance'
flagadv.scale = (1.5, T, 2.5 * T)   # identical half-extents to flagpole_trigger
bpy.ops.object.transform_apply(scale=True)
attach_schema(flagadv, 'actbox')
flagadv['wf_MailBox']            = LEVEL_TO_RUN
flagadv['wf_MailBoxValue']       = NEXT_LEVEL_INDEX
flagadv['wf_Activated By Actor'] = 'Player'
flagadv['wf_Activated Actor Mailbox'] = 4005   # scratch sink (same reserved-mb-0 gotcha)

# ── 11. CamShot + Targets ─────────────────────────────────────────────────────
camshot = find_by_class('camshot')
if camshot:
    camshot.location = CAMSHOT_POS
    camshot.name = 'cs_side'
    # All absolute — fixed overview of the starting area
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
    # SMB scroll: read INDEXOF_SMB_TARGET_CAM_X written by the Director on
    # the previous tick (Director runs after main loop, this runs in it),
    # and apply it to our own X via the local INDEXOF_X_POS mailbox. Y and
    # Z stay at the .lev-loaded values (CAM_Y, MARIO_Z+3) untouched.
    camshot['wf_Script'] = (
        "\\ wf\n"
        "INDEXOF_SMB_TARGET_CAM_X read-mailbox INDEXOF_X_POS write-mailbox\n"
    )

# Target01 — world-origin anchor
# Target02 — look-at point (level midpoint at Mario height)
targets = [o for o in bpy.data.objects if get_class(o) == 'target']
while len(targets) < 2:
    tn = bpy.data.objects.new(f'Target_new_{len(targets)}', None)
    scene.collection.objects.link(tn)
    attach_schema(tn, 'target')
    targets.append(tn)

targets[0].location = (0.0, 0.0, 0.0)
targets[0].name = 'Target01'
targets[0]['wf_Model Type'] = 'None'

targets[1].location = LOOKAT_POS
targets[1].name = 'Target02'
targets[1]['wf_Model Type'] = 'None'

# Surface camera zone. The imported actboxor's bbox is offset way out of the room
# (center Z≈52) so it never fires — the surface camera has been running on the
# construct-time EMAILBOX_CAMSHOT bootstrap alone. That's fine until we ALSO switch
# to cs_coin underground: on the RETURN nothing would switch back to cs_side (the
# bootstrap is one-time, abor_coin stops firing). So give the surface zone a real
# in-room volume that re-asserts cs_side every frame the player is on the surface.
# MailBox=1921 (INDEXOF_CAMSHOT — NOT 1021; see the room-switch notes in the plan).
actboxor = find_by_class('actboxor')
if actboxor:
    bpy.data.objects.remove(actboxor, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(SCENE_MID_X, 0.0, 5.0))
abs_ = bpy.context.object
abs_.name = 'abor_surface'; abs_.data.name = 'abor_surface'
abs_.scale = ((GROUND_X1 - GROUND_X0)/2 + 6.0, GROUND_Y + 2.0, 8.0)   # surface playfield, Z[-3,13]
bpy.ops.object.transform_apply(scale=True)
attach_schema(abs_, 'actboxor')
abs_['wf_MailBox']            = 1921
abs_['wf_Object']             = 'cs_side'
abs_['wf_Activated By Actor'] = 'Player'
abs_['wf_Model Type']         = 'None'

# ── 12. Room bbox ─────────────────────────────────────────────────────────────
# Absolute extremes of all actor centres:
#   X: GROUND_X0 .. FLAGPOLE_X+7.5 — now 325 m; bbox must cover all of it.
#   Y: camera at Y=-30, light at Y≈-12       → [-32, +5]
#   Z: ground bottom -T ≈ -1.5, pole top 15  → [-3, +18]
# Room placed at (SCENE_MID_X, 0, 5); bbox is relative to that centre.
ROOM_CENTRE = (SCENE_MID_X, 0.0, 5.0)
_half_span  = (GROUND_X1 - GROUND_X0) / 2 + 5   # covers full level width + margin
RX0, RX1 = -_half_span, _half_span
RY0, RY1 =  -35.0,   10.0
RZ0, RZ1 =  -15.0,   20.0
ROOM_BBOX_REL = (RX0, RY0, RZ0, RX1, RY1, RZ1)

# Coin-room bbox in WORLD space. Its TOP touches the surface room's bottom (Z=-10)
# so room coverage is CONTINUOUS — the camera entity physically pans between camshot
# poses, and if there were a Z gap between the rooms it would land in "no room" mid-pan,
# stop updating, and FREEZE (it's updated only via the active room's update list). The
# player switch still fires: the warp drops Mario to Z=-46.5, well clear of the surface
# room (Z[-10,25]), so he leaves room 0. The upper part (Z -10..-40) is the empty pipe
# shaft the camera travels down. (Surface room bottom = ROOM_CENTRE.z 5 + RZ0 -15 = -10.)
CR_BBOX_WORLD = (CR_X0 - 4.0, -40.0, CR_FLOOR_TOP - 10.0,
                 CR_X1 + 4.0,  12.0, -10.0)                 # x[-4,22] y[-40,12] z[-58,-10]
_cx0,_cy0,_cz0,_cx1,_cy1,_cz1 = CR_BBOX_WORLD
CR_CENTRE = ((_cx0+_cx1)/2, (_cy0+_cy1)/2, (_cz0+_cz1)/2)    # (9, -14, -47)
CR_BBOX_REL = (_cx0-CR_CENTRE[0], _cy0-CR_CENTRE[1], _cz0-CR_CENTRE[2],
               _cx1-CR_CENTRE[0], _cy1-CR_CENTRE[1], _cz1-CR_CENTRE[2])



room = find_by_class('room')
if room:
    room.name = 'room_surface'
    room.location = ROOM_CENTRE
    room['wf_original_bbox'] = ROOM_BBOX_REL
    old = room.data
    room.data = _room_bounds_mesh('RoomBounds', ROOM_BBOX_REL)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

    # Second room: the underground coin room. room.copy() inherits the room schema +
    # Mobility/MovementClass; we give it its own bounds mesh + disjoint bbox.
    coin_room = room.copy()
    scene.collection.objects.link(coin_room)
    coin_room.name = 'room_coin'
    coin_room.location = CR_CENTRE
    coin_room['wf_original_bbox'] = CR_BBOX_REL
    coin_room.data = _room_bounds_mesh('CoinRoomBounds', CR_BBOX_REL)

    # MUTUAL ADJACENCY is load-bearing here. The room SWITCH is bbox-driven (no
    # adjacency needed), but the CAMERA entity is updated only via the active
    # room's update list (level.cc:948-964) — it is not a special/global actor.
    # With a hard switch the camera (which lives in the surface room) goes inactive
    # the instant we switch to the coin room and FREEZES at its last surface pose,
    # so it never adopts cs_coin → the coin room renders off-camera (black screen).
    # Listing the rooms as each other's neighbour keeps BOTH active simultaneously
    # (MAX_ACTIVE_ROOMS=3), so the camera keeps ticking and follows cs_coin down.
    # (room.copy() also carried the snowgoons self-adjacency "room_6"; overwrite it.)
    room['wf_Adjacent Room 1']      = 'room_coin'
    room['wf_Adjacent Room 2']      = ''
    coin_room['wf_Adjacent Room 1'] = 'room_surface'
    coin_room['wf_Adjacent Room 2'] = ''

# ── 14. Pipe warp → underground coin room ─────────────────────────────────────
# Entry pipe + ActBox sense (SMB_AT_PIPE), gated by Down in the player script
# (above). Coin room geometry, a dedicated static CamShot (cs_coin) framing it,
# and an ActBoxOR zone that switches the camera while Mario is underground.
# See docs/plans/2026-05-25-smb-pipe-warp-coin-room.md.
PIPE_GREEN = smb_common.mat_pipe()
CR_FLOOR_MAT = make_mat('smb_cr_floor',   (0.45, 0.22, 0.05))   # dark brick-brown

# Faithful W1-1 surface pipes. PIPE_GREEN is defined above.
# Pipe 1 (cols 28-29, 2T tall), Pipe 2 (cols 38-39, 2T tall) — plain, no warp.
# Pipe 4 exit surface (cols 64-65, 4T tall) — unreachable entry, exit from underground.
_PIPE_H2 = GROUND_TOP_Z + 2*T
_PIPE_H4 = GROUND_TOP_Z + 4*T
add_statplat('pipe_28', 28*T - T, -GROUND_Y, GROUND_TOP_Z,
             28*T + T,  GROUND_Y, _PIPE_H2, PIPE_GREEN)
add_statplat('pipe_38', 38*T - T, -GROUND_Y, GROUND_TOP_Z,
             38*T + T,  GROUND_Y, _PIPE_H2, PIPE_GREEN)
add_statplat('pipe_64', 64*T - T, -GROUND_Y, GROUND_TOP_Z,
             64*T + T,  GROUND_Y, _PIPE_H4, PIPE_GREEN)

# Surface entry pipe: 2 tiles wide × 3 tall (col 46-47 → center 47*T = 70.5 m).
add_statplat('entry_pipe', ENTRY_PIPE_X - T, -GROUND_Y, GROUND_TOP_Z,
             ENTRY_PIPE_X + T,  GROUND_Y, GROUND_TOP_Z + 3*T, PIPE_GREEN)

# Entry sense: a thin ActBox lid over the pipe mouth. The band must sit at the pipe
# TOP so Mario standing there (origin Z≈4.5 on the 3T pipe) overlaps it, while a
# ground walk-past (origin Z≈1.5) does not. BUG FIX 2026-05-31: this box was authored
# for the old 2T pipe (band [2.8,4.0], "feet Z=3"); the faithful expansion made
# entry_pipe 3T (top 4.5) but left the box behind, so standing on top fell ABOVE the
# band and the warp never triggered (verified: SMB_AT_PIPE 0/30 frames). Raised to the
# 3T mouth: GROUND_TOP_Z + 3*T + 0.2 = 4.7 → band [4.1,5.3] covers the resting origin.
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(ENTRY_PIPE_X, 0.0, GROUND_TOP_Z + 3*T + 0.2))
es = bpy.context.object
es.name = 'pipe_entry_sense'; es.data.name = 'pipe_entry_sense'
es.scale = (T, GROUND_Y, 0.6)
bpy.ops.object.transform_apply(scale=True)
attach_schema(es, 'actbox')
es['wf_MailBox']                 = SMB_AT_PIPE
es['wf_MailBoxValue']            = 1
es['wf_ClearOnExit']             = 'True'    # reset SMB_AT_PIPE when Mario steps off
es['wf_Mailbox Exit Value']      = 0
es['wf_Activated By Actor']      = 'Player'
es['wf_Activated Actor Mailbox'] = 4005      # scratch (must be >=2; default 0 aborts)

# Coin-room floor + side walls (contain Mario; exit pipe gap comes in Phase B).
# WIDE in Y (±5) and THICK in Z (4 units) on purpose: the warp-landing can penetrate
# the floor slightly and Jolt then depenetrates the character *sideways* (it drifted to
# Y≈-2.2 and fell off a Y±1.5 floor through the room bottom). A wide+thick slab keeps
# him on it regardless of landing jitter. (Surface ground is narrow because Mario never
# warp-lands there.)
add_statplat('cr_floor',  CR_X0 - 1, -5.0, CR_FLOOR_TOP - 4.0,
             CR_X1 + 1,    5.0, CR_FLOOR_TOP,        CR_FLOOR_MAT)
add_statplat('cr_wall_l', CR_X0 - 1, -GROUND_Y, CR_FLOOR_TOP,
             CR_X0,        GROUND_Y, CR_FLOOR_TOP + 10*T,  CR_FLOOR_MAT)
add_statplat('cr_wall_r', CR_X1,     -GROUND_Y, CR_FLOOR_TOP,
             CR_X1 + 1,    GROUND_Y, CR_FLOOR_TOP + 10*T,  CR_FLOOR_MAT)

# Collectible coins: static gold discs the player collects by proximity (the player
# script awards GOLD and flips each coin's visibility mailbox off). Pre-placed `gold`
# actors can't be used — the gold class TTL is hardcoded 5 s so they'd despawn before
# Mario arrives (see TODO). Mario warps in at X=3 and walks RIGHT past these to the
# exit warp (X=12), collecting them en route.
COIN_DISC_MAT = make_mat('smb_coinroom_coin', (1.0, 0.84, 0.0))
# 19 coins in 3 rows — faithful W1-1 underground room (SMBDIS.ASM L_UndergroundArea3).
# Row 7 (low): cols 4-10 (7 coins). Row 5 (mid): cols 4-10 (7 coins). Row 3 (top): cols 5-9 (5 coins).
# Pickup uses X-proximity + player-Z underground gate; coin Z is purely visual.
_CR_LOW_Z  = CR_FLOOR_TOP + 4.5*T   # -41.25 — row 7
_CR_MID_Z  = CR_FLOOR_TOP + 6.5*T   # -38.25 — row 5
_CR_HIGH_Z = CR_FLOOR_TOP + 8.5*T   # -35.25 — row 3
CR_COINS = [
    # (X,         Z,         mailbox)
    # Row 7 (lowest) — cols 4-10
    (4.5*T,  _CR_LOW_Z,  SMB_COIN_0),
    (5.5*T,  _CR_LOW_Z,  SMB_COIN_1),
    (6.5*T,  _CR_LOW_Z,  SMB_COIN_2),
    (7.5*T,  _CR_LOW_Z,  SMB_COIN_3),
    (8.5*T,  _CR_LOW_Z,  SMB_COIN_4),
    (9.5*T,  _CR_LOW_Z,  SMB_COIN_5),
    (10.5*T, _CR_LOW_Z,  SMB_COIN_6),
    # Row 5 (middle) — cols 4-10
    (4.5*T,  _CR_MID_Z,  SMB_COIN_7),
    (5.5*T,  _CR_MID_Z,  SMB_COIN_8),
    (6.5*T,  _CR_MID_Z,  SMB_COIN_9),
    (7.5*T,  _CR_MID_Z,  SMB_COIN_10),
    (8.5*T,  _CR_MID_Z,  SMB_COIN_11),
    (9.5*T,  _CR_MID_Z,  SMB_COIN_12),
    (10.5*T, _CR_MID_Z,  SMB_COIN_13),
    # Row 3 (top) — cols 5-9
    (5.5*T,  _CR_HIGH_Z, SMB_COIN_14),
    (6.5*T,  _CR_HIGH_Z, SMB_COIN_15),
    (7.5*T,  _CR_HIGH_Z, SMB_COIN_16),
    (8.5*T,  _CR_HIGH_Z, SMB_COIN_17),
    (9.5*T,  _CR_HIGH_Z, SMB_COIN_18),
]
# Spinning coin discs (NOT statplats): anchored 'enemy'-schema mesh actors so they
# run COIN_SCRIPT (ROTATION_C = TIME) and spin like the surface coins, without
# gold.cc's 5 s TTL despawning them (the popup_score actor uses the same trick).
# Pickup is true-XZ contact in the player script above. One shared disc mesh; each
# coin exports its own cr_coin_N.iff.
_crc_mesh = bpy.data.meshes.new('cr_coin')
_crc_bm = _bmesh.new()
_bmesh.ops.create_cube(_crc_bm, size=1.0)
_bmesh.ops.scale(_crc_bm, vec=(COIN_X*2, COIN_T*2, COIN_Z*2), verts=_crc_bm.verts)
_crc_bm.to_mesh(_crc_mesh); _crc_bm.free()
_crc_mesh.materials.append(mat_coin)
for _p in _crc_mesh.polygons:
    _p.material_index = 0
for _ci, (_cx, _cz, _cmb) in enumerate(CR_COINS):
    _coin = bpy.data.objects.new(f'cr_coin_{_ci}', _crc_mesh)
    scene.collection.objects.link(_coin)
    _coin.location = (_cx, 0.0, _cz)
    attach_schema(_coin, 'enemy')
    _coin['wf_Mobility']           = 'Anchored'
    _coin['wf_Model Type']         = 'Mesh'
    _coin['wf_Visibility Mailbox'] = _cmb   # seeded to 1, set to 0 on pickup
    # No per-instance wf_Mesh Name — all coins share the _crc_mesh datablock, so the
    # exporter dedup writes one cr_coin .iff and every coin references it (one room-pool
    # mesh, not 19). (A per-instance name would defeat the dedup, as it did before.)
    _coin['wf_Script']             = COIN_SCRIPT


# Entry landing (where Down warps Mario) + cs_coin look-at point.
_make_target('Target_cr_entry',  (CR_ENTRY_X, 0.0, CR_ENTRY_Z))
_make_target('Target_cr_lookat', (CR_MID, 0.0, CR_FLOOR_TOP + T))

# cs_coin: static shot framing the whole coin room (no scroll script → unlike
# cs_side it does not read SMB_TARGET_CAM_X). Direction = lookat - campos.
cs_coin = bpy.data.objects.new('cs_coin', None)
scene.collection.objects.link(cs_coin)
attach_schema(cs_coin, 'camshot')
cs_coin.location = (CR_MID, -35.0, CR_FLOOR_TOP + 4.5)    # centred on room, inside coin-room bbox
cs_coin['wf_Position X'] = 'Absolute'
cs_coin['wf_Position Y'] = 'Absolute'
cs_coin['wf_Position Z'] = 'Absolute'
cs_coin['wf_Rotation']   = 'Fixed'
cs_coin['wf_FOV']                 = 35.0
cs_coin['wf_Pan Time In Seconds'] = 0.1
cs_coin['wf_Model Type']          = 'None'
cs_coin['wf_Track Object'] = 'Player'
cs_coin['wf_Target']       = 'Target_cr_lookat'
cs_coin['wf_Follow']       = 'Target_cr_lookat'

# abor_coin: ActBoxOR volume over the coin-room play space (centred on the player
# plane Y=0, NOT the bbox Y-centre). While Mario is inside it writes cs_coin's
# index to EMAILBOX_CAMSHOT (1021) each frame, so the camera tracks him underground.
# Volume is entirely below Z=-37 → disjoint from the surface camera zone.
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(CR_MID, 0.0, CR_FLOOR_TOP + 4.5))
ab = bpy.context.object
ab.name = 'abor_coin'; ab.data.name = 'abor_coin'
ab.scale = ((CR_X1 - CR_X0)/2 + 1.0, GROUND_Y + 2.0, 6.0)   # X[-1,25] Y[-3.5,3.5] Z[-49.5,-37.5]
bpy.ops.object.transform_apply(scale=True)
attach_schema(ab, 'actboxor')
ab['wf_MailBox']            = 1921        # INDEXOF_CAMSHOT (mailbox.inc:59 — NOT 1021; the
                                          # level-building.md scope table is wrong, verified
                                          # against the engine's `zforth: INDEXOF_CAMSHOT = 1921`)
ab['wf_Object']             = 'cs_coin'
ab['wf_Activated By Actor'] = 'Player'
ab['wf_Model Type']         = 'None'

# Coin-room light: the surface Light01 lives in the surface room and unloads on the
# switch, so without a light here the underground renders pure black (engine warns
# " has no lights, gonna be hard to see!"). Clone the surface directional light.
if light:
    coin_light = light.copy()
    scene.collection.objects.link(coin_light)
    coin_light.name = 'Light_coin'
    coin_light.location = (CR_MID, -22.0, CR_FLOOR_TOP + 6.0)   # centre of room, inside coin-room bbox
    coin_light.rotation_euler = (math.pi / 3, 0, 0)

# ── 15. Exit pipe → warp back to the surface (Phase B) ────────────────────────
# A pure Warp + Target: Mario walks RIGHT into the warp volume → teleported to the
# surface return point (past the entry pipe, so no instant re-trigger; the entry
# needs Down anyway). The Warp class teleports any overlapping actor in its filter
# (no input gate needed for a walk-into exit) — this validates Warp's Jolt teleport.
# Exit pipe flush with right wall (CR_X1=24); warp sensor 3 tiles to its left.
EXIT_PIPE_X0, EXIT_PIPE_X1 = 13*T, 15*T   # = [19.5, 22.5]  cols 13-14, 2-tile wide pipe
add_statplat('exit_pipe', EXIT_PIPE_X0, -GROUND_Y, CR_FLOOR_TOP,
             EXIT_PIPE_X1,  GROUND_Y, CR_FLOOR_TOP + 2*T, PIPE_GREEN)

# Surface return: solidly past the entry pipe (ENTRY_PIPE_X ± T = 69–72 m).
_make_target('Target_surface_return', (ENTRY_PIPE_X + 3*T, 0.0, MARIO_SPAWN_Z))

# Warp volume just LEFT of the exit pipe — 3 tiles wide, centred between coin end and pipe.
_warp_cx = EXIT_PIPE_X0 - 1.5*T          # centre of warp zone: EXIT_PIPE_X0 - 2.25 = 17.25
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(_warp_cx, 0.0, CR_FLOOR_TOP + 1.0))
wp = bpy.context.object
wp.name = 'pipe_exit_warp'; wp.data.name = 'pipe_exit_warp'
wp.scale = (1.5, GROUND_Y, 1.0)        # ±1.5 → X[_warp_cx-1.5, _warp_cx+1.5]
bpy.ops.object.transform_apply(scale=True)
attach_schema(wp, 'warp')
wp['wf_Target']             = 'Target_surface_return'
wp['wf_Activated By Actor'] = 'Player'
wp['wf_Model Type']         = 'None'
# warp.oas has no DEFAULT_MODEL_TYPE override (unlike actbox.oas's =3), so the
# volume mesh would render as a white debug box. Activation is independent of
# rendering, so force always-invisible (Visibility Mailbox 0 = mb[0] = always false).
wp['wf_Visibility Mailbox'] = 0

# ── 16. Breakable bricks ──────────────────────────────────────────────────────
# Super Mario shatters a brick from below (4-fragment debris burst + despawn);
# Small Mario only bumps it (a brief upward nudge, brick stays solid). Each brick
# is a Generator that throws `debris_template` on a Super hit. Built LAST (right
# before export) so the new actors take fresh high indices and the existing static
# indices the test harnesses hardcode (Player, qblock_00) don't shift.
# See docs/plans/2026-05-26-breakable-bricks-smb-world-1-1.md.
brick_tex = _make_brick_tga(os.path.join(SCRIPT_DIR, 'brick_tex.tga'))
smb_common.set_textures(brick=brick_tex)

# Per-actor local brick state (must match mailbox.inc). The brick reuses
# SMB_QBLOCK_ACTIVATE (2010) as its debris-throw pulse.
MB_SMB_BRICK_BREAK_END = 2013
MB_SMB_BRICK_BUMP_END  = 2014
MB_SMB_BRICK_BUMP_PEAK = 2015

# Debris fragment — a small physics body that arcs up, falls (through the floor,
# off-screen — generator-vs-ground isn't in objects.mac COLTABLE), and self-despawns
# after ~1 s. It is a `generator` class (NOT `gold`) on purpose: gold would award a
# coin on pickup (the stale-OAD path drops Gold Value 0, TODO §63), whereas a
# generator that throws nothing has no scoring path at all. Activation MailBox 0
# (mailbox[0] = always-false) means its own spawn branch never runs.
mat_debris = smb_common.mat_debris()
DEBRIS_H = 0.18   # half-extent → ~0.36 m cube (quarter-brick chunk)

# DEBRIS_SCRIPT: tumble (ROTATION_C = time) and hold a DETERMINISTIC outward X velocity
# fanned by the fragment's own actor index — `idx 4 % 1.5 - 3.0 *` → {-4.5,-1.5,+1.5,+4.5}
# m/s — so fragments split left/right like the NES shatter (set every tick = constant
# horizontal drift; the generator's +Z launch + gravity gives the arc). Despawn once the
# fragment has fallen below the floor (Z < -20). Uses ONLY LOCAL_SYSTEM mailboxes
# (3000+, always allocated), so the template needs no Number Of Local Mailboxes — writing
# a LOCAL_USER slot (2000-2099) on a default-sized template overflows its array → crash.
# (The engine's Random Displacement path is unusable: Scalar::Random() asserts via
# RangeCheck's integer cast — see TODO.) `%` casts to int in zForth.

_make_debris_template()

# BRICK_SCRIPT — three behaviours, gated on the global SMB_MARIO_STATE the player owns:
#   • break window open (SMB_BRICK_BREAK_END set): keep pulsing the debris generator
#     until TIME passes the window end, then ALIVE=0 → brick vanishes.
#   • bump in progress (SMB_BRICK_BUMP_END set): write an ADDITIVE Z offset that rises
#     (0.30) then settles (0.10 → 0) — never a world Z (world-baked mesh, additive).
#   • idle/solid: on a hit-from-below (COLLIDER_IDX≠0 & COLLISION_NORMAL_Z>0, the proven
#     qblock gate), Super (state≠0) opens the break window + pulses; Small latches a bump.
# Ordering matters: on the first break tick we set the window end AND pulse, but defer
# ALIVE=0 to a later tick so the Generator (spawn-check runs before the script) actually
# throws fragments across the window first (plan risk #3).

# Faithful W1-1 brick layout (docs/smb-level-layouts.md §1-1):
#   Cols 20, 22, 24 — cluster flanking the coin ? blocks at cols 21, 23
#   Cols 91-98     — extended overhead brick row (8 wide)
#   Cols 108, 110  — hi-row bricks flanking the flower ? block at col 109 (row 6)
BLOCK_Z_6 = GROUND_TOP_Z + 6*T + T/2   # row-6 block centre (2 tiles above BLOCK_Z)

_add_brick('brick_0', 20*T)
_add_brick('brick_1', 22*T)
_add_brick('brick_2', 24*T)

for _bi, _bc in enumerate(range(91, 99)):
    _add_brick(f'brick_row_{_bi}', _bc * T)

_add_brick('brick_hi_0', 108*T, z=BLOCK_Z_6)
_add_brick('brick_hi_1', 110*T, z=BLOCK_Z_6)
# Also add a coin ? block at col 107 (row 8) and a flower ? block at col 109 (row 6)
_make_powerup_block('qblock_107', 107*T, 'powerup_template', 0.0)
_make_powerup_block('fireflower_block_hi', 109*T, 'powerup_template', 0.0, z=BLOCK_Z_6)

# Hidden 1UP brick — tile 40 (x=60m), just before the flagpole (x=63m).
# Looks like a plain brick; hit from below → launches a green 1UP mushroom that
# slides right; player catches it for +1 life. Faithful to W1-1 hidden 1UP.
ONEUP_BRICK_X = 57 * T   # 85.5 — col 57, hidden 1-UP block (was 40*T)
hbrick_1up = _add_textured_box('brick_1up',
                               ONEUP_BRICK_X - BSIZE, -BSIZE, BLOCK_Z - BSIZE,
                               ONEUP_BRICK_X + BSIZE,  BSIZE, BLOCK_Z + BSIZE,
                               brick_tex)
attach_schema(hbrick_1up, 'generator')
hbrick_1up['wf_Mobility']           = 'Anchored'
hbrick_1up['wf_Model Type']         = 'Mesh'
hbrick_1up['wf_Visibility Mailbox'] = 1
hbrick_1up['wf_Number Of Local Mailboxes'] = 13
hbrick_1up['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
hbrick_1up['wf_Object To Throw']    = 'oneup_template'
hbrick_1up['wf_Generation Rate']    = 10.0
hbrick_1up['wf_Object X Velocity']  = 1.5
hbrick_1up['wf_Object Y Velocity']  = 0.0
hbrick_1up['wf_Object Z Velocity']  = 6.0
hbrick_1up['wf_Script']             = POWERUP_BLOCK_SCRIPT

# ── 12b. Score pop-up actor (docs/plans/2026-05-27-smb-score-pop-up-actors.md) ─
# Pre-placed diamond actor parked underground at (0,0,-5), inside the surface room
# bbox (x[-66,133] z[-10,25]) so its script runs every tick.  Scoring events write
# SMB_POPUP_X/Z + pulse SMB_POPUP_TRIGGER=1; this script teleports the diamond
# above the event, floats it up for 0.75 s, then parks it back underground.
# Uses `enemy` schema (Anchored) so gold.cc::TryPickup never despawns it.


_make_popup_template()

# ── 12c. Pyramids + staircase (faithful W1-1 terrain features) ───────────────
mat_hard = smb_common.mat_hard()


_add_pyramid('pyramid_a', base_col=134)
_add_pyramid('pyramid_b', base_col=148)
_add_staircase('staircase', base_col=198)

# ── 13. Export ────────────────────────────────────────────────────────────────
print(f"[smb] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print("[smb] Objects in scene:", [o.name for o in bpy.data.objects])
print(f"[smb] Done — {OUT_LEV}")
