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

# W1-1 landmark X positions (tile counts × T)
MARIO_SPAWN_X = 3  * T
QBLOCK_XS     = [8*T, 14*T, 17*T]        # lone ? block, then cluster pair
GOOMBA_X      = 22 * T
KOOPA_X       = 28 * T
FLAGPOLE_X    = 42 * T

GROUND_X0 = -2 * T
GROUND_X1 = FLAGPOLE_X + 5*T
GROUND_Y  = T                             # half-depth of ground slab in Y

# Pits (bottomless gaps in the ground). The ground slab is split into solid
# segments around these X-ranges; an invisible pit-death ActBox sits below each.
# Real W1-1 has two signature gaps — one mid-level, one on the final approach by
# the double-pyramid staircase. This level is geometrically compressed (~49 tiles
# vs the real ~212), so these reproduce the two-pit *structure* proportionally,
# clear of the ? cluster (tiles 8/14/17), Goomba (22), Koopa (28) and flag (42).
# Each is a 2-tile (3 m) gap — jumpable under the current jump tuning.
# See docs/plans/2026-05-25-smb-pit-death-and-level-timer.md.
PITS = [(28.5, 31.5),   # tiles 19-20: mid-level gap, between the ? cluster and the first Goomba
        (51.0, 54.0)]   # tiles 34-35: the signature late gap on the final approach to the flag

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
ENTRY_PIPE_X = 12 * T             # = 18, on ground_0 between qblock0 (x12) and qblock1 (x21)
CR_FLOOR_TOP = -48.0              # coin-room floor top
CR_X0, CR_X1 = 0.0, 18.0         # coin-room play span (12 tiles)
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
    #              X_MAX-HALF_FRUSTUM = 70.5-12.0 = 58.5.
    # Deadzone test uses (delta < 1.5) — true for both in-deadzone AND
    # Mario-behind-camera cases (the one-way ratchet falls out for free).
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
        "dup 58.5 > if drop 58.5 then "
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
mat_coin   = make_mat('smb_coin',   (1.0,  0.84, 0.0))   # gold #FFD600
BSIZE = T / 2  # half-side of a 1-tile block
qblock_tex = _make_qblock_tga(os.path.join(SCRIPT_DIR, 'qblock_tex.tga'))
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
QBLOCK_SCRIPT = (
    "\\ wf\n"
    f"INDEXOF_SMB_QBLOCK_USED read-mailbox 0<> if\n"
    f"  0x{QBLOCK_TAN:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
    "else\n"
    "  INDEXOF_SMB_QBLOCK_ACTIVATE read-mailbox 0<> if\n"
    "    0 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "  then\n"
    "  INDEXOF_SMB_QBLOCK_DIE read-mailbox dup not if\n"
    "    drop\n"
    "    INDEXOF_COLLIDER_IDX read-mailbox 0<> if\n"
    "      INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 > if\n"
    "        INDEXOF_TIME read-mailbox 4.0 +\n"
    "        INDEXOF_SMB_QBLOCK_DIE write-mailbox\n"
    "        1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "      then\n"
    "    then\n"
    "  else\n"
    "    INDEXOF_TIME read-mailbox > if\n"
    "      INDEXOF_COLLIDER_IDX read-mailbox 0<> if\n"
    "        INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 > if\n"
    "          1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "        then\n"
    "      then\n"
    "    else\n"
    f"      0x{QBLOCK_TAN:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
    "      1 INDEXOF_SMB_QBLOCK_USED write-mailbox\n"
    "    then\n"
    "  then\n"
    "then\n"
)

COIN_SCRIPT = "\\ wf\nINDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"

