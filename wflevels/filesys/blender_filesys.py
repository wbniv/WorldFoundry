"""
blender_filesys.py — FSN-style filesystem browser level.

Inspired by the SGI FSN filesystem navigator (1992, IRIX; famous from Jurassic Park).
  Phase 1 (this script): flat one-directory-deep view.
    • Subdirectories → tall yellow towers  (height ∝ √file_count_inside)
    • Files          → short grey boxes    (height ∝ √file_size_KB)
    • Mixed grid; height contrast creates the FSN "skyline"
  Phase 2 (deferred): recursive, files on top of parent tower, wires.

The Director Forth script scans the CWD at game start and spawns template
instances of Dir/File actors, scaling them via scale mailboxes 3040-3042.

Run headlessly:
    blender --background --python blender_filesys.py
Or via BlenderMCP:
    execute_blender_code

See docs/plans/2026-06-11-web-canvas-port.md for build context.
Plan: docs/plans/2026-06-12-filesys-browser-level.md (if it exists).
"""

import bpy
import addon_utils
import math
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
OAD_DIR    = os.path.join(REPO, 'wflevels', 'oad')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'filesys.lev')

def oad(name):
    return os.path.join(OAD_DIR, f'{name}.oad')

# ── Level layout ──────────────────────────────────────────────────────────────
# Floor: 44×76 to cover grid (X: -17..+18, Y: -35..+35) with margin.
FLOOR_X0 = -22.0
FLOOR_X1 =  22.0
FLOOR_Y0 = -38.0
FLOOR_Y1 =  38.0
FLOOR_Z0 =  -0.5
FLOOR_Z1 =   0.0

PLAYER_SPAWN = (0.0, 0.0, 1.0)

# Camera at (0,-70,40) — same position that was verified working before.
# Grid is now centred: Y0=-35 so rows span -35..+35 around the player.
# Camera looks from behind at 30° downward; tower tops break the horizon
# in middle rows, creating the FSN cityscape silhouette.
CAM_OFFSET   = (0.0, -70.0, 40.0)
TARGET1_POS  = (0.0, 0.0, 0.0)
TARGET2_POS  = (0.0, 5.0, 0.0)

# Room bbox — wider than needed so spring transients can't escape.
# Camera at (0,-70,41); grid X: -17..+18, Y: -35..+35, Z: 0..8.
ROOM_CENTER     = (0.0, 0.0, 25.0)
ROOM_LOCAL_BBOX = (-35.0, -72.0, -28.0, 35.0, 40.0, 28.0)
# Keeping room X=±35 from the previously-verified working config — bungee
# camera initialises cleanly at this X extent. Y extended to +40 so the
# far grid rows (Y up to +35) are comfortably inside.
# World X: [-35,35], Y: [-72,40], Z: [-3,53]  (cam at (0,-70,41) ✓)

# Template objects sit OOB (Z=-200), outside all room bboxes.
# Their data is loaded; they're never constructed by the normal load pass
# (OBJECTONLYTEMPLATEENTRY returns NULL from ConstructOadObject).
# spawn-template (syscall 135) calls ConstructTemplateObject by actor index.
#
# Object ordering in the exported .lev determines runtime indices.
# The engine uses 1-based indices (index 0 is a null sentinel overwritten at
# load time), so the .lvl index = Blender scene index + 1.
#
# Blender  .lvl  Actor
#    0       1   Room
#    1       2   LevelObj
#    2       3   Matte
#    3       4   Light
#    4       5   Camera
#    5       6   CamShot
#    6       7   Target01
#    7       8   Target02
#    8       9   Director
#    9      10   Player
#   10      11   Floor (StatPlat)
#   11      12   DirTemplate  ← DIR-TMPL  in the Forth script
#   12      13   FileTemplate ← FILE-TMPL in the Forth script
#   13      14   ActBoxOR
#   14      15   AmbientLight (appended last so 11/12 above stay fixed)
#   15      16   ConnectorTemplate (FSN wire, appended for Phase 2)
#
# These .lvl indices are passed to spawn-template / fsn-config.
DIR_TMPL_IDX   = 12
FILE_TMPL_IDX  = 13
CONN_TMPL_IDX  = 16    # ConnectorTemplate (.lvl index)
PLAYER_LVL_IDX = 10    # Player (.lvl index) — fsn-navigate reads its position
FSN_MAX_DEPTH  = 2     # render the tree this many levels from the current root
FSN_MAX_NODES  = 120   # hard cap on total spawned actors (towers+files+wires) < 500 pool

