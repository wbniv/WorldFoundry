"""
blender_dome.py — Planetarium dome: the Filelight sunburst wrapped onto a hemisphere.

Fourth view in the filesystem-visualization family (FSN node-link · Filelight flat
sunburst · KDirStat treemap · this). The player stands at the centre of a dome and
LOOKS UP: the cwd is a cap directly overhead (the zenith), its children fan out in
concentric ELEVATION bands descending toward the horizon, each segment's AZIMUTH
arc ∝ recursive size, coloured per branch (Filelight's hue signature).

Architecture — REUSES Filelight's emitter VERBATIM (no engine code):
  • C `fl-scan` already emits {depth, a0, a1 (revolutions), sizeKB, branchId}. The
    dome reads depth→ELEVATION band, a0/a1→azimuth, branch→hue; sizeKB is unused
    (size already lives in the arc, not in height). So a new view = a new Director
    .fth + new meshes; scripting_zforth.cc is untouched.
  • This Director iterates the table and spawns a baked spherical-patch band
    template per arc wedge, Z-rotating it to its azimuth (set-rotation, revolutions)
    and colouring by hue. The zenith cap is spawned once for depth 0.

Meshes are wound for INWARD normals (toward the player at the centre) so they're
visible from inside under backface culling — run with WF_CULL=1 (the dome is the
first opt-in consumer; see docs/level-design-troubleshooting.md). With culling off
(default) they render regardless.

Run headlessly:
    blender --background --python blender_dome.py
Then: task build-level -- dome ; WF_CULL=1 task run-dome

Plan: docs/plans/2026-06-13-planetarium-dome-view.md
"""

import bpy
import addon_utils
import math
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
OAD_DIR    = os.path.join(REPO, 'wflevels', 'oad')
OUT_LEV    = os.path.join(SCRIPT_DIR, 'dome.lev')

def oad(name):
    return os.path.join(OAD_DIR, f'{name}.oad')

# ── Dome geometry ───────────────────────────────────────────────────────────────
DOME_R     = 35.0         # hemisphere radius (world units)
WEDGE_DEG  = 6.0          # baked azimuth wedge width (MUST match Director WEDGE-STEP rev)
MAX_DEPTH  = 3            # zenith cap (depth 0) + 3 elevation bands
MAX_NODES  = 450          # spawn-budget cap (wedges); pool = 500

# Elevation bands (degrees from horizon; deeper = lower toward the horizon). The
# cap (depth 0) owns the zenith; band-3 stops above the horizon so it never clips
# the floor. Index by depth: BANDS[depth] = (phi_lo, phi_hi).
CAP_PHI    = 72.0                       # zenith cap spans [CAP_PHI, 90]
BANDS      = {1: (50.0, 72.0), 2: (28.0, 50.0), 3: (8.0, 28.0)}

PLAYER_SPAWN = (0.0, 0.0, 1.0)          # player at the dome centre

# Camera — player turns to look around (Rotation='Track' follows the player heading
# C; Position Relative keeps it at the centre). Look-at target is high+forward so
# the gaze pitches UP at the dome; turning sweeps that upward view around. (Framing
# is a tuning step — adjust CAM_OFFSET / TARGET2_POS against a screenshot.)
CAM_OFFSET  = (0.0,  0.0,  2.0)         # camera ≈ at the player's head
TARGET1_POS = (0.0,  0.0,  1.0)         # follow anchor (centre)
TARGET2_POS = (0.0,  9.0, 26.0)         # look-at: up + forward → pitch toward the dome

# Room bbox — contains the hemisphere (±35, z≤35), player, and camera, with margin.
#   world = ROOM_CENTER + local  →  X[-45,45] Y[-45,45] Z[-2,45].
ROOM_CENTER     = (0.0, 0.0, 20.0)
ROOM_LOCAL_BBOX = (-45.0, -45.0, -22.0, 45.0, 45.0, 25.0)

