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
OUT_LEV    = os.path.join(SCRIPT_DIR, 'smb_w1_2.lev')
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

# Mario tint colours the player script drives (orig W1-1 §6). Kept even though W1-2
# is bare: _build_mario references them for Fire-Mario warm-white + the Star flicker.
FIRE_TINT          = 0xF8F0E0   # warm white (Fire Mario)
MARIO_DEFAULT_TINT = 0xFFFFFF   # neutral restore
STAR_FLASH_A       = 0xFFE000   # Star-invincibility flicker yellow
STAR_FLASH_B       = 0xFFFFFF   # Star-invincibility flicker white

# W1-2 landmark X positions (tile counts × T) — faithful 256-tile underground.
# docs/smb-level-layouts.md §1-2. Coin ?-blocks, bricks, and Koopas are placed
# explicitly in the population section below, so QBLOCK_XS / KOOPA_X are kept for
# symmetry with W1-1 but left unused here.
MARIO_SPAWN_X = 3  * T
QBLOCK_XS     = []                       # W1-2 ? blocks placed explicitly (5-block row + others)
KOOPA_X       = None                     # W1-2 koopas placed explicitly (3 green + 1 red)
FLAGPOLE_X    = 248 * T                  # 372 m — faithful W1-2 (256-tile underground, flagpole col 248)

# ── Celebration mailboxes (mailbox.inc 1862-1871) — flagpole end-of-level cutscene ──
# Mario walks into the castle + hides, the rooftop flag raises, radial spark fireworks
# pop above the castle (count = remaining-timer last digit if 1/3/6 else 0). Identical
# machinery to W1-1 (ported, not re-derived; FLAGPOLE_X-relative so it follows col 248).
# (SMB_CELEBRATE itself is defined at the flagpole trigger below — the only Python use.)
SMB_CELEBRATE_START = 1863   # level-TIME at the rising edge; phase elapsed = TIME - this
SMB_MARIO_VIS       = 1864   # Player visibility (1=show, 0=hide once he enters the castle)
SMB_FIREWORK        = [1865, 1866, 1867, 1868, 1869, 1870]  # 6 firework-generator activations
SMB_FIREWORK_COUNT  = 1871   # how many bursts fire = remaining-timer last digit if 1/3/6 else 0

# 14 Goombas at faithful W1-2 reference positions (docs/smb-level-layouts.md §1-2):
#   S1 2 after entry + 1 on the block-tower; S2 cluster of 5 + 1 flanking the Koopas;
#   S3 2 before the pipe corridor; S4 2 on the half-pyramid. Total = 14.
GOOMBA_XS = [
    12*T, 16*T,                          # S1: 2 Goombas after the entry pipe
    28*T,                                # S1: Goomba on the block tower
    58*T,                                # S2: Goomba flanking the Koopas
    71*T, 74*T, 77*T, 80*T, 83*T,        # S2: cluster of 5 Goombas
    122*T, 126*T,                        # S3: 2 Goombas before the pipe corridor
    191*T, 194*T,                        # S4: 2 Goombas on the half-pyramid
]

GROUND_X0 = -2 * T
GROUND_X1 = FLAGPOLE_X + 5*T
GROUND_Y  = T                             # half-depth of ground slab in Y

# W1-2 Section 4 has 2 gaps (docs/smb-level-layouts.md §1-2). Each (x_left, x_right)
# span is skipped when the ground slabs are built, leaving a real bottomless hole; the
# existing pit-death-sensor loop drops an invisible ActBox under each so a fall costs a
# life. ~3-tile gaps the player jumps across (or rides the static lift-platforms over).
PITS = [
    (184*T, 187*T),                      # S4 gap 1 (cols 184-187)
    (199*T, 202*T),                      # S4 gap 2 (cols 199-202)
]

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
ENTRY_PIPE_X = 130 * T            # = 195.0 — Section-3 pipe 1 (col 130); leads to the bonus coin room
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
#    See docs/plans/2026-06-02-smb-common-extraction-and-mesh-sharing.md (Phase P1b).
import sys as _sys
_sys.path.insert(0, os.path.join(SCRIPT_DIR, '..'))
import smb_common
smb_common.init(scene, OAD_DIR)
from smb_common import (make_mat, attach_schema, find_by_class, get_class,
    add_box, add_statplat, _add_textured_box, _make_qblock_tga, _make_brick_tga,
    _make_grid_tile_tga, build_textured_ground_mesh, _room_bounds_mesh, _build_mario)
from smb_common import (_add_brick, _make_powerup_block, _add_qblock)
from smb_common import (_make_coin_template, _make_debris_template, _make_spark_template, _make_powerup_template, _add_pyramid, _add_staircase, _add_pipe)
from smb_common import (_apply_enemy_movement, _build_goomba, _make_target, _make_popup_template)
from smb_common import (
    QBLOCK_SCRIPT, DEBRIS_SCRIPT, SPARK_SCRIPT, BRICK_SCRIPT, POPUP_SCRIPT, ENEMY_SCRIPT, KOOPA_SCRIPT, POWERUP_BLOCK_SCRIPT, POWERUP_SCRIPT, STAR_SCRIPT, ONEUP_SCRIPT, PIRANHA_SCRIPT)

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
    director['wf_Script'] = smb_common.director_script({'FLAGPOLE_X': FLAGPOLE_X, 'TIMER_UNITS': TIMER_UNITS, 'TIMER_REAL_SECONDS': TIMER_REAL_SECONDS})

