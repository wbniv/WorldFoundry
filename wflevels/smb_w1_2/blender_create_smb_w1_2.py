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

# W1-1 landmark X positions (tile counts × T) — faithful 224-tile original
MARIO_SPAWN_X = 3  * T
QBLOCK_XS     = [21*T, 107*T]            # coin ? blocks at faithful cols 21, 107
KOOPA_X       = 113 * T                  # col 113 (was 32*T)
FLAGPOLE_X    = 24 * T                   # 36 m — bare W1-2 proof: short underground corridor

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

# Bare W1-2 proof: flat ground, no bottomless gaps. Empty PITS -> §5 builds one
# continuous slab and the pit-death sensor loop is a no-op.
PITS = []

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

# ── 2. Import snowgoons for infrastructure ────────────────────────────────────
print(f"[smb] Importing snowgoons from {SNOWGOONS}")
bpy.ops.wf.import_level(filepath=SNOWGOONS)

# ── 3. Strip gameplay objects; keep one of each infrastructure class ──────────
KEEP_CLASSES   = {'director', 'camera', 'levelobj', 'matte', 'light',
                  'room', 'camshot', 'target', 'actboxor', 'player'}
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile',
                  'tool', 'tool01', 'ground01', 'hp', 'gold', 'generator'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


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


def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None


def attach_schema(obj, oad_name):
    obj['wf_schema_path'] = os.path.join(OAD_DIR, oad_name + '.oad')


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
        "INDEXOF_SMB_TIMER_START read-mailbox not if "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox then\n"
        f"{TIMER_UNITS} INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START read-mailbox - "
        f"{TIMER_UNITS / TIMER_REAL_SECONDS:.5f} * -\n"        # 400 - elapsed*RATE
        "dup 0 <= if "
        "1 INDEXOF_SMB_PLAYER_HURT write-mailbox "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox "
        "drop 0 then\n"                                        # clamp display to 0
        "INDEXOF_HUD_TIMER write-mailbox\n"
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
def make_mat(name, rgb):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def add_box(mesh_name, x0, y0, z0, x1, y1, z1, mat):
    """Add a box mesh [x0..x1]×[y0..y1]×[z0..z1], return the object."""
    cx, cy, cz = (x0+x1)/2, (y0+y1)/2, (z0+z1)/2
    sx, sy, sz = x1-x0, y1-y0, z1-z0
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    obj = bpy.context.object
    obj.name      = mesh_name
    obj.data.name = mesh_name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    return obj


def add_statplat(mesh_name, x0, y0, z0, x1, y1, z1, mat):
    obj = add_box(mesh_name, x0, y0, z0, x1, y1, z1, mat)
    attach_schema(obj, 'statplat')
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Model Type'] = 'Mesh'
    return obj