FLOOR_X0, FLOOR_X1 = -40.0, 40.0
FLOOR_Y0, FLOOR_Y1 = -40.0, 40.0
FLOOR_Z0, FLOOR_Z1 =  -0.5,  0.0

# Object export order → runtime .lvl index = Blender scene index + 1.
#   0→1 Room01   1→2 LevelObj  2→3 Matte    3→4 Light01  4→5 Camera
#   5→6 CamShot01 (CAMSHOT)    6→7 Target01 7→8 Target02 8→9 Director
#   9→10 Player (PLAYER)       10→11 Floor
#   11→12 Band1Template (BAND1) 12→13 Band2 (BAND2) 13→14 Band3 (BAND3)
#   14→15 CapTemplate (CAP)     15→16 ActBoxOR      16→17 AmbientLight
BAND1_IDX, BAND2_IDX, BAND3_IDX = 12, 13, 14
CAP_IDX         = 15
PLAYER_LVL_IDX  = 10
CAMSHOT_LVL_IDX = 6

COLOR_BG    = 0x05050c               # near-black sky
COLOR_FLOOR = (0.05, 0.05, 0.10, 1.0)
COLOR_BAND  = (0.55, 0.55, 0.60, 1.0)   # overridden per-segment at runtime by hue

# ── Director Forth script — RENDER POLICY (hot-reloadable). Reuses fl-scan. ──────
DIRECTOR_SCRIPT = (
    r'\\ wf' '\n'
    f': BAND1 {BAND1_IDX} ;\n'
    f': BAND2 {BAND2_IDX} ;\n'
    f': BAND3 {BAND3_IDX} ;\n'
    f': CAP   {CAP_IDX} ;\n'
    f': MAXDEPTH {MAX_DEPTH} ;\n'
    f': MAXNODES {MAX_NODES} ;\n'
    f': PLAYER-IDX {PLAYER_LVL_IDX} ;\n'
    ': WEDGE-STEP 0.0167 ;\n'                       # 6° in revolutions; == WEDGE_DEG

    # depth → elevation-band template (the band's φ range is baked into the mesh)
    ': band-tmpl ( depth -- tmpl )\n'
    '   dup 1 = if drop BAND1 else\n'
    '   dup 2 = if drop BAND2 else\n'
    '       drop BAND3\n'
    '   fi fi ;\n'

    # branch,depth → packed 0xRRGGBB (Filelight per-branch hue; identical policy).
    ': seg-color ( branch depth -- 0xRRGGBB )\n'
    '   swap 8 mod 8 /\n'
    '   swap 1 - 0.18 * 0.85 swap - 0.25 max\n'
    '   0.95\n'
    '   hsv>rgb ;\n'

    # spawn one azimuth wedge of segment i at `angle` (revolutions). No height
    # scale — size lives in the arc, not in extrusion.
    ': place-wedge ( i angle -- )\n'
    '   over seg-depth band-tmpl spawn0\n'
    '   >r\n'
    '   r@ swap set-rotation\n'
    '   r@ over seg-branch 2 pick seg-depth seg-color set-color\n'
    '   r> drop drop ;\n'

    # depth-0 zenith cap: spawned once, fixed light-blue "you are here" marker.
    ': place-cap ( i -- )\n'
    '   CAP spawn0\n'
    '   >r\n'
    '   r@ 0xd0e8ff set-color\n'
    '   r> drop drop ;\n'

    # tile segment i's arc [a0,a1) with WEDGE-STEP-wide wedges
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
    '   dup seg-depth 0 = if place-cap else tile-wedges fi ;\n'

    ': render-dome\n'
    '   fl-scan dup 0 = if drop else 0 do i tile-seg loop fi ;\n'

    # ── per-frame body (no `;` past here). Static — no fl-navigate / fl-flydown.
    '10 read-mailbox 0 = if\n'
    '  1 10 write-mailbox\n'
    '  MAXDEPTH MAXNODES PLAYER-IDX fl-config\n'
    '  render-dome\n'
    'fi\n'
)

