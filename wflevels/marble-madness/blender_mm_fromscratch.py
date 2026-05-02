"""
blender_mm_fromscratch.py — Build the MM Beginner Race level from scratch in Blender.

Demonstrates the minimum set of WF infrastructure objects required for a
playable level — no .lev import; every actor created from first principles.

Run via Blender MCP (execute_blender_code) or headless:
    blender --background --python blender_mm_fromscratch.py

Level geometry comes from rom_to_blender.py (Beginner Race path mesh).

What this creates and why:
    Director    — runs the level Forth script (timer, lives, camshot routing)
    Player      — marble actor (MarbleHandler, physics-driven)
    Room01      — containment volume; all actors placed inside its bbox
    Camera      — BungeeCam entity (must be inside Room01)
    CamShot01   — iso-offset camera configuration (inside Room01)
    Target01    — camera Follow anchor (world-space, at origin)
    Target02    — camera Look At point (just above player spawn)
    ActBoxOR    — camera activation trigger (fills level; first CamShot bootstrap)
    Light01     — illumination (must be inside Room01)
    LevelObj    — level configuration actor
    Matte       — background matte
    Practice_path — ROM-derived trough mesh from decode_levels.py output

Key gotchas encoded here (see docs/level-design-troubleshooting.md):
  - Camera, CamShot, Light all placed at positions strictly inside Room01 bbox
  - Room bbox set via wf_original_bbox property, not from mesh geometry
  - Target02 must exist — BungeeCam dereferences it; null → crash
  - Non-geometry actors must NOT have wf_original_bbox set (no BOX3 emitted)
  - Player Turn Rate = 0.0 selects MarbleHandler; Max Air Speed > 0 required

Path geometry coordinate system (see rom_to_blender.py):
  - Heading angle from type field lower byte: 0° = +X (East), CCW positive
  - Beginner seg 0: start platform (h_center=3 < H_ZERO), heading 56.25°
  - Beginner segs 1-6: all troughs (ball is contained), headings 66.09° → 90°
  - Beginner segs 7-8: goal platform (h_center=5=H_ZERO)
  - Spawn above seg 1 start (1.39, 2.08) — GAME_UNIT=0.1, seg-1 floor at Z=1.3m
  - All path segments are troughs — ball stays in without steering
"""

import bpy
import addon_utils
import math
import os
import sys

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
OAD_DIR    = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'mm_fromscratch.lev')

def oad(name):
    return os.path.join(OAD_DIR, f'{name}.oad')


# --------------------------------------------------------------------------
# Level layout constants
# --------------------------------------------------------------------------
# Beginner path (rom_to_blender.py heading-based layout, GAME_UNIT=0.05):
#   Seg 0:    start platform, heading 56.25°, ends at (1.39, 2.08)
#   Segs 1-2: heading 66.09° (NNE), all troughs
#   Segs 3-6: heading 90.00° (N),   all troughs, ends at (3.42, 16.65)
#   Segs 7-8: goal platform at Z=0, ends at (3.42, 24.15)
#   Z range:  floor -0.1–0.85 m, wall tops up to 5.1 m
#   Wall angles: 30–48° (Beginner troughs), matching arcade MAME captures
#
# Isometric camera offset: (-8,-8,+10) from player

# Room = global bounding box of ALL scene objects + 2-unit margin.
# Path: X[-5,9.4] Y[-3.3,19.2] Z[-0.1,5.1]; CamShot(-8,-8,10); Camera(-4.58,3.65,11.5)
# Light(1,7.5,17); margin→ X[-10,14] Y[-12,22] Z[-3,20]; center=(2,5,8.5)
ROOM_POS        = (2.0,  5.0,  8.5)
ROOM_LOCAL_BBOX = (-12.0, -17.0, -11.5, 12.0, 17.0, 11.5)
# world: X[-10,14] Y[-12,22] Z[-3,20]  — all actors inside ✓

# Spawn above seg-5→6 transition (first downhill section): path floor drops
# from Z=0.85m (seg5) to Z=0.55m (seg6) to Z=0m (goal) — ball rolls without input.
# Seg-5 center pos: (3.42, 11.65), floor Z=0.85m (GAME_UNIT=0.05).
SPAWN_POS    = (3.42, 11.65, 1.5)   # above seg-5 floor (Z=0.85m), first downhill

# Camera: SW of marble (−X, −Y, +Z) looking NE+down — classic isometric view.
#   Path going North appears as upper-right on screen (standard MM arcade framing).
#   Camera at X=−4.58 is west of path left wall (X=−0.58) — no geometry clipping ✓
#   Room X expanded to −10 so CamShot at X=−8 is strictly inside room ✓
#   WF/Blender coords: +X=East, +Y=North, +Z=Up (same system — no axis flip)
CAMSHOT_POS  = (-8.0,  -8.0, 10.0)   # SW+above: camera = player + this offset
TARGET1_POS  = (0.0,    0.0,  0.0)   # world-space follow anchor (origin)
TARGET2_POS  = (3.42,  12.65,  1.0)  # look-at: 1m north of spawn, just above floor
LIGHT_POS    = (1.0,    7.5, 17.0)   # overhead, inside room ✓
CAMERA_POS   = (-4.58,  3.65, 11.5)  # initial camera pos = SPAWN_POS + CAMSHOT_POS