def _make_qblock_tga(out_path, scale=2):
    """Generate a 32×32 NES-style ?-block texture and save as TGA.

    Each "NES pixel" is `scale`×`scale` output pixels so the block reads
    clearly on a 1.5 m face.  Output is always a power-of-2 square
    (32×32 at scale=2) per textile-rs bitmap.rs:507.

    Palette:
      0 = dark border  (101,  47,   0)
      1 = orange fill  (196, 106,   0)
      2 = bright edge  (252, 180,  36)  — lighter row inside top/bottom border
      3 = white mark   (252, 248, 200)  — ? glyph interior

    The ? glyph uses the classic NES double-arch style:
      rows 3-7  arch (two bumps, right arm closes into stem)
      row  8    stem
      row  9    gap
      rows 10-12 dot
    """
    from PIL import Image
    PALETTE = [
        (101,  47,   0),   # 0 dark border
        (196, 106,   0),   # 1 orange fill
        (252, 180,  36),   # 2 bright edge
        (252, 248, 200),   # 3 white mark
    ]
    # 16×16 NES pixel map (palette indices)
    MAP = [
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0],
        [0,2,1,1,1,1,1,1,1,1,1,1,1,2,0,0],
        [0,2,1,1,0,0,0,1,0,0,0,1,1,2,0,0],  # arch top
        [0,2,1,1,0,3,3,0,3,3,0,1,1,2,0,0],  # arch interior
        [0,2,1,1,0,0,0,0,3,3,0,1,1,2,0,0],  # left arm closes
        [0,2,1,1,1,1,1,0,3,3,0,1,1,2,0,0],  # right arm
        [0,2,1,1,1,1,0,0,0,1,1,1,1,2,0,0],  # arch closes into stem
        [0,2,1,1,1,1,0,3,0,1,1,1,1,2,0,0],  # stem
        [0,2,1,1,1,1,1,1,1,1,1,1,1,2,0,0],  # gap
        [0,2,1,1,1,1,0,0,0,1,1,1,1,2,0,0],  # dot top
        [0,2,1,1,1,1,0,3,0,1,1,1,1,2,0,0],  # dot centre
        [0,2,1,1,1,1,0,0,0,1,1,1,1,2,0,0],  # dot bottom
        [0,2,1,1,1,1,1,1,1,1,1,1,1,2,0,0],
        [0,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    ]
    size = 16 * scale
    img = Image.new('RGB', (size, size))
    px  = img.load()
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            color = PALETTE[c]
            for dy in range(scale):
                for dx in range(scale):
                    px[x * scale + dx, y * scale + dy] = color
    img.save(out_path)
    return out_path


def _make_brick_tga(out_path, scale=2):
    """Generate a 32×32 NES-style breakable-brick texture and save as TGA.

    Classic SMB running-bond brick: four 4-pixel courses of orange bricks,
    each capped by a dark horizontal mortar line and a bright lit top edge,
    with the vertical mortar seams offset half a brick between alternating
    courses. Same palette family + scale convention as `_make_qblock_tga`
    so the brick reads next to the ? blocks. Output is power-of-2 square
    (32×32 at scale=2).

    Palette:
      0 = dark mortar  (101,  47,   0)  — shared with the ?-block border
      1 = orange fill  (196, 106,   0)
      2 = bright edge  (252, 180,  36)  — lit row just under each mortar line
    """
    from PIL import Image
    PALETTE = [
        (101,  47,   0),   # 0 dark mortar
        (196, 106,   0),   # 1 orange fill
        (252, 180,  36),   # 2 bright edge
    ]
    # 16×16 NES pixel map. Courses A (seams at cols 0,8) and B (seams at 4,12)
    # alternate to make the offset running-bond brickwork.
    A = [
        [0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0],   # horizontal mortar
        [0,2,2,2,2,2,2,2, 0,2,2,2,2,2,2,2],   # lit top edge + vertical seams
        [0,1,1,1,1,1,1,1, 0,1,1,1,1,1,1,1],
        [0,1,1,1,1,1,1,1, 0,1,1,1,1,1,1,1],
    ]
    B = [
        [0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0],   # horizontal mortar
        [2,2,2,2,0,2,2,2, 2,2,2,2,0,2,2,2],   # seams offset half a brick
        [1,1,1,1,0,1,1,1, 1,1,1,1,0,1,1,1],
        [1,1,1,1,0,1,1,1, 1,1,1,1,0,1,1,1],
    ]
    MAP = A + B + A + B
    size = 16 * scale
    img = Image.new('RGB', (size, size))
    px  = img.load()
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            color = PALETTE[c]
            for dy in range(scale):
                for dx in range(scale):
                    px[x * scale + dx, y * scale + dy] = color
    img.save(out_path)
    return out_path