# SGI FSN aesthetic: near-black blue background and floor, yellow towers, grey boxes.
COLOR_BG       = 0x0a0a14   # near-black blue for Matte
COLOR_FLOOR    = (0.05, 0.05, 0.10, 1.0)
COLOR_DIR      = (1.00, 0.85, 0.00, 1.0)   # yellow
COLOR_FILE     = (0.50, 0.50, 0.70, 1.0)   # grey-blue

# Grid: 8 columns × 5-unit spacing.
# Y0=-35 centres ~15 rows around Y=0: rows 0..14 → Y: -35..+35.
# Each entry (dir or file) gets the next sequential grid slot.
GRID_COLS = 8
GRID_CELL = 5
GRID_X0   = -17
GRID_Y0   = -35

# Director Forth script — FSN populator.
# Runs every frame; a first-frame init guard (mailbox 10) ensures the scan
# happens exactly once.  Mailbox 11 is the shared grid counter.
# Mailboxes 0 (EMAILBOX_FALSE) and 1 (EMAILBOX_TRUE) are global write-protected
# constants — use indices ≥ 2 for any state the script writes.
#
# isqrt uses begin..until (zForth has no while/repeat):
#   begin [increment s] [check s²>n] until → exits when s²>n, returns s-1.
#
# Grid formula:
#   x = (counter mod COLS) * CELL + X0
#   y = (counter /   COLS) * CELL + Y0
#
# scale mailboxes 3040/3041/3042 are X/Y/Z stretch.
# set-z-scale (defined in scripting_zforth.cc) sets X=Y=1.0, Z=computed height,
# so towers are tall and thin rather than uniformly scaled cubes.
#
# DIR-TMPL / FILE-TMPL are the level-actor indices of DirTemplate/FileTemplate.
# Phase 2: the recursive scan + radial layout + spawning all live in C++
# (fsn-build, scripting_zforth.cc) — zForth can't do the recursion/trig. The
# Director just configures and triggers the build once, then polls navigation.
#   fsn-config ( dirT fileT connT maxDepth maxNodes playerIdx -- )
#   fsn-build  ( -- nodeCount )
#   fsn-navigate ( -- )   \ proximity descend / back ascend (M3)
# Mailbox 10 = one-shot init guard.
DIRECTOR_SCRIPT = (
    r'\\ wf' '\n'
    f': DIR-T   {DIR_TMPL_IDX} ;\n'
    f': FILE-T  {FILE_TMPL_IDX} ;\n'
    f': CONN-T  {CONN_TMPL_IDX} ;\n'
    f': MAXDEPTH {FSN_MAX_DEPTH} ;\n'
    f': MAXNODES {FSN_MAX_NODES} ;\n'
    f': PLAYER-IDX {PLAYER_LVL_IDX} ;\n'

    '10 read-mailbox 0 = if\n'
    '  1 10 write-mailbox\n'
    '  DIR-T FILE-T CONN-T MAXDEPTH MAXNODES PLAYER-IDX fsn-config\n'
    '  fsn-build drop\n'
    'fi\n'

    'fsn-navigate\n'
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block)
    addon_utils.enable("wf_blender", default_set=False, persistent=False)


def make_mat(name, rgba):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = rgba
    return mat


def make_empty(name, pos, oad_name, props=None):
    obj = bpy.data.objects.new(name, None)
    obj.location = pos
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = oad(oad_name)
    if props:
        for k, v in props.items():
            obj[f'wf_{k}'] = v
    return obj


def make_box_mesh(name, pos, bbox_local, oad_name, props=None, wire=True):
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
    if wire:
        obj.display_type = 'WIRE'
    return obj


