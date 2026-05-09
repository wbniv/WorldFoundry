"""
blender_create_qbert.py — drive Blender to produce qbert_practice.lev.

Run headlessly:
  blender --background --python blender_create_qbert.py

Strategy: import snowgoons-blender.lev (gets all infrastructure objects with
correct OAD schemas attached), strip everything except the reusable
infrastructure, reposition objects for the Q*bert pyramid layout, then
generate 28 cube actors × 3 colour variants = 84 statplat instances at
axial-coordinate positions, plus the player at the apex, plus a second
camshot (cs_death) for the fall cutscene. Export to qbert_practice.lev.

MVP scope (per docs/plans/2026-05-03-qbert-mvp.md):
  - 28-cube pyramid in a 7-row triangular layout.
  - Per-cube colour state via 4*3=12 child mesh variants; director drives
    visibility mailboxes 440..775 (round*84 + cube*3 + state).
  - Player as an Anchored actor with the hop state machine in its Script.
  - Director script for cube-state advance and win check (colour rule 0).
  - Two CamShots (cs_pyramid and cs_death) wired through INDEXOF_CAMSHOT.
  - No enemies, no discs, no HUD, no audio.
"""

import bpy
import os
import sys
import math

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OUT_LEV = os.path.join(SCRIPT_DIR, 'qbert_practice.lev')
OAD_DIR = os.path.join(REPO, 'wfsource', 'source', 'oas')
STATPLAT_OAD = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures', 'statplat.oad')

# ── Pyramid geometry ──────────────────────────────────────────────────────────
NUM_ROWS = 7  # rows 0 (apex) through 6 (bottom)
TOTAL_CUBES = NUM_ROWS * (NUM_ROWS + 1) // 2  # 28
CUBE_SIZE = 2.0  # matches gen_cube.py — 2×2×2 cube
CUBE_BASE_Z = 1.0  # bottom row centre Z (cubes extend ±1 around their centre)
# Cubes are rotated 45° about Z (diamond presentation); their footprint
# extends √2 along the new X/Y axes. Multiply XY centre offsets by √2 so
# adjacent diamonds touch corner-to-corner with no overlap.
SQRT2 = math.sqrt(2.0)

# Mailbox layout — engine cap was bumped to GLOBAL_USER_MAX=999 on 2026-05-03,
# so the original spacious plan from docs/plans/2026-05-03-qbert-mvp.md applies:
#   2          END_TIME (engine sentinel — mm convention)
#   13         DEATH (engine signal — mm convention)
#   70..72     HUD score/timer/lives (mm convention; mb 72 LIVES rendered by DrawHud)
#   100..101   camshot zone signals from ActBoxOR (mm convention)
#   200..227   CUBE_STATE_BASE (28 slots, cube N at 200+N)
#   440..775   VIS_BASE (336 slots, round R cube N state S at 440+R*84+N*3+S)
#   400        QBERT_ROW
#   401        QBERT_COL
#   402        HOP_COOLDOWN
#   411        QBERT_LANDED (player→director one-shot)
#   412        CUBES_TO_TARGET (director→HUD count)
#   413        ROUND_CLEAR (director→engine win flag)
#   414        FALL_DEATH (player→director one-shot at end of fall animation)
#   415        cs_death countdown (frames remaining holding cs_death)
#   416        INTRO_PHASE (0..5 active sweep, 6 done)
#   417        INTRO_TIMER (frames into current intro leg)
#   418        INTRO_DONE (1 latch when intro complete; gates joystick + camshot routing)
#   419        FALL_PHASE (0=not falling, 1..30=ramping Z down each tick)
#   420        GAME_OVER (1 latch when lives→0; cleared on player restart)
#   421        LEVEL_INITIALIZED (director one-shot init flag — sets lives=3 once)
#   422        LAST_STICK (player edge-detect snapshot for restart-button trigger)
#   424        ROUND_CLEAR_TIMER (director internal — counts down 90→0 on win, then resets)
#   425        ROUND_NUMBER (0-based; increments on each clear)
#   430        AUTOPILOT_ON (0=joystick mode, 1=autopilot demo mode)
#   431        AUTOPILOT_STEP (current step index 0..31; reset on respawn/restart)
INDEXOF_CUBE_STATE_BASE = 200
INDEXOF_VIS_BASE = 440   # 440 + r*84 + i*3 + s; max = 440+3*84+27*3+2 = 775
NUM_ROUNDS = 4           # palette cycles; matches gen_cube.py ROUND_COLORS

NUM_MAILBOXES = 800  # >= 775 (highest vis slot)


def cube_index(row, col):
    """Triangular packing index — matches the GDD's INDEXOF_CUBE_STATE_BASE + row*(row+1)/2 + col."""
    return row * (row + 1) // 2 + col


def cube_world_position(row, col):
    """Centre of cube (row, col) in world coords. Z-up.

    Iconic Q*bert pyramid stacking: each row sits on the back half of the
    row below, so successive rows offset by (CUBE_SIZE/2) in +Y and
    CUBE_SIZE in +Z. This gives the staircase look where the cube tops
    are all visible from a 3/4 camera angle.
    """
    world_x = SQRT2 * (col - row / 2.0) * CUBE_SIZE
    # Apex row (r=0) is furthest back in +Y; bottom row (r=NUM_ROWS-1) is at Y=0.
    world_y = SQRT2 * (NUM_ROWS - 1 - row) * (CUBE_SIZE / 2.0)
    # Apex highest Z; bottom row at CUBE_BASE_Z.
    world_z = CUBE_BASE_Z + (NUM_ROWS - 1 - row) * CUBE_SIZE
    return (world_x, world_y, world_z)