# Director script: 90 s timer, 3 lives, respawn + camshot routing
DIRECTOR_SCRIPT = (
    r'\\ wf' '\n'
    r': init-game  INDEXOF_TIME read-mailbox 90 +  2 write-mailbox'
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

# Player script: forward joystick; respawn above seg-1 start on Z < -2; signal director
PLAYER_SCRIPT = (
    r'\\ wf' '\n'
    r': respawn  1 INDEXOF_X_POS write-mailbox  2 INDEXOF_Y_POS write-mailbox'
    r'  2 INDEXOF_Z_POS write-mailbox'
    r'  0 INDEXOF_XSPEED write-mailbox  0 INDEXOF_YSPEED write-mailbox'
    r'  0 INDEXOF_ZSPEED write-mailbox  1 13 write-mailbox ;' '\n'
    r'INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox' '\n'
    r'INDEXOF_Z_POS read-mailbox -2 < if respawn then' '\n'
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def clear_scene():
    # Delete all objects without using read_factory_settings — that call kills
    # the BlenderMCP socket, ending the MCP session mid-script.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block)
    addon_utils.enable("wf_blender", default_set=False, persistent=False)


def make_empty(name, pos, oad_name, props=None):
    """Create an Empty (non-geometry) actor with an OAD schema."""
    obj = bpy.data.objects.new(name, None)
    obj.location = pos
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = oad(oad_name)
    if props:
        for k, v in props.items():
            obj[f'wf_{k}'] = v
    return obj


def make_box_empty(name, pos, bbox_local, oad_name, props=None):
    """Create a box-shaped MESH actor (e.g. Room, ActBoxOR).
    Must be a mesh object (not Empty) so the bbox is visible in the viewport.
    The exporter reads bbox from wf_original_bbox, not the mesh geometry.
    """
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
    # Room bbox is read from wf_original_bbox by the exporter — not mesh geometry
    obj['wf_original_bbox'] = bbox_local
    if props:
        for k, v in props.items():
            obj[f'wf_{k}'] = v
    # Bounding-box actors don't render in the game — show as wireframe cage so they
    # don't obscure actual level geometry in the Blender viewport.
    obj.display_type = 'WIRE'
    return obj


# --------------------------------------------------------------------------
# Build scene
# --------------------------------------------------------------------------

clear_scene()
scene = bpy.context.scene

# ── Room ──────────────────────────────────────────────────────────────────
# The room bbox MUST contain Camera, CamShot, and all Lights (world-space).
# World bounds = ROOM_POS + ROOM_LOCAL_BBOX.
room = make_box_empty(
    'Room01', ROOM_POS, ROOM_LOCAL_BBOX, 'room',
    props={'Adjacent Room 1': '', 'Adjacent Room 2': '', 'Room Loaded Mailbox': 0}
)

# ── LevelObj ──────────────────────────────────────────────────────────────
make_empty('LevelObj', ROOM_POS, 'levelobj',
    props={'Mobility': 'Anchored', 'MovementClass': 15, 'Model Type': 'Box'})

# ── Matte ─────────────────────────────────────────────────────────────────
make_empty('Matte', ROOM_POS, 'matte',
    props={
        'Mobility':           'Anchored',
        'MovementClass':      11,
        'Model Type':         'Box',
        'Matte Type':         'Color',
        'Background Color':   0,
        'Visibility Mailbox': 1,
    })

# ── Light ─────────────────────────────────────────────────────────────────
# Must be inside room. LIGHT_POS=(0,15,8): world Z=8 < room Z-max=2+8=10. ✓
# Rotation = π/2 around X axis — Directional light at (0,0,0) doesn't
# illuminate geometry (all black); same value as working mm_practice light.
_light = make_empty('Light01', LIGHT_POS, 'light',
    props={'Mobility': 'Anchored', 'MovementClass': 23, 'Model Type': 'None'})
_light.rotation_euler = (math.pi / 2, 0, 0)

# ── Director ──────────────────────────────────────────────────────────────
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

# ── Camera entity ─────────────────────────────────────────────────────────
# Must be inside room. CAMERA_POS=(0,-1,7): world Y=-1>-3, Z=7<10. ✓
make_empty('Camera', CAMERA_POS, 'camera',
    props={'Mobility': 'Camera', 'MovementClass': 13, 'Model Type': 'Box'})

# ── Targets ───────────────────────────────────────────────────────────────
# Target01 = Follow anchor (world-space, at origin — effectively "no drift").
# Target02 = Look At point (just above player spawn; camera orients toward here).
# BungeeCam: direction = (Target02 - Follow + TrackObject) - camera_pos
#   TrackObject = Player, Follow = Target01 at origin → direction ≈ Player + offset.
make_empty('Target01', TARGET1_POS, 'target',
    props={'Mobility': 'Anchored', 'MovementClass': 3, 'Model Type': 'Box'})
make_empty('Target02', TARGET2_POS, 'target',
    props={'Mobility': 'Anchored', 'MovementClass': 3, 'Model Type': 'Box'})

# ── CamShot01 ─────────────────────────────────────────────────────────────
# All-Relative: camera position = CamShot_offset + player_pos.
# CAM_OFFSET = (0,-2,7): camera stays 2 m behind player and 7 m above.
# CAMSHOT_POS placed inside room for levcomp assignment.
# See wf-games/investigations/2026-04-30-camera-system-overview.md for axis config.
make_empty(
    'CamShot01', CAMSHOT_POS, 'camshot',
    props={
        'Mobility':           'Anchored',
        'MovementClass':      16,
        'Target':             'Target02',   # Look At
        'Follow':             'Target01',   # Follow anchor
        'Track Object':       'Player',     # dynamic target (marble)
        'Rotation':           'Track',      # orient toward Look At
        'Position X':         'Relative',   # camera X = CamShot X + player X
        'Position Y':         'Relative',   # camera Y = CamShot Y + player Y
        'Position Z':         'Relative',   # camera Z = CamShot Z + player Z
        'FOV':                50.0,         # degrees; tune toward 25 for iso look
        'Climb Rate':         5.0,
        'Elasticity':         10.0,         # rigid-ish follow
        'Pan Time In Seconds': 1.0,
        'Hither':             0.1,
        'Yon':                1000.0,
        'Model Type':         'Box',
        'Visibility Mailbox': 1,
    }
)

# ── ActBoxOR ──────────────────────────────────────────────────────────────
# Fills the room; writes CamShot01's index to the camshot mailbox when
# Player enters.  The engine bootstrap in level.cc already writes the first
# CamShot index at construction time, so this is belt-and-suspenders.
actbox_bbox = (-12.0, -17.0, -11.5, 12.0, 17.0, 11.5)  # same as room local bbox
make_box_empty(
    'ActBoxOR', ROOM_POS, actbox_bbox, 'actboxor',
    props={
        'Mobility':     'Anchored',
        'MovementClass': 17,
        'Model Type':   'None',            # trigger volume — invisible
        'MailBox':      100,               # mailbox 100 → director routes to CAMSHOT
        'Object':       'CamShot01',
        'Activated By': 'Player',
    }
)

# ── Player ────────────────────────────────────────────────────────────────
# MarbleHandler is selected when Turn Rate = 0.0 (NOT a bipedal character).
# Max Air Speed MUST be > 0 — zero zeroes all velocity including gravity.
# See docs/level-design-troubleshooting.md § "Marble frozen at spawn"
player = make_empty(
    'Player', SPAWN_POS, 'player',
    props={
        'Mobility':              'Physics',
        'MovementClass':         22,
        'Moves Between Rooms':   'True',
        'Turn Rate':             0.0,       # selects MarbleHandler
        'Running Acceleration':  15.0,
        'Running Deceleration':  0.9,
        'Max Ground Speed':      15.0,
        'Air Acceleration':      10.0,
        'Horiz Air Drag':        0.0,
        'Vert Air Drag':         0.0,
        'Max Air Speed':         50.0,      # must NOT be 0 — see gotcha above
        'Falling Acceleration':  9.8,
        'Vertical Elasticity':   0.3,
        'Horizontal Elasticity': 0.7,
        'Step Size':             0.25,
        'Mass':                  75.0,
        'Surface Friction':      0.95,
        'hp':                    32767.0,
        'Number Of Local Mailboxes': 6,
        'Script':                PLAYER_SCRIPT,
        'Script Controls Input': 'True',
        'Mesh Name':             'player.iff',
        'Model Type':            'Mesh',
        'Visibility Mailbox':    2002,      # local mailbox; always visible during play
    }
)
# Player bbox: roughly sphere of radius 0.33 m
player['wf_original_bbox'] = (-0.33, -0.33, 0.0, 0.33, 0.33, 0.66)

# --------------------------------------------------------------------------
# Add Beginner Race path geometry from ROM decoder output
# --------------------------------------------------------------------------
# exec into a named namespace so the module-level guard (__name__ == '__main__')
# does NOT fire.  Then call build_path_mesh directly.
_rtb_path = os.path.join(SCRIPT_DIR, 'rom_to_blender.py')
_rtb_ns   = {'__file__': _rtb_path, '__name__': 'rom_to_blender', 'bpy': bpy}
exec(open(_rtb_path).read(), _rtb_ns)
_rtb_ns['build_path_mesh']('Beginner', _rtb_ns['load_levels']())

# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------
print(f'[fromscratch] Exporting to {OUT_LEV}')
bpy.ops.wf.export_level(filepath=OUT_LEV)
print(f'[fromscratch] Done. Objects in scene:')
for o in bpy.data.objects:
    print(f'  {o.name} @ {tuple(round(x,2) for x in o.location)}')
