"""Mockup renders for docs/plans/2026-11-13-snowgoons-one-acre-arena.md (plan stage, not the shipped asset).

Imports the classic snowgoons level (wflevels/snowgoons-blender/snowgoons.lev) with the wf_blender add-on,
prints the measured world-space extents, renders the current yard, then hides the 3ds Max arena
(statplat_2, quadpatch01.iff) and builds the proposed one-acre yard from the plan's numbers, with
the level's own textures, and renders it from the same cameras.

Run in the Blender container (CPU Cycles, no GL):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh \
    blender --background --python-exit-code 1 \
    --python docs/plans/2026-11-13-snowgoons-one-acre-arena/render_mockup.py -- <out-dir>

The geometry here only approximates the design so a reviewer can see it; the shipped mesh is written
by the generator the plan specifies (Phase 1), not by this script.
"""
import math
import os
import sys

import addon_utils
import bpy
from mathutils import Vector

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
LEVEL_DIR = os.path.join(REPO, "wflevels", "snowgoons-blender")
LEV = os.path.join(LEVEL_DIR, "snowgoons.lev")
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp"
SAMPLES = int(os.environ.get("MOCKUP_SAMPLES", "16"))
RES = (int(os.environ.get("MOCKUP_W", "1200")), int(os.environ.get("MOCKUP_H", "750")))

# ── The plan's recommended layout (option B), WF world metres ─────────────────
LAWN_X = (-30.0, 30.0)      # 60 m wide
LAWN_Y = (-46.0, 22.0)      # 68 m deep; north edge 6 m behind the house, a walkable path round it
LAWN_Z = -0.62              # the house's base (house.iff z_min -0.50 + actor z -0.12)
TILE = 4.0                  # one 32 px snowy-grass tile per 4 m cell
HEDGE_T, HEDGE_H = 2.0, 2.1  # current hedge band: 2 m thick, ~2.1 m above the lawn
SEG = 2.0                   # one hedge texture repeat per 2 m of hedge
PILLAR_W, PILLAR_H = 0.8, 4.2

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)
bpy.ops.wf.import_level(filepath=LEV)
scene = bpy.context.scene


def world_bounds(obj, mat_names=None):
    me = obj.data
    pts = []
    for poly in me.polygons:
        if mat_names is not None:
            m = me.materials[poly.material_index] if poly.material_index < len(me.materials) else None
            if m is None or not any(m.name.lower().startswith(n.lower()) for n in mat_names):
                continue
        pts += [obj.matrix_world @ me.vertices[i].co for i in poly.vertices]
    if not pts:
        return None
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


print("MEASURE ---------------------------------------------------------------")
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    if o.type == "MESH" and o.name.startswith(("statplat_1", "statplat_2", "statplat_3", "statplat_4", "player")) \
            and len(o.data.polygons) > 12:
        b = world_bounds(o)
        print(f"MEASURE {o.name:12s} loc={tuple(round(v, 2) for v in o.location)} "
              f"rot={tuple(round(v, 4) for v in o.rotation_euler)} "
              f"min={tuple(round(v, 2) for v in b[0])} max={tuple(round(v, 2) for v in b[1])}")
for name in ("statplat_15", "statplat_19", "statplat_20", "statplat_21", "statplat_22"):
    o = bpy.data.objects.get(name)
    if o is not None and o.type == "MESH":
        b = world_bounds(o)
        print(f"MEASURE collider {name} rot={tuple(round(v, 4) for v in o.rotation_euler)} "
              f"min={tuple(round(v, 2) for v in b[0])} max={tuple(round(v, 2) for v in b[1])}")
arena = bpy.data.objects["statplat_2"]
print("MEASURE arena materials:", [m.name for m in arena.data.materials][:10])
for label, mats in (("lawn", {"G_SnowyGrass11"}), ("hedge-top", {"G_HedgeWsnowTp"}),
                    ("hedge-side", {"G_HedgeWsnowSide"})):
    b = world_bounds(arena, mats)
    if b:
        print(f"MEASURE arena {label:10s} min={tuple(round(v, 2) for v in b[0])} max={tuple(round(v, 2) for v in b[1])}")

# Only the visible scenery takes part in the render: the arena, house, trees, player.
VISIBLE = {"statplat_1", "statplat_2", "statplat_3", "statplat_4", "player_33"}
for o in bpy.data.objects:
    o.hide_render = o.name not in VISIBLE
    o.hide_viewport = o.hide_render


def texture_material(tga, name=None):
    mat = bpy.data.materials.new(name or ("mock_" + tga))
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.95
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(LEVEL_DIR, tga), check_existing=True)
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"   # the engine clamps UVs to [0,1]; each face shows one copy
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def fix_imported_materials():
    """Imported WF materials: make sure textures clamp like the engine (CLIP01) and read as matte."""
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        for n in mat.node_tree.nodes:
            if n.type == "TEX_IMAGE":
                n.extension = "EXTEND"
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Roughness"].default_value = 0.95


fix_imported_materials()

# ── Lighting and render settings (CPU Cycles, the container has no GL) ────────
world = bpy.data.worlds.new("sky")
scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs["Color"].default_value = (0.55, 0.62, 0.72, 1.0)
bg.inputs["Strength"].default_value = 0.9
sun_data = bpy.data.lights.new("sun", "SUN")
sun_data.energy = 2.6
sun_data.angle = math.radians(3)
sun = bpy.data.objects.new("sun", sun_data)
sun.rotation_euler = (math.radians(50), 0.0, math.radians(35))
scene.collection.objects.link(sun)

try:
    scene.render.engine = "CYCLES"