# ── Player + camera positions ─────────────────────────────────────────────────
# Apex cube is at world (0, 6, 13). Player sits on top of it.
APEX_X, APEX_Y, APEX_Z = 0.0, SQRT2 * (NUM_ROWS - 1) * (CUBE_SIZE / 2.0), CUBE_BASE_Z + (NUM_ROWS - 1) * CUBE_SIZE
PLAYER_SPAWN_XYZ = (APEX_X, APEX_Y, APEX_Z + 1.5)
# Arcade-Q*bert framing: symmetric in X (x=0), 30° iso down-tilt. Look-at is
# the pyramid centroid; camera is south (-Y) and elevated (+Z) so the down-
# vector from camera to look-at is ~30° below horizontal. Matches the
# Gottlieb cabinet's 30° dimetric iso projection — cube tops are clearly
# visible (the diamond-on-top view), front faces show as parallelograms.
# (Earlier (12, -15, 14) was 3-quarters offset + only 17° down — too
# horizontal; pyramid rendered as a thin triangle.)
CAMSHOT_POS = (0.0, -15.0, 19.0)   # ~21 units from look-at; pyramid fills ~70% of frame
CAMSHOT_LOOKAT = (0.0, 3.0, 8.5)   # apex+player in frame; offset above pyramid centre
# Iso-angle check: down-angle = atan((19-8.5)/(3-(-15))) = atan(10.5/18) = 30.3°.

# Room bbox is **relative to the room's position** in the exported BOX3.
# Must strictly enclose every actor (no equality on edges, or levcomp drops
# the actor into PERM — see level-design-troubleshooting.md).
#
# Actor extremes that drive the bbox:
#   Pyramid cubes:   X=[-6..+6], Y=[0..6], Z=[0..14]
#   Player at apex:  (0, 6, 14.5)
#   cs_pyramid:      (12, -15, 14)   ← gameplay camera
#   cs_death:        (12, -15, 14)
#   cs_intro_0:      (48, -90, 41)   ← far-back intro start (drives X+/Y-/Z+ extremes)
#   cs_intro_1..4:   between cs_intro_0 and cs_pyramid
#   light:           (0, -5, 16)
#   director/levelobj: (0, -10, 7)
#   matte:           (0, 0, 6)
ROOM_CENTRE = (0.0, 0.0, 7.0)
ROOM_BBOX_REL = (-15.0, -100.0, -45.0, 75.0, 15.0, 45.0)
# Resulting absolute bbox: (-15, -100, -38) to (75, 15, 52).
# Z floor extended to -38 so the 30-tick fall animation completes before the
# actor exits the room. Worst-case fall starts at z=3 (bottom-row cube top)
# and reaches z=-27 at tick 30; floor at -38 gives 11 units of margin.
# Asymmetric in Y because the intro sweep starts deep in -Y; centre stays
# at world origin for editor sanity.

# ── 1. Start with a clean scene ─────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# ── 2. Import the snowgoons reference level ─────────────────────────────────────
print(f"[qbert] Importing {SNOWGOONS_LEV}")
bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)

# ── 3. Identify what to keep vs delete ─────────────────────────────────────────
KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light',
                'room', 'camshot', 'target', 'actboxor', 'player'}
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile',
                  'tool', 'tool01', 'ground01', 'hp'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    if schema:
        return os.path.splitext(os.path.basename(schema))[0]
    return ''


# Delete gameplay objects from snowgoons
for obj in list(bpy.data.objects):
    if get_class(obj) in DELETE_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)

# Drop duplicates: keep only the first of each infrastructure class
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in KEEP_CLASSES:
        if cn in seen:
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            seen.add(cn)

print("[qbert] Classes after strip:", sorted({get_class(o) for o in bpy.data.objects}))


def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None


# ── 4. Reposition infrastructure ───────────────────────────────────────────────
# Director, levelobj, matte, light: doesn't matter much (no rendered geometry,
# but matte renders the background). Place them around the camera.
director = find_by_class('director')
if director:
    director.location = (0, -10, 7)

levelobj = find_by_class('levelobj')
if levelobj:
    levelobj.location = (0, -10, 7)
    levelobj['wf_Number Of Mailboxes'] = NUM_MAILBOXES
    levelobj['wf_Model Type'] = 'None'  # suppress debug-box render

matte = find_by_class('matte')
if matte:
    matte.location = (0, 0, 6)
    matte['wf_Matte Type'] = 'Color'
    matte['wf_Background Color'] = 0x000020  # very dark blue
    matte['wf_Visibility Mailbox'] = 1  # always visible
    # The matte renders the background via its own backdrop logic. Without this
    # override, Model Type defaults to "Box" and RenderActor3DBox draws the
    # matte as a small random-coloured cube *in front of* the pyramid (the
    # pyramid's apex was getting masked by a pink hex).
    matte['wf_Model Type'] = 'None'

camera = find_by_class('camera')
if camera:
    camera.location = CAMSHOT_POS
    # Fog defaults from the snowgoons template (start=20, end=30, color=0x888888)
    # would fully fog out anything past 30 units. Camera at (20,-25,22) puts the
    # pyramid at distance ~35 → fully replaced by fog colour (gray) and the
    # cubes lose their material colour entirely. Push fog back so the pyramid
    # fits inside the unfogged near range, and dial the colour to the matte
    # background so the transition (if reached) is invisible.
    camera['wf_FoggingStartDistance'] = 100.0
    camera['wf_FoggingCompleteDistance'] = 200.0
    camera['wf_FoggingColor'] = 0x000020  # match matte background
    camera['wf_Model Type'] = 'None'  # suppress debug-box render

