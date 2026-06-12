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
#
# These .lvl indices are what spawn-template passes to FindTemplateObjectData().
DIR_TMPL_IDX  = 12
FILE_TMPL_IDX = 13

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
DIRECTOR_SCRIPT = (
    r'\\ wf' '\n'

    # Template indices (must match object ordering in the exported .lev)
    f': DIR-TMPL  {DIR_TMPL_IDX} ;\n'
    f': FILE-TMPL {FILE_TMPL_IDX} ;\n'

    # Grid layout constants
    f': COLS  {GRID_COLS} ;\n'
    f': CELL  {GRID_CELL} ;\n'
    f': X0    {GRID_X0} ;\n'
    f': Y0    {GRID_Y0} ;\n'

    ': grid-x ( n -- x ) COLS mod CELL * X0 + ;\n'
    ': grid-y ( n -- y ) COLS /   CELL * Y0 + ;\n'

    # Level mailboxes: 10=init flag, 11=shared grid counter.
    # Mailboxes 0 (FALSE) and 1 (TRUE) are write-protected global constants.
    ': cnt@  11 read-mailbox ;\n'
    ': cnt+  cnt@ 1 + 11 write-mailbox ;\n'

    # Integer square root: begin..until exits when s²>n.
    # For n=0: if-branch leaves 0 on stack (the dup'd 0).
    ': isqrt ( n -- s )\n'
    '  dup 0 = if else\n'
    '    1 swap\n'
    '    begin swap 1+ swap over dup * over > until\n'
    '    swap drop 1-\n'
    '  fi ;\n'

    # Spawn a Dir tower for CWD entry idx.
    # height = clamp(isqrt(file_count_in_subdir), 1, 6). X/Y stay unit width.
    # Grid position from shared counter.
    ': spawn-dir ( idx -- )\n'
    '  cwd-dir-count isqrt dup 6 > if drop 6 fi dup 1 < if drop 1 fi\n'
    '  cnt@ dup grid-x swap grid-y 0 DIR-TMPL spawn-template\n'
    '  swap set-z-scale\n'
    '  cnt+ ;\n'

    # Spawn a File box for CWD entry idx.
    # height = clamp(isqrt(file_size/1000), 1, 4). X/Y stay unit width.
    ': spawn-file ( idx -- )\n'
    '  cwd-file-size 1000 / isqrt dup 4 > if drop 4 fi dup 1 < if drop 1 fi\n'
    '  cnt@ dup grid-x swap grid-y 0 FILE-TMPL spawn-template\n'
    '  swap set-z-scale\n'
    '  cnt+ ;\n'

    # One-shot init: populate the FSN grid on the first frame only.
    # mailbox 10 = 0 → not done yet; set to 1 then scan + spawn.
    '10 read-mailbox 0 = if\n'
    '  1 10 write-mailbox\n'
    '  0 11 write-mailbox\n'
    '  cwd-scan 0 do\n'
    '    i cwd-is-dir if\n'
    '      i spawn-dir\n'
    '    else\n'
    '      i spawn-file\n'
    '    fi\n'
    '  loop\n'
    'fi\n'
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
# Marble-style controller (TurnRate=0 → MarbleHandler).
# Doom-stick with C=π/2: LEFT/RIGHT strafe along X axis.
player = make_empty('Player', PLAYER_SPAWN, 'player',
    props={
        'Mobility':               'Physics',
        'Moves Between Rooms':    'True',
        'Turn Rate':              0.0,
        'Running Acceleration':   15.0,
        'Running Deceleration':   0.5,
        'Max Ground Speed':       12.0,
        'Air Acceleration':       8.0,
        'Horiz Air Drag':         0.5,
        'Max Air Speed':          20.0,
        'Falling Acceleration':   9.8,
        'Vertical Elasticity':    0.2,
        'Horizontal Elasticity':  0.5,
        'Step Size':              0.25,
        'Mass':                   1.0,
        'Mesh Name':              'sphere.iff',
        'Model Type':             'Mesh',
        'Visibility Mailbox':     1,
    }
)
player.rotation_euler.z = math.pi / 2   # C=π/2: currentDir=+Y, strafes ±X
player['wf_original_bbox'] = (-0.4, -0.4, 0.0, 0.4, 0.4, 0.8)

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
