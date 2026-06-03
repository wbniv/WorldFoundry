"""
blender_create_moon.py — create the Moon Site 01 (Connecting Ridge) walkable level.

Tier 2 of docs/plans/2026-05-30-moon-surface-tier2.md: a single Artemis III
candidate site rendered as a static terrain mesh that an astronaut-scale player
falls onto and walks around.

Pipeline:
  python3 dem_to_grid.py             # reads PGDA GeoTIFF, writes terrain_heights.npy
  blender --background --python blender_create_moon.py
  bash build_level_binary.sh
  task run -- wflevels/moon_site01/moon_site01-standalone.iff

The Blender step assumes terrain_heights.npy already exists (built by
dem_to_grid.py, which needs rasterio outside Blender). Blender's bundled Python
ships with numpy, so reading the .npy is free here.
"""

import bpy
import bmesh
import os
import math
import json
import addon_utils
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO        = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS   = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OAD_DIR     = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
OUT_LEV     = os.path.join(SCRIPT_DIR, 'moon_site01.lev')
HEIGHTS_NPY = os.path.join(SCRIPT_DIR, 'terrain_heights.npy')
HEIGHTS_JSON= os.path.join(SCRIPT_DIR, 'terrain_heights.json')

# ── Load heightfield ──────────────────────────────────────────────────────────
heights = np.load(HEIGHTS_NPY)
with open(HEIGHTS_JSON) as f:
    meta = json.load(f)

# Engine caps both vertex and FACE counts at <32000 (rendobj3.hpi:30-32) —
# hard ceiling is int16 v?Index (face.hp:35). Quads triangulate 1:2, so
# the binding constraint is 2·(N-1)² < 32000, giving N ≤ 127. Decimate the
# input grid uniformly until it fits.
src_cell = float(meta['cell_size_m'])
decim = 1
while heights[::decim, ::decim].shape[0] > 127:
    decim += 1
heights = heights[::decim, ::decim]
N         = heights.shape[0]                # samples per side
CELL_M    = src_cell * decim                # metres per sample after decimation
SIDE_M    = (N - 1) * CELL_M                # span between outermost vertices
HALF_M    = SIDE_M / 2.0
print(f"[moon] heightfield: {N}x{N} samples @ {CELL_M} m/sample, "
      f"Z range {heights.min():+.1f} to {heights.max():+.1f} m")


def terrain_z(wx, wy):
    """Sample the LOLA heightfield at world position (wx, wy) — nearest-neighbour."""
    col = max(0.0, min(float(N - 1), (wx + HALF_M) / CELL_M))
    row = max(0.0, min(float(N - 1), (wy + HALF_M) / CELL_M))
    return float(heights[int(round(row)), int(round(col))])


# ── Player (astronaut) — 1.8 m tall, WF unit = 1 m ───────────────────────────
PLAYER_HEIGHT = 1.8
# Spawn at centre of play area, 5 m above terrain centre (drop is the proof of
# collision). Centre vertex of the heightfield is at Z=0 by construction.
PLAYER_SPAWN  = (0.0, 0.0, 5.0)

# Camera: vista from −Y, elevated to show NAC texture detail across a
# real field of view. Distance ~85 m, ~30° downward angle, 60° FOV →
# visible footprint ~100 m → ~100 NAC texels (1024² over 1 km play area).
# Vista camera at (0, -100, 80) — looks down at the play area centre at
# ~38° from a 128 m diagonal. Fog is disabled on the camera actor below so
# distant terrain renders cleanly (snowgoons inherits Earth-atmosphere fog
# that fades everything past 30 m to flat #888888; see
# docs/plans/2026-05-31-uninitialised-fog-defaults.md).
CAM_OFFSET    = (0.0, -100.0, 80.0)
LOOK_TARGET   = (0.0, 0.0, 0.0)   # cs_chase looks ~39° down — overhead camp view

# Sun direction — az 20°, alt 2° (matches LOLA illumination at site latitude).
# Used by both the engine directional-light actor and the visible Sun disc mesh.
SUN_AZ_DEG  = 20.0
SUN_ALT_DEG = 2.0
SUN_DIST_M  = 480.0   # sun disc placed 480 m from origin (≤505 m room half-size)

NUM_MAILBOXES = 100

# ── 1. Clean scene & enable addon ─────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# ── 2. Import snowgoons for infrastructure ────────────────────────────────────
print(f"[moon] Importing snowgoons scaffold from {SNOWGOONS}")
bpy.ops.wf.import_level(filepath=SNOWGOONS)

# ── 3. Strip everything except bare infrastructure ────────────────────────────
KEEP_CLASSES   = {'director', 'camera', 'levelobj', 'matte', 'light',
                  'room', 'camshot', 'target', 'player'}
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile', 'actboxor',
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

print("[moon] Classes after strip:", sorted({get_class(o) for o in bpy.data.objects}))


def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None


def attach_schema(obj, oad_name):
    obj['wf_schema_path'] = os.path.join(OAD_DIR, oad_name + '.oad')


# ── 4. Build the terrain mesh ─────────────────────────────────────────────────
# Subdivided plane: N×N vertices at (col*CELL_M − HALF_M, row*CELL_M − HALF_M,
# heights[row, col]). (N−1)² quads. Centre vertex sits exactly at the world
# origin (0, 0, 0) by construction.

def build_terrain_mesh(name, tex_path):
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new('UVMap')

    # Vertices, indexed by (row, col) → grid[row][col]. UV is planar — (col,
    # row) normalised into [0, 1] — so the texture maps 1:1 onto the same
    # geographic crop the heightfield came from.
    grid = [[None] * N for _ in range(N)]
    uvs  = [[None] * N for _ in range(N)]
    for row in range(N):
        y = row * CELL_M - HALF_M
        v_uv = row / (N - 1)
        for col in range(N):
            x = col * CELL_M - HALF_M
            z = float(heights[row, col])
            grid[row][col] = bm.verts.new((x, y, z))
            uvs[row][col]  = (col / (N - 1), v_uv)
    bm.verts.ensure_lookup_table()

    # Quads — CCW from above (+Z), per-loop UVs.
    for row in range(N - 1):
        for col in range(N - 1):
            v00 = grid[row    ][col    ]; uv00 = uvs[row    ][col    ]
            v10 = grid[row    ][col + 1]; uv10 = uvs[row    ][col + 1]
            v11 = grid[row + 1][col + 1]; uv11 = uvs[row + 1][col + 1]
            v01 = grid[row + 1][col    ]; uv01 = uvs[row + 1][col    ]
            face = bm.faces.new((v00, v10, v11, v01))
            for loop, uv_xy in zip(face.loops, (uv00, uv10, uv11, uv01)):
                loop[uv_layer].uv = uv_xy

    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    # Hillshaded regolith material (Phase 3a — texture baked from the DEM
    # via make_terrain_texture.py). Phase 3b will swap in a NAC+WAC bake.
    mat = bpy.data.materials.new('lunar_regolith')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = bpy.data.images.load(tex_path)
    mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    # WF fragment shader (gfx/glpipeline/backend_modern.cc kFS) samples the
    # texture only when v_color is white (`step(0.99, min(rgb))`); the
    # exported MATL `_color` is what becomes v_color per vertex. Force the
    # BSDF base RGB to white so is_white=1 and the texture is actually used.
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    mesh.materials.append(mat)
    return mesh