light = find_by_class('light')
if light:
    light.location = (0, -5, 16)
    light.rotation_euler = (math.pi / 2, 0, 0)  # required for surfaces to be lit

# Player — Anchored, Q*bert hop state machine in Script
player = find_by_class('player')
if player:
    player.location = PLAYER_SPAWN_XYZ
    player['wf_Mobility'] = 'Anchored'
    player['wf_Mass'] = 0.0
    player['wf_Mesh Name'] = 'qbert_player.iff'
    player['wf_Model Type'] = 'Mesh'
    player['wf_Visibility Mailbox'] = 1  # always visible
    # MVP hop state machine: one-tick teleport per stick edge, with cooldown
    # to prevent rapid-fire hops. Mailbox slots (per the original plan):
    #   400 ROW, 401 COL, 402 COOLDOWN, 411 LANDED, 414 FALL_DEATH
    # Cube positions are computed inline from (row, col):
    #   X = 2*col - row,  Y = 6 - row,  Z = 1 + (6-row)*2 + 2 (player offset)
    # Cardinal joystick → diagonal hop mapping (cabinet was rotated 45°):
    #   UP    (0x0800) → up-right  (dr=-1, dc= 0)
    #   RIGHT (0x2000) → down-right (dr= 1, dc= 1)
    #   DOWN  (0x1000) → down-left  (dr= 1, dc= 0)
    #   LEFT  (0x4000) → up-left    (dr=-1, dc=-1)
    # See DIRECTOR_SCRIPT below for the Forth gotchas (real \n only, no \
    # comments after the first sigil line, ASCII-only inside script body).
    # Per-tick body order (top→bottom) — each layer EXITs to gate the rest:
    #   1. game-over restart trigger (mb 420 == 1): edge-detect joystick press
    #      against last-tick snapshot in mb 422; on transition reset all level
    #      state and re-arm the intro state machine. Always EXIT — no other
    #      input is processed during game-over.
    #   2. fall-animation state machine (mb 419 > 0): ramps INDEXOF_Z_POS
    #      down 1 unit per tick for 30 ticks, then snaps player back to apex
    #      and latches mb 414 (FALL_DEATH) for the director to pick up.
    #      EXIT during fall so joystick is frozen.
    #   3. cooldown + INTRO_DONE-gated joystick processing (cardinal → diagonal
    #      hop mapping per cabinet 45° rotation):
    #        UP    (0x0800) → up-right  (dr=-1, dc= 0)
    #        RIGHT (0x2000) → down-right (dr= 1, dc= 1)
    #        DOWN  (0x1000) → down-left  (dr= 1, dc= 0)
    #        LEFT  (0x4000) → up-left    (dr=-1, dc=-1)
    #   4. cooldown decrement (always).
    #   5. Z<-2 safety net (gated on FALL_PHASE==0 so it doesn't fire mid-fall).
    #
    # do-hop: replaces the original "set Z=-10 on off-edge" instant-teleport
    # with a predictive fall trigger — when the destination is off-pyramid,
    # clamp the row used for the X/Y/Z computation to [0..6] (so Q*bert appears
    # at a sensible Z, the level of the cube he hopped from), then set
    # FALL_PHASE=1 to let the per-tick state machine ramp Z down each tick.
    #
    # See feedback_zforth_script_gotchas.md: real \n only, no `\` comments
    # after sigil line, ASCII-only, `( ... )` for inline comments.
    player['wf_Script'] = (
        "\\ wf qbert player\n"
        ": stick INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox ;\n"
        ": cd 402 read-mailbox ;\n"
        ": tick-cd cd dup 0 > if 1 - 402 write-mailbox else drop then ;\n"
        ": step-move "
        "dup  0 = if drop  1  0 exit then "
        "dup  1 = if drop -1  0 exit then "
        "dup  2 = if drop  1  1 exit then "
        "dup  3 = if drop  1  0 exit then "
        "dup  4 = if drop -1 -1 exit then "
        "dup  5 = if drop  1  0 exit then "
        "dup  6 = if drop  1  0 exit then "
        "dup  7 = if drop  1  0 exit then "
        "dup  8 = if drop -1  0 exit then "
        "dup  9 = if drop  1  1 exit then "
        "dup 10 = if drop -1  0 exit then "
        "dup 11 = if drop  1  1 exit then "
        "dup 12 = if drop -1  0 exit then "
        "dup 13 = if drop -1  0 exit then "
        "dup 14 = if drop  1  1 exit then "
        "dup 15 = if drop  1  0 exit then "
        "dup 16 = if drop  1  1 exit then "
        "dup 17 = if drop -1  0 exit then "
        "dup 18 = if drop  1  1 exit then "
        "dup 19 = if drop  1  1 exit then "
        "dup 20 = if drop -1 -1 exit then "
        "dup 21 = if drop  1  0 exit then "
        "dup 22 = if drop -1 -1 exit then "
        "dup 23 = if drop  1  0 exit then "
        "dup 24 = if drop -1 -1 exit then "
        "dup 25 = if drop  1  0 exit then "
        "dup 26 = if drop -1 -1 exit then "
        "dup 27 = if drop  1  0 exit then "
        "dup 28 = if drop -1 -1 exit then "
        "dup 29 = if drop  1  0 exit then "
        "dup 30 = if drop -1 -1 exit then "
        "drop  1  0 ;\n"
        ": do-hop 401 read-mailbox + swap 400 read-mailbox + "
        "dup 400 write-mailbox over 401 write-mailbox "
        "over over swap 2 * swap - 1.4142136 * INDEXOF_X_POS write-mailbox "  # 2dup not in bootstrap; over over does the same; * sqrt(2) for diamond layout
        "6 over - 1.4142136 * INDEXOF_Y_POS write-mailbox "
        "6 swap - 2 * 1 + 2 + INDEXOF_Z_POS write-mailbox "
        "drop 1 411 write-mailbox 12 402 write-mailbox "
        "400 read-mailbox dup 0 < swap 6 > | "
        "401 read-mailbox 0 < | "
        "401 read-mailbox 400 read-mailbox > | "
        "if "
        # Off-edge: re-clamp row for safe-Z computation, then trigger fall.
        "400 read-mailbox dup 0 < if drop 0 then dup 6 > if drop 6 then "
        "6 swap - 2 * 1 + 2 + INDEXOF_Z_POS write-mailbox "
        "1 419 write-mailbox "
        "then ;\n"
        # 1. Game-over restart trigger. Snapshot prev-stick before updating
        # mb 422 so edge-detect can compare; then update mb 422 = current.
        "422 read-mailbox stick 422 write-mailbox\n"
        "420 read-mailbox 1 = if "
        "0 = if "  # consumes prev_stick: prev was zero?
        "stick 0 <> if "
        # Restart: reset every per-game mailbox + snap player to apex.
        "3 72 write-mailbox "
        "0 411 write-mailbox 0 412 write-mailbox 0 413 write-mailbox "
        "0 414 write-mailbox 0 415 write-mailbox "
        "0 416 write-mailbox 0 417 write-mailbox 0 418 write-mailbox "
        "0 419 write-mailbox 0 420 write-mailbox "
        "0 400 write-mailbox 0 401 write-mailbox 0 402 write-mailbox "
        "0 431 write-mailbox "
        "28 0 do 0 200 i + write-mailbox loop "
        "0 INDEXOF_X_POS write-mailbox "
        "6 1.4142136 * INDEXOF_Y_POS write-mailbox "
        "15 INDEXOF_Z_POS write-mailbox "
        "then "
        "then "
        "exit "
        "else drop "
        "then\n"
        # 1.5. Round-clear apex respawn. Director sets mb[426]=1 when round
        # timer expires; we handle it here (player context) so INDEXOF_X/Y/Z
        # writes go to the player actor's position, not the director's.
        # exit prevents joystick processing on the same tick as the teleport.
        "426 read-mailbox 1 = if "
        "0 INDEXOF_X_POS write-mailbox 6 1.4142136 * INDEXOF_Y_POS write-mailbox 15 INDEXOF_Z_POS write-mailbox "
        "0 431 write-mailbox 0 426 write-mailbox exit "
        "then\n"
        # 2. Fall-animation state machine. While mb 419 > 0:
        #    1..29 → ramp Z down 1 per tick, increment FALL_PHASE.
        #    >=30  → snap player to apex, latch FALL_DEATH=1, reset FALL_PHASE.
        "419 read-mailbox dup 0 > if "
        "dup 30 < if "
        "INDEXOF_Z_POS read-mailbox 1 - INDEXOF_Z_POS write-mailbox "
        "1 + 419 write-mailbox "
        "else "
        "drop "
        "0 419 write-mailbox 1 414 write-mailbox "
        "0 INDEXOF_X_POS write-mailbox "
        "6 1.4142136 * INDEXOF_Y_POS write-mailbox "
        "15 INDEXOF_Z_POS write-mailbox "
        "0 400 write-mailbox 0 401 write-mailbox "
        "then "
        "exit "
        "else drop "
        "then\n"
        # 3. Autopilot or joystick — gated on cooldown and INTRO_DONE.
        # When AUTOPILOT_ON (mb 430) != 0, execute the next step of the 32-hop
        # coverage sequence (step-move) instead of reading the joystick.
        # Both paths share do-hop and the 12-tick cooldown.
        "cd 0 = if "
        "418 read-mailbox 1 = if "
        "430 read-mailbox 0 <> if "
        "431 read-mailbox dup 32 < if "
        "step-move do-hop "
        "431 read-mailbox 1 + 431 write-mailbox "
        "else drop then "
        "exit "
        "then "
        "stick 0x0800 & if -1 0 do-hop exit then "
        "stick 0x2000 & if 1 1 do-hop exit then "
        "stick 0x1000 & if 1 0 do-hop exit then "
        "stick 0x4000 & if -1 -1 do-hop exit then "
        "then "
        "then\n"
        # 4. Cooldown decrement.
        "tick-cd\n"
        # 5. Safety-net Z<-2 — gated on FALL_PHASE==0 so the fall state
        # machine isn't pre-empted while ramping Z down past -2.
        "INDEXOF_Z_POS read-mailbox -2 < if "
        "419 read-mailbox 0 = if "
        "0 INDEXOF_X_POS write-mailbox 6 1.4142136 * INDEXOF_Y_POS write-mailbox "
        "15 INDEXOF_Z_POS write-mailbox "
        "0 400 write-mailbox 0 401 write-mailbox 1 414 write-mailbox "
        "then "
        "then\n"
    )