def _add_textured_box(mesh_name, x0, y0, z0, x1, y1, z1, tex_path):
    """Box with a UV-mapped texture on all 6 faces (full [0,1]² per face).

    The front face (-Y, camera-side) gets vertex order chosen so the
    texture appears right-side-up when the camera is at Y≈-30 looking +Y.
    UV V=0 = top of the PIL image; V=1 = bottom — opposite of the Blender
    default but matching the WF/textile-rs VRAM convention where row 0 is
    the image top.
    """
    import bmesh

    mat = bpy.data.materials.new(name=f'{mesh_name}_mat')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf  = nodes['Principled BSDF']
    tex   = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(tex_path)
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')

    v = [
        bm.verts.new((x0, y0, z0)),  # 0
        bm.verts.new((x1, y0, z0)),  # 1
        bm.verts.new((x1, y1, z0)),  # 2
        bm.verts.new((x0, y1, z0)),  # 3
        bm.verts.new((x0, y0, z1)),  # 4
        bm.verts.new((x1, y0, z1)),  # 5
        bm.verts.new((x1, y1, z1)),  # 6
        bm.verts.new((x0, y1, z1)),  # 7
    ]

    # UV corners per face: (bottom-left, bottom-right, top-right, top-left)
    # viewed from outside, with V=0=image-top / V=1=image-bottom (WF VRAM convention).
    # Each face lists (vert, uv) pairs.
    face_defs = [
        # front -Y (camera-side): CCW from -Y; bl→br→tr→tl as seen by camera
        ([v[0], v[1], v[5], v[4]], [(0,1),(1,1),(1,0),(0,0)]),
        # back +Y: CCW from +Y
        ([v[2], v[3], v[7], v[6]], [(0,1),(1,1),(1,0),(0,0)]),
        # top +Z: CCW from +Z (camera looks along +Y, so "near" = -Y edge)
        ([v[4], v[5], v[6], v[7]], [(0,1),(1,1),(1,0),(0,0)]),
        # bottom -Z: CCW from -Z
        ([v[3], v[2], v[1], v[0]], [(0,1),(1,1),(1,0),(0,0)]),
        # left -X: CCW from -X
        ([v[3], v[0], v[4], v[7]], [(0,1),(1,1),(1,0),(0,0)]),
        # right +X: CCW from +X
        ([v[1], v[2], v[6], v[5]], [(0,1),(1,1),(1,0),(0,0)]),
    ]

    for verts, uvs in face_defs:
        f = bm.faces.new(verts)
        f.material_index = 0
        for loop, uv_coord in zip(f.loops, uvs):
            loop[uv].uv = uv_coord

    mesh = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)

    obj = bpy.data.objects.new(mesh_name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    return obj


def _make_grid_tile_tga(out_path, width=256, height=32, cells_x=64, cells_y=8,
                         line_px=1):
    """Pre-tiled grid texture (one image, no mesh subdivision needed):
    `cells_x` × `cells_y` grid lines baked in, light brown fill with darker
    brown lines along the top + left edge of each cell.

    Dims forced to {16,32,64,128,256,512,1024}^2 (textile-rs power-of-2
    constraint at bitmap.rs:507). The whole texture is mapped UV [0, 1]
    across the ground top face — works around the renderer's atlas-UV
    uint8 overflow that breaks GL_REPEAT for mesh UVs above ~5
    (docs/investigations/2026-05-18-texture-uv-uint8-overflow.md).

    Defaults: 256×32 texture, 64 grid cells in X, 8 in Y. Mapped across the
    73.5 m ground that gives one grid line every 73.5/64 ≈ 1.15 m — close
    enough to a 1-metre grid for visual position estimation."""
    from PIL import Image
    BG = (143, 97, 38)
    FG = (102, 66, 23)
    cell_w = width // cells_x
    cell_h = height // cells_y
    img = Image.new('RGB', (width, height), BG)
    px = img.load()
    for y in range(height):
        for x in range(width):
            if (x % cell_w) < line_px or (y % cell_h) < line_px:
                px[x, y] = FG
    img.save(out_path)
    return out_path


def build_textured_ground_mesh(name, x0, y0, z0, x1, y1, z1, tex_path):
    """Box ground with a UV-mapped grid texture on the top face only. Sides
    and bottom use a solid-brown material (material 0). Top face uses the
    grid material (material 1). UV is 1:1 with world XY so the tile repeats
    every 1 m."""
    import bmesh

    mat_brown = make_mat('smb_ground_side', (0.56, 0.38, 0.15))

    mat_grid = bpy.data.materials.new('smb_ground_grid')
    mat_grid.use_nodes = True
    bsdf = mat_grid.node_tree.nodes['Principled BSDF']
    tex_node = mat_grid.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = bpy.data.images.load(tex_path)
    mat_grid.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    v000 = bm.verts.new((x0, y0, z0))
    v100 = bm.verts.new((x1, y0, z0))
    v110 = bm.verts.new((x1, y1, z0))
    v010 = bm.verts.new((x0, y1, z0))
    v001 = bm.verts.new((x0, y0, z1))
    v101 = bm.verts.new((x1, y0, z1))
    v111 = bm.verts.new((x1, y1, z1))
    v011 = bm.verts.new((x0, y1, z1))

    # Top face (+Z, grid material) — CCW from above.
    top = bm.faces.new((v001, v101, v111, v011))
    top.material_index = 1
    # Other faces (solid brown).
    sides = [
        bm.faces.new((v000, v010, v110, v100)),  # -Z bottom (CCW from below)
        bm.faces.new((v000, v100, v101, v001)),  # -Y front
        bm.faces.new((v110, v010, v011, v111)),  # +Y back
        bm.faces.new((v010, v000, v001, v011)),  # -X left
        bm.faces.new((v100, v110, v111, v101)),  # +X right
    ]
    for f in sides:
        f.material_index = 0

    bm.faces.ensure_lookup_table()
    # UV in [0, 1] — pre-tiled grid baked into the texture itself. Keeps
    # UV in the safe range to dodge the atlas-UV uint8 overflow that
    # breaks GL_REPEAT for mesh UVs above ~5
    # (docs/investigations/2026-05-18-texture-uv-uint8-overflow.md).
    top_uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for loop, uv_xy in zip(top.loops, top_uvs):
        loop[uv].uv = uv_xy

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat_brown)
    mesh.materials.append(mat_grid)
    return mesh


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
def _build_mario():
    mat_red  = make_mat('mario_red',  (0.87, 0.14, 0.07))
    mat_blue = make_mat('mario_blue', (0.18, 0.34, 0.76))
    mat_skin = make_mat('mario_skin', (0.96, 0.73, 0.41))

    parts = []

    # Hat+head — red sphere upper half (origin at ground level = 0)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.38*T, segments=8, ring_count=5,
        location=(0, 0, 0.80*T))
    parts.append((bpy.context.object, mat_red))

    # Face — skin band
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=0.33*T, depth=0.14*T,
        location=(0, 0, 0.64*T))
    parts.append((bpy.context.object, mat_skin))

    # Body — blue overalls cylinder
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=0.33*T, depth=0.28*T,
        location=(0, 0, 0.34*T))
    parts.append((bpy.context.object, mat_blue))

    # Legs — two small red cylinders
    for yo in (-0.18*T, 0.18*T):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6, radius=0.12*T, depth=0.18*T,
            location=(0, yo, 0.09*T))
        parts.append((bpy.context.object, mat_red))

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0
            p.use_smooth = True

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    # Bake body.location into the mesh verts so mesh-local origin sits at the
    # feet (the lowest leg z = 0), not at the head-sphere's location (z=0.80T).
    # WF's actor.pos = feet convention requires mesh-local feet at z=0;
    # otherwise Physics-mobility settling leaves Mario buried in the ground.
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name      = 'player'
    body.data.name = 'player'
    return body


