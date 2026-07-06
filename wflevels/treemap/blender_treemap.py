"""
blender_treemap.py — KDirStat/QDirStat-style flat squarified disk-usage treemap.

Third view in the filesystem-visualization family (cf. wflevels/filesys/ node-link
and wflevels/filelight/ sunburst). The plane is tiled with rectangles, area ∝
recursive size, nested by directory, coloured by file type — read from above like
the 2D tool, walkable.

Architecture (the §6 split):
  • C (engine, scripting_zforth.cc) runs the squarified-treemap layout (Bruls,
    pure arithmetic — no trig) and classifies file extensions into type ids,
    EMITTING a flat table of axis-aligned cells (tm-scan + tm-* accessors).
  • This Director .fth RENDERS the table — spawns a corner-pivot unit box per
    cell, scales it (w,h,slab) with set-scale3, and colours it by type>rgb. The
    palette + slab height are hot-reloadable Director policy.

Cells are axis-aligned boxes, so ONE unit-box template + non-uniform scale is all
the geometry — no bespoke meshes, no trig. Static view: no navigation, no fly-down.

Run headlessly:
    blender --background --python blender_treemap.py
Then: task build-level -- treemap ; task run-treemap

Plan: docs/plans/2026-06-13-kdirstat-treemap-view.md
"""

import bpy
import addon_utils
import math
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
OAD_DIR    = os.path.join(REPO, 'wflevels', 'oad')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'treemap.lev')

def oad(name):
    return os.path.join(OAD_DIR, f'{name}.oad')

# ── Layout ────────────────────────────────────────────────────────────────────
# Treemap root rect ≈ X/Y ∈ [-34,34] (matches C TM_X0/TM_Y0/TM_X1/TM_Y1).
MAX_DEPTH = 6
MAX_NODES = 1900         # spawn-budget cap; pool = 2000 (raised from 480/500)

PLAYER_SPAWN = (0.0, 0.0, 1.0)

# Steep top-down camera so it reads like the 2D tool. STATIC (no fly-down).
CAM_POSE    = (0.0, -18.0, 72.0)
TARGET1_POS = (0.0,   0.0,  0.0)
TARGET2_POS = (0.0,   5.0,  0.0)

ROOM_CENTER     = (0.0, 0.0, 25.0)
ROOM_LOCAL_BBOX = (-42.0, -65.0, -28.0, 42.0, 42.0, 52.0)   # world X[-42,42] Y[-65,42] Z[-3,77]

FLOOR_X0, FLOOR_X1 = -37.0, 37.0
FLOOR_Y0, FLOOR_Y1 = -37.0, 37.0
FLOOR_Z0, FLOOR_Z1 =  -0.5,  0.0

# Object export order → runtime .lvl index = Blender scene index + 1.
#   9→10 Player, 5→6 CamShot01, 11→12 BoxTemplate
BOX_IDX         = 12
PLAYER_LVL_IDX  = 10
CAMSHOT_LVL_IDX = 6

COLOR_BG    = 0x0a0a14
COLOR_FLOOR = (0.04, 0.04, 0.08, 1.0)
COLOR_BOX   = (0.55, 0.55, 0.60, 1.0)   # overridden per-cell at runtime by type>rgb