levelobj = find_by_class('levelobj')
if levelobj:
    levelobj.location = (0, CAM_Y - 2, MARIO_Z)
    levelobj['wf_Number Of Mailboxes'] = NUM_MAILBOXES
    levelobj['wf_Model Type'] = 'None'

matte = find_by_class('matte')
if matte:
    matte.location = (SCENE_MID_X, CAM_Y - 2, MARIO_Z)
    matte['wf_Matte Type'] = 'Color'
    matte['wf_Background Color'] = 0x041018   # near-black teal — SMB underground
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

# ── 5b. Brick ceiling (underground signature) ─────────────────────────────────
# A solid brick-coloured slab spanning the corridor, 9 tiles up. This is what
# gives the bare W1-2 its "underground" read alongside the near-black matte.
mat_ceiling = make_mat('smb_ug_ceiling', (0.55, 0.30, 0.14))
CEIL_Z = GROUND_TOP_Z + 5 * T   # 7.5 m — low cave ceiling, in the side-camera frame
add_statplat('ceiling',
             GROUND_X0, -GROUND_Y, CEIL_Z,
             GROUND_X1,  GROUND_Y, CEIL_Z + GROUND_THICK,
             mat_ceiling)

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
    player['wf_Script'] = smb_common.player_script({'CR_ENTRY_X': CR_ENTRY_X, 'CR_ENTRY_Z': CR_ENTRY_Z, 'FIRE_TINT': FIRE_TINT, 'FLAGPOLE_X': FLAGPOLE_X, 'GROUND_X0': GROUND_X0, 'GROUND_X1': GROUND_X1, 'GROUND_Y': GROUND_Y, 'MARIO_DEFAULT_TINT': MARIO_DEFAULT_TINT, 'MARIO_SPAWN_X': MARIO_SPAWN_X, 'MARIO_SPAWN_Z': MARIO_SPAWN_Z, 'STAR_FLASH_A': STAR_FLASH_A, 'STAR_FLASH_B': STAR_FLASH_B})

    mario_mesh = _build_mario()
    old = player.data
    player.data = mario_mesh.data
    bpy.data.objects.remove(mario_mesh, do_unlink=True)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

# ── 10. Flagpole ──────────────────────────────────────────────────────────────
mat_pole = make_mat('smb_pole', (0.72, 0.72, 0.72))
mat_flag = make_mat('smb_flag', (0.10, 0.65, 0.16))

POLE_HEIGHT = 10 * T
POLE_RADIUS = 0.10 * T

# Pole — thin cylinder from ground to 10 tiles high
bpy.ops.mesh.primitive_cylinder_add(
    vertices=8, radius=POLE_RADIUS, depth=POLE_HEIGHT,
    location=(FLAGPOLE_X, 0, POLE_HEIGHT / 2))
pole_obj = bpy.context.object
pole_obj.name      = 'flagpole_pole'
pole_obj.data.name = 'flagpole_pole'
pole_obj.data.materials.clear()
pole_obj.data.materials.append(mat_pole)
attach_schema(pole_obj, 'statplat')
pole_obj['wf_Visibility Mailbox'] = 1
pole_obj['wf_Model Type'] = 'Mesh'

# Flag — a scriptable Anchored 'enemy' (statplats can't tick a script) so it SLIDES DOWN
# the pole during the celebration: phase A (elapsed 0–0.9 s) lerps its Z from the top to
# the base. Before SMB_CELEBRATE it sits at the authored top. A thin VERTICAL slab (a flat
# plane lies in XY → edge-on/invisible to the side camera).
FLAG_TOP_Z  = POLE_HEIGHT - T        # 13.5 — authored start (near pole top)
FLAG_BASE_Z = T * 0.7                # ~1.05 — slide target (pole base, the "grab")
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
# (Player walk phase); its rooftop flag RAISES (0.8–1.4 s); then up to 6 radial spark
# fireworks pop above it. The flags + fireworks are scriptable Anchored 'enemy' actors
# driving their own Z / visibility off the celebration clock (elapsed = TIME − START).
mat_castle = make_mat('smb_castle', (0.60, 0.55, 0.50))
CASTLE_X0, CASTLE_X1 = FLAGPOLE_X + 1.5 * T, FLAGPOLE_X + 4.5 * T   # on the ground, right of the pole
CASTLE_TOP   = 3 * T                                               # 4.5 m tall
CASTLE_MID_X = (CASTLE_X0 + CASTLE_X1) / 2
add_statplat('castle', CASTLE_X0, -GROUND_Y, GROUND_TOP_Z, CASTLE_X1, GROUND_Y, CASTLE_TOP, mat_castle)
add_statplat('castle_pole', CASTLE_MID_X - 0.1, -0.1, CASTLE_TOP,
             CASTLE_MID_X + 0.1, 0.1, CASTLE_TOP + 2 * T, mat_pole)