player = find_by_class('player')
if player:
    player.name = 'Player'   # CamShot Track Object references this name
    player.location = (MARIO_SPAWN_X, 0.0, MARIO_SPAWN_Z)
    # Physics mobility = engine handles gravity, ground collision, jump.
    # Mobility value 1 = "Physics" (Anchored|Physics|Path|Camera|Follow).
    player['wf_Mobility'] = 'Physics'  # restored for diagnosis
    player['wf_Mass']     = 1.0
    player['wf_Model Type'] = 'Mesh'
    player['wf_Visibility Mailbox'] = 1
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
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox "
        "dup 16384 & 256 / over 8192 & 64 / | | "
        "INDEXOF_INPUT write-mailbox\n"
        "INDEXOF_X_POS read-mailbox INDEXOF_SMB_PLAYER_X write-mailbox\n"
        "INDEXOF_Z_POS read-mailbox INDEXOF_SMB_PLAYER_Z write-mailbox\n"   # enemies use proximity
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
        # Flagpole height + time bonus — one-shot on the tick END_OF_LEVEL fires.
        # Height tiers: Z≥9→5000, ≥6→2000, ≥4.5→800, ≥3→400, ≥1.5→200, else→100.
        # Time bonus: HUD_TIMER remaining × 50.
        # EOL_LATCH prevents re-firing if the level lingers a tick before unloading.
        "INDEXOF_END_OF_LEVEL read-mailbox 0<> if\n"
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
        "  then\n"
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