# Coin template — Gold collectible class (pickup-driven despawn via
# Gold::Collision + SetPendingRemove; spins via ROTATION_C each frame).
import bmesh as _bmesh
def _make_coin_template():
    bm = _bmesh.new()
    _bmesh.ops.create_cube(bm, size=1.0)
    _bmesh.ops.scale(bm, vec=(COIN_X*2, COIN_T*2, COIN_Z*2), verts=bm.verts)
    mesh = bpy.data.meshes.new('coin_template')
    bm.to_mesh(mesh); bm.free()
    mesh.materials.append(mat_coin)
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new('coin_template', mesh)
    obj.location = (-50.0, 0.0, 0.0)
    scene.collection.objects.link(obj)
    attach_schema(obj, 'gold')
    obj['wf_Template Object']      = 'True'
    obj['wf_Moves Between Rooms']  = 'True'
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 0.001
    obj['wf_Falling Acceleration'] = 12.0
    obj['wf_Max Air Speed']        = 50.0
    # NOTE: under Jolt, Surface Friction / Air Drag are DEAD (the old wheel-friction
    # path never runs). The live ground-friction knob for a doom-stick/MarbleHandler
    # actor is Running Deceleration (movebloc default 0.90 ≈ full stop per frame).
    # Set it to 0 so the coin keeps its generator-imparted +X drift on the ground
    # instead of freezing the instant it lands.
    obj['wf_Surface Friction']     = 0.0
    obj['wf_Horiz Air Drag']       = 0.0
    obj['wf_Vert Air Drag']        = 0.0
    obj['wf_Running Deceleration'] = 0.0    # frictionless ground → coin slides right
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = 'coin_template.iff'
    obj['wf_Script']               = COIN_SCRIPT
    return obj

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
    player['wf_Running Deceleration']  = 0.85
    player['wf_Max Ground Speed']      = 32.0
    player['wf_Jumping Acceleration']  = 60.0
    player['wf_Falling Acceleration']  = 12.0
    player['wf_Air Acceleration']      = 0.0
    player['wf_Max Air Speed']         = 32.0
    # No air control (Air Acceleration=0) means takeoff momentum sails for the
    # whole jump unless damped. HorizAirDrag=3 ≈ 5% per frame at 60Hz, so a
    # 32 m/s launch decays to ~12 m/s by the time gravity brings Mario back.
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
        "INDEXOF_GOLD read-mailbox INDEXOF_HUD_SCORE write-mailbox\n"
        # seed lives once (guarded so game-over at LIVES=0 never re-seeds)
        "INDEXOF_SMB_LIVES_INIT read-mailbox not if "
        "3 INDEXOF_LIVES write-mailbox 1 INDEXOF_SMB_LIVES_INIT write-mailbox then\n"
        # bounce up when we stomped an enemy this frame
        "INDEXOF_SMB_STOMP read-mailbox 0<> if "
        "8.0 INDEXOF_ZSPEED write-mailbox 0 INDEXOF_SMB_STOMP write-mailbox then\n"
        # enemy side-hit -> lose a life + respawn at spawn (unless still invulnerable)
        "INDEXOF_SMB_PLAYER_HURT read-mailbox 0<> if\n"
        "  INDEXOF_TIME read-mailbox INDEXOF_SMB_INVULN_UNTIL read-mailbox > if\n"
        "    INDEXOF_LIVES read-mailbox 1 - INDEXOF_LIVES write-mailbox\n"
        f"    {MARIO_SPAWN_X} INDEXOF_X_POS write-mailbox\n"
        "    0 INDEXOF_Y_POS write-mailbox\n"
        f"    {MARIO_SPAWN_Z} INDEXOF_Z_POS write-mailbox\n"
        "    0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox "
        "0 INDEXOF_ZSPEED write-mailbox\n"
        # restart the countdown for the new life (any death resets the timer, SMB-faithful)
        "    INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox\n"
        "    INDEXOF_TIME read-mailbox 2.0 + INDEXOF_SMB_INVULN_UNTIL write-mailbox\n"
        "    INDEXOF_LIVES read-mailbox 1 < if 1 INDEXOF_END_OF_LEVEL write-mailbox then\n"
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
ENEMY_SCRIPT = (
    "\\ wf\n"
    f"{-ENEMY_WALK_SPEED} INDEXOF_XSPEED write-mailbox\n"   # walk left (toward Mario)
    # Proximity to the player. Player<->enemy contacts (both CharacterVirtual) do NOT
    # fire the Jolt collision dispatch (neither is in gBodies — same reason Gold uses
    # proximity), so compare the broadcast player X/Z to our own position.
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox -\n"    # dx = playerX - myX
    "dup * 1.0 <\n"                                                       # dx^2 < 1  (close horizontally)
    "if\n"
    "  INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox -\n"  # dz = playerZ - myZ
    "  dup 0.7 >\n"                                                       # player clearly ABOVE us?
    "  if\n"
    "    drop\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"                # stomped -> die
    "    1 INDEXOF_SMB_STOMP write-mailbox\n"            # tell the player to bounce
    "  else\n"
    "    -1.5 >\n"                                       # roughly level (not far below) = side hit
    "    if 1 INDEXOF_SMB_PLAYER_HURT write-mailbox then\n"
    "  then\n"
    "then\n"
)