# Room — bbox is stored relative to the room's position (verified against
# mm_practice_blender.lev: wf_original_bbox value is exported to BOX3 as-is).
room = find_by_class('room')
if room:
    room.location = ROOM_CENTRE
    bx0, by0, bz0, bx1, by1, bz1 = ROOM_BBOX_REL
    # Visualisation mesh — position-relative since Blender meshes are local-space.
    box_verts = [
        (bx0, by0, bz0), (bx1, by0, bz0), (bx1, by1, bz0), (bx0, by1, bz0),
        (bx0, by0, bz1), (bx1, by0, bz1), (bx1, by1, bz1), (bx0, by1, bz1),
    ]
    box_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    room['wf_original_bbox'] = ROOM_BBOX_REL
    new_mesh = bpy.data.meshes.new("RoomBounds")
    new_mesh.from_pydata(box_verts, [], box_faces)
    new_mesh.update()
    old_mesh = room.data
    room.data = new_mesh
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

# Actboxor — covers the playable volume and writes cs_pyramid index to mailbox 100
actboxor = find_by_class('actboxor')
if actboxor:
    actboxor.location = ROOM_CENTRE
    # The snowgoons template's actboxor.Object referenced "CamShot01" by name.
    # We renamed CamShot01 → cs_pyramid above, so update the reference too.
    actboxor['wf_Object'] = 'cs_pyramid'