TERRAIN_TEX = os.path.join(SCRIPT_DIR, 'terrain_texture.tga')
if not os.path.isfile(TERRAIN_TEX):
    raise SystemExit(f"missing {TERRAIN_TEX} — run `python3 make_terrain_texture.py` first")
terrain_mesh = build_terrain_mesh('lunar_terrain', TERRAIN_TEX)
terrain_obj  = bpy.data.objects.new('lunar_terrain', terrain_mesh)
scene.collection.objects.link(terrain_obj)
attach_schema(terrain_obj, 'statplat')
terrain_obj['wf_Mobility']         = 'Anchored'
terrain_obj['wf_Model Type']       = 'Mesh'
terrain_obj['wf_Visibility Mailbox'] = 1
print(f"[moon] terrain mesh: {len(terrain_mesh.vertices)} verts, "
      f"{len(terrain_mesh.polygons)} quads")

# ── 5. Sky / lighting (Phase 6: astronaut polish) ────────────────────────────
# The Moon has no atmosphere → black sky, hard-edged shadows, no ambient fill.
# At Site 01 (~89.5° S) the sun stays a few degrees above the horizon all
# "day"; we use az 20° / alt 2° to match the texture bake.

matte = find_by_class('matte')
if matte:
    matte.location = (0.0, -490.0, 0.0)  # parked at edge of room, no chance of frustum overlap
    matte['wf_Matte Type']        = 'Color'
    matte['wf_Background Color']  = 0x000000      # space-black
    matte['wf_Visibility Mailbox']= 1
    matte['wf_Model Type']        = 'None'

light = find_by_class('light')
if light:
    light.name = 'Sun'
    # Position has to sit inside the room's bbox or level.cc's room-iter
    # skips this actor and the room reports "no lights" — Z=200 was outside
    # the rel-bbox z=±99 around centre Z≈-35. (Directional-light position is
    # cosmetic; only the orientation matters for shading.)
    light.location = (0.0, 0.0, 50.0)
    # In SMB's lighting convention (blender_create_smb.py:225 calls
    # rotation_euler.x = π/3 "sun ~60° above horizon"), the X rotation tilts
    # the beam off zenith. South-pole sun at altitude 2° → X = π/2 − 2°.
    # Z rotation rotates the cast-shadow azimuth around the vertical.
    light.rotation_euler = (math.pi / 2 - math.radians(SUN_ALT_DEG),
                            0.0,
                            math.radians(SUN_AZ_DEG))
    light['wf_lightType']  = 'Directional'
    light['wf_lightRed']   = 1.0
    light['wf_lightGreen'] = 1.0
    light['wf_lightBlue']  = 1.0

    # Ambient — without it, WF's shader (backend_modern.cc:84) leaves any
    # curved-geometry actor pure black on the camera-facing side because
    # u_ambient defaults to Color::black at level.cc:1158. See
    # docs/level-design-troubleshooting.md "Actor renders pure black despite
    # light" and docs/plans/2026-06-01-ambient-light-default-and-warnings.md.
    ambient = light.copy()
    ambient.data = light.data.copy() if light.data else None
    scene.collection.objects.link(ambient)
    ambient.name = 'AmbientLight'
    ambient.location = (0.0, 0.0, 50.0)
    ambient['wf_lightType']  = 'Ambient'
    ambient['wf_lightRed']   = 0.40
    ambient['wf_lightGreen'] = 0.42
    ambient['wf_lightBlue']  = 0.50

# ── 6. Player (astronaut) ────────────────────────────────────────────────────
# Built in-script from primitives like SMB Mario / Q*bert, not imported. ~14
# primitives joined into one mesh, feet at z=0 via transform_apply. See
# docs/plans/2026-05-31-moon-astronaut-mesh.md.

