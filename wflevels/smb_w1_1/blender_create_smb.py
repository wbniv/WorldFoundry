"""
blender_create_smb.py — create smb_w1_1 validation level.

Super Mario Bros. W1-1 first-pass validation scene (brief §Verification steps 1–10):
  - Flat ground platform (brown)
  - Three ? blocks at tile-row 4 height (gold)
  - Mario placeholder (red/blue figure, Physics mobility)
  - Goomba placeholder (brown mushroom, static)
  - Koopa Troopa placeholder (green shell, static)
  - Flagpole at level end (grey pole + green flag)
  - Side-scrolling camera (Y=-20, looking in +Y at X-Z gameplay plane)

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

SCENE_MID_X = (GROUND_X0 + GROUND_X1) / 2

# Camera: fixed side-view, Y=-20, looking toward +Y at Mario's spawn position.
# SCENE_MID_X (33.75) is the level midpoint, but the player starts at MARIO_SPAWN_X
# (4.5). Centering on MARIO_SPAWN_X keeps Mario in frame at game start.
CAM_Y = -20.0
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
                  'tool', 'tool01', 'ground01', 'hp'}


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


# ── 5. Ground platform ────────────────────────────────────────────────────────
mat_ground = make_mat('smb_ground', (0.56, 0.38, 0.15))  # NES brown/tan
add_statplat('ground',
             GROUND_X0, -GROUND_Y, GROUND_TOP_Z - GROUND_THICK,
             GROUND_X1,  GROUND_Y, GROUND_TOP_Z,
             mat_ground)

# ── 6. ? Blocks ───────────────────────────────────────────────────────────────
mat_qblock = make_mat('smb_qblock', (0.94, 0.72, 0.02))  # NES gold
BSIZE = T / 2  # half-side of a 1-tile block
for i, bx in enumerate(QBLOCK_XS):
    add_statplat(f'qblock_{i:02d}',
                 bx - BSIZE, -BSIZE, BLOCK_Z - BSIZE,
                 bx + BSIZE,  BSIZE, BLOCK_Z + BSIZE,
                 mat_qblock)

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
    player.location = (MARIO_SPAWN_X, 0.0, MARIO_SPAWN_Z)
    # Physics mobility = engine handles gravity, ground collision, jump.
    # Mobility value 1 = "Physics" (Anchored|Physics|Path|Camera|Follow).
    player['wf_Mobility'] = 'Physics'  # restored for diagnosis
    player['wf_Mass']     = 1.0
    player['wf_Model Type'] = 'Mesh'
    player['wf_Visibility Mailbox'] = 1
    # Physics movement parameters — tuned for SMB feel.
    # Jump apex = (JumpAccel × 0.2)² / (2 × FallAccel); 70 × 0.2 = 14 m/s → ~8.2 m
    # apex, enough to clear a ? block top at z=7.5 m. MaxGroundSpeed 12 m/s ≈ 8
    # tiles/sec at T=1.5 m. See docs/plans/2026-05-17-smb-mario-speed-jump-tuning.md.
    player['wf_Running Acceleration']  = 16.0
    player['wf_Running Deceleration']  = 0.85
    player['wf_Max Ground Speed']      = 12.0
    player['wf_Jumping Acceleration']  = 70.0
    player['wf_Falling Acceleration']  = 12.0
    player['wf_Air Acceleration']      = 16.0
    player['wf_Max Air Speed']         = 12.0
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
        # Broadcast own X to INDEXOF_SMB_PLAYER_X for the SMB scroll Director
        # (which runs after the main loop) to consume this tick.
        "INDEXOF_X_POS read-mailbox INDEXOF_SMB_PLAYER_X write-mailbox\n"
    )

    mario_mesh = _build_mario()
    old = player.data
    player.data = mario_mesh.data
    bpy.data.objects.remove(mario_mesh, do_unlink=True)
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

# ── 8. Goomba placeholder (static visual) ────────────────────────────────────
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
goomba_obj['wf_Mobility']           = 'Anchored'
goomba_obj['wf_Mass']               = 1.0
goomba_obj['wf_Model Type']         = 'Mesh'
goomba_obj['wf_Visibility Mailbox'] = 1
goomba_obj['wf_Script']             = "\\ smb goomba placeholder\n"

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
koopa_obj['wf_Mobility']           = 'Anchored'
koopa_obj['wf_Mass']               = 1.0
koopa_obj['wf_Model Type']         = 'Mesh'
koopa_obj['wf_Visibility Mailbox'] = 1
koopa_obj['wf_Script']             = "\\ smb koopa placeholder\n"

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
    camshot['wf_Track Object'] = 'Target02'
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

# ── 12. Room bbox ─────────────────────────────────────────────────────────────
# Absolute extremes of all actor centres:
#   X: GROUND_X0 ≈ -3   ..  FLAGPOLE_X+7.5 ≈ +70.5
#   Y: camera at Y=-20, light at Y≈-12       → [-22, +5]
#   Z: ground bottom -T ≈ -1.5, pole top 15  → [-3, +18]
# Room placed at (SCENE_MID_X, 0, 5); bbox is relative to that centre.
ROOM_CENTRE = (SCENE_MID_X, 0.0, 5.0)
RX0, RX1 = -100.0,  100.0
RY0, RY1 =  -30.0,   10.0
RZ0, RZ1 =  -15.0,   20.0
ROOM_BBOX_REL = (RX0, RY0, RZ0, RX1, RY1, RZ1)

room = find_by_class('room')
if room:
    room.location = ROOM_CENTRE
    room['wf_original_bbox'] = ROOM_BBOX_REL
    bvs = [
        (RX0,RY0,RZ0),(RX1,RY0,RZ0),(RX1,RY1,RZ0),(RX0,RY1,RZ0),
        (RX0,RY0,RZ1),(RX1,RY0,RZ1),(RX1,RY1,RZ1),(RX0,RY1,RZ1),
    ]
    bfs = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    nm = bpy.data.meshes.new('RoomBounds')
    nm.from_pydata(bvs, [], bfs)
    nm.update()
    old = room.data
    room.data = nm
    if old and old.users == 0:
        bpy.data.meshes.remove(old)

# ── 13. Export ────────────────────────────────────────────────────────────────
print(f"[smb] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print("[smb] Objects in scene:", [o.name for o in bpy.data.objects])
print(f"[smb] Done — {OUT_LEV}")