CFLAG_BASE_Z = CASTLE_TOP                          # 4.5 — authored low (rooftop base)
CFLAG_TOP_Z  = CASTLE_TOP + 2.0 * T - 0.35 * T     # flag TOP (not center) meets the pole top 7.5
# Thin VERTICAL slab; X so the flag's right edge overlaps the pole centre (attached, not floating).
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

# Castle door — a dark face where Mario walks in (he stops at FLAGPOLE_X+2 ≈ the door,
# then SMB_MARIO_VIS=0 hides him → "entered the castle").
mat_door = make_mat('smb_castle_door', (0.05, 0.04, 0.06))
add_statplat('castle_door', CASTLE_X0 + 0.15, -GROUND_Y - 0.06, GROUND_TOP_Z,
             CASTLE_X0 + 1.35, -GROUND_Y - 0.02, GROUND_TOP_Z + 2.2, mat_door)

# ── Radial spark-burst fireworks (debris idiom) ───────────────────────────────
# A parked Physics `spark_template` is THROWN by 6 invisible `generator` actors in an arc
# in the open sky above the castle. Each generator pulses its activation mailbox during a
# staggered window, but ONLY if its index < SMB_FIREWORK_COUNT (the faithful 1/3/6 count
# the Player latched). The up-launch + gravity arc the sparks; SPARK_SCRIPT fans XSPEED by
# actor index for the radial spread; the spark despawns once it falls below the burst height.
# LOCAL_SYSTEM mailboxes only on the template; no Random Displacement (Scalar::Random asserts).
mat_spark = smb_common.mat_spark()
SPARK_H = 0.16                                          # ~0.32 m spark cube
SPARK_DESPAWN_Z = CASTLE_TOP + 1.5                     # fallen back below the burst → vanish


_make_spark_template()

# 6 invisible generators in an arc in the open sky above the castle. Burst n fires in its
# window iff n < SMB_FIREWORK_COUNT, so a count of 1/3/6 lights 1/3/6 bursts.
FW_SKY_Z = CASTLE_TOP + 5.0   # burst origins above the flag (7.5), in open sky
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
# celebration (pole-flag slide, castle flag raise, timer→score drain, fireworks) and
# fires END_OF_LEVEL itself at the end. No script, no coordinate baked into a script
# (the box's placement IS the trigger region).
# See docs/plans/2026-05-31-smb-flagpole-celebration.md + 2026-05-25-smb-flagpole-end-of-level.md.
END_OF_LEVEL  = 1905   # INDEXOF_END_OF_LEVEL (wfsource/source/mailbox/mailbox.inc:31)
SMB_CELEBRATE = 1862   # INDEXOF_SMB_CELEBRATE — flag touch starts the celebration cutscene
# Flag-driven level advance: a SECOND ActBox at the flag writes LEVEL_TO_RUN, the
# persistent mailbox the meta-loop reads to pick the next level. shell.fth only seeds
# it on first boot, so the value persists across the reload. mailbox.inc:247 documents
# 5000 as "written by a flagpole ActBox to advance"; a level-side write to 5000 routes
# to WFGame::WriteSystemMailbox (mailbox.cc:90-102) -> _desiredLevelNum (game.cc:705).
# See docs/plans/2026-05-31-smb-flag-next-level-transition-and-w1-2-scaffold.md.
LEVEL_TO_RUN     = 5000   # INDEXOF_LEVEL_TO_RUN (wfsource/source/mailbox/mailbox.inc:247)
NEXT_LEVEL_INDEX = 0      # W1-2 is bundle level 1 -> loop back to W1-1 (level 0; no W1-3 yet)

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

    # Second room: the W1-2 bonus coin room (pipe-warp target). Same idiom as W1-1 §14 —
    # room.copy() inherits the schema + Mobility/MovementClass; we give it its own bounds
    # mesh + disjoint bbox. MUTUAL ADJACENCY is load-bearing: the room SWITCH is bbox-driven
    # but the camera entity is updated only via the active room's update list, so listing the
    # rooms as each other's neighbour keeps BOTH active (MAX_ACTIVE_ROOMS=3) and the camera
    # keeps ticking + follows cs_coin down. (room.copy() also carried snowgoons' self-adjacency
    # "room_6"; overwrite it.)
    coin_room = room.copy()
    scene.collection.objects.link(coin_room)
    coin_room.name = 'room_coin'
    coin_room.location = CR_CENTRE
    coin_room['wf_original_bbox'] = CR_BBOX_REL
    coin_room.data = _room_bounds_mesh('CoinRoomBounds', CR_BBOX_REL)

    room['wf_Adjacent Room 1']      = 'room_coin'
    room['wf_Adjacent Room 2']      = ''
    coin_room['wf_Adjacent Room 1'] = 'room_surface'
    coin_room['wf_Adjacent Room 2'] = ''

# ══════════════════════════════════════════════════════════════════════════════
# W1-2 POPULATION (faithful per docs/smb-level-layouts.md §1-2). All builders are
# copied VERBATIM from wflevels/smb_w1_1/blender_create_smb.py — they reference the
# module globals already defined above. The inline W1-1 Koopa is factored into
# _build_koopa(x, red=False) so this level can place 4 (3 green + 1 red).
# Layout left→right across cols 0-256 (X = col × T):
#   S1 (0-40)   S2 (40-120)   S3 (120-180)   S4 (180-230)   S5 (230-256)
#   + bonus coin room (pipe-warp) + decorative warp zone.
# ══════════════════════════════════════════════════════════════════════════════
import bmesh as _bmesh