# CamShot 1 — cs_pyramid, the gameplay shot, all axes Absolute
camshot = find_by_class('camshot')
if camshot:
    camshot.location = CAMSHOT_POS
    camshot.name = 'cs_pyramid'
    # All three axes Absolute, rotation Fixed (look-at via Target)
    camshot['wf_Position X'] = 'Absolute'
    camshot['wf_Position Y'] = 'Absolute'
    camshot['wf_Position Z'] = 'Absolute'
    camshot['wf_Rotation'] = 'Fixed'
    camshot['wf_FOV'] = 60.0
    # Pan time = 1.2 s so the FINAL leg of the intro sweep (cs_intro_4 → cs_pyramid)
    # decelerates smoothly into the gameplay shot. Also affects the post-cs_death
    # return — death cycle now ends with a 1.2 s pan back to gameplay (was instant).
    camshot['wf_Pan Time In Seconds'] = 1.2
    camshot['wf_Model Type'] = 'None'  # suppress debug-box render
    # BungeeCam folds TrackObject's world position into the look-at vector.
    # The snowgoons template ships with Track Object='Player', which makes the
    # camera follow the player around — undesired for Q*bert's fixed pyramid
    # framing. Point Track Object at Target02 (pyramid centre) so the look-at
    # stays on the pyramid regardless of where the player has hopped.
    camshot['wf_Track Object'] = 'Target02'
    camshot['wf_Follow'] = 'Target02'  # equal Follow → Position math degenerates
                                        # to absolute camshot position

# Targets — use existing Target01/02 from snowgoons
# Target01 = world-origin anchor for the BungeeCam Follow vector.
# Target02 = look-at point for the CamShot's Target field. Place it at
# the pyramid centre so the camera frames the whole pyramid, not above it.
# Also force Model Type = None so the targets don't render as random-coloured
# debug boxes (RenderActor3DBox uses MakeRandMaterialList).
targets = [o for o in bpy.data.objects if get_class(o) == 'target']
if len(targets) >= 1:
    targets[0].location = (0.0, 0.0, 0.0)
    targets[0].name = 'Target01'
    targets[0]['wf_Model Type'] = 'None'
if len(targets) == 1:
    t1 = targets[0]
    t2 = t1.copy()
    t2.data = t1.data.copy() if t1.data else None
    scene.collection.objects.link(t2)
    targets.append(t2)
if len(targets) >= 2:
    targets[1].location = CAMSHOT_LOOKAT
    targets[1].name = 'Target02'
    targets[1]['wf_Model Type'] = 'None'

# ── 5. Add a second CamShot (cs_death) — follows player on fall ───────────────
# Duplicate cs_pyramid and reconfigure
if camshot:
    cs_death = camshot.copy()
    cs_death.data = camshot.data.copy() if camshot.data else None
    scene.collection.objects.link(cs_death)
    cs_death.name = 'cs_death'
    cs_death.location = CAMSHOT_POS  # same world position
    cs_death['wf_FOV'] = 22.0  # tighter framing
    cs_death['wf_Pan Time In Seconds'] = 0.2  # smooth pan when switching to it
    # Track the player so the death cutscene follows the falling body.
    # Equal Track Object and Follow keeps Position math degenerate (camera
    # stays at CAMSHOT_POS); only the look-at vector swings to follow the
    # player. With the fall state machine landing FALL_DEATH=1 AT END of the
    # 30-frame fall, the player is back at apex by the time cs_death takes
    # over — so this configuration also frames the apex post-fall, but is
    # forward-compatible with future flows that want cs_death active during
    # the fall (just trigger FALL_DEATH=1 in do-hop instead of at end).
    cs_death['wf_Track Object'] = 'Player'
    cs_death['wf_Follow'] = 'Player'