def _apply_enemy_movement(obj):
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 1.0
    obj['wf_Turn Rate']            = 0.0     # → MarbleHandler (no input, carries velocity)
    obj['wf_Running Deceleration'] = 0.0     # frictionless: keeps walk velocity
    obj['wf_Max Ground Speed']     = 8.0
    obj['wf_Max Air Speed']        = 50.0    # don't let the speed cap zero gravity (marble bug)
    obj['wf_Falling Acceleration'] = 12.0
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Script']               = ENEMY_SCRIPT


def _build_goomba():
    mat_br = make_mat('goomba_brown', (0.55, 0.27, 0.06))
    mat_tn = make_mat('goomba_tan',   (0.83, 0.65, 0.34))

    parts = []

    # Body — flattened brown sphere
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.48*T, segments=10, ring_count=6,
        location=(0, 0, 0.44*T))
    bpy.context.object.scale.z = 0.72
    bpy.ops.object.transform_apply(scale=True)
    parts.append((bpy.context.object, mat_br))

    # Face band — tan strip for eyes
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=10, radius=0.34*T, depth=0.09*T,
        location=(0, 0, 0.54*T))
    parts.append((bpy.context.object, mat_tn))

    # Feet — two brown spheres
    for yo in (-0.19*T, 0.19*T):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.14*T, segments=6, ring_count=4,
            location=(0, yo, 0.10*T))
        parts.append((bpy.context.object, mat_br))

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
    body.name      = 'goomba_00'
    body.data.name = 'goomba_00'
    return body


goomba_mesh = _build_goomba()
goomba_obj  = bpy.data.objects.new('goomba_00', goomba_mesh.data)
scene.collection.objects.link(goomba_obj)
bpy.data.objects.remove(goomba_mesh, do_unlink=True)
goomba_obj.location = (GOOMBA_X, 0.0, MARIO_Z)
attach_schema(goomba_obj, 'enemy')
_apply_enemy_movement(goomba_obj)

# ── 9. Koopa Troopa placeholder (static visual) ───────────────────────────────
mat_kgreen = make_mat('koopa_green', (0.14, 0.56, 0.20))
mat_kskin  = make_mat('koopa_skin',  (0.90, 0.76, 0.34))

parts = []

# Shell — green flattened sphere
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.48*T, segments=10, ring_count=6,
    location=(0, 0, 0.52*T))
bpy.context.object.scale.z = 0.80
bpy.ops.object.transform_apply(scale=True)
bpy.context.object.data.materials.clear()
bpy.context.object.data.materials.append(mat_kgreen)
for p in bpy.context.object.data.polygons:
    p.material_index = 0
    p.use_smooth = True
parts.append(bpy.context.object)

# Head — small skin sphere
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.22*T, segments=8, ring_count=5,
    location=(0.30*T, 0, 0.90*T))
bpy.context.object.data.materials.clear()
bpy.context.object.data.materials.append(mat_kskin)
for p in bpy.context.object.data.polygons:
    p.material_index = 0
    p.use_smooth = True
parts.append(bpy.context.object)

bpy.ops.object.select_all(action='DESELECT')
for obj in parts:
    obj.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.join()
koopa_mesh = bpy.context.object
koopa_mesh.name      = 'koopa_00'
koopa_mesh.data.name = 'koopa_00'

koopa_obj = bpy.data.objects.new('koopa_00', koopa_mesh.data)
scene.collection.objects.link(koopa_obj)
bpy.data.objects.remove(koopa_mesh, do_unlink=True)
koopa_obj.location = (KOOPA_X, 0.0, MARIO_Z)
attach_schema(koopa_obj, 'enemy')
_apply_enemy_movement(koopa_obj)

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

actboxor = find_by_class('actboxor')
if actboxor:
    actboxor.location = (SCENE_MID_X, 0.0, MARIO_Z + 2)
    actboxor['wf_Object'] = 'cs_side'
    actboxor['wf_Activated By Actor'] = 'Player'