except TypeError as e:
    print("engine list:", e)
    raise
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"


def add_camera(name, loc, look_at, lens=24.0):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.clip_end = 1000.0
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = loc
    d = Vector(look_at) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(cam)
    return cam


# Drone view from behind the south-east corner of the NEW yard, so the same camera frames both.
drone = add_camera("drone", (44.0, -66.0, 46.0), (-2.0, -10.0, 0.0), lens=22.0)
# Roughly the game's opening: bungee camera a few metres behind and above the player (-1, -0.1).
game = add_camera("game", (-5.0, -11.0, 3.4), (2.0, 10.0, 0.4), lens=20.0)


def render(cam, name):
    scene.camera = cam
    scene.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)


render(drone, "drone-before.png")
render(game, "game-before.png")

# ── Proposed yard ──────────────────────────────────────────────────────────────
arena.hide_render = True
grass = texture_material("G_SnowyGrass11.tga")
side = texture_material("G_HedgeWsnowSide.tga")
top = texture_material("G_HedgeWsnowTp.tga")

verts, faces, uvs, mats = [], [], [], []


def quad(p0, p1, p2, p3, mat, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
    base = len(verts)
    verts.extend([p0, p1, p2, p3])
    faces.append((base, base + 1, base + 2, base + 3))
    uvs.append(uv)
    mats.append(mat)


z0 = LAWN_Z
nx = round((LAWN_X[1] - LAWN_X[0]) / TILE)
ny = round((LAWN_Y[1] - LAWN_Y[0]) / TILE)
for i in range(nx):
    for j in range(ny):
        x0, y0 = LAWN_X[0] + i * TILE, LAWN_Y[0] + j * TILE
        # Mirrored tiling: alternate cells flip U/V so shared edges match (what the generator does with
        # shared vertices). One texture, the current lawn's G_SnowyGrass11: the other "SnowyGrass"
        # files are green grass or grass-with-snow-edge transitions and read as a checkerboard.
        u0, u1 = (0, 1) if i % 2 == 0 else (1, 0)
        v0, v1 = (0, 1) if j % 2 == 0 else (1, 0)
        m = 0
        quad((x0, y0, z0), (x0 + TILE, y0, z0), (x0 + TILE, y0 + TILE, z0), (x0, y0 + TILE, z0), m,
             ((u0, v0), (u1, v0), (u1, v1), (u0, v1)))

zt = z0 + HEDGE_H


def hedge_run(a, b, inward):
    """Hedge along the lawn edge from a to b (2D); `inward` is the unit normal pointing at the lawn."""
    ax, ay = a
    bx, by = b
    length = math.hypot(bx - ax, by - ay)
    n = max(1, round(length / SEG))
    ox, oy = -inward[0] * HEDGE_T, -inward[1] * HEDGE_T
    for k in range(n):
        t0, t1 = k / n, (k + 1) / n
        p0 = (ax + (bx - ax) * t0, ay + (by - ay) * t0)
        p1 = (ax + (bx - ax) * t1, ay + (by - ay) * t1)
        # Inner face (faces the lawn) and top.
        quad((p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], zt), (p0[0], p0[1], zt), 1)
        quad((p0[0], p0[1], zt), (p1[0], p1[1], zt), (p1[0] + ox, p1[1] + oy, zt), (p0[0] + ox, p0[1] + oy, zt), 2)


(x0, x1), (y0, y1) = LAWN_X, LAWN_Y
hedge_run((x0, y0), (x1, y0), (0, 1))
hedge_run((x1, y0), (x1, y1), (-1, 0))
hedge_run((x1, y1), (x0, y1), (0, -1))
hedge_run((x0, y1), (x0, y0), (1, 0))
# Corner squares of the hedge band (top only) and pillars, as the current arena has.
for cx, cy, sx, sy in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x1, y1, 1, 1), (x0, y1, -1, 1)):
    ex, ey = cx + sx * HEDGE_T, cy + sy * HEDGE_T
    quad((min(cx, ex), min(cy, ey), zt), (max(cx, ex), min(cy, ey), zt), (max(cx, ex), max(cy, ey), zt),
         (min(cx, ex), max(cy, ey), zt), 2)
    px, py = cx + sx * HEDGE_T / 2, cy + sy * HEDGE_T / 2
    h = PILLAR_W / 2
    zp = z0 + PILLAR_H
    c = [(px - h, py - h), (px + h, py - h), (px + h, py + h), (px - h, py + h)]
    for k in range(4):
        a, b = c[k], c[(k + 1) % 4]
        quad((a[0], a[1], zt), (b[0], b[1], zt), (b[0], b[1], zp), (a[0], a[1], zp), 1)
    quad((c[0][0], c[0][1], zp), (c[1][0], c[1][1], zp), (c[2][0], c[2][1], zp), (c[3][0], c[3][1], zp), 2)

me = bpy.data.meshes.new("yard_mock")
me.from_pydata(verts, [], faces)
me.update()
uvl = me.uv_layers.new(name="UVMap")
for poly, uv, m in zip(me.polygons, uvs, mats):
    poly.material_index = m
    for k, li in enumerate(poly.loop_indices):
        uvl.data[li].uv = uv[k]
for m in (grass, side, top):
    me.materials.append(m)
yard = bpy.data.objects.new("yard_mock", me)
scene.collection.objects.link(yard)
print(f"MOCK yard faces(quads)={len(faces)} lawn cells={nx}x{ny} area={(x1 - x0) * (y1 - y0):.0f} m2")

# The mock lawn sits at the house's base; the classic actors keep their places.
render(drone, "drone-after.png")
render(game, "game-after.png")
print("DONE")
