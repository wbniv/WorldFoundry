"""
blender_filelight.py — 3D Filelight: a walkable radial disk-usage sunburst.

The other canonical disk-usage encoding (cf. the FSN node-link browser in
wflevels/filesys/). A flat radial sunburst, centred on the player: a centre disk
for the cwd, concentric rings outward for depth, each segment's angular span ∝
its recursive byte size, extruded UPWARD by size into a walkable relief. Walk
onto a wedge + button B to re-root (zoom in); button C ascends.

Architecture (the §6 split):
  • C (engine, scripting_zforth.cc) walks the tree, computes recursive sizes, and
    subdivides the [0,1) revolution circle ∝ size — emitting a FLAT NUMERIC TABLE
    of segments (fl-scan + seg-* accessors). No string crosses to Forth.
  • This Director .fth ITERATES the table and applies the render *policy* —
    size→height, per-branch hue, wedge tiling — by spawning baked annular-sector
    wedge templates at the origin, rotating them to their arc (revolutions, the
    engine-native Euler unit), Z-scaling by size, colouring by hue. All the look
    is in this script → hot-reloadable, no engine rebuild.

Run headlessly:
    blender --background --python blender_filelight.py
Then: task build-level -- filelight ; task run-filelight

Plan: docs/plans/2026-06-13-filesystem-viz-on-a-flat-table-forth-policy-core-f.md
"""

import bpy
import addon_utils
import math
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
OAD_DIR    = os.path.join(REPO, 'wflevels', 'oad')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'filelight.lev')

def oad(name):
    return os.path.join(OAD_DIR, f'{name}.oad')

# ── Sunburst geometry ─────────────────────────────────────────────────────────
RING_WIDTH = 9.0          # world units per ring band (MUST match C FL_RING_WIDTH)
WEDGE_DEG  = 6.0          # baked wedge angular width (MUST match Director WEDGE-STEP rev)
MAX_DEPTH  = 3            # centre disk + 3 rings; sunburst radius = (MAX_DEPTH+1)*w = 36
MAX_NODES  = 450          # spawn-budget cap (towers of wedges); pool = 500

PLAYER_SPAWN = (0.0, 0.0, 1.0)

# Camera: high overhead establishing pose, eased to an angled play pose by the C
# fl-flydown (writes camshot Y/Z mailboxes 3010/3011). X stays 0 (centred).
CAM_HIGH    = (0.0, -70.0, 96.0)     # matches fl_flydown HY/HZ start
TARGET1_POS = (0.0,   0.0,  0.0)     # the sunburst centre
TARGET2_POS = (0.0,   5.0,  0.0)

# Room bbox — contains the sunburst (±36), the player, and the high camera pose.
# make_box_mesh puts verts at LOCAL bbox coords, object at ROOM_CENTER:
#   world = center + local  →  X[-50,50] Y[-90,50] Z[-3,100].
ROOM_CENTER     = (0.0, 0.0, 28.0)
ROOM_LOCAL_BBOX = (-50.0, -90.0, -31.0, 50.0, 50.0, 72.0)

FLOOR_X0, FLOOR_X1 = -45.0, 45.0
FLOOR_Y0, FLOOR_Y1 = -45.0, 45.0
FLOOR_Z0, FLOOR_Z1 =  -0.5,  0.0

# Object export order → runtime .lvl index = Blender scene index + 1.
#   Blender  .lvl  Actor
#      0       1   Room01
#      1       2   LevelObj
#      2       3   Matte
#      3       4   Light01
#      4       5   Camera
#      5       6   CamShot01      ← CAMSHOT-IDX
#      6       7   Target01
#      7       8   Target02
#      8       9   Director
#      9      10   Player         ← PLAYER-IDX
#     10      11   Floor
#     11      12   Ring1Template  ← RING1
#     12      13   Ring2Template  ← RING2
#     13      14   Ring3Template  ← RING3
#     14      15   DiskTemplate   ← DISK
#     15      16   ActBoxOR
#     16      17   AmbientLight
RING1_IDX, RING2_IDX, RING3_IDX = 12, 13, 14
DISK_IDX        = 15
PLAYER_LVL_IDX  = 10
CAMSHOT_LVL_IDX = 6