# ── 5b. Intro cinematic CamShots — chained sweep-in to cs_pyramid ─────────────
# Five CamShots placed along an arc from "very far back" to the existing
# cs_pyramid view. The director's Forth state machine writes their indices
# to INDEXOF_CAMSHOT in sequence; each pan is linear (PanCameraHandler) but
# the chain approximates a curve and the per-leg Pan times shape an ease-
# in-out speed profile (slow → fast → slow). Total intro length ~3.7 s.
#
# Engine fact (docs/investigations/2026-04-29-camera-system.md): the
# PanCameraHandler does linear lerp between source and dest CamShot
# positions over destShot.PanTimeInSeconds. There is no built-in spline or
# ease curve. See docs/investigations/2026-05-04-camera-path-support-revival.md
# for what would be needed to drive the camera from a Blender curve directly.
INTRO_CAMSHOTS = [
    # (name, world position, Pan time on transition INTO this shot)
    # Positions chosen so the sweep curves toward the new (0, -15, 19) gameplay
    # cam at a 30° iso angle; first leg is "5x distance, more elevated"; final
    # leg lands face-on (centred in X) to match arcade Q*bert framing.
    ('cs_intro_0', (48.0, -90.0, 41.0), 0.0),  # initial cut — far back + high
    ('cs_intro_1', (34.0, -68.0, 35.0), 1.2),  # ease-in: slow start
    ('cs_intro_2', (20.0, -47.0, 29.0), 0.5),  # accelerating
    ('cs_intro_3', (10.0, -32.0, 24.0), 0.3),  # fastest leg
    ('cs_intro_4', ( 3.0, -22.0, 21.0), 0.5),  # decelerating into cs_pyramid
]
intro_camshot_objs = []
if camshot:
    for name, pos, pan_time in INTRO_CAMSHOTS:
        cs_intro = camshot.copy()
        cs_intro.data = camshot.data.copy() if camshot.data else None
        scene.collection.objects.link(cs_intro)
        cs_intro.name = name
        cs_intro.location = pos
        cs_intro['wf_FOV'] = 60.0
        cs_intro['wf_Pan Time In Seconds'] = pan_time
        intro_camshot_objs.append(cs_intro)

# ── 6. Director — wire its Script for the game loop ───────────────────────────
# MVP director: cube-state advance, visibility fan-out, win check, camera
# fan-out, HUD plumbing. Per actor.cc:665 statplats forbid scripts, so the
# 84 cube children are script-free; the director drives their visibility
# mailboxes every tick from the per-cube state mailboxes.
#
# Forth must be single-line in the .lev STR field, with \n escapes.
# Important Forth gotchas (learned the hard way):
#  - zForth has NO `\` line-comment word. The script handler in
#    engine/stubs/scripting_zforth.cc skips only the FIRST line as the
#    `\ wf` sigil; all subsequent `\` lines get parsed as the unknown
#    word `\` and abort with NOT_A_WORD.
#  - Use real "\n" newline chars in Python strings; the wf_blender
#    exporter converts them to the .lev `\n` escape, which iffcomp
#    decodes back to a runtime newline. Writing literal "\\n" in Python
#    causes the exporter to double-escape, producing a runtime "\n"
#    (backslash + n) that confuses the tokenizer.
#  - Stay within ASCII in the script body — non-ASCII bytes break
#    parsing.
# Camshot actor indices (assigned by .lev OBJ load order — verified via debug
# bridge: `wf_game --debug-port 7777` then watch INDEXOF_CAMSHOT=1021 at idle).
# These shift if you add/remove actors above them in blender_create_qbert.py.
# If the order changes, re-run the engine with --debug-port and re-check.
CS_PYRAMID_IDX = 8
CS_DEATH_IDX = 12
# cs_intro_0..cs_intro_4 are added immediately after cs_death in the actor
# list (see "Intro cinematic CamShots" block above), so they take indices
# 13..17 in OBJ load order. The director script references them as
# (intro phase + CS_INTRO_BASE_IDX). Cubes shift to idx 18+; cube indices
# don't matter (cubes are referenced by mailbox slot, not actor idx).
CS_INTRO_BASE_IDX = 13  # cs_intro_0 = 13, ..., cs_intro_4 = 17

# Death cutscene duration in ticks (~60 = 1s at 60 Hz).
CS_DEATH_HOLD_FRAMES = 60

# Intro state machine — leg durations in frames at 60 Hz (must match each
# destination CamShot's Pan Time in INTRO_CAMSHOTS / cs_pyramid Pan Time).
# Phase N: write shot[N] on first tick (timer==0), then wait
# INTRO_LEG_FRAMES[N] frames for the pan to complete before advancing.
#   phase 0 → cs_intro_0  (instant cut, 1 frame, before phase 1's pan starts)
#   phase 1 → cs_intro_1  (1.2 s pan from cs_intro_0)
#   phase 2 → cs_intro_2  (0.5 s pan)
#   phase 3 → cs_intro_3  (0.3 s pan)
#   phase 4 → cs_intro_4  (0.5 s pan)
#   phase 5 → cs_pyramid  (1.2 s pan; on advance to phase 6 set INTRO_DONE=1)
#   phase 6 → terminal (intro complete)
# Total: 1 + 72 + 30 + 18 + 30 + 72 = 223 frames ≈ 3.72 s at 60 Hz.
INTRO_LEG_FRAMES = [1, 72, 30, 18, 30, 72]