# Flag — flat plane near top, offset left of pole
bpy.ops.mesh.primitive_plane_add(size=1.0, location=(FLAGPOLE_X - T, 0, POLE_HEIGHT - T))
flag_obj = bpy.context.object
flag_obj.name      = 'flagpole_flag'
flag_obj.data.name = 'flagpole_flag'
flag_obj.scale = (T, 0.01, 0.65 * T)
bpy.ops.object.transform_apply(scale=True)
flag_obj.data.materials.clear()
flag_obj.data.materials.append(mat_flag)
attach_schema(flag_obj, 'statplat')
flag_obj['wf_Visibility Mailbox'] = 1
flag_obj['wf_Model Type'] = 'Mesh'

# ── 10b. Flagpole end-of-level trigger ────────────────────────────────────────
# Composition, NOT a class: an invisible ActBox sensor volume over the flagpole.
# On Player overlap it writes END_OF_LEVEL=1 → the level unloads. No script, no
# coordinate baked into a script (the box's placement IS the trigger region).
# See docs/plans/2026-05-25-smb-flagpole-end-of-level.md and the composition
# pattern in docs/level-building.md.
END_OF_LEVEL = 1905   # INDEXOF_END_OF_LEVEL (wfsource/source/mailbox/mailbox.inc:31)
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
flagtrig['wf_MailBox']            = END_OF_LEVEL   # write-to-mailbox on activation
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

_box_faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]


def _room_bounds_mesh(name, b):
    """Build a box-bounds mesh from a (x0,y0,z0,x1,y1,z1) rel-bbox tuple."""
    x0,y0,z0,x1,y1,z1 = b
    verts = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
             (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    m = bpy.data.meshes.new(name)
    m.from_pydata(verts, [], _box_faces)
    m.update()
    return m


room = find_by_class('room')
if room:
    room.name = 'room_surface'
    room.location = ROOM_CENTRE
    room['wf_original_bbox'] = ROOM_BBOX_REL
    old = room.data
    room.data = _room_bounds_mesh('RoomBounds', ROOM_BBOX_REL)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

    # Bare W1-2 is a single room. Clear the snowgoons self-adjacency ("room_6")
    # that room.copy()'s source carried, so the surface room has no stale neighbour.
    # (The W1-1 underground coin room + its mutual-adjacency camera trick are dropped
    # here — see the faithful-W1-2 follow-up in the plan.)
    room['wf_Adjacent Room 1']      = ''
    room['wf_Adjacent Room 2']      = ''

# ── 13. Export ────────────────────────────────────────────────────────────────
print(f"[smb_w1_2] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print("[smb] Objects in scene:", [o.name for o in bpy.data.objects])
print(f"[smb] Done — {OUT_LEV}")