# ── Shared materials / textures / constants (verbatim from W1-1 §6) ────────────
mat_coin = smb_common.mat_coin()
BSIZE = T / 2  # half-side of a 1-tile block
qblock_tex = _make_qblock_tga(os.path.join(SCRIPT_DIR, 'qblock_tex.tga'))
smb_common.set_textures(qblock=qblock_tex)
brick_tex  = _make_brick_tga(os.path.join(SCRIPT_DIR, 'brick_tex.tga'))
smb_common.set_textures(brick=brick_tex)
COIN_X = T * 0.25
COIN_Z = T * 0.5
COIN_T = 0.2

# Per-actor local block state (matches mailbox.inc 2010-2015).
MB_SMB_QBLOCK_ACTIVATE = 2010
MB_SMB_QBLOCK_USED     = 2011
MB_SMB_QBLOCK_DIE      = 2012
MB_SMB_BRICK_BREAK_END = 2013
MB_SMB_BRICK_BUMP_END  = 2014
MB_SMB_BRICK_BUMP_PEAK = 2015
# Per-actor Piranha state (mailbox.inc 2016-2017 — NEW; per-plant so 4 oscillate independently).
MB_SMB_PIRANHA_UP   = 2016
MB_SMB_PIRANHA_NEXT = 2017

QBLOCK_TAN  = 0xC77D2E
FLOWER_TINT = 0xF2731A

# Row heights (block centres). BLOCK_Z = row 8; BLOCK_Z_6 = row 6 (2 tiles higher).
BLOCK_Z_6 = GROUND_TOP_Z + 6*T + T/2

# ── Scripts (verbatim from W1-1) ──────────────────────────────────────────────

COIN_SCRIPT = "\\ wf\nINDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"





ENEMY_WALK_SPEED = 4.0

# Koopa shell-kick — object-oriented PER-ACTOR state via the local slot SMB_KOOPA_STATE_L
# (2018), so each of the 4 Koopas walks/retracts/slides on its own state machine (local
# mailboxes are per-actor → no cross-talk). Each Koopa needs Number Of Local Mailboxes ≥ 19.
# (Sliding-shell broadcasts SMB_SHELL_LIVE_* are still global — one shell usually slides at
# a time; independent multi-shell-vs-enemy collisions are a later refinement.)
SHELL_SPEED = 14.0

# Debris fragment (verbatim from W1-1 §16) — LOCAL_SYSTEM-only template; deterministic
# index-fanned X drift (no Scalar::Random). `%` casts to int in zForth.
mat_debris = smb_common.mat_debris()
DEBRIS_H = 0.18


# Score pop-up (verbatim from W1-1 §12b).

# ── Piranha Plant (Anchored, non-colliding Enemy; PER-ACTOR oscillation) ──────
# docs/plans/2026-05-27-smb-piranha-plant.md — W1-1 used GLOBAL phase state for a single
# plant; W1-2 needs 4, so this script uses PER-ACTOR local slots (2016/2017) seeded on the
# first tick from the plant's own ACTOR_INDEX (staggers the four plants out of phase). The
# plant slides its own Z_POS between a hidden Z (inside the opaque pipe) and an emerged Z
# (head above the pipe top) at RATE × DELTA_TIME, retracts while Mario stands on the pipe,
# hurts on overhead contact, and dies to a fresh fireball. No stomp (a Piranha always hurts).
PIRANHA_HIDDEN_Z  = GROUND_TOP_Z + 0.5*T   # inside the 2T pipe → occluded
PIRANHA_EMERGED_Z = GROUND_TOP_Z + 3.2*T   # head clears the 2T pipe top
PIRANHA_PIPE_TOP  = GROUND_TOP_Z + 2*T
PIRANHA_RATE      = 4.0
PIRANHA_DWELL     = 2.0

# ── Builder factories (verbatim from W1-1) ────────────────────────────────────
MUSH_X = T * 0.40
MUSH_Z = T * 0.40
MUSH_T = 0.25


def _build_koopa(name, x, red=False):
    """3 green + 1 red Koopa. Geometry is shared via smb_common.koopa_mesh (one
    datablock per colour — all greens share, the red shares), so the exporter writes
    just koopa_green.iff + koopa_red.iff (was 4 `.001` copies). Green walks off ledges;
    Red is the same model in a red shell (the 'turns at ledges' AI is not modelled)."""
    ko = smb_common.koopa_mesh(name, red=red)
    ko.location = (x, 0.0, MARIO_Z)
    attach_schema(ko, 'enemy')
    _apply_enemy_movement(ko)
    ko['wf_Script']           = KOOPA_SCRIPT
    ko['wf_Max Ground Speed'] = 16.0
    ko['wf_Number Of Local Mailboxes'] = 19   # per-actor shell state at SMB_KOOPA_STATE_L (2018)
    return ko