# ── Helpers (cloned from blender_filelight.py) ──────────────────────────────────

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


# ── Dome geometry generators (INWARD normals — viewed from the centre) ──────────

def _sph(R, th, phi):
    """Sphere point: azimuth th, elevation phi (both radians), Z up."""
    return (R * math.cos(phi) * math.cos(th),
            R * math.cos(phi) * math.sin(th),
            R * math.sin(phi))


def spherical_band_geo(R, phi0_deg, phi1_deg, sweep_deg, az_segs=4, el_segs=3):
    """One spherical-shell patch: azimuth [0, sweep], elevation [phi0, phi1], on
    radius R. Centred on azimuth 0 so a spawned instance needs only a Z-rotation to
    land on its arc. Wound for INWARD normals (toward the player at the centre): the
    face order (j,i)(j,i+1)(j+1,i+1)(j+1,i) gives n = (v2-v0)x(v1-v0) pointing
    -radial (verified)."""
    phi0, phi1, sw = map(math.radians, (phi0_deg, phi1_deg, sweep_deg))
    n_th = az_segs + 1
    verts = []
    for j in range(el_segs + 1):
        phi = phi0 + (phi1 - phi0) * j / el_segs
        for i in range(az_segs + 1):
            verts.append(_sph(R, sw * i / az_segs, phi))
    idx = lambda j, i: j * n_th + i
    faces = [(idx(j, i), idx(j, i + 1), idx(j + 1, i + 1), idx(j + 1, i))
             for j in range(el_segs) for i in range(az_segs)]
    return verts, faces


def cap_geo(R, phi_lo_deg, segs=24):
    """Zenith spherical cap: a fan from the pole (0,0,R) out to the phi_lo circle,
    full 360°. Wound (pole, rim[i], rim[i+1]) for an INWARD/downward normal (toward
    the player below)."""
    phi_lo = math.radians(phi_lo_deg)
    verts = [(0.0, 0.0, R)]                                   # 0 = pole
    verts += [_sph(R, 2 * math.pi * i / segs, phi_lo) for i in range(segs)]
    rim = lambda i: 1 + (i % segs)
    faces = [(0, rim(i), rim(i + 1)) for i in range(segs)]
    return verts, faces


def add_band_template(name, depth, mat, park_x):
    phi0, phi1 = BANDS[depth]
    verts, faces = spherical_band_geo(DOME_R, phi0, phi1, WEDGE_DEG, az_segs=4, el_segs=3)
    obj = add_mesh(name, verts, faces, mat)
    obj['wf_schema_path']        = oad('dir')
    obj['wf_Template Object']    = 'True'
    obj['wf_Mobility']           = 'Anchored'
    obj['wf_Model Type']         = 'Mesh'
    obj['wf_Visibility Mailbox'] = 1
    obj.location                 = (park_x, -200.0, 0.0)   # parked OOB (never built at load)
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

# 0 ── Room ──────────────────────────────────────────────────────────────────
make_box_mesh('Room01', ROOM_CENTER, ROOM_LOCAL_BBOX, 'room',
    props={'Adjacent Room 1': '', 'Adjacent Room 2': '', 'Room Loaded Mailbox': 0})

# 1 ── LevelObj ──────────────────────────────────────────────────────────────
make_empty('LevelObj', ROOM_CENTER, 'levelobj',
    props={
        'Number Of Mailboxes':         50,
        'Number Of Temporary Objects': 500,   # the dome spawns ~hundreds of wedges
        'Mobility':   'Anchored',
        'Model Type': 'None',
    })

# 2 ── Matte ──────────────────────────────────────────────────────────────────
make_empty('Matte', ROOM_CENTER, 'matte',
    props={
        'Mobility':           'Anchored',
        'Matte Type':         'Color',
        'Background Color':   COLOR_BG,
        'Visibility Mailbox': 1,
        'Model Type':         'None',
    })