# ── Director Forth script — the RENDER POLICY (hot-reloadable) ─────────────────
# C emits the flat cell table (tm-scan + tm-*). This script decides the LOOK:
# the file-type colour palette and the slab height. No navigate, no fly-down.
DIRECTOR_SCRIPT = (
    r'\\ wf' '\n'
    f': BOX-T {BOX_IDX} ;\n'
    f': MAXDEPTH {MAX_DEPTH} ;\n'
    f': MAXNODES {MAX_NODES} ;\n'
    ': SLAB 0.5 ;\n'

    # type-id → packed 0xRRGGBB (KDirStat-style palette — the recognizable LOOK)
    ': type>rgb ( type -- 0xRRGGBB )\n'
    '   dup 1 = if drop 0x4080ff else\n'   # source  = blue
    '   dup 2 = if drop 0x40c060 else\n'   # image   = green
    '   dup 3 = if drop 0xb050d0 else\n'   # video   = purple
    '   dup 4 = if drop 0x40c0c0 else\n'   # audio   = cyan
    '   dup 5 = if drop 0xd04040 else\n'   # archive = red
    '   dup 6 = if drop 0xe0c040 else\n'   # docs    = yellow
    '   dup 7 = if drop 0xe08030 else\n'   # binary  = orange
    '       drop 0x707078\n'               # dir/other = grey
    '   fi fi fi fi fi fi fi ;\n'

    # spawn + configure one cell (footprint/position come from the C table)
    ': place-cell ( i -- )\n'
    '   dup tm-x over tm-y 0 BOX-T spawn-template\n'
    '   >r\n'
    '   r@ over tm-w 2 pick tm-h SLAB set-scale3\n'
    '   r@ over tm-type type>rgb set-color\n'
    '   r> drop drop ;\n'

    ': render-treemap\n'
    '   tm-scan dup 0 = if drop else 0 do i place-cell loop fi ;\n'

    # --- per-frame body (no `;` past here) ---
    '10 read-mailbox 0 = if\n'
    '  1 10 write-mailbox\n'
    '  MAXDEPTH MAXNODES tm-config\n'
    '  render-treemap\n'
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
    """Low-poly EVA-suit astronaut (verbatim from filesys/blender_filesys.py)."""
    mat_white = make_mat('astro_white',    (0.92, 0.92, 0.92, 1.0))
    mat_off   = make_mat('astro_offwhite', (0.85, 0.85, 0.82, 1.0))
    mat_dark  = make_mat('astro_dark',     (0.18, 0.18, 0.20, 1.0))
    mat_visor = make_mat('astro_visor',    (0.76, 0.53, 0.25, 1.0))
    parts = []
    SEG = 8; RING = 5

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

    for yo in (-0.12, 0.12):
        add_cube(0.18, 0.15, 0.10, (0.0, yo, 0.05), mat_white)
        add_cyl(0.09, 0.42, (0.0, yo, 0.31), mat_white)
        add_cyl(0.10, 0.42, (0.0, yo, 0.73), mat_white)
    add_cyl(0.20, 0.10, (0.0, 0.0, 0.95), mat_white)
    add_cyl(0.22, 0.45, (0.0, 0.0, 1.225), mat_white)
    add_cube(0.20, 0.08, 0.12, (+0.20, 0.0, 1.30), mat_dark)
    add_cube(0.30, 0.18, 0.50, (-0.27, 0.0, 1.20), mat_off)
    for yo in (-0.27, 0.27):
        add_sph(0.11, (0.0, yo, 1.42), mat_white)
        add_cyl(0.08, 0.30, (0.0, yo, 1.27), mat_white)
        add_cyl(0.08, 0.28, (0.0, yo, 0.98), mat_white)
        add_sph(0.09, (0.0, yo, 0.84), mat_white)
    add_cyl(0.06, 0.06, (0.0, 0.0, 1.475), mat_dark)
    add_sph(0.14, (0.0, 0.0, 1.66), mat_white)
    add_sph(0.13, (+0.05, 0.0, 1.66), mat_visor)

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
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    mesh = body.data
    mesh.name = 'astronaut'
    bpy.data.objects.remove(body, do_unlink=True)
    mesh.use_fake_user = True
    return mesh


# ── Build scene ───────────────────────────────────────────────────────────────

clear_scene()
scene = bpy.context.scene

# 0 ── Room ────────────────────────────────────────────────────────────────────
make_box_mesh('Room01', ROOM_CENTER, ROOM_LOCAL_BBOX, 'room',
    props={'Adjacent Room 1': '', 'Adjacent Room 2': '', 'Room Loaded Mailbox': 0})

# 1 ── LevelObj ────────────────────────────────────────────────────────────────
make_empty('LevelObj', ROOM_CENTER, 'levelobj',
    props={
        'Number Of Mailboxes':        50,
        'Number Of Temporary Objects': 2000,
        'Mobility':   'Anchored',
        'Model Type': 'None',
    })

# 2 ── Matte ───────────────────────────────────────────────────────────────────
make_empty('Matte', ROOM_CENTER, 'matte',
    props={
        'Mobility':           'Anchored',
        'Matte Type':         'Color',
        'Background Color':   COLOR_BG,
        'Visibility Mailbox': 1,
        'Model Type':         'None',
    })

# 3 ── Light ───────────────────────────────────────────────────────────────────
light = make_empty('Light01', (0.0, 0.0, 45.0), 'light',
    props={
        'Mobility':   'Anchored',
        'lightType':  'Directional',
        'lightRed':   0.7, 'lightGreen': 0.7, 'lightBlue': 0.8,
        'Model Type': 'None',
    })
light.rotation_euler = (math.pi / 2, 0, 0)   # straight down (treemap read from above)

# 4 ── Camera ──────────────────────────────────────────────────────────────────
make_empty('Camera', CAM_POSE, 'camera',
    props={
        'Mobility':                'Camera',
        'Model Type':              'None',
        'FoggingColor':            0x000000,
        'FoggingStartDistance':    999.0,
        'FoggingCompleteDistance': 1000.0,
    })

# 5 ── CamShot (static steep top-down, tracks the player) ──────────────────────
make_empty('CamShot01', CAM_POSE, 'camshot',
    props={
        'Mobility':            'Anchored',
        'Target':              'Target02',
        'Follow':              'Target01',
        'Track Object':        'Player',
        'Rotation':            'Fixed',
        'Position X':          'Absolute',
        'Position Y':          'Absolute',
        'Position Z':          'Absolute',
        'FOV':                 75.0,
        'Climb Rate':          3.0,
        'Elasticity':          8.0,
        'Pan Time In Seconds': 0.2,
        'Hither':              0.1,
        'Yon':                 500.0,
        'Model Type':          'None',
        'Visibility Mailbox':  1,
    })

# 6 ── Target01 ────────────────────────────────────────────────────────────────
make_empty('Target01', TARGET1_POS, 'target', props={'Mobility': 'Anchored', 'Model Type': 'None'})
# 7 ── Target02 ────────────────────────────────────────────────────────────────
make_empty('Target02', TARGET2_POS, 'target', props={'Mobility': 'Anchored', 'Model Type': 'None'})

# 8 ── Director ────────────────────────────────────────────────────────────────
make_empty('Director', (0.0, 0.0, 1.0), 'director',
    props={
        'Mobility':                  'Anchored',
        'Number Of Local Mailboxes': 5,
        'Script':                    DIRECTOR_SCRIPT,
        'Script Controls Input':     'False',
        'Model Type':                'None',
    })

# 9 ── Player (walking EVA astronaut) ──────────────────────────────────────────
_astro_mesh = build_astronaut_mesh()
player = bpy.data.objects.new('Player', _astro_mesh)
player.location = PLAYER_SPAWN
bpy.context.scene.collection.objects.link(player)
player['wf_schema_path'] = oad('player')
for k, v in {
    'Mobility':              'Physics',
    'Moves Between Rooms':   'True',
    'Script Controls Input': 'True',
    'Turn Rate':             0.5,
    'Running Acceleration':  8.0,
    'Running Deceleration':  0.85,
    'Max Ground Speed':      5.0,
    'Jumping Acceleration':  15.0,
    'Falling Acceleration':  9.8,
    'Air Acceleration':      0.0,
    'Max Air Speed':         8.0,
    'Horiz Air Drag':        1.5,
    'Mass':                  80.0,
    'Model Type':            'Mesh',
    'Visibility Mailbox':    1,
}.items():
    player[f'wf_{k}'] = v
player.rotation_euler.z = math.pi / 2
player['wf_Script'] = (
    "\\ wf\n"
    "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n"
)
_astro_mesh.use_fake_user = False

# 10 ── Floor (StatPlat) ───────────────────────────────────────────────────────
mat_floor = make_mat('tm_floor', COLOR_FLOOR)
floor_obj = add_solid_box('Floor', FLOOR_X0, FLOOR_Y0, FLOOR_Z0,
                          FLOOR_X1, FLOOR_Y1, FLOOR_Z1, mat_floor)
floor_obj['wf_schema_path']        = oad('statplat')
floor_obj['wf_Mobility']           = 'Anchored'
floor_obj['wf_Model Type']         = 'Mesh'
floor_obj['wf_Visibility Mailbox'] = 1

# 11 ── BoxTemplate (corner-pivot unit box: [0,1]^3) ───────────────────────────
# Spawn at a cell's min-corner (x,y,0) + scale (w,h,slab) → the cell box. The
# column-scale grows from the origin corner, so this one mesh is every cell.
mat_box = make_mat('tm_box', COLOR_BOX)
box_tmpl = add_solid_box('BoxTemplate', 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, mat_box)
box_tmpl['wf_schema_path']        = oad('dir')
box_tmpl['wf_Template Object']    = 'True'
box_tmpl['wf_Mobility']           = 'Anchored'
box_tmpl['wf_Model Type']         = 'Mesh'
box_tmpl['wf_Visibility Mailbox'] = 1
box_tmpl.location                 = (0.0, -200.0, 0.0)   # parked OOB

# 12 ── ActBoxOR: bootstrap camera ─────────────────────────────────────────────
make_box_mesh('ActBoxOR', ROOM_CENTER, ROOM_LOCAL_BBOX, 'actboxor',
    props={
        'Mobility':     'Anchored',
        'Model Type':   'None',
        'MailBox':      1921,            # INDEXOF_CAMSHOT
        'Object':       'CamShot01',
        'Activated By': 'Player',
    })

# 13 ── AmbientLight ───────────────────────────────────────────────────────────
make_empty('AmbientLight', (0.0, 0.0, 45.0), 'light',
    props={
        'Mobility':   'Anchored',
        'lightType':  'Ambient',
        'lightRed':   0.45, 'lightGreen': 0.45, 'lightBlue': 0.50,
        'Model Type': 'None',
    })

# ── Export ────────────────────────────────────────────────────────────────────
print(f'[treemap] Exporting to {OUT_LEV}')
try:
    bpy.ops.wf.export_level(filepath=OUT_LEV)
except AttributeError:
    import importlib.util as _ilu
    _addon_dir = os.path.expanduser('~/.config/blender/4.0/scripts/addons/wf_blender')
    _spec = _ilu.spec_from_file_location('wf_blender.export_level',
        os.path.join(_addon_dir, 'export_level.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ok, msg = _mod.export_scene_to_lev(bpy.context, OUT_LEV)
    if not ok:
        raise RuntimeError(f'export_scene_to_lev failed: {msg}')
    print(f'Info: Exported to {OUT_LEV}')

print(f'[treemap] Done. Objects in scene (export order):')
for i, o in enumerate(o for o in bpy.context.scene.objects if o.get('wf_schema_path')):
    print(f'  [{i:2d}] {o.name} @ {tuple(round(x,2) for x in o.location)}')