DIRECTOR_SCRIPT = (
    "\\ wf qbert director MVP\n"  # first line skipped as sigil
    # One-shot level init — sets lives = 3 once on first tick. The player's
    # restart trigger ALSO writes lives=3 directly (mb 72=3) without
    # touching mb 421, so subsequent runs of this block are no-ops. Also
    # touches mb 70/71 so the HUD shows SCORE/TIMER lines from the start
    # (not strictly required — DrawHud reads zero as zero — but explicit
    # is clearer, and pre-allocates the slots for future scoring work).
    "421 read-mailbox 0 = if "
    "3 72 write-mailbox "
    "0 70 write-mailbox 0 71 write-mailbox "
    "1 421 write-mailbox "
    "then\n"
    # Intro state machine — runs only while phase 0..5; gates the rest of
    # the camera routing via mb 418 (INTRO_DONE). See the per-phase
    # narrative in the Python comments above INTRO_LEG_FRAMES.
    "416 read-mailbox 6 < if "
    # First tick of this phase (timer==0): write the matching CamShot index.
    # Phase 0..4 → cs_intro_0..4 (indices 13..17). Phase 5 → cs_pyramid (8).
    "417 read-mailbox 0 = if "
    f"416 read-mailbox dup 5 < if {CS_INTRO_BASE_IDX} + else drop {CS_PYRAMID_IDX} then "
    "INDEXOF_CAMSHOT write-mailbox "
    "then "
    # Increment timer (every tick).
    "417 read-mailbox 1 + 417 write-mailbox "
    # Compare timer to this phase's leg-duration threshold.
    "417 read-mailbox 416 read-mailbox "
    f"dup 0 = if drop {INTRO_LEG_FRAMES[0]} else "
    f"dup 1 = if drop {INTRO_LEG_FRAMES[1]} else "
    f"dup 2 = if drop {INTRO_LEG_FRAMES[2]} else "
    f"dup 3 = if drop {INTRO_LEG_FRAMES[3]} else "
    f"dup 4 = if drop {INTRO_LEG_FRAMES[4]} else "
    f"drop {INTRO_LEG_FRAMES[5]} "
    "then then then then then "
    # Threshold met (timer == leg duration): advance to next phase, reset
    # timer. If we just entered phase 6, latch INTRO_DONE.
    "= if "
    "416 read-mailbox 1 + dup 416 write-mailbox "
    "0 417 write-mailbox "
    "6 = if 1 418 write-mailbox then "
    "then "
    "then\n"
    # Camshot routing: when death timer (mb 415) > 0, hold cs_death.
    # When 414 (FALL_DEATH) fires, latch cs_death and start countdown.
    # Otherwise pass actboxor's signal (mb 100) through to INDEXOF_CAMSHOT.
    # Gated on INTRO_DONE so the intro state machine has exclusive control of
    # INDEXOF_CAMSHOT during the sweep.
    #
    # Also fold lives decrement + game-over latch into the FALL_DEATH branch
    # — both fire in the same tick FALL_DEATH=1 latches, so this is the
    # natural single-source one-shot. Decrement mb 72; if it hits 0, latch
    # mb 420 (GAME_OVER) which the player picks up to freeze input + arm
    # the restart-button trigger.
    f"414 read-mailbox 1 = if {CS_DEATH_IDX} INDEXOF_CAMSHOT write-mailbox "
    f"{CS_DEATH_HOLD_FRAMES} 415 write-mailbox "
    "72 read-mailbox 1 - dup 72 write-mailbox "
    "0 = if 1 420 write-mailbox then "
    "0 414 write-mailbox then\n"
    "418 read-mailbox 1 = if "
    "415 read-mailbox dup 0 > if 1 - dup 415 write-mailbox "
    f"0 = if {CS_PYRAMID_IDX} INDEXOF_CAMSHOT write-mailbox then "
    "else drop 100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then "
    "then "
    "then\n"
    # Cube-state advance on landed event
    "411 read-mailbox 0 <> if "
    "400 read-mailbox dup 1 + * 2 / 401 read-mailbox + 200 + "
    "dup read-mailbox 0 = if 2 swap write-mailbox else drop then "
    "0 411 write-mailbox then\n"
    # Visibility fan-out: for each cube, show only the actor for
    # (cur_palette, cube_state); hide all 12 variants (4 rounds * 3 states).
    # cur_palette = ROUND_NUMBER % 4.
    # Vis mailbox = 440 + r*84 + cube*3 + s.
    # Two nested do/loops: outer=cube (j in inner), inner=combo (i in inner).
    # r = combo/3, s = combo mod 3.
    "425 read-mailbox 4 % "     # ( cur_pal )  — % is zForth modulo primitive
    "28 0 do "                  # outer: i=cube 0..27
    "200 i + read-mailbox "     # ( cur_pal cube_state ) — read before inner loop
    "12 0 do "                  # inner: i=combo 0..11; j=cube (outer i promoted to j)
    "i 3 / over = "             # r==cur_pal?   (/ is integer divide in zForth)
    "i 3 % 2 pick = & "         # also s==cube_state?
    "if 1 else 0 then "
    "440 i 3 / 84 * + j 3 * + i 3 % + write-mailbox "
    "loop "
    "drop "                     # drop cube_state
    "loop "
    "drop\n"                    # drop cur_pal
    # Win check: count cubes whose state != 2; write count to mb 412, win flag to 413
    "0 28 0 do 200 i + read-mailbox 2 <> if 1 + then loop "
    "dup 412 write-mailbox 0 = if 1 413 write-mailbox then\n"
    # Round-clear: start 90-tick countdown when win latches (one-shot — only if
    # timer is not already running), then on expiry reset all cube states,
    # clear the win flag, increment the round counter, and respawn at apex.
    "413 read-mailbox 1 = if 424 read-mailbox 0 = if 90 424 write-mailbox then then\n"
    "424 read-mailbox dup 0 > if "
    "1 - dup 424 write-mailbox "
    "0 = if "
    "28 0 do 0 200 i + write-mailbox loop "
    "0 411 write-mailbox "
    "0 413 write-mailbox "
    "425 read-mailbox 1 + 425 write-mailbox "
    "0 400 write-mailbox 0 401 write-mailbox 0 402 write-mailbox "
    "0 414 write-mailbox 0 415 write-mailbox 0 419 write-mailbox "
    # Re-init visibility for the new palette: hide all 336 vis slots, then
    # show only state-0 actors for cur_palette (ROUND_NUMBER % 4).
    "336 0 do 0 440 i + write-mailbox loop "  # zero all vis slots
    # Now show round's state-0 row.  Compute base = 440 + cur_pal*84 once,
    # then write 1 to base+i*3 for each cube.
    "440 425 read-mailbox 4 % 84 * + "    # ( vis_base ) — % is zForth modulo
    "28 0 do 1 over i 3 * + write-mailbox loop "
    "drop "
    "1 426 write-mailbox "
    "then "
    "else drop then\n"
)
if director:
    director['wf_Script'] = DIRECTOR_SCRIPT