# Hard-block / pipe materials (verbatim from W1-1).
mat_hard = smb_common.mat_hard()
PIPE_GREEN = smb_common.mat_pipe()


def _build_piranha(name, col):
    """Anchored, non-colliding Enemy plant that oscillates out of a pipe at `col`.
    Geometry shared via smb_common.piranha_mesh (one piranha.iff for all plants, was 4
    `.001` copies). Per-actor local mailboxes (2016/2017) so the plants run independent clocks."""
    po = smb_common.piranha_mesh(name)
    po.location = (col*T, 0.0, PIRANHA_HIDDEN_Z)
    attach_schema(po, 'enemy')
    po['wf_Mobility']                  = 'Anchored'
    po['wf_Model Type']                = 'Mesh'
    po['wf_Visibility Mailbox']        = 1
    po['wf_Number Of Local Mailboxes'] = 18   # 2000..2017 covers the piranha slots
    po['wf_Script']                    = PIRANHA_SCRIPT
    return po


# ══ Templates (one per kind, parked off-screen) ══════════════════════════════
_make_coin_template()
_make_debris_template()
_make_popup_template()

mat_powerup = make_mat('powerup_red', (0.85, 0.16, 0.12))
_make_powerup_template('powerup_template', mat_powerup, POWERUP_SCRIPT, 0.0, -55.0)
mat_star  = make_mat('star_yellow', (0.98, 0.85, 0.10))
_make_powerup_template('star_template', mat_star, STAR_SCRIPT, 0.0, -59.0)
mat_oneup = make_mat('smb_oneup', (0.05, 0.75, 0.05))
_make_powerup_template('oneup_template', mat_oneup, ONEUP_SCRIPT, 0.0, -65.0)

# ══ SECTION 1 (cols 0-40): entry ════════════════════════════════════════════
# Row of 5 ?-blocks at row 8, cols 19-23: leftmost (19) = powerup, 20-23 = coin blocks.
_make_powerup_block('s1_powerup_block', 19*T, 'powerup_template', 0.0)   # mushroom/fire-flower
_add_qblock('s1_qcoin_0', 20*T)
_add_qblock('s1_qcoin_1', 21*T)
_add_qblock('s1_qcoin_2', 22*T)
_add_qblock('s1_qcoin_3', 23*T)
# Block tower (hard blocks) with 1 Goomba on it (Goomba @28 in GOOMBA_XS).
add_statplat('s1_tower_0', 27*T - BSIZE, -GROUND_Y, GROUND_TOP_Z,
             27*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + 1*T, mat_hard)
add_statplat('s1_tower_1', 28*T - BSIZE, -GROUND_Y, GROUND_TOP_Z,
             28*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + 2*T, mat_hard)
# Brick hiding a 10-coin block (a brick that dispenses coins over its 4 s window).
_s1_10coin = _add_textured_box('s1_brick_10coin',
                               34*T - BSIZE, -BSIZE, BLOCK_Z - BSIZE,
                               34*T + BSIZE,  BSIZE, BLOCK_Z + BSIZE, brick_tex)