# SGI cyberspace aesthetic for the backdrop; per-segment colour comes from the
# Director's hue policy via FACE_COLOR mailboxes, so the template base is neutral.
COLOR_BG    = 0x0a0a14
COLOR_FLOOR = (0.05, 0.05, 0.10, 1.0)
COLOR_RING  = (0.55, 0.55, 0.60, 1.0)   # overridden per-segment at runtime

# ── Director Forth script — the RENDER POLICY (hot-reloadable) ─────────────────
# C emits the flat segment table (fl-scan + seg-*). This script iterates it and
# decides the LOOK: depth→template, size→height, branch→hue, tiling resolution.
# Stack notes: zForth has no locals (we juggle via pick / >r..r@..r>), no
# while/repeat (tile loop uses begin..until), and `do` runs once at count==0
# (render-sunburst guards that). Angles are REVOLUTIONS (engine-native Euler).
DIRECTOR_SCRIPT = (
    r'\\ wf' '\n'
    f': RING1 {RING1_IDX} ;\n'
    f': RING2 {RING2_IDX} ;\n'
    f': RING3 {RING3_IDX} ;\n'
    f': DISK  {DISK_IDX} ;\n'
    f': MAXDEPTH {MAX_DEPTH} ;\n'
    f': MAXNODES {MAX_NODES} ;\n'
    f': PLAYER-IDX {PLAYER_LVL_IDX} ;\n'
    f': CAMSHOT-IDX {CAMSHOT_LVL_IDX} ;\n'
    ': WEDGE-STEP 0.0167 ;\n'                       # 6° in revolutions; == WEDGE_DEG

    # depth → ring template (policy: ring spacing lives in the baked templates)
    ': ring-tmpl ( depth -- tmpl )\n'
    '   dup 1 = if drop RING1 else\n'
    '   dup 2 = if drop RING2 else\n'
    '   dup 3 = if drop RING3 else\n'
    '       drop RING3\n'
    '   fi fi fi ;\n'

    # size(KB) → Z-scale height (policy: the height curve). Double-isqrt ≈ 4th
    # root — compresses the KB..GB range into a gentle 1..10 relief so the
    # RADIAL pattern dominates, not 40-tall walls.
    ': size>height ( kb -- h ) isqrt isqrt 1 max 10 min ;\n'

    # branch,depth → packed 0xRRGGBB (policy: Filelight per-branch hue).
    # hue = (branch mod 8)/8 around the wheel; deeper rings desaturate (pale
    # tints of the ancestor hue), value stays bright. hsv>rgb is the C math prim.
    ': seg-color ( branch depth -- 0xRRGGBB )\n'
    '   swap 8 mod 8 /\n'                     # ( depth h )
    '   swap 1 - 0.18 * 0.85 swap - 0.25 max\n'  # ( h s )  s = clamp(0.85-(depth-1)*0.18, .25)
    '   0.95\n'                               # ( h s v )
    '   hsv>rgb ;\n'

    # spawn + configure one wedge of segment i at `angle` (revolutions)
    ': place-wedge ( i angle -- )\n'
    '   over seg-depth ring-tmpl spawn0\n'
    '   >r\n'
    '   r@ swap set-rotation\n'
    '   r@ over seg-size size>height set-z-scale\n'
    '   r@ over seg-branch 2 pick seg-depth seg-color set-color\n'
    '   r> drop drop ;\n'

    # depth-0 centre disk: one full-circle disk, no tiling. Flat pedestal (the
    # "you are here" cwd marker) rather than size-scaled — it represents the whole
    # tree, so a tall central tower would just occlude.
    ': place-disk ( i -- )\n'
    '   DISK spawn0\n'
    '   >r\n'
    '   r@ 2 set-z-scale\n'
    '   r@ 0xd0e8ff set-color\n'              # fixed light-blue "you are here" marker
    '   r> drop drop ;\n'

    # tile segment i's arc [a0,a1) with wedges of WEDGE-STEP width
    ': tile-wedges ( i -- )\n'
    '   dup seg-a1\n'
    '   over seg-a0\n'
    '   begin\n'
    '      2 pick over place-wedge\n'
    '      WEDGE-STEP +\n'
    '      2dup <\n'
    '   until\n'
    '   2drop drop ;\n'

    ': tile-seg ( i -- )\n'
    '   dup seg-depth 0 = if place-disk else tile-wedges fi ;\n'

    # render the whole table (guard the do-loop against 0 rows)
    ': render-sunburst\n'
    '   fl-scan dup 0 = if drop else 0 do i tile-seg loop fi ;\n'

    # ── per-frame body (no `;` past here — RunScript splits defs/body at last `;`)
    '10 read-mailbox 0 = if\n'
    '  1 10 write-mailbox\n'
    '  MAXDEPTH MAXNODES PLAYER-IDX fl-config\n'
    '  render-sunburst\n'
    'fi\n'
    '1906 read-mailbox CAMSHOT-IDX fl-flydown\n'
    'fl-navigate if render-sunburst fi\n'
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


def add_mesh(name, verts, faces, mat=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0.0, 0.0, 0.0)
    bpy.context.scene.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def annular_sector_geo(inner_r, outer_r, sweep_deg, segs, h):
    """A pie-slice-with-a-hole prism: annular sector [inner_r,outer_r] swept
    sweep_deg from angle 0, extruded z∈[0,h] (base-pivot). Centred on the origin
    so a spawned instance only needs a Z-rotation to land on its arc."""
    sw = math.radians(sweep_deg)
    ang = [i * sw / segs for i in range(segs + 1)]
    n = segs + 1
    verts = []
    verts += [(inner_r*math.cos(a), inner_r*math.sin(a), 0.0) for a in ang]   # IB 0..n-1
    verts += [(outer_r*math.cos(a), outer_r*math.sin(a), 0.0) for a in ang]   # OB n..2n-1
    verts += [(inner_r*math.cos(a), inner_r*math.sin(a), h)   for a in ang]   # IT 2n..3n-1
    verts += [(outer_r*math.cos(a), outer_r*math.sin(a), h)   for a in ang]   # OT 3n..4n-1
    IB = lambda i: i
    OB = lambda i: n + i
    IT = lambda i: 2*n + i
    OT = lambda i: 3*n + i
    faces = []
    for i in range(segs):
        faces.append((IT(i), IT(i+1), OT(i+1), OT(i)))     # top (z=h)
        faces.append((IB(i), OB(i), OB(i+1), IB(i+1)))     # bottom (z=0)
        faces.append((OB(i), OB(i+1), OT(i+1), OT(i)))     # outer wall
        faces.append((IB(i+1), IT(i+1), IT(i), IB(i)))     # inner wall
    faces.append((IB(0), IT(0), OT(0), OB(0)))                       # start cap
    faces.append((OB(segs), OT(segs), IT(segs), IB(segs)))          # end cap
    return verts, faces


def disk_geo(radius, segs, h):
    """A short solid cylinder (centre disk): base-pivot z∈[0,h], full circle."""
    verts = [(0.0, 0.0, 0.0), (0.0, 0.0, h)]   # 0 = centre base, 1 = centre top
    base0 = 2
    verts += [(radius*math.cos(2*math.pi*i/segs), radius*math.sin(2*math.pi*i/segs), 0.0)
              for i in range(segs)]
    top0 = base0 + segs
    verts += [(radius*math.cos(2*math.pi*i/segs), radius*math.sin(2*math.pi*i/segs), h)
              for i in range(segs)]
    RB = lambda i: base0 + (i % segs)
    RT = lambda i: top0 + (i % segs)
    faces = []
    for i in range(segs):
        faces.append((1, RT(i), RT(i+1)))                  # top fan
        faces.append((0, RB(i+1), RB(i)))                  # bottom fan
        faces.append((RB(i), RB(i+1), RT(i+1), RT(i)))     # outer wall
    return verts, faces


def add_ring_template(name, depth, mat, park_x):
    """Annular-sector wedge for ring band `depth` (inner=depth·w, outer=(depth+1)·w)."""
    verts, faces = annular_sector_geo(depth * RING_WIDTH, (depth + 1) * RING_WIDTH,
                                      WEDGE_DEG, segs=2, h=1.0)
    obj = add_mesh(name, verts, faces, mat)
    obj['wf_schema_path']        = oad('dir')   # trivial template mesh actor
    obj['wf_Template Object']    = 'True'
    obj['wf_Mobility']           = 'Anchored'
    obj['wf_Model Type']         = 'Mesh'
    obj['wf_Visibility Mailbox'] = 1
    obj.location                 = (park_x, -200.0, 0.0)   # parked OOB (never built at load)
    return obj


def build_astronaut_mesh():
    """Low-poly EVA-suit astronaut, ported verbatim from filesys/blender_filesys.py
    (origin baked to the feet, local z=0; suit faces mesh +X)."""
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
        'Number Of Temporary Objects': 500,   # the sunburst spawns ~hundreds of wedges
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
light = make_empty('Light01', (0.0, 0.0, 40.0), 'light',
    props={
        'Mobility':   'Anchored',
        'lightType':  'Directional',
        'lightRed':   0.6, 'lightGreen': 0.6, 'lightBlue': 0.8,
        'Model Type': 'None',
    })
light.rotation_euler = (math.pi / 2, 0, 0)   # aim downward

# 4 ── Camera ──────────────────────────────────────────────────────────────────
make_empty('Camera', CAM_HIGH, 'camera',
    props={
        'Mobility':                'Camera',
        'Model Type':              'None',
        'FoggingColor':            0x000000,
        'FoggingStartDistance':    999.0,
        'FoggingCompleteDistance': 1000.0,
    })

# 5 ── CamShot ─────────────────────────────────────────────────────────────────
make_empty('CamShot01', CAM_HIGH, 'camshot',
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
make_empty('Target01', TARGET1_POS, 'target',
    props={'Mobility': 'Anchored', 'Model Type': 'None'})

# 7 ── Target02 ────────────────────────────────────────────────────────────────
make_empty('Target02', TARGET2_POS, 'target',
    props={'Mobility': 'Anchored', 'Model Type': 'None'})

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
    'Max Ground Speed':      4.0,
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
mat_floor = make_mat('fl_floor', COLOR_FLOOR)
floor_obj = add_solid_box('Floor', FLOOR_X0, FLOOR_Y0, FLOOR_Z0,
                          FLOOR_X1, FLOOR_Y1, FLOOR_Z1, mat_floor)
floor_obj['wf_schema_path']        = oad('statplat')
floor_obj['wf_Mobility']           = 'Anchored'
floor_obj['wf_Model Type']         = 'Mesh'
floor_obj['wf_Visibility Mailbox'] = 1

# 11-13 ── Ring templates (annular-sector wedges, base-pivot, centred at origin) ─
mat_ring = make_mat('fl_ring', COLOR_RING)
add_ring_template('Ring1Template', 1, mat_ring, park_x=0.0)
add_ring_template('Ring2Template', 2, mat_ring, park_x=4.0)
add_ring_template('Ring3Template', 3, mat_ring, park_x=8.0)

# 14 ── Disk template (centre, full circle) ────────────────────────────────────
disk_verts, disk_faces = disk_geo(RING_WIDTH, segs=24, h=1.0)
disk_tmpl = add_mesh('DiskTemplate', disk_verts, disk_faces, mat_ring)
disk_tmpl['wf_schema_path']        = oad('dir')
disk_tmpl['wf_Template Object']    = 'True'
disk_tmpl['wf_Mobility']           = 'Anchored'
disk_tmpl['wf_Model Type']         = 'Mesh'
disk_tmpl['wf_Visibility Mailbox'] = 1
disk_tmpl.location                 = (12.0, -200.0, 0.0)

# 15 ── ActBoxOR: bootstrap camera (activates CamShot01 when Player enters) ─────
make_box_mesh('ActBoxOR', ROOM_CENTER, ROOM_LOCAL_BBOX, 'actboxor',
    props={
        'Mobility':     'Anchored',
        'Model Type':   'None',
        'MailBox':      1921,            # INDEXOF_CAMSHOT
        'Object':       'CamShot01',
        'Activated By': 'Player',
    })

# 16 ── AmbientLight (appended last so template indices 11-14 stay fixed) ───────
make_empty('AmbientLight', (0.0, 0.0, 40.0), 'light',
    props={
        'Mobility':   'Anchored',
        'lightType':  'Ambient',
        'lightRed':   0.40, 'lightGreen': 0.40, 'lightBlue': 0.50,
        'Model Type': 'None',
    })

# ── Export ────────────────────────────────────────────────────────────────────
print(f'[filelight] Exporting to {OUT_LEV}')
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

print(f'[filelight] Done. Objects in scene (export order):')
for i, o in enumerate(o for o in bpy.context.scene.objects if o.get('wf_schema_path')):
    print(f'  [{i:2d}] {o.name} @ {tuple(round(x,2) for x in o.location)}')