# ── 7. Create the 28 × 4 rounds × 3 states = 336 cube child-mesh actors ────────
print(f"[qbert] Creating {TOTAL_CUBES} cubes × {NUM_ROUNDS} rounds × 3 states = "
      f"{TOTAL_CUBES * NUM_ROUNDS * 3} actors...")
created_count = 0
for row in range(NUM_ROWS):
    for col in range(row + 1):
        N = cube_index(row, col)
        wx, wy, wz = cube_world_position(row, col)
        for r in range(NUM_ROUNDS):
            for state_idx in range(3):
                obj_name = f"cube_{N:02d}_r{r}_s{state_idx}"
                mesh_data = bpy.data.meshes.new(f"cube_mesh_{N:02d}_r{r}_s{state_idx}")
                s = CUBE_SIZE / 2
                box_verts = [
                    (-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
                    (-s, -s,  s), (s, -s,  s), (s, s,  s), (-s, s,  s),
                ]
                box_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
                mesh_data.from_pydata(box_verts, [], box_faces)
                mesh_data.update()

                obj = bpy.data.objects.new(obj_name, mesh_data)
                obj.location = (wx, wy, wz)
                obj.rotation_euler = (0.0, 0.0, math.pi / 4)  # diamond top
                scene.collection.objects.link(obj)

                vis_mb = INDEXOF_VIS_BASE + r * 84 + N * 3 + state_idx
                # Only round-0, state-0 actors start visible.
                initial_vis = 1 if (r == 0 and state_idx == 0) else 0

                obj['wf_schema_path'] = STATPLAT_OAD
                obj['wf_Mesh Name'] = f'cube_state{state_idx}_r{r}.iff'
                obj['wf_Model Type'] = 'Mesh'
                obj['wf_Mobility'] = 'Anchored'
                obj['wf_Mass'] = 0.0
                obj['wf_Visibility Mailbox'] = vis_mb
                created_count += 1

print(f"[qbert] Created {created_count} cube actors.")

# ── 8. Wireframe-display non-rendering infrastructure ────────────────────────
# Per docs/level-building.md "Blender Viewport Display by Object Type": anything
# whose wf_Model Type is not 'Mesh' or 'Matte' doesn't render in the game
# engine, so display it as Wire in Blender to keep the viewport readable.
RENDERED_MODEL_TYPES = ('Mesh', 'Matte')
wire_count = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    mt = obj.get('wf_Model Type', None)
    if mt not in RENDERED_MODEL_TYPES:
        obj.display_type = 'WIRE'
        wire_count += 1
print(f"[qbert] Set {wire_count} non-rendering objects to wireframe display.")

# ── 9. Save the .blend so the user can open it interactively ─────────────────
OUT_BLEND = os.path.join(SCRIPT_DIR, 'qbert_practice.blend')
print(f"[qbert] Saving .blend to {OUT_BLEND}")
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

# ── 9. Export the level ─────────────────────────────────────────────────────────
print(f"[qbert] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)

# The exporter writes a Blender-side mesh IFF for every actor (cube_NN_rR_sS.iff)
# with a white default material. Overwrite each with the gen_cube.py-generated
# cube_state{s}_r{r}.iff so the correct per-round material colour reaches the engine.
import shutil
overwrite_count = 0
for row in range(NUM_ROWS):
    for col in range(row + 1):
        N = cube_index(row, col)
        for r in range(NUM_ROUNDS):
            for state_idx in range(3):
                src = os.path.join(SCRIPT_DIR, f'cube_state{state_idx}_r{r}.iff')
                dst = os.path.join(SCRIPT_DIR, f'cube_{N:02d}_r{r}_s{state_idx}.iff')
                shutil.copyfile(src, dst)
                overwrite_count += 1
print(f"[qbert] Overwrote {overwrite_count} per-cube IFFs with coloured gen_cube.py output.")

# Same dual-Mesh-Name workaround for the player: the exporter writes player.iff
# from the Blender object's geometry (white default-material box), overriding
# the wf_Mesh Name='qbert_player.iff'. Copy the gen_player.py output over
# player.iff so the engine's first Mesh Name resolves to the orange Q*bert
# placeholder, not a white box.
shutil.copyfile(
    os.path.join(SCRIPT_DIR, 'qbert_player.iff'),
    os.path.join(SCRIPT_DIR, 'player.iff'),
)
print(f"[qbert] Overwrote player.iff with gen_player.py output.")

print(f"[qbert] Done — {OUT_LEV}")