attach_schema(_s1_10coin, 'generator')
_s1_10coin['wf_Mobility']           = 'Anchored'
_s1_10coin['wf_Model Type']         = 'Mesh'
_s1_10coin['wf_Visibility Mailbox'] = 1
_s1_10coin['wf_Number Of Local Mailboxes'] = 13
_s1_10coin['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
_s1_10coin['wf_Object To Throw']    = 'coin_template'
_s1_10coin['wf_Generation Rate']    = 10.0   # ~10 coins over the 4 s coin window
_s1_10coin['wf_Object X Velocity']  = 1.5
_s1_10coin['wf_Object Y Velocity']  = 0.0
_s1_10coin['wf_Object Z Velocity']  = 6.0
_s1_10coin['wf_Script']             = QBLOCK_SCRIPT   # multi-coin 4 s window = "10-coin block"

# ══ SECTION 2 (cols 40-120) ══════════════════════════════════════════════════
# Brick formations.
for _bi, _bc in enumerate(range(44, 49)):
    _add_brick(f's2_bricks_a_{_bi}', _bc * T)
# Brick hiding a Starman (reuses W1-1 star machinery: SMB_STAR_PICKUP).
_make_powerup_block('s2_star_brick', 50*T, 'star_template', 1.5)
# 2 Green Koopa Troopas.
_build_koopa('koopa_green_0', 55*T)
_build_koopa('koopa_green_1', 60*T)
# Cluster of 5 Goombas + 1 Koopa (the 5 Goombas come from GOOMBA_XS @71-83;
# the 3rd Green Koopa sits in the cluster).
_build_koopa('koopa_green_2', 68*T)
# Brick hiding a power-up.
_make_powerup_block('s2_powerup_brick', 90*T, 'powerup_template', 0.0)
# Brick with a 10-coin block.
_s2_10coin = _add_textured_box('s2_brick_10coin',
                               95*T - BSIZE, -BSIZE, BLOCK_Z - BSIZE,
                               95*T + BSIZE,  BSIZE, BLOCK_Z + BSIZE, brick_tex)
attach_schema(_s2_10coin, 'generator')
_s2_10coin['wf_Mobility']           = 'Anchored'
_s2_10coin['wf_Model Type']         = 'Mesh'
_s2_10coin['wf_Visibility Mailbox'] = 1
_s2_10coin['wf_Number Of Local Mailboxes'] = 13
_s2_10coin['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
_s2_10coin['wf_Object To Throw']    = 'coin_template'
_s2_10coin['wf_Generation Rate']    = 10.0
_s2_10coin['wf_Object X Velocity']  = 1.5
_s2_10coin['wf_Object Y Velocity']  = 0.0
_s2_10coin['wf_Object Z Velocity']  = 6.0
_s2_10coin['wf_Script']             = QBLOCK_SCRIPT
# Short gap: a non-bottomless step (raised platform after a brick row) + hidden 1-Up.
# (NOT in PITS — the doc's "short gap" is jumpable, not a death pit.) The platform with
# a hidden 1-Up: a brick at col 110 that dispenses the green 1-UP mushroom.
add_statplat('s2_platform', 104*T - BSIZE, -GROUND_Y, GROUND_TOP_Z,
             108*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + 1*T, mat_hard)
_s2_1up = _add_textured_box('s2_brick_1up',
                            110*T - BSIZE, -BSIZE, BLOCK_Z - BSIZE,
                            110*T + BSIZE,  BSIZE, BLOCK_Z + BSIZE, brick_tex)
attach_schema(_s2_1up, 'generator')
_s2_1up['wf_Mobility']           = 'Anchored'
_s2_1up['wf_Model Type']         = 'Mesh'
_s2_1up['wf_Visibility Mailbox'] = 1
_s2_1up['wf_Number Of Local Mailboxes'] = 13
_s2_1up['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
_s2_1up['wf_Object To Throw']    = 'oneup_template'
_s2_1up['wf_Generation Rate']    = 10.0
_s2_1up['wf_Object X Velocity']  = 1.5
_s2_1up['wf_Object Y Velocity']  = 0.0
_s2_1up['wf_Object Z Velocity']  = 6.0
_s2_1up['wf_Script']             = POWERUP_BLOCK_SCRIPT

# ══ SECTION 3 (cols 120-180): pipe corridor ══════════════════════════════════
# 2 Goombas come from GOOMBA_XS (@122, 126). 3 pipes with Piranha Plants (~cols 130/145/160).
# Pipe 1 (col 130 = ENTRY_PIPE_X) leads to the bonus coin room (entry sense + warp below).
_add_pipe('pipe_s3_1', 130, 2)   # = ENTRY_PIPE_X/T; warp pipe
_add_pipe('pipe_s3_2', 145, 2)
_add_pipe('pipe_s3_3', 160, 2)
_build_piranha('piranha_0', 130)
_build_piranha('piranha_1', 145)
_build_piranha('piranha_2', 160)

# ══ SECTION 4 (cols 180-230): gaps + half-pyramid + (deferred) lifts + red koopa ═
# The 2 gaps are in PITS (built above as real holes + pit-death sensors).
# Half-pyramid with 2 Goombas (Goombas @191, 194 in GOOMBA_XS).
_add_pyramid('s4_pyramid', base_col=189, steps=4)
# LIFTS DEFERRED → static jump-across platforms over the descending/ascending-lift bays
# (cols ~205-220) so the level stays traversable. Stone (hard-block) platforms at staggered
# heights the player hops between.
add_statplat('s4_lift_static_0', 205*T - BSIZE, -GROUND_Y, GROUND_TOP_Z + 1*T,
             206*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + 1*T + 0.5, mat_hard)
add_statplat('s4_lift_static_1', 211*T - BSIZE, -GROUND_Y, GROUND_TOP_Z + 2*T,
             212*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + 2*T + 0.5, mat_hard)
add_statplat('s4_lift_static_2', 217*T - BSIZE, -GROUND_Y, GROUND_TOP_Z + 1*T,
             218*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + 1*T + 0.5, mat_hard)
# Brick platform with 1 Red Koopa Troopa + bricks.
for _bi, _bc in enumerate(range(221, 225)):
    _add_brick(f's4_bricks_{_bi}', _bc * T, z=BLOCK_Z_6)
_build_koopa('koopa_red_0', 223*T, red=True)
# Final brick row with a hidden power-up.
for _bi, _bc in enumerate(range(227, 230)):
    _add_brick(f's4_final_bricks_{_bi}', _bc * T)
_make_powerup_block('s4_final_powerup', 228*T, 'powerup_template', 0.0, z=BLOCK_Z_6)

# ══ SECTION 5 (cols 230-256): surface/exit ═══════════════════════════════════
# Pipe with a Piranha Plant on the surface.
_add_pipe('pipe_s5', 235, 2)
_build_piranha('piranha_3', 235)
# Hard-block staircase up to the flagpole (col 248, already built). 8 ascending steps.
_add_staircase('s5_staircase', base_col=240, steps=8)

# ══ Goombas (14, from GOOMBA_XS) ═════════════════════════════════════════════
_goomba_body = _build_goomba()
_goomba_data = _goomba_body.data
bpy.data.objects.remove(_goomba_body, do_unlink=True)
for _gi, _gx in enumerate(GOOMBA_XS):
    _go = bpy.data.objects.new(f'goomba_{_gi:02d}', _goomba_data)
    scene.collection.objects.link(_go)
    _go.location = (_gx, 0.0, MARIO_Z)
    attach_schema(_go, 'enemy')
    _apply_enemy_movement(_go)

# ══ DECORATIVE WARP ZONE (~col 210, non-functional) ══════════════════════════
# Three pipes + a "WELCOME TO WARP ZONE" sign. NO warps wired (worlds 2-1/3-1/4-1 don't
# exist) — this is pure set-dressing behind the playfield so it reads as the famous secret.
# Placed slightly into +Y (Y=2.5) so it sits behind the player plane and the camera frames it.
for _wi, _wc in enumerate((208, 211, 214)):
    add_statplat(f'warp_pipe_{_wi}',
                 _wc*T - T, 1.5, GROUND_TOP_Z + 1*T,
                 _wc*T + T, 3.5, GROUND_TOP_Z + (2 + _wi)*T, PIPE_GREEN)
# Sign — a bright statplat slab above the warp pipes (textured colour stands in for text).
mat_warp_sign = make_mat('smb_warp_sign', (0.95, 0.92, 0.20))
add_statplat('warp_zone_sign',
             207*T, 2.0, GROUND_TOP_Z + 4*T,
             215*T, 2.2, GROUND_TOP_Z + 4*T + 0.8*T, mat_warp_sign)

# ══ BONUS COIN ROOM (pipe-warp target, copied from W1-1 §14) ═════════════════
CR_FLOOR_MAT = make_mat('smb_cr_floor', (0.45, 0.22, 0.05))

# Entry sense: a thin ActBox lid over the Section-3 pipe-1 mouth (col 130, 2T tall → top 3.0).
# Standing on top (origin Z≈4.5 once Mario is on the pipe? — the pipe is 2T = top 3.0, so a
# resting origin Z≈3.0+T=… ) ; band at the pipe TOP so a stand-on overlaps, a ground walk-past
# (origin Z≈1.5) does not. SMB_AT_PIPE + Down (player script) warps to CR_ENTRY_X/Z.
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(ENTRY_PIPE_X, 0.0, GROUND_TOP_Z + 2*T + 0.2))
es = bpy.context.object
es.name = 'pipe_entry_sense'; es.data.name = 'pipe_entry_sense'
es.scale = (T, GROUND_Y, 0.6)
bpy.ops.object.transform_apply(scale=True)
attach_schema(es, 'actbox')
es['wf_MailBox']                 = SMB_AT_PIPE
es['wf_MailBoxValue']            = 1
es['wf_ClearOnExit']             = 'True'
es['wf_Mailbox Exit Value']      = 0
es['wf_Activated By Actor']      = 'Player'
es['wf_Activated Actor Mailbox'] = 4005

# Coin-room floor + side walls (wide+thick to catch the warp-landing jitter).
add_statplat('cr_floor',  CR_X0 - 1, -5.0, CR_FLOOR_TOP - 4.0,
             CR_X1 + 1,    5.0, CR_FLOOR_TOP,        CR_FLOOR_MAT)
add_statplat('cr_wall_l', CR_X0 - 1, -GROUND_Y, CR_FLOOR_TOP,
             CR_X0,        GROUND_Y, CR_FLOOR_TOP + 10*T,  CR_FLOOR_MAT)
add_statplat('cr_wall_r', CR_X1,     -GROUND_Y, CR_FLOOR_TOP,
             CR_X1 + 1,    GROUND_Y, CR_FLOOR_TOP + 10*T,  CR_FLOOR_MAT)

# 19 collectible coin discs in 3 rows at the EXACT X/Z the player script checks
# (cols 4-10, rows 7/5/3). Anchored 'enemy' meshes so COIN_SCRIPT spins them without
# gold.cc's 5 s TTL despawning. Pickup is true-XZ contact in the player script.
_CR_LOW_Z  = CR_FLOOR_TOP + 4.5*T   # -41.25 — matches player-script Z check
_CR_MID_Z  = CR_FLOOR_TOP + 6.5*T   # -38.25
_CR_HIGH_Z = CR_FLOOR_TOP + 8.5*T   # -35.25
CR_COINS = [
    (4.5*T,  _CR_LOW_Z,  SMB_COIN_0),  (5.5*T,  _CR_LOW_Z,  SMB_COIN_1),
    (6.5*T,  _CR_LOW_Z,  SMB_COIN_2),  (7.5*T,  _CR_LOW_Z,  SMB_COIN_3),
    (8.5*T,  _CR_LOW_Z,  SMB_COIN_4),  (9.5*T,  _CR_LOW_Z,  SMB_COIN_5),
    (10.5*T, _CR_LOW_Z,  SMB_COIN_6),
    (4.5*T,  _CR_MID_Z,  SMB_COIN_7),  (5.5*T,  _CR_MID_Z,  SMB_COIN_8),
    (6.5*T,  _CR_MID_Z,  SMB_COIN_9),  (7.5*T,  _CR_MID_Z,  SMB_COIN_10),
    (8.5*T,  _CR_MID_Z,  SMB_COIN_11), (9.5*T,  _CR_MID_Z,  SMB_COIN_12),
    (10.5*T, _CR_MID_Z,  SMB_COIN_13),
    (5.5*T,  _CR_HIGH_Z, SMB_COIN_14), (6.5*T,  _CR_HIGH_Z, SMB_COIN_15),
    (7.5*T,  _CR_HIGH_Z, SMB_COIN_16), (8.5*T,  _CR_HIGH_Z, SMB_COIN_17),
    (9.5*T,  _CR_HIGH_Z, SMB_COIN_18),
]
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
    _coin['wf_Visibility Mailbox'] = _cmb
    _coin['wf_Mesh Name']          = f'cr_coin_{_ci}.iff'
    _coin['wf_Script']             = COIN_SCRIPT

# 10-coin block in the coin room (a brick that dispenses coins on bump-from-below).
_cr_10coin = _add_textured_box('cr_brick_10coin',
                               CR_MID - BSIZE, -BSIZE, _CR_LOW_Z - 2*T - BSIZE,
                               CR_MID + BSIZE,  BSIZE, _CR_LOW_Z - 2*T + BSIZE, brick_tex)
attach_schema(_cr_10coin, 'generator')
_cr_10coin['wf_Mobility']           = 'Anchored'
_cr_10coin['wf_Model Type']         = 'Mesh'
_cr_10coin['wf_Visibility Mailbox'] = 1
_cr_10coin['wf_Number Of Local Mailboxes'] = 13
_cr_10coin['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
_cr_10coin['wf_Object To Throw']    = 'coin_template'
_cr_10coin['wf_Generation Rate']    = 10.0
_cr_10coin['wf_Object X Velocity']  = 1.5
_cr_10coin['wf_Object Y Velocity']  = 0.0
_cr_10coin['wf_Object Z Velocity']  = 6.0
_cr_10coin['wf_Script']             = QBLOCK_SCRIPT


_make_target('Target_cr_entry',  (CR_ENTRY_X, 0.0, CR_ENTRY_Z))
_make_target('Target_cr_lookat', (CR_MID, 0.0, CR_FLOOR_TOP + T))

# cs_coin: static shot framing the coin room (no scroll script → unlike cs_side).
cs_coin = bpy.data.objects.new('cs_coin', None)
scene.collection.objects.link(cs_coin)
attach_schema(cs_coin, 'camshot')
cs_coin.location = (CR_MID, -35.0, CR_FLOOR_TOP + 4.5)
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

# abor_coin: ActBoxOR over the coin-room play space; while Mario is inside it writes
# cs_coin's index to INDEXOF_CAMSHOT (1921) each frame so the camera tracks underground.
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(CR_MID, 0.0, CR_FLOOR_TOP + 4.5))
ab = bpy.context.object
ab.name = 'abor_coin'; ab.data.name = 'abor_coin'
ab.scale = ((CR_X1 - CR_X0)/2 + 1.0, GROUND_Y + 2.0, 6.0)
bpy.ops.object.transform_apply(scale=True)
attach_schema(ab, 'actboxor')
ab['wf_MailBox']            = 1921
ab['wf_Object']             = 'cs_coin'
ab['wf_Activated By Actor'] = 'Player'
ab['wf_Model Type']         = 'None'

# Coin-room light (the surface light unloads on the room switch).
if light:
    coin_light = light.copy()
    scene.collection.objects.link(coin_light)
    coin_light.name = 'Light_coin'
    coin_light.location = (CR_MID, -22.0, CR_FLOOR_TOP + 6.0)
    coin_light.rotation_euler = (math.pi / 3, 0, 0)

# Exit pipe + walk-into warp back to the surface (Mario collects coins L→R then exits).
EXIT_PIPE_X0, EXIT_PIPE_X1 = 13*T, 15*T
add_statplat('exit_pipe', EXIT_PIPE_X0, -GROUND_Y, CR_FLOOR_TOP,
             EXIT_PIPE_X1,  GROUND_Y, CR_FLOOR_TOP + 2*T, PIPE_GREEN)
# Surface return: just RIGHT of the Section-3 entry pipe so no instant re-trigger.
_make_target('Target_surface_return', (ENTRY_PIPE_X + 3*T, 0.0, MARIO_SPAWN_Z))
_warp_cx = EXIT_PIPE_X0 - 1.5*T
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(_warp_cx, 0.0, CR_FLOOR_TOP + 1.0))
wp = bpy.context.object
wp.name = 'pipe_exit_warp'; wp.data.name = 'pipe_exit_warp'
wp.scale = (1.5, GROUND_Y, 1.0)
bpy.ops.object.transform_apply(scale=True)
attach_schema(wp, 'warp')
wp['wf_Target']             = 'Target_surface_return'
wp['wf_Activated By Actor'] = 'Player'
wp['wf_Model Type']         = 'None'
wp['wf_Visibility Mailbox'] = 0

# ── 13. Export ────────────────────────────────────────────────────────────────
print(f"[smb_w1_2] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print("[smb] Objects in scene:", [o.name for o in bpy.data.objects])
print(f"[smb] Done — {OUT_LEV}")