def _make_mat(name, rgb):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def _build_astronaut():
    mat_white = _make_mat('astro_white', (0.92, 0.92, 0.92))
    mat_off   = _make_mat('astro_offwhite', (0.85, 0.85, 0.82))   # PLSS backpack
    mat_dark  = _make_mat('astro_dark', (0.18, 0.18, 0.20))       # chest panel, neck
    mat_visor = _make_mat('astro_visor', (0.76, 0.53, 0.25))      # gold-amber #c28840

    parts = []
    SEG = 8; RING = 5  # low-poly UV sphere segments (matches SMB Mario)

    def add_cyl(r, h, loc, mat):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        parts.append((bpy.context.object, mat))

    def add_sph(r, loc, mat):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=SEG, ring_count=RING, location=loc)
        parts.append((bpy.context.object, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((obj, mat))

    # Boots, lower legs, upper legs (mirrored in ±Y)
    for yo in (-0.12, 0.12):
        add_cube(0.18, 0.15, 0.10, (0.0, yo, 0.05), mat_white)               # boot
        add_cyl(0.09, 0.42, (0.0, yo, 0.31), mat_white)                       # lower leg
        add_cyl(0.10, 0.42, (0.0, yo, 0.73), mat_white)                       # upper leg

    add_cyl(0.20, 0.10, (0.0, 0.0, 0.95), mat_white)                          # hips
    add_cyl(0.22, 0.45, (0.0, 0.0, 1.225), mat_white)                         # torso
    add_cube(0.20, 0.08, 0.12, (+0.20, 0.0, 1.30), mat_dark)                  # chest panel at mesh +X (front, per WF convention)
    add_cube(0.30, 0.18, 0.50, (-0.27, 0.0, 1.20), mat_off)                   # PLSS backpack at mesh -X (back)

    for yo in (-0.27, 0.27):
        add_sph(0.11, (0.0, yo, 1.42), mat_white)                             # shoulder
        add_cyl(0.08, 0.30, (0.0, yo, 1.27), mat_white)                       # upper arm
        add_cyl(0.08, 0.28, (0.0, yo, 0.98), mat_white)                       # forearm
        add_sph(0.09, (0.0, yo, 0.84), mat_white)                             # glove

    add_cyl(0.06, 0.06, (0.0, 0.0, 1.475), mat_dark)                          # neck
    add_sph(0.14, (0.0, 0.0, 1.66), mat_white)                                # helmet
    add_sph(0.13, (+0.05, 0.0, 1.66), mat_visor)                              # visor at mesh +X (front)

    # Apply per-part material assignments
    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0
            p.use_smooth = True

    # Join all parts into one mesh, then bake the root part's location into
    # mesh-local verts so the joined mesh's origin lands at feet (z=0).
    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = 'astronaut'
    body.data.name = 'astronaut'
    return body


_astronaut = _build_astronaut()


def _build_earth():
    """Blue Marble Earth — UV sphere R=20 m, NASA earth.tga (128×64) texture.
    Placed at (0, 200, 50) — 301 m from the camera, ~7.6° angular diameter,
    ~81 px on a 640 px / 60° FOV window. 128×64 texels ≈ 1 texel per screen
    pixel at the equator; going higher wastes atlas space with no visible gain.
    See docs/investigations/2026-06-02-texture-lod-for-distant-spheres.md."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=80.0, segments=24, ring_count=12,
        location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = 'earth'
    obj.data.name = 'earth'

    mat = bpy.data.materials.new('earth_mat')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = bpy.data.images.load(os.path.join(SCRIPT_DIR, 'earth.tga'))
    mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    # WF fragment shader (backend_modern.cc kFS) samples the texture only when
    # v_color is white (step(0.99, min(rgb))).  Force Base Color = white so the
    # exported MATL _color drives v_color = (1,1,1) per vertex.
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    obj.data.materials.append(mat)

    for poly in obj.data.polygons:
        poly.use_smooth = True

    return obj


def _build_artemis_lander():
    """Starship HLS Artemis lander — primitive build at 1:1 real scale
    (~47 m tall, ~9 m diameter). Joined into one mesh with the engine-mount
    base at z=0. See docs/plans/2026-05-31-moon-artemis-lander.md."""
    mat_white = _make_mat('lander_white', (0.92, 0.92, 0.92))
    mat_dark  = _make_mat('lander_dark',  (0.20, 0.20, 0.22))

    parts = []
    SEG = 12   # smoother silhouette than the astronaut — this is a vehicle hull

    def add_cyl(r, h, loc, mat):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        parts.append((bpy.context.object, mat))

    def add_cone(r1, r2, h, loc, mat):
        bpy.ops.mesh.primitive_cone_add(vertices=SEG, radius1=r1, radius2=r2, depth=h, location=loc)
        parts.append((bpy.context.object, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((obj, mat))

    # Engine-mount base (Starship HLS doesn't need a heat shield; this is the
    # thrust-structure ring the Raptors hang from).
    add_cyl(4.5, 2.0, (0.0, 0.0, 1.0), mat_dark)

    # Three Raptor nozzles clustered at the base, ring radius 2.4 m.
    for ang_deg in (0.0, 120.0, 240.0):
        ang = math.radians(ang_deg)
        add_cone(1.0, 0.55, 3.2,
                 (2.4 * math.cos(ang), 2.4 * math.sin(ang), -0.6),
                 mat_dark)

    # Main body — the recognisable Starship cylinder, 36 m tall.
    add_cyl(4.5, 36.0, (0.0, 0.0, 20.0), mat_white)

    # Crew access door + ARTEMIS stripe — both on the −X face so they read
    # from the vista camera (the lander sits at +X relative to player spawn,
    # so its −X face points back toward the astronaut and camera).
    add_cube(0.3, 1.8, 2.0, (-4.5, 0.0, 10.0), mat_dark)
    add_cube(0.4, 9.0, 0.7, (-4.6, 0.0, 28.0), mat_dark)

    # Nose cone — tip at z=47, base meets body top at z=38.
    add_cone(4.5, 0.0, 9.0, (0.0, 0.0, 42.5), mat_white)

    # Raptor exhaust flames — three bright-orange tapered cones below each
    # nozzle, mesh-local z = -2 (top) to -4 (tip). Buried under the regolith
    # initially; the moment the lander Z rises during ascent they become
    # visible as the flame trail. See
    # docs/plans/2026-06-02-moon-lander-launch-sequence.md.
    mat_exhaust = _make_mat('lander_exhaust', (1.0, 0.6, 0.1))
    for ang_deg in (0.0, 120.0, 240.0):
        ang = math.radians(ang_deg)
        add_cone(1.2, 0.2, 2.0,
                 (2.4 * math.cos(ang), 2.4 * math.sin(ang), -3.0),
                 mat_exhaust)

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
    body.name = 'artemis_lander'
    body.data.name = 'artemis_lander'
    return body


def _build_moon_racer():
    """Moon RACER LTV — open-cab electric buggy ~4×2×1.5 m.
    Intuitive Machines / Boeing / Northrop Grumman (Artemis V+).
    Mobility=Anchored for now; will be hooked to Jolt vehicle physics later.
    See docs/plans/2026-06-03-moon-site-01-surface-asset-models.md."""
    mat_white = _make_mat('rover_white', (0.92, 0.92, 0.92))
    mat_dark  = _make_mat('rover_dark',  (0.15, 0.15, 0.17))

    parts = []
    SEG = 8

    def add_cyl(r, h, loc, mat, rot=(0.0, 0.0, 0.0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        obj = bpy.context.object
        obj.rotation_euler = rot
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        parts.append((obj, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((obj, mat))

    # Chassis frame — 4×2×0.5 m, centre at z=0.6
    add_cube(4.0, 2.0, 0.5, (0.0, 0.0, 0.6), mat_white)

    # 4 wheels (r=0.5, w=0.3 m). Blender cylinders run along Z; rotate 90° around X
    # so the wheel axis aligns with Y and the rover rolls in X.
    for fx in (+1.6, -1.6):
        for fy in (+1.1, -1.1):
            add_cyl(0.5, 0.3, (fx, fy, 0.5), mat_dark, rot=(math.pi / 2, 0.0, 0.0))

    # Crew seat — centre of chassis
    add_cube(1.0, 0.8, 0.4, (0.0, 0.0, 1.25), mat_white)

    # Camera mast — front-centre
    add_cyl(0.06, 1.5, (1.6, 0.0, 1.6), mat_dark)

    # Solar panel atop mast
    add_cube(1.5, 0.8, 0.06, (1.6, 0.0, 2.42), mat_white)

    # Robotic arm (folded) — starboard rear
    add_cube(1.2, 0.15, 0.15, (-1.0, -1.1, 1.1), mat_dark)

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = 'moon_racer'
    body.data.name = 'moon_racer'
    return body


def _build_vsat_tower():
    """Astrobotic LunaGrid VSAT — 10 m vertical solar mast.
    See docs/plans/2026-06-03-moon-site-01-surface-asset-models.md."""
    mat_dark   = _make_mat('vsat_dark',   (0.18, 0.18, 0.20))
    mat_silver = _make_mat('vsat_silver', (0.78, 0.78, 0.80))
    mat_white  = _make_mat('vsat_white',  (0.92, 0.92, 0.92))

    parts = []
    SEG = 8

    def add_cyl(r, h, loc, mat):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        parts.append((bpy.context.object, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((obj, mat))

    add_cube(1.5, 1.5, 0.4, (0.0, 0.0, 0.2), mat_dark)      # ground anchor
    add_cyl(0.12, 9.5, (0.0, 0.0, 5.15), mat_silver)         # mast
    add_cube(2.5, 0.06, 2.0, (0.0, 0.0, 10.5), mat_white)    # solar array face A
    add_cube(0.06, 2.5, 2.0, (0.0, 0.0, 10.5), mat_white)    # solar array face B (90°)

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = 'vsat_tower'
    body.data.name = 'vsat_tower'
    return body


def _build_lunar_cruiser():
    """Toyota/JAXA Lunar Cruiser — pressurized 6-wheel rover 6×5.2×3.8 m.
    Mobility=Anchored; will be hooked to Jolt vehicle physics later.
    See docs/plans/2026-06-03-moon-site-01-surface-asset-models.md."""
    mat_white = _make_mat('cruiser_white', (0.90, 0.90, 0.88))
    mat_dark  = _make_mat('cruiser_dark',  (0.18, 0.19, 0.20))

    parts = []
    SEG = 8

    def add_cyl(r, h, loc, mat, rot=(0.0, 0.0, 0.0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        obj = bpy.context.object
        obj.rotation_euler = rot
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        parts.append((obj, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((obj, mat))

    add_cube(5.5, 4.5, 2.2, (0.0, 0.0, 1.8), mat_white)       # main pressurised body
    add_cube(5.6, 4.6, 0.4, (0.0, 0.0, 2.9), mat_dark)         # viewport window strip
    add_cube(0.5, 3.0, 2.0, (3.0, 0.0, 1.8), mat_dark)         # airlock end-cap +X

    # 6 wheels: 2 rows of 3 (fore/mid/aft), port and starboard
    for fx in (+1.9, 0.0, -1.9):
        for fy in (+2.6, -2.6):
            add_cyl(0.7, 0.35, (fx, fy, 0.7), mat_dark, rot=(math.pi / 2, 0.0, 0.0))

    add_cube(2.0, 0.10, 0.08, (0.0, 0.0, 3.19), mat_dark)      # roof boom
    add_cube(2.0, 1.50, 0.06, (0.0, 0.0, 3.27), mat_white)     # roof solar panel
    add_cyl(0.05, 1.0, (0.0, 0.0, 3.82), mat_dark)              # antenna

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = 'lunar_cruiser'
    body.data.name = 'lunar_cruiser'
    return body


def _build_blue_moon_mk1():
    """Blue Origin Blue Moon Mark 1 — uncrewed cargo lander ~8 m tall.
    Gold thermal-blanket cylinder, 4 splayed landing legs.
    Mobility=Anchored; could get a landing/launch sequence like the Starship HLS.
    See docs/plans/2026-06-03-moon-site-01-surface-asset-models.md."""
    mat_gold   = _make_mat('mk1_gold',   (0.72, 0.55, 0.10))
    mat_silver = _make_mat('mk1_silver', (0.70, 0.72, 0.73))
    mat_dark   = _make_mat('mk1_dark',   (0.20, 0.20, 0.22))

    parts = []
    SEG = 12

    def add_cyl(r, h, loc, mat, rot=(0.0, 0.0, 0.0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        obj = bpy.context.object
        obj.rotation_euler = rot
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        parts.append((obj, mat))

    def add_cone(r1, r2, h, loc, mat):
        bpy.ops.mesh.primitive_cone_add(vertices=SEG, radius1=r1, radius2=r2, depth=h,
                                        location=loc)
        parts.append((bpy.context.object, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((obj, mat))

    add_cyl(1.4, 5.0, (0.0, 0.0, 4.5), mat_gold)              # main tank
    add_cyl(1.6, 0.6, (0.0, 0.0, 1.8), mat_dark)              # engine skirt
    add_cone(1.0, 0.4, 1.5, (0.0, 0.0, 0.75), mat_dark)       # engine bell
    add_cube(3.2, 3.2, 0.4, (0.0, 0.0, 7.2), mat_silver)      # payload deck

    # 4 landing legs at ±45°/±135° azimuth, tilted ~34° outward from vertical.
    # Leg runs from attachment (r=1.6, z=1.8) to foot (r=2.8, z=0), length≈2.2m.
    for ang_deg in (45.0, 135.0, 225.0, 315.0):
        ang = math.radians(ang_deg)
        cx = 2.2 * math.cos(ang)
        cy = 2.2 * math.sin(ang)
        add_cyl(0.08, 2.2, (cx, cy, 0.9), mat_dark,
                rot=(0.0, math.radians(34), ang))              # leg strut
        add_cyl(0.25, 0.1, (2.8 * math.cos(ang),              # foot pad
                             2.8 * math.sin(ang), 0.05), mat_dark)

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = 'blue_moon_mk1'
    body.data.name = 'blue_moon_mk1'
    return body


def _build_fsh():
    """NASA Foundation Surface Habitat — 3-storey hybrid metallic+inflatable.
    4 m-dia metallic base (~3 m tall) + 6.5 m-dia inflatable upper (~7 m tall).
    See docs/plans/2026-06-03-moon-site-01-surface-asset-models.md."""
    mat_white = _make_mat('fsh_white', (0.90, 0.90, 0.88))
    mat_dark  = _make_mat('fsh_dark',  (0.25, 0.27, 0.30))

    parts = []
    SEG = 16

    def add_cyl(r, h, loc, mat):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        parts.append((bpy.context.object, mat))

    def add_cube(sx, sy, sz, loc, mat):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
        obj = bpy.context.object
        obj.scale = (sx, sy, sz)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append((obj, mat))

    add_cyl(2.0, 3.0, (0.0, 0.0, 1.5), mat_dark)               # metallic base module
    add_cube(2.0, 1.8, 2.0, (2.9, 0.0, 1.5), mat_dark)         # airlock stub (+X)
    add_cyl(2.6, 0.8, (0.0, 0.0, 3.4), mat_dark)               # transition ring
    add_cyl(3.2, 6.5, (0.0, 0.0, 6.75), mat_white)             # inflatable upper
    # Radiator panels on ±X faces of the inflatable section
    add_cube(0.1, 1.0, 2.0, (3.2, 0.0, 6.75), mat_white)       # radiator +X
    add_cube(0.1, 1.0, 2.0, (-3.2, 0.0, 6.75), mat_white)      # radiator −X

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = 'fsh'
    body.data.name = 'fsh'
    return body


def _build_fsp_reactor():
    """NASA/DOE Fission Surface Power — 40 kWe reactor with 4-fin radiator array.
    Sited away from the habitat; distinctive cross-fin silhouette.
    See docs/plans/2026-06-03-moon-site-01-surface-asset-models.md."""
    mat_dark   = _make_mat('fsp_dark',   (0.30, 0.30, 0.32))
    mat_silver = _make_mat('fsp_silver', (0.65, 0.65, 0.68))
    mat_lunar  = _make_mat('fsp_lunar',  (0.82, 0.80, 0.73))

    parts = []
    SEG = 12

    def add_cyl(r, h, loc, mat):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
        parts.append((bpy.context.object, mat))

    def add_cone(r1, r2, h, loc, mat):
        bpy.ops.mesh.primitive_cone_add(vertices=SEG, radius1=r1, radius2=r2, depth=h,
                                        location=loc)
        parts.append((bpy.context.object, mat))

    add_cyl(2.5, 0.5, (0.0, 0.0, 0.25), mat_lunar)             # regolith shielding berm
    add_cyl(0.9, 2.0, (0.0, 0.0, 1.0), mat_dark)               # reactor vessel
    add_cone(0.9, 0.5, 1.0, (0.0, 0.0, 2.5), mat_dark)         # conical top shield

    # 4 radiator fins fanning out at 0°/45°/90°/135° — each a flat slab
    for ang_deg in (0.0, 45.0, 90.0, 135.0):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 1.0))
        fin = bpy.context.object
        fin.scale = (2.8, 0.06, 1.6)
        fin.rotation_euler = (0.0, 0.0, math.radians(ang_deg))
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        parts.append((fin, mat_silver))

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = 'fsp_reactor'
    body.data.name = 'fsp_reactor'
    return body


player = find_by_class('player')
if player:
    player.name = 'Player'
    player.location = PLAYER_SPAWN
    player['wf_Mobility']             = 'Physics'
    player['wf_Mass']                 = 80.0       # ~80 kg astronaut
    player['wf_Model Type']           = 'Mesh'
    player['wf_Visibility Mailbox']   = 1891   # MOON_PLAYER_VIS: 1=visible, 0=hidden in vehicle
    # Use the built astronaut mesh — already 1.8 m tall in mesh-local coords
    # with feet at z=0. No actor-side scale (the old 1.8×1.8×1.8 blanket scale
    # was a cube-shaped placeholder).
    player.data = _astronaut.data
    bpy.data.objects.remove(_astronaut, do_unlink=True)
    player.scale = (1.0, 1.0, 1.0)
    # Walking on the Moon at ~1 m/s — slower than SMB Mario.
    player['wf_Running Acceleration']  = 8.0
    player['wf_Running Deceleration']  = 0.85
    player['wf_Max Ground Speed']      = 2.5       # m/s
    player['wf_Jumping Acceleration']  = 15.0
    player['wf_Falling Acceleration']  = 1.62      # lunar g (set per-level in Phase 4)
    player['wf_Air Acceleration']      = 0.0
    player['wf_Max Air Speed']         = 8.0
    player['wf_Horiz Air Drag']        = 1.5
    player['wf_Turn Rate']             = 0.5             # rev/sec — LEFT/RIGHT rotate (180°/sec, full turn in 2s)
    player.rotation_euler.z            = math.pi / 2     # face +Y (into vista) at spawn
    # Doomstick 4-direction strafe (UP forward / DOWN back / LEFT-RIGHT strafe
    # since TurnRate=0). Raw passthrough — every bit (UP/DOWN/LEFT/RIGHT and A
    # for jump) flows into INPUT at its native position; movement.cc reads them
    # via the gDoomStick branch (the level's RAM FLAG sets gDoomStick=true).
    # See docs/plans/2026-05-31-doomstick-4-direction-strafe-input-on-the-moon-lev.md.
    # EJ_BUTTONF_B = (1 << EJ_BUTTONB_B) = (1 << 1) = 2 — B button, not used by
    # movement so safe as the vehicle interact / enter-exit button.
    _INTERACT_BIT = 2
    player['wf_Script'] = (
        "\\ wf\n"
        # ── On-foot mode ───────────────────────────────────────────────────────
        # Seed visibility, run normal locomotion, handle launch sequence and
        # camera cuts. Skip all of this when the player is inside a vehicle.
        "INDEXOF_MOON_ACTIVE_VEHICLE read-mailbox 0 = if\n"
        "1 INDEXOF_MOON_PLAYER_VIS write-mailbox\n"
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n"
        # Position HUD overlay.
        "1 INDEXOF_MOON_OVERLAY_ENABLED write-mailbox\n"
        "INDEXOF_X_POS read-mailbox INDEXOF_MOON_PLAYER_X write-mailbox\n"
        "INDEXOF_Y_POS read-mailbox INDEXOF_MOON_PLAYER_Y write-mailbox\n"
        "INDEXOF_Z_POS read-mailbox INDEXOF_MOON_PLAYER_Z write-mailbox\n"
        "INDEXOF_ROTATION_C read-mailbox INDEXOF_MOON_PLAYER_HEADING write-mailbox\n"
        # Launch sequence.
        "INDEXOF_TIME read-mailbox "
        "dup 10 < if "
        "1 INDEXOF_MOON_LAUNCH_PHASE write-mailbox "
        "10 swap - INDEXOF_MOON_LAUNCH_T_MINUS write-mailbox "
        "else dup 11 < if drop 2 INDEXOF_MOON_LAUNCH_PHASE write-mailbox "
        "0 INDEXOF_MOON_LAUNCH_T_MINUS write-mailbox "
        "else 3 INDEXOF_MOON_LAUNCH_PHASE write-mailbox "
        "11 - INDEXOF_MOON_LAUNCH_T_MINUS write-mailbox "
        "then then\n"
        # Camera cuts (unchanged).
        "INDEXOF_MOON_LAUNCH_PHASE read-mailbox 1 > if "
        "INDEXOF_MOON_LAUNCH_PHASE read-mailbox 2 > if "
        "INDEXOF_MOON_LAUNCH_T_MINUS read-mailbox 20 > if "
        "INDEXOF_MOON_CHASE_CAM_IDX read-mailbox dup 0 = if drop else INDEXOF_CAMSHOT write-mailbox then "
        "else "
        "INDEXOF_MOON_EARTH_CAM_IDX read-mailbox dup 0 = if drop else INDEXOF_CAMSHOT write-mailbox then "
        "then "
        "else "
        "INDEXOF_MOON_EARTH_CAM_IDX read-mailbox dup 0 = if drop else INDEXOF_CAMSHOT write-mailbox then "
        "then "
        "else "
        "INDEXOF_MOON_EARTH_CAM_IDX read-mailbox dup 0 = if drop else INDEXOF_CAMSHOT write-mailbox then "
        "then\n"
        # Enter vehicle: adjacent (ActBox wrote MOON_NEARBY_VEHICLE) + B button.
        "INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 0 > if\n"
        f"INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox {_INTERACT_BIT} & 0 > if\n"
        "INDEXOF_MOON_NEARBY_VEHICLE read-mailbox INDEXOF_MOON_ACTIVE_VEHICLE write-mailbox\n"
        "0 INDEXOF_MOON_PLAYER_VIS write-mailbox\n"
        "0 INDEXOF_INPUT write-mailbox\n"
        # Resolve vehicle ID (1/2/3) → actual actor index → MOON_ACTIVE_VEH_IDX.
        "INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 1 = if\n"
        "INDEXOF_MOON_CRUISER_0_IDX read-mailbox INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox then\n"
        "INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 2 = if\n"
        "INDEXOF_MOON_CRUISER_1_IDX read-mailbox INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox then\n"
        "INDEXOF_MOON_NEARBY_VEHICLE read-mailbox 3 = if\n"
        "INDEXOF_MOON_CRUISER_2_IDX read-mailbox INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox then\n"
        "then then\n"   # close NEARBY_VEHICLE > 0 and outer on-foot if
        # ── In-vehicle mode ────────────────────────────────────────────────────
        "else\n"
        "0 INDEXOF_INPUT write-mailbox\n"
        # Snap player to vehicle so cs_chase tracks the vehicle.
        "INDEXOF_MOON_VEHICLE_X read-mailbox INDEXOF_X_POS write-mailbox\n"
        "INDEXOF_MOON_VEHICLE_Y read-mailbox INDEXOF_Y_POS write-mailbox\n"
        "INDEXOF_MOON_VEHICLE_Z read-mailbox INDEXOF_Z_POS write-mailbox\n"
        # Input routing: the vehicle's own script reads HARDWARE_JOYSTICK1_RAW
        # and writes to its own local INDEXOF_INPUT — no write-actor-mailbox needed
        # (cross-actor mailbox write fails range check since INPUT index differs per actor).
        # Exit on B button.
        f"INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox {_INTERACT_BIT} & 0 > if\n"
        "0 INDEXOF_MOON_ACTIVE_VEHICLE write-mailbox\n"
        "0 INDEXOF_MOON_ACTIVE_VEH_IDX write-mailbox\n"
        "1 INDEXOF_MOON_PLAYER_VIS write-mailbox\n"
        "then\n"
        "then\n"   # close outer on-foot/in-vehicle if-else
    )

# ── 6b. Artemis lander (Starship HLS) ────────────────────────────────────────
# Real actor, not background scenery — uses class 'platform' (movable actor),
# Mobility='Anchored' for v1 so it sits still. Future launch sequence (v2) can
# flip the mobility or drive position via script. See
# docs/plans/2026-05-31-moon-artemis-lander.md.

_lander = _build_artemis_lander()
attach_schema(_lander, 'platform')
_lander.location = (30.0, 25.0, 0.0)
_lander['wf_Mobility']            = 'Anchored'
_lander['wf_Model Type']          = 'Mesh'
_lander['wf_Visibility Mailbox']  = 1
_lander['wf_Moves Between Rooms'] = 'True'   # prop, not terrain — goes in PERM atlas
# Launch sequence script: when phase ≥ 3 (ascent), compute Z from quadratic
# t² curve and write to own Z_POS. See
# docs/plans/2026-06-02-moon-lander-launch-sequence.md.
_lander['wf_Script'] = (
    "\\ wf\n"
    "INDEXOF_MOON_LAUNCH_PHASE read-mailbox 2 > if "    # >2 == >=3 (zForth lacks >=)
    "INDEXOF_MOON_LAUNCH_T_MINUS read-mailbox dup * 0.5 * "
    "dup INDEXOF_MOON_LANDER_Z write-mailbox "          # publish z for launch_tracker proxy
    "dup 500 > if "                                     # z > 500 m → despawn (t≈32 s)
    "drop 0 INDEXOF_ALIVE write-mailbox "
    "else "
    "INDEXOF_Z_POS write-mailbox "
    "then "
    "then\n"
)
print(f"[moon] lander mesh: {len(_lander.data.vertices)} verts, "
      f"{len(_lander.data.polygons)} polys at {_lander.location[:]}")

# ── 6c. Earth in the lunar sky ────────────────────────────────────────────────
# Real NASA Blue Marble texture (earth.tga, 128×64) on a UV sphere R=20 m.
# Placed 301 m from the camera so it subtends ~7.6° — large enough to read
# continents but not dominating the frame. Anchored so it never moves.
# See docs/investigations/2026-06-02-texture-lod-for-distant-spheres.md.
_earth = _build_earth()
attach_schema(_earth, 'platform')
_earth.location = (0.0, 2000.0, 400.0)
_earth['wf_Mobility']             = 'Anchored'
_earth['wf_Model Type']           = 'Mesh'
_earth['wf_Visibility Mailbox']   = 1
_earth['wf_Moves Between Rooms']  = 'True'   # routes texture to PERM atlas (Room0 is full)
print(f"[moon] Earth sphere at {_earth.location[:]}")

# ── 6d. Surface assets ───────────────────────────────────────────────────────
# All use class 'platform' (movable actor) with Mobility='Anchored' for now.
# Vehicles will be hooked to Jolt vehicle physics when controls are added.
# See docs/plans/2026-06-03-moon-site-01-surface-asset-models.md.

def _place_prop(obj, loc, mobility='Anchored', name=None):
    """Wire a surface-asset mesh as a platform actor and place it."""
    attach_schema(obj, 'platform')
    obj.location                  = loc
    obj['wf_Mobility']            = mobility
    obj['wf_Model Type']          = 'Mesh'
    obj['wf_Visibility Mailbox']  = 1
    obj['wf_Moves Between Rooms'] = 'True'
    tag = name or obj.name
    print(f"[moon] {tag} ({mobility}) at {obj.location[:]}, "
          f"{len(obj.data.vertices)} verts, {len(obj.data.polygons)} polys")


def _add_entry_trigger(cx, cy, cz, vehicle_id):
    """Anchored ActBox beside the Cruiser +X airlock face.
    Writes MOON_NEARBY_VEHICLE = vehicle_id on entry, 0 on exit.
    Activated Actor Mailbox set to 4005 (default 0 aborts — see TODO.md)."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx + 5.5, cy, cz + 2.0))
    trig = bpy.context.object
    trig.scale = (3.0, 4.0, 2.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    attach_schema(trig, 'actbox')
    trig['wf_Activated By']            = 'All'
    trig['wf_MailBox']                 = 1889     # MOON_NEARBY_VEHICLE
    trig['wf_MailBoxValue']            = float(vehicle_id)
    trig['wf_ClearOnExit']             = 'True'
    trig['wf_Mailbox Exit Value']      = 0.0
    trig['wf_Activated Actor Mailbox'] = 4005
    trig['wf_Mobility']                = 'Anchored'
    trig.name = f'entry_trigger_{vehicle_id}'
    print(f"[moon] entry_trigger_{vehicle_id} at {trig.location[:]}")


def _build_sun():
    """Visible sun disc — UV sphere R=8 m along the directional-light vector at
    SUN_DIST_M from origin.  White/yellow material so the texture-gate branch
    in backend_modern.cc's fragment shader keeps it bright."""
    sun_az  = math.radians(SUN_AZ_DEG)
    sun_alt = math.radians(SUN_ALT_DEG)
    sx = math.cos(sun_alt) * math.sin(sun_az) * SUN_DIST_M
    sy = math.cos(sun_alt) * math.cos(sun_az) * SUN_DIST_M
    sz = math.sin(sun_alt)                     * SUN_DIST_M
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=8.0, segments=16, ring_count=8,
        location=(sx, sy, sz))
    obj = bpy.context.object
    obj.name      = 'sun_disc'
    obj.data.name = 'sun_disc'
    mat = bpy.data.materials.new('sun_mat')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1.0, 0.98, 0.88, 1.0)  # warm white
    mat.diffuse_color = (1.0, 0.98, 0.88, 1.0)
    obj.data.materials.append(mat)
    print(f"[moon] sun_disc at ({sx:.1f}, {sy:.1f}, {sz:.1f}), R=8 m")
    return obj


def _build_skydome():
    """Star-field skydome — UV sphere R=2000 m, normals flipped so the inner
    surface is visible.  starfield.tga (512x256) equirectangular map.

    Depth safety: minimum distance from camera (0,-100,80) to the sphere
    surface is ≈1872 m; maximum terrain distance is ≈785 m → terrain always
    wins the depth test (closer = lower depth value).  Yon=2500 m lets the
    skydome reach the far clip.  No engine changes required.

    See docs/plans/2026-06-01-moon-sky-earth-in-frame-sun-disc-starfield-skydome.md."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=2000.0, segments=32, ring_count=16,
        location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name      = 'skydome'
    obj.data.name = 'skydome'

    # Flip all normals so the inner (concave) surface is the visible face.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    # starfield.tga — equirectangular star map.  White diffuse base so the
    # WF shader's texture-gate (step(0.99,min(rgb))) passes the texture through.
    mat = bpy.data.materials.new('skydome_mat')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = bpy.data.images.load(os.path.join(SCRIPT_DIR, 'starfield.tga'))
    mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    obj.data.materials.append(mat)
    print(f"[moon] skydome R=2000 m, {len(obj.data.vertices)} verts, "
          f"{len(obj.data.polygons)} polys")
    return obj


# Non-vehicle props — all clamped to terrain.
_racer = _build_moon_racer()
_place_prop(_racer, (15.0,  20.0,  terrain_z(15.0,  20.0)))

_vsat = _build_vsat_tower()
_place_prop(_vsat,  (60.0,  40.0,  terrain_z(60.0,  40.0)))

_mk1 = _build_blue_moon_mk1()
_place_prop(_mk1,   (-40.0, -15.0, terrain_z(-40.0, -15.0)))

_fsh = _build_fsh()
_place_prop(_fsh,   (-55.0,  55.0, terrain_z(-55.0,  55.0)))

_fsp = _build_fsp_reactor()
_place_prop(_fsp,   (-90.0,  80.0, terrain_z(-90.0,  80.0)))

# Lunar Cruisers — shared mesh, MOBILITY_VEHICLE, entry ActBox each.
# Three Cruisers share one mesh datablock → one .iff entry in the room pool.
_CRUISER_XY = [(-20.0, 35.0), (-50.0, 0.0), (10.0, -40.0)]
_cruiser_mesh = _build_lunar_cruiser()
_cruiser_mesh.name      = 'lunar_cruiser_0'
_cruiser_mesh.data.name = 'lunar_cruiser_0'

_c1 = bpy.data.objects.new('lunar_cruiser_1', _cruiser_mesh.data)
bpy.context.scene.collection.objects.link(_c1)
_c2 = bpy.data.objects.new('lunar_cruiser_2', _cruiser_mesh.data)
bpy.context.scene.collection.objects.link(_c2)

for _i, (_cobj, (_cx, _cy)) in enumerate(
        zip([_cruiser_mesh, _c1, _c2], _CRUISER_XY)):
    _cz = terrain_z(_cx, _cy)
    _place_prop(_cobj, (_cx, _cy, _cz), mobility='Vehicle',
                name=f'lunar_cruiser_{_i}')
    _cidx_mb = 1886 + _i   # MOON_CRUISER_0/1/2_IDX
    _cobj['wf_Script'] = (
        "\\ wf\n"
        # Publish own actor index every tick (needed for entry resolve in player script).
        f"INDEXOF_ACTOR_INDEX read-mailbox {_cidx_mb} write-mailbox\n"
        # When I am the active vehicle: route joystick to own INPUT and publish position.
        # Reading HARDWARE_JOYSTICK1_RAW is safe here — it is a global mailbox (index 1909)
        # accessible to all actors. Writing to INDEXOF_INPUT writes to THIS actor's local
        # INPUT mailbox (within [vehicle_base, vehicle_base+N]), which is what MovementHandlerVehicle
        # reads via GetInputDevice(). This avoids the cross-actor write-actor-mailbox range trap.
        "INDEXOF_MOON_ACTIVE_VEH_IDX read-mailbox INDEXOF_ACTOR_INDEX read-mailbox = if\n"
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n"
        "INDEXOF_X_POS read-mailbox INDEXOF_MOON_VEHICLE_X write-mailbox\n"
        "INDEXOF_Y_POS read-mailbox INDEXOF_MOON_VEHICLE_Y write-mailbox\n"
        "INDEXOF_Z_POS read-mailbox INDEXOF_MOON_VEHICLE_Z write-mailbox\n"
        "then\n"
    )
    _add_entry_trigger(_cx, _cy, _cz, _i + 1)   # vehicle_id 1/2/3

_sun = _build_sun()
attach_schema(_sun, 'platform')
_sun['wf_Mobility']            = 'Anchored'
_sun['wf_Model Type']          = 'Mesh'
_sun['wf_Visibility Mailbox']  = 1
_sun['wf_Moves Between Rooms'] = 'True'

_dome = _build_skydome()
attach_schema(_dome, 'platform')
_dome['wf_Mobility']            = 'Anchored'
_dome['wf_Model Type']          = 'Mesh'
_dome['wf_Visibility Mailbox']  = 1
_dome['wf_Moves Between Rooms'] = 'True'

# ── 7. Camera ────────────────────────────────────────────────────────────────
target = find_by_class('target')
if target:
    target.name = 'CamTarget'
    target.location = LOOK_TARGET

# Pre-position the camera actor at the camshot location so BungeeCameraHandler
# doesn't have to spring it from the snowgoons-imported default (10, -40, 8)
# to the vista camshot at (0, -75, 50) over multiple frames — at large
# distances the bungee can take many seconds to converge, and the
# WF_GAME_SCREENSHOT_PPM dump fires at frame 30.
camera_actor = find_by_class('camera')
if camera_actor:
    camera_actor.location = (PLAYER_SPAWN[0] + CAM_OFFSET[0],
                             PLAYER_SPAWN[1] + CAM_OFFSET[1],
                             PLAYER_SPAWN[2] + CAM_OFFSET[2])
    # Snowgoons inherits a fog setup tuned for Earth atmosphere (start 20 m,
    # complete 30 m, mid-grey #888888) — at vista distances this fogs the
    # entire terrain to flat grey. The Moon has no atmosphere; push fog far
    # beyond the 1000 m far clip so it never affects rendering. Black fog
    # colour matches the space-black sky in case it does kick in.
    camera_actor['wf_FoggingColor']            = 0x000000
    camera_actor['wf_FoggingStartDistance']    = 999.0
    camera_actor['wf_FoggingCompleteDistance'] = 1000.0

camshot = find_by_class('camshot')
if camshot:
    camshot.name = 'cs_chase'
    camshot.location = (PLAYER_SPAWN[0] + CAM_OFFSET[0],
                        PLAYER_SPAWN[1] + CAM_OFFSET[1],
                        PLAYER_SPAWN[2] + CAM_OFFSET[2])
    # Mirror smb_w1_1's static-camera setup: absolute world position, fixed
    # rotation, look at a Target actor. (Relative positioning seems to leave
    # the BungeeCameraHandler in an inconsistent state during init.)
    camshot['wf_Position X'] = 'Absolute'
    camshot['wf_Position Y'] = 'Absolute'
    camshot['wf_Position Z'] = 'Absolute'
    camshot['wf_Rotation']   = 'Fixed'
    camshot['wf_FOV']                 = 60.0
    camshot['wf_Pan Time In Seconds'] = 0.1
    camshot['wf_Model Type']          = 'None'
    camshot['wf_Track Object'] = 'Player'
    camshot['wf_Target']       = 'CamTarget'
    camshot['wf_Follow']       = 'CamTarget'
    camshot['wf_Yon']          = 2500.0  # skydome R=2000 m; default 100 m clips it
    camshot['wf_Moves Between Rooms'] = 'True'
    # Publish own actor index so player script can restore chase cam after cutscene.
    camshot['wf_Script'] = (
        "\\ wf\n"
        "INDEXOF_ACTOR_INDEX read-mailbox INDEXOF_MOON_CHASE_CAM_IDX write-mailbox\n"
    )

# ── launch_tracker — invisible proxy actor for cs_earth Track Object ──────────
# cs_earth can't track artemis_lander directly: both are in PERM and
# GetObject(lander_idx) returns null at runtime (cross-PERM timing).
# launch_tracker is a room actor (not PERM) so GetObject finds it reliably.
# Its script reads MOON_LANDER_Z (written by the lander each frame) and
# copies it to own Z_POS, keeping the camera look-at on the rising lander.
# See docs/plans/2026-06-03-moon-earth-cutscene.md.
tracker_mesh = bpy.data.meshes.new('launch_tracker_mesh')
tracker_obj  = bpy.data.objects.new('launch_tracker', tracker_mesh)
bpy.context.scene.collection.objects.link(tracker_obj)
attach_schema(tracker_obj, 'platform')
tracker_obj.location = (30.0, 25.0, 0.0)   # same XY as lander
tracker_obj['wf_Mobility']   = 'Anchored'
tracker_obj['wf_Model Type'] = 'None'
tracker_obj['wf_Script'] = (
    "\\ wf\n"
    "INDEXOF_MOON_LANDER_Z read-mailbox INDEXOF_Z_POS write-mailbox\n"
)

# ── cs_earth — low telephoto shot behind lander for launch cutscene ───────────
# Position (30, -80, 5): 105 m behind lander, 5 m above ground.
# Tracks launch_tracker (room actor proxy) so camera tilts up as lander ascends.
# FOV 40° (telephoto) compresses lander+Earth into same frame.
# Triggered at phase ≥ 2 (ignition onward) by player Forth script via
# EMAILBOX_CAMSHOT (1921). See docs/plans/2026-06-03-moon-earth-cutscene.md.
cs_earth_data = bpy.data.meshes.new('cs_earth_mesh')
cs_earth_obj  = bpy.data.objects.new('cs_earth', cs_earth_data)
bpy.context.scene.collection.objects.link(cs_earth_obj)
attach_schema(cs_earth_obj, 'camshot')
cs_earth_obj.location = (30.0, -80.0, 5.0)
cs_earth_obj['wf_Position X']          = 'Absolute'
cs_earth_obj['wf_Position Y']          = 'Absolute'
cs_earth_obj['wf_Position Z']          = 'Absolute'
cs_earth_obj['wf_Rotation']            = 'Fixed'
cs_earth_obj['wf_FOV']                 = 40.0
cs_earth_obj['wf_Pan Time In Seconds'] = 0.5
cs_earth_obj['wf_Model Type']          = 'None'
cs_earth_obj['wf_Track Object']        = 'launch_tracker'  # room actor — avoids PERM→PERM crash
cs_earth_obj['wf_Target']              = 'CamTarget'   # required non-null by movecam.cc:236
cs_earth_obj['wf_Follow']              = 'CamTarget'   # required non-null by movecam.cc:236
cs_earth_obj['wf_Yon']                 = 2500.0
cs_earth_obj['wf_Moves Between Rooms'] = 'True'
# Publish own actor index for player script camera switching.
cs_earth_obj['wf_Script'] = (
    "\\ wf\n"
    "INDEXOF_ACTOR_INDEX read-mailbox INDEXOF_MOON_EARTH_CAM_IDX write-mailbox\n"
)

# ── 8. Level object ──────────────────────────────────────────────────────────
# ── 7b. Room bounds ──────────────────────────────────────────────────────────
# Must enclose terrain extent + player jump headroom + camera offset so levcomp
# doesn't warn "actor falls outside every room bbox — it will not render".

room = find_by_class('room')
if room:
    z_min = float(heights.min()) - 10.0      # 10 m below lowest terrain pixel
    z_max = max(2000.0, float(heights.max()) + 50.0)  # headroom for lander ascent (z=0.5t²)
    centre = (0.0, 0.0, (z_min + z_max) / 2.0)
    # Y max extended to cover Earth actor at Y=2000 (PERM actors still need to
    # fall inside room bbox or levcomp won't associate them with any room).
    y_max = max(HALF_M + 10.0, 2100.0)
    rel = (-HALF_M - 10.0, -HALF_M - 10.0, z_min - centre[2],
           +HALF_M + 10.0, y_max, z_max - centre[2])

    room.name = 'room_moon'
    room.location = centre
    room['wf_original_bbox'] = rel

    # Replace the imported room-bounds mesh with one matching our rel-bbox.
    verts = [(rel[0], rel[1], rel[2]), (rel[3], rel[1], rel[2]),
             (rel[3], rel[4], rel[2]), (rel[0], rel[4], rel[2]),
             (rel[0], rel[1], rel[5]), (rel[3], rel[1], rel[5]),
             (rel[3], rel[4], rel[5]), (rel[0], rel[4], rel[5])]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    new_mesh = bpy.data.meshes.new('RoomBounds')
    new_mesh.from_pydata(verts, [], faces)
    new_mesh.update()
    old = room.data
    room.data = new_mesh
    if old and old.users == 0:
        bpy.data.meshes.remove(old)
    print(f"[moon] room bounds: centre {centre}, rel-bbox {rel}")

levelobj = find_by_class('levelobj')
if levelobj:
    levelobj['wf_Num Mailboxes'] = NUM_MAILBOXES
    # NB: WF gravity is per-actor via MovementBlock.FallingAcceleration,
    # not per-level. The player above already has FallingAcceleration=1.62
    # (lunar g). Jolt's global gravity is passed as zero to character
    # updates (jolt_backend.cc:744-745), so the backend default doesn't
    # leak through. No engine change needed for Tier 2.

# ── 9. Render preview (Phase 6 verification) ─────────────────────────────────
# Render a still from the camshot POV so we can eyeball what the engine should
# display — Blender's Eevee approximates the WF GL renderer closely enough for
# a sanity check (black sky + low-az sun direction).
preview_cam_data = bpy.data.cameras.new('PreviewCam')
preview_cam      = bpy.data.objects.new('PreviewCam', preview_cam_data)
scene.collection.objects.link(preview_cam)
preview_cam.location = (CAM_OFFSET[0], CAM_OFFSET[1], CAM_OFFSET[2])
# Aim at player spawn — translate look-vector to Euler.
import mathutils
direction = mathutils.Vector(LOOK_TARGET) - mathutils.Vector(preview_cam.location)
preview_cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
preview_cam_data.lens = 25  # ~70° FOV horizontally — closer to wf game cam
scene.camera = preview_cam

# Black world background — match the matte's space-black.
world = bpy.data.worlds.new('SpaceBlack') if 'SpaceBlack' not in bpy.data.worlds else bpy.data.worlds['SpaceBlack']
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
scene.world = world

scene.render.resolution_x = 800
scene.render.resolution_y = 600
scene.render.engine = 'BLENDER_EEVEE'
scene.render.image_settings.file_format = 'PNG'
PREVIEW_PNG = os.path.join(SCRIPT_DIR, 'preview.png')
scene.render.filepath = PREVIEW_PNG
try:
    bpy.ops.render.render(write_still=True)
    print(f"[moon] preview rendered → {PREVIEW_PNG}")
except Exception as e:
    print(f"[moon] preview render skipped: {e}")

# ── 10. Export ───────────────────────────────────────────────────────────────
# Remove the preview camera so it doesn't pollute the .lev export.
scene.collection.objects.unlink(preview_cam)
bpy.data.objects.remove(preview_cam)
bpy.data.cameras.remove(preview_cam_data)

print(f"[moon] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print(f"[moon] Done — {OUT_LEV}")
print("[moon] Objects in scene:", [o.name for o in bpy.data.objects])