# 3 ── Light (directional, aimed down at the dome from above) ──────────────────
light = make_empty('Light01', (0.0, 0.0, 40.0), 'light',
    props={
        'Mobility':   'Anchored',
        'lightType':  'Directional',
        'lightRed':   0.65, 'lightGreen': 0.65, 'lightBlue': 0.85,
        'Model Type': 'None',
    })
light.rotation_euler = (math.pi / 2, 0, 0)

# 4 ── Camera ──────────────────────────────────────────────────────────────────
make_empty('Camera', CAM_OFFSET, 'camera',
    props={
        'Mobility':                'Camera',
        'Model Type':              'None',
        'FoggingColor':            0x000000,
        'FoggingStartDistance':    999.0,
        'FoggingCompleteDistance': 1000.0,
    })

# 5 ── CamShot — player-relative, heading-tracking (turn to look around) ───────
make_empty('CamShot01', CAM_OFFSET, 'camshot',
    props={
        'Mobility':            'Anchored',
        'Target':              'Target02',   # look-at (up + forward → pitch up)
        'Follow':              'Target01',
        'Track Object':        'Player',     # camera = CamShot offset + Player
        'Rotation':            'Track',      # heading follows the player → look around
        'Position X':          'Relative',
        'Position Y':          'Relative',
        'Position Z':          'Relative',
        'FOV':                 80.0,          # wide, to take in the dome overhead
        'Climb Rate':          4.0,
        'Elasticity':          10.0,
        'Pan Time In Seconds': 0.4,
        'Hither':              0.1,
        'Yon':                 500.0,
        'Model Type':          'None',
        'Visibility Mailbox':  1,
    })

# 6 ── Target01 (follow anchor) ────────────────────────────────────────────────
make_empty('Target01', TARGET1_POS, 'target',
    props={'Mobility': 'Anchored', 'Model Type': 'None'})

# 7 ── Target02 (look-at, high → up-pitch) ─────────────────────────────────────
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

# 9 ── Player (walking EVA astronaut, turns to look around) ────────────────────
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
mat_floor = make_mat('dome_floor', COLOR_FLOOR)
floor_obj = add_solid_box('Floor', FLOOR_X0, FLOOR_Y0, FLOOR_Z0,
                          FLOOR_X1, FLOOR_Y1, FLOOR_Z1, mat_floor)
floor_obj['wf_schema_path']        = oad('statplat')
floor_obj['wf_Mobility']           = 'Anchored'
floor_obj['wf_Model Type']         = 'Mesh'
floor_obj['wf_Visibility Mailbox'] = 1

# 11-13 ── Band templates (spherical patches, INWARD normals, parked OOB) ───────
mat_band = make_mat('dome_band', COLOR_BAND)
add_band_template('Band1Template', 1, mat_band, park_x=0.0)
add_band_template('Band2Template', 2, mat_band, park_x=4.0)
add_band_template('Band3Template', 3, mat_band, park_x=8.0)

# 14 ── Cap template (zenith spherical cap, INWARD/down normal) ─────────────────
cap_verts, cap_faces = cap_geo(DOME_R, CAP_PHI, segs=24)
cap_tmpl = add_mesh('CapTemplate', cap_verts, cap_faces, mat_band)
cap_tmpl['wf_schema_path']        = oad('dir')
cap_tmpl['wf_Template Object']    = 'True'
cap_tmpl['wf_Mobility']           = 'Anchored'
cap_tmpl['wf_Model Type']         = 'Mesh'
cap_tmpl['wf_Visibility Mailbox'] = 1
cap_tmpl.location                 = (12.0, -200.0, 0.0)

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
print(f'[dome] Exporting to {OUT_LEV}')
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

print('[dome] Done. Objects in scene (export order):')
for i, o in enumerate(o for o in bpy.context.scene.objects if o.get('wf_schema_path')):
    print(f'  [{i:2d}] {o.name} @ {tuple(round(x,2) for x in o.location)}')
