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

# ── Player (astronaut) — 1.8 m tall, WF unit = 1 m ───────────────────────────
PLAYER_HEIGHT = 1.8
# Spawn at centre of play area, 5 m above terrain centre (drop is the proof of
# collision). Centre vertex of the heightfield is at Z=0 by construction.
PLAYER_SPAWN  = (0.0, 0.0, 5.0)

# Camera: third-person from −Y. Tuned 2026-05-30 by iteration on engine
# screenshots: (0, -8, 3.5) was too low + close (player filled frame, no
# terrain visible); (0, -25, 18) was too high + far (player lost in distant
# terrain). (0, -12, 6) framing the player at ~25° downward angle works.
CAM_OFFSET    = (0.0, -12.0, 6.0)
LOOK_TARGET   = (PLAYER_SPAWN[0], PLAYER_SPAWN[1], 1.5)

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
    matte.location = (0.0, 0.0, 50.0)
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
    SUN_AZ_DEG  = 20.0
    SUN_ALT_DEG = 2.0
    light.rotation_euler = (math.pi / 2 - math.radians(SUN_ALT_DEG),
                            0.0,
                            math.radians(SUN_AZ_DEG))
    light['wf_lightType']  = 'Directional'
    light['wf_lightRed']   = 1.0
    light['wf_lightGreen'] = 1.0
    light['wf_lightBlue']  = 1.0

# ── 6. Player ────────────────────────────────────────────────────────────────
player = find_by_class('player')
if player:
    player.name = 'Player'
    player.location = PLAYER_SPAWN
    player['wf_Mobility']             = 'Physics'
    player['wf_Mass']                 = 80.0       # ~80 kg astronaut
    player['wf_Model Type']           = 'Mesh'
    player['wf_Visibility Mailbox']   = 1
    # 1.8 m astronaut. Player.location is feet; capsule extends +Z.
    player.scale = (PLAYER_HEIGHT, PLAYER_HEIGHT, PLAYER_HEIGHT)
    # Walking on the Moon at ~1 m/s — slower than SMB Mario.
    player['wf_Running Acceleration']  = 8.0
    player['wf_Running Deceleration']  = 0.85
    player['wf_Max Ground Speed']      = 2.5       # m/s
    player['wf_Jumping Acceleration']  = 15.0
    player['wf_Falling Acceleration']  = 1.62      # lunar g (set per-level in Phase 4)
    player['wf_Air Acceleration']      = 0.0
    player['wf_Max Air Speed']         = 8.0
    player['wf_Horiz Air Drag']        = 1.5
    player['wf_Turn Rate']             = 0.0
    player.rotation_euler.z            = math.pi / 2     # face +Y so LEFT/RIGHT are ±X
    # Joystick → INPUT mailbox. Same doom-stick mapping as smb_w1_1.
    player['wf_Script'] = (
        "\\ wf\n"
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox "
        "dup 16384 & 256 / over 8192 & 64 / | | "
        "INDEXOF_INPUT write-mailbox\n"
    )

# ── 7. Camera ────────────────────────────────────────────────────────────────
target = find_by_class('target')
if target:
    target.name = 'CamTarget'
    target.location = LOOK_TARGET

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

# ── 8. Level object ──────────────────────────────────────────────────────────
# ── 7b. Room bounds ──────────────────────────────────────────────────────────
# Must enclose terrain extent + player jump headroom + camera offset so levcomp
# doesn't warn "actor falls outside every room bbox — it will not render".

room = find_by_class('room')
if room:
    z_min = float(heights.min()) - 10.0      # 10 m below lowest terrain pixel
    z_max = max(50.0, float(heights.max()) + 50.0)  # headroom for jumps / cam
    centre = (0.0, 0.0, (z_min + z_max) / 2.0)
    rel = (-HALF_M - 10.0, -HALF_M - 10.0, z_min - centre[2],
           +HALF_M + 10.0, +HALF_M + 10.0, z_max - centre[2])

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