def add_solid_box(name, x0, y0, z0, x1, y1, z1, mat=None):
    """Create a solid box via explicit object creation (preserves scene insertion order)."""
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0.0, 0.0, 0.0)
    bpy.context.scene.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def build_astronaut_mesh():
    """Low-poly EVA-suit astronaut, ported from moon_site01 `_build_astronaut`.

    Joins ~14 primitives into one mesh and bakes the origin to the feet (local
    z=0) via transform_apply(location=True) — the base-pivot convention. The
    suit faces mesh +X (chest/visor front, PLSS backpack at -X). Returns the
    mesh datablock and leaves the scene with NO temp objects, so the caller can
    create the Player at the correct scene-export index.
    """
    mat_white = make_mat('astro_white',    (0.92, 0.92, 0.92, 1.0))
    mat_off   = make_mat('astro_offwhite', (0.85, 0.85, 0.82, 1.0))   # PLSS backpack
    mat_dark  = make_mat('astro_dark',     (0.18, 0.18, 0.20, 1.0))   # chest panel, neck
    mat_visor = make_mat('astro_visor',    (0.76, 0.53, 0.25, 1.0))   # gold-amber visor

    parts = []
    SEG = 8; RING = 5   # low-poly UV sphere/cylinder segments

    def add_cyl(r, h, loc, mat):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        parts.append((bpy.context.object, mat))

    def add_sph(r, loc, mat):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=SEG, ring_count=RING, location=loc)
        parts.append((bpy.context.object, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        o = bpy.context.object
        o.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((o, mat))

    # Boots, lower legs, upper legs (mirrored in ±Y)
    for yo in (-0.12, 0.12):
        add_cube(0.18, 0.15, 0.10, (0.0, yo, 0.05), mat_white)   # boot
        add_cyl(0.09, 0.42, (0.0, yo, 0.31), mat_white)          # lower leg
        add_cyl(0.10, 0.42, (0.0, yo, 0.73), mat_white)          # upper leg

    add_cyl(0.20, 0.10, (0.0, 0.0, 0.95), mat_white)             # hips
    add_cyl(0.22, 0.45, (0.0, 0.0, 1.225), mat_white)            # torso
    add_cube(0.20, 0.08, 0.12, (+0.20, 0.0, 1.30), mat_dark)     # chest panel (mesh +X front)
    add_cube(0.30, 0.18, 0.50, (-0.27, 0.0, 1.20), mat_off)      # PLSS backpack (mesh -X back)

    for yo in (-0.27, 0.27):
        add_sph(0.11, (0.0, yo, 1.42), mat_white)                # shoulder
        add_cyl(0.08, 0.30, (0.0, yo, 1.27), mat_white)          # upper arm
        add_cyl(0.08, 0.28, (0.0, yo, 0.98), mat_white)          # forearm
        add_sph(0.09, (0.0, yo, 0.84), mat_white)                # glove

    add_cyl(0.06, 0.06, (0.0, 0.0, 1.475), mat_dark)             # neck
    add_sph(0.14, (0.0, 0.0, 1.66), mat_white)                   # helmet
    add_sph(0.13, (+0.05, 0.0, 1.66), mat_visor)                 # visor (mesh +X front)

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0
            p.use_smooth = True

    # Join all parts, then bake the root part's location into verts so the
    # joined mesh origin lands at the feet (z=0).
    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    mesh = body.data
    mesh.name = 'astronaut'
    bpy.data.objects.remove(body, do_unlink=True)   # leave scene clean; keep the mesh
    mesh.use_fake_user = True                         # protect the now-userless datablock
    return mesh


# ── Build scene ───────────────────────────────────────────────────────────────

clear_scene()
scene = bpy.context.scene

# 0 ── Room ────────────────────────────────────────────────────────────────────
make_box_mesh(
    'Room01', ROOM_CENTER, ROOM_LOCAL_BBOX, 'room',
    props={
        'Adjacent Room 1': '',
        'Adjacent Room 2': '',
        'Room Loaded Mailbox': 0,
    }
)

# 1 ── LevelObj ────────────────────────────────────────────────────────────────
make_empty('LevelObj', ROOM_CENTER, 'levelobj',
    props={
        'Number Of Mailboxes': 50,
        # Phase 2 spawns a recursive tree of towers + files + connector wires at
        # runtime; raise the temp-object pool to the max so the build fits.
        'Number Of Temporary Objects': 500,
        'Mobility':   'Anchored',
        'Model Type': 'None',
    }
)

# 2 ── Matte ───────────────────────────────────────────────────────────────────
# Dark near-black blue background — SGI FSN aesthetic.
make_empty('Matte', ROOM_CENTER, 'matte',
    props={
        'Mobility':           'Anchored',
        'Matte Type':         'Color',
        'Background Color':   COLOR_BG,
        'Visibility Mailbox': 1,
        'Model Type':         'None',
    }
)

# 3 ── Light ───────────────────────────────────────────────────────────────────
# Cool-tinted directional light from above — blue-white, SGI cyberspace feel.
light = make_empty('Light01', (0.0, 0.0, 35.0), 'light',
    props={
        'Mobility':     'Anchored',
        'lightType':    'Directional',
        'lightRed':     0.6,
        'lightGreen':   0.6,
        'lightBlue':    0.8,
        'Model Type':   'None',
    }
)
light.rotation_euler = (math.pi / 2, 0, 0)   # aim downward

# 4 ── Camera ──────────────────────────────────────────────────────────────────
# Initial position = spawn + offset (inside room bbox).
cam_initial = tuple(PLAYER_SPAWN[i] + CAM_OFFSET[i] for i in range(3))
make_empty('Camera', cam_initial, 'camera',
    props={
        'Mobility':              'Camera',
        'Model Type':            'None',
        'FoggingColor':          0x000000,
        'FoggingStartDistance':  999.0,
        'FoggingCompleteDistance': 1000.0,
    }
)

# 5 ── CamShot ─────────────────────────────────────────────────────────────────
# Camera at (0,-70,41): verified working position. Tracks player; Position Absolute
# prevents bungee drift. Grid centred around Y=0 — towers visible as skyline.
camshot_world = tuple(PLAYER_SPAWN[i] + CAM_OFFSET[i] for i in range(3))
make_empty('CamShot01', camshot_world, 'camshot',
    props={
        'Mobility':             'Anchored',
        'Target':               'Target02',
        'Follow':               'Target01',
        'Track Object':         'Player',
        'Rotation':             'Fixed',
        'Position X':           'Absolute',
        'Position Y':           'Absolute',
        'Position Z':           'Absolute',
        'FOV':                  75.0,
        'Climb Rate':           3.0,
        'Elasticity':           8.0,
        'Pan Time In Seconds':  0.2,
        'Hither':               0.1,
        'Yon':                  500.0,
        'Model Type':           'None',
        'Visibility Mailbox':   1,
    }
)

# 6 ── Target01 ────────────────────────────────────────────────────────────────
make_empty('Target01', TARGET1_POS, 'target',
    props={'Mobility': 'Anchored', 'Model Type': 'None'}
)

# 7 ── Target02 ────────────────────────────────────────────────────────────────
make_empty('Target02', TARGET2_POS, 'target',
    props={'Mobility': 'Anchored', 'Model Type': 'None'}
)

# 8 ── Director ────────────────────────────────────────────────────────────────
# Needs at least 2 local mailboxes: 0=init flag, 1=grid counter.
make_empty('Director', (0.0, 0.0, 1.0), 'director',
    props={
        'Mobility':               'Anchored',
        'Number Of Local Mailboxes': 5,
        'Script':                 DIRECTOR_SCRIPT,
        'Script Controls Input':  'False',
        'Model Type':             'None',
    }
)

# 9 ── Player ──────────────────────────────────────────────────────────────────
# Walking EVA astronaut — moon_site01 locomotion.  Turn Rate>0 → GroundHandler
# (movement.cc:577): UP/DOWN walk forward/back along facing dir, LEFT/RIGHT turn.
#
# Movement REQUIRES both of the following, or the player can never move:
#   • Script Controls Input=True — else Actor::_InitInput (actor.cc:334) binds
#     &theNullInputDigital, whose arePressed() is always 0 (this is why the old
#     marble was immobile despite gDoomStick=1 and a working handler).
#   • the wf_Script below, which copies the hardware joystick (mailbox 1909) into
#     the player INPUT mailbox (3024) every frame — exactly what moon's player does.
# Mesh is the inline astronaut (feet at local z=0); the exporter derives the
# Global Bounding Box → Jolt capsule from the mesh AABB (no wf_original_bbox).
_astro_mesh = build_astronaut_mesh()
player = bpy.data.objects.new('Player', _astro_mesh)
player.location = PLAYER_SPAWN
bpy.context.scene.collection.objects.link(player)
player['wf_schema_path'] = oad('player')
for k, v in {
    'Mobility':               'Physics',
    'Moves Between Rooms':    'True',
    'Script Controls Input':  'True',    # real input device — the core movement fix
    'Turn Rate':              0.5,       # GroundHandler walk+turn (was 0.0 = marble)
    'Running Acceleration':   8.0,
    'Running Deceleration':   0.85,
    'Max Ground Speed':       4.0,       # moon uses 2.5; bumped for the FSN floor
    'Jumping Acceleration':   15.0,
    'Falling Acceleration':   9.8,       # keep grounded (not the moon's 1.62)
    'Air Acceleration':       0.0,
    'Max Air Speed':          8.0,
    'Horiz Air Drag':         1.5,
    'Mass':                   80.0,
    'Model Type':             'Mesh',
    'Visibility Mailbox':     1,
}.items():
    player[f'wf_{k}'] = v
player.rotation_euler.z = math.pi / 2   # C=π/2: faces mesh +X → world +Y (into the scene)
# Route the hardware joystick into the player INPUT mailbox each frame (1909 → 3024).
player['wf_Script'] = (
    "\\ wf\n"
    "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n"
)
_astro_mesh.use_fake_user = False        # Player now owns the datablock

# 10 ── Floor (StatPlat) ───────────────────────────────────────────────────────
mat_floor = make_mat('fsn_floor', COLOR_FLOOR)
floor_obj = add_solid_box(
    'Floor',
    FLOOR_X0, FLOOR_Y0, FLOOR_Z0,
    FLOOR_X1, FLOOR_Y1, FLOOR_Z1,
    mat_floor
)
floor_obj['wf_schema_path'] = oad('statplat')
floor_obj['wf_Mobility']           = 'Anchored'
floor_obj['wf_Model Type']         = 'Mesh'
floor_obj['wf_Visibility Mailbox'] = 1

# 11 ── DirTemplate ────────────────────────────────────────────────────────────
# Template Object=1: not constructed at load time; spawned at runtime via
# spawn-template (syscall 135).  Scale mailboxes 3040-3042 set height.
# Base-pivot: mesh-local Z spans [0, 2] (base at the local origin), so the
# Z-scale (which column-multiplies about the origin, rendacto.cc:481-483) grows
# the tower purely UPWARD from the floor — a centered [-1,+1] cube would sink
# half its scaled height below z=0.  See level-building.md "Mesh origin".
# 2×2 footprint; scale=n makes it 2n units tall.  Placed OOB (Z=-200).
mat_dir = make_mat('fsn_dir', COLOR_DIR)
dir_tmpl = add_solid_box(
    'DirTemplate',
    -1.0, -1.0, 0.0,
     1.0,  1.0, 2.0,
    mat_dir
)
dir_tmpl['wf_schema_path']          = oad('dir')
dir_tmpl['wf_Template Object']      = 'True'
dir_tmpl['wf_Mobility']             = 'Anchored'
dir_tmpl['wf_Model Type']           = 'Mesh'
dir_tmpl['wf_Visibility Mailbox']   = 1
dir_tmpl.location                   = (0.0, -200.0, 0.0)

# 12 ── FileTemplate ───────────────────────────────────────────────────────────
# Base-pivot: mesh-local Z spans [0, 0.5] (base at the local origin) so Z-scale
# grows the box upward from the floor, never below it.  See DirTemplate above /
# level-building.md "Mesh origin".  2×2 footprint, 0.5 tall before scale;
# scale=n makes it n×0.5 units tall (files stay shorter than dir towers).
mat_file = make_mat('fsn_file', COLOR_FILE)
file_tmpl = add_solid_box(
    'FileTemplate',
    -1.0, -1.0, 0.0,
     1.0,  1.0, 0.5,
    mat_file
)
file_tmpl['wf_schema_path']         = oad('file')
file_tmpl['wf_Template Object']     = 'True'
file_tmpl['wf_Mobility']            = 'Anchored'
file_tmpl['wf_Model Type']          = 'Mesh'
file_tmpl['wf_Visibility Mailbox']  = 1
file_tmpl.location                  = (4.0, -200.0, 0.0)

# ── ActBoxOR: bootstrap camera ────────────────────────────────────────────────
# Fills the room; activates CamShot01 when Player enters.
abor = make_box_mesh(
    'ActBoxOR', ROOM_CENTER, ROOM_LOCAL_BBOX, 'actboxor',
    props={
        'Mobility':         'Anchored',
        'Model Type':       'None',
        'MailBox':          1921,       # INDEXOF_CAMSHOT
        'Object':           'CamShot01',
        'Activated By': 'Player',
    }
)

# 14 ── AmbientLight ───────────────────────────────────────────────────────────
# Appended LAST so the DirTemplate/FileTemplate scene indices (11,12) the Director
# script hardcodes (DIR_TMPL_IDX/FILE_TMPL_IDX) stay put. Every level needs a
# Directional AND an Ambient light (docs/level-building.md "Lighting"): the flat
# tower faces read fine off the directional alone, but the curved astronaut suit
# renders pure-black on its shadowed side without ambient fill.
make_empty('AmbientLight', (0.0, 0.0, 35.0), 'light',
    props={
        'Mobility':   'Anchored',
        'lightType':  'Ambient',
        'lightRed':   0.40,
        'lightGreen': 0.40,
        'lightBlue':  0.50,   # faint cool tint, SGI cyberspace feel
        'Model Type': 'None',
    }
)

# 15 ── ConnectorTemplate (FSN wire) ───────────────────────────────────────────
# Phase 2 connector: a thin beam whose length runs local +X ∈ [0,1], base-pivot
# at the parent end (X=0). fsn-build spawns it at a parent tower, rotates +X to
# aim at the child, and X-scales it to the gap (rendacto column-scale grows it
# toward the child). Thin in Y/Z; bright cyan-green emissive for the FSN glow.
# Appended last; its .lvl index (16) is passed to fsn-config (CONN_TMPL_IDX).
mat_conn = make_mat('fsn_conn', (0.20, 1.00, 0.70, 1.0))   # cyan-green wire
conn_tmpl = add_solid_box(
    'ConnectorTemplate',
    0.0,  -0.04, -0.04,
    1.0,   0.04,  0.04,
    mat_conn
)
conn_tmpl['wf_schema_path']        = oad('dir')   # reuse dir.oad (trivial mesh actor)
conn_tmpl['wf_Template Object']    = 'True'
conn_tmpl['wf_Mobility']           = 'Anchored'
conn_tmpl['wf_Model Type']         = 'Mesh'
conn_tmpl['wf_Visibility Mailbox'] = 1
conn_tmpl.location                 = (8.0, -200.0, 0.0)

# ── Export ────────────────────────────────────────────────────────────────────
print(f'[filesys] Exporting to {OUT_LEV}')
try:
    bpy.ops.wf.export_level(filepath=OUT_LEV)
except AttributeError:
    import importlib.util as _ilu
    _addon_dir = os.path.expanduser('~/.config/blender/4.0/scripts/addons/wf_blender')
    _spec = _ilu.spec_from_file_location(
        'wf_blender.export_level',
        os.path.join(_addon_dir, 'export_level.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ok, msg = _mod.export_scene_to_lev(bpy.context, OUT_LEV)
    if not ok:
        raise RuntimeError(f'export_scene_to_lev failed: {msg}')
    print(f'Info: Exported to {OUT_LEV}')

print(f'[filesys] Done. Objects in scene (export order):')
for i, o in enumerate(o for o in bpy.context.scene.objects if o.get('wf_schema_path')):
    print(f'  [{i:2d}] {o.name} @ {tuple(round(x,2) for x in o.location)}')