# ── 12. Room bbox ─────────────────────────────────────────────────────────────
# Absolute extremes of all actor centres:
#   X: GROUND_X0 ≈ -3   ..  FLAGPOLE_X+7.5 ≈ +70.5
#   Y: camera at Y=-30, light at Y≈-12       → [-32, +5]
#   Z: ground bottom -T ≈ -1.5, pole top 15  → [-3, +18]
# Room placed at (SCENE_MID_X, 0, 5); bbox is relative to that centre.
ROOM_CENTRE = (SCENE_MID_X, 0.0, 5.0)
RX0, RX1 = -100.0,  100.0
RY0, RY1 =  -35.0,   10.0
RZ0, RZ1 =  -15.0,   20.0
ROOM_BBOX_REL = (RX0, RY0, RZ0, RX1, RY1, RZ1)

# Coin-room bbox in WORLD space, DISJOINT from the surface room in Z (gap -36..-10).
# (centre + rel are derived so the bounds mesh sits in local space like the surface.)
CR_BBOX_WORLD = (CR_X0 - 4.0, -40.0, CR_FLOOR_TOP - 10.0,
                 CR_X1 + 4.0,  12.0, CR_FLOOR_TOP + 12.0)   # x[-4,22] y[-40,12] z[-58,-36]
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
PIPE_GREEN   = make_mat('smb_pipe_green', (0.0, 0.62, 0.0))
CR_FLOOR_MAT = make_mat('smb_cr_floor',   (0.45, 0.22, 0.05))   # dark brick-brown

# Surface entry pipe: 2 tiles wide x 2 tall, solid (Mario jumps onto the mouth).
add_statplat('entry_pipe', ENTRY_PIPE_X - T, -GROUND_Y, GROUND_TOP_Z,
             ENTRY_PIPE_X + T,  GROUND_Y, GROUND_TOP_Z + 2*T, PIPE_GREEN)

# Entry sense: a thin ActBox lid over the pipe mouth. Only Mario standing ON TOP
# (feet Z=3) overlaps the Z band [2.8,4.0]; walking past on the ground (Z 0) does
# not. Sets SMB_AT_PIPE=1 on overlap and clears it to 0 on exit.
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(ENTRY_PIPE_X, 0.0, GROUND_TOP_Z + 2*T + 0.4))
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
add_statplat('cr_floor',  CR_X0 - 1, -GROUND_Y, CR_FLOOR_TOP - T,
             CR_X1 + 1,    GROUND_Y, CR_FLOOR_TOP,        CR_FLOOR_MAT)
add_statplat('cr_wall_l', CR_X0 - 1, -GROUND_Y, CR_FLOOR_TOP,
             CR_X0,        GROUND_Y, CR_FLOOR_TOP + 6*T,  CR_FLOOR_MAT)
add_statplat('cr_wall_r', CR_X1,     -GROUND_Y, CR_FLOOR_TOP,
             CR_X1 + 1,    GROUND_Y, CR_FLOOR_TOP + 6*T,  CR_FLOOR_MAT)


def _make_target(name, loc):
    t = bpy.data.objects.new(name, None)
    scene.collection.objects.link(t)
    attach_schema(t, 'target')
    t.location = loc
    t['wf_Model Type'] = 'None'
    return t

# Entry landing (where Down warps Mario) + cs_coin look-at point.
_make_target('Target_cr_entry',  (CR_ENTRY_X, 0.0, CR_ENTRY_Z))
_make_target('Target_cr_lookat', (9.0, 0.0, CR_FLOOR_TOP + T))

# cs_coin: static shot framing the whole coin room (no scroll script → unlike
# cs_side it does not read SMB_TARGET_CAM_X). Direction = lookat - campos.
cs_coin = bpy.data.objects.new('cs_coin', None)
scene.collection.objects.link(cs_coin)
attach_schema(cs_coin, 'camshot')
cs_coin.location = (9.0, -35.0, CR_FLOOR_TOP + 4.5)    # (9,-35,-43.5), inside coin-room bbox
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
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(9.0, 0.0, CR_FLOOR_TOP + 4.5))
ab = bpy.context.object
ab.name = 'abor_coin'; ab.data.name = 'abor_coin'
ab.scale = ((CR_X1 - CR_X0)/2 + 1.0, GROUND_Y + 2.0, 6.0)   # X[-1,19] Y[-3.5,3.5] Z[-49.5,-37.5]
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
    coin_light.location = (9.0, -22.0, CR_FLOOR_TOP + 6.0)   # (9,-22,-42), inside coin-room bbox
    coin_light.rotation_euler = (math.pi / 3, 0, 0)

# ── 13. Export ────────────────────────────────────────────────────────────────
print(f"[smb] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print("[smb] Objects in scene:", [o.name for o in bpy.data.objects])
print(f"[smb] Done — {OUT_LEV}")
