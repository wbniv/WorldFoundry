"""
blender_create_aquarium_idle.py — standalone spike level for the clownfish idle animation.

A dark-blue backdrop, a sand strip, a static side-on camera and the canonical
clownfish (wflevels/aquarium/clownfish.py): an invisible Physics `Player` hull plus
five Mass-0 statplat parts that the Director poses every tick from Forth.

Usage:
    task aquarium-idle-level                 # this script + build_level_binary.sh
    task run-aquarium-idle
    IDLE_PROBE=1 → builds `aquarium_idle_probe` instead: the ROTATION_* write probe
    (a visible Physics fish writing its own ROTATION_C, a statplat rotated by the
    Director, an anchored platform rotating itself). `task aquarium-idle-probe-level`.

Pattern: wflevels/moon_site01/blender_create_moon.py and
wflevels/condo_639_640/blender_create_condo.py — import the snowgoons scaffold, keep
one actor of each infrastructure class and rename it, add our geometry, export.

Plan: docs/plans/2026-09-30-clownfish-idle-animation.md
"""

import math
import os
import sys

import addon_utils
import bpy

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OAD_DIR = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
PROBE = os.environ.get('IDLE_PROBE', '') not in ('', '0', 'false', 'False')
LEVEL_NAME = 'aquarium_idle_probe' if PROBE else 'aquarium_idle'
OUT_DIR = os.path.join(REPO, 'wflevels', LEVEL_NAME)
OUT_LEV = os.path.join(OUT_DIR, LEVEL_NAME + '.lev')

sys.path.insert(0, os.path.join(REPO, 'wflevels', 'aquarium'))
import clownfish  # noqa: E402  the canonical fish

FISH = clownfish.Clownfish(world_scale=clownfish.DEFAULT_WORLD_SCALE)

# ── Level constants (metres; WF == Blender axes: X right, Y depth, Z up) ──────
SPAWN = (0.0, 0.0, 1.0)             # body origin of the fish; mid-water
CAM_DIST = 2.2 if PROBE else 1.45   # camera on -Y, side-on. Hither is a fixed 1.0 m (display.cc)
LOOK_AT = (0.3, 0.0, 1.0) if PROBE else (0.0, 0.0, 1.03)
BACKDROP_Y = 2.5
SAND_TOP = 0.30
WATER_BLUE = (0.035, 0.12, 0.23)    # backdrop; matte and fog use the same colour
SAND = (0.80, 0.70, 0.48)
FOG_RGB = 0x092040
FOG_START, FOG_END = 6.0, 40.0      # aquarium plan § 7 values at ×10; nothing here is past 3 m
SUN_ALT_DEG, SUN_AZ_DEG = 50.0, 115.0   # from the camera side and above (condo convention, verified by capture)
AMBIENT = (0.40, 0.42, 0.50)
ROOM_CENTRE = (0.0, 0.5, 1.5)
ROOM_HALF = (6.0, 6.0, 4.0)
# Runtime actor index = position in the exporter's list + this bias (condo § 9c;
# measured with `wf_game --debug-print-actors`, asserted by tests/test_aquarium_idle.py).
ACTOR_IDX_BIAS = int(os.environ.get('IDLE_ACTOR_IDX_BIAS', '1'))
PROBE_REV = 0.125                   # probe heading: 45°

# ── 1. Clean scene, enable add-on, import the snowgoons scaffold ─────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)
if not hasattr(bpy.ops.wf, 'import_level'):
    raise SystemExit("[aquarium_idle] wf_blender add-on not available")
scene = bpy.context.scene
bpy.ops.wf.import_level(filepath=SNOWGOONS)

KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light', 'room', 'camshot', 'target', 'player'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


def find_by_class(cn):
    return next((o for o in bpy.data.objects if get_class(o) == cn), None)


for obj in list(bpy.data.objects):
    if get_class(obj) not in KEEP_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in seen:
        bpy.data.objects.remove(obj, do_unlink=True)
    else:
        seen.add(cn)
print("[aquarium_idle] scaffold classes:", sorted({get_class(o) for o in bpy.data.objects}))

MATERIALS = {}


def flat_material(name, rgb):
    if name not in MATERIALS:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
        mat.diffuse_color = (*rgb, 1.0)
        MATERIALS[name] = mat
    return MATERIALS[name]


def statplat(obj, mass=0.0):
    obj['wf_schema_path'] = os.path.join(OAD_DIR, 'statplat.oad')
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Mass'] = float(mass)
    obj['wf_original_mesh_name'] = clownfish.mesh_file(obj.name)
    return obj


def box(name, x0, y0, z0, x1, y1, z1, rgb, mass=0.0, centred=False):
    """Axis-aligned box actor, outward faces. centred=True puts the origin at the box centre."""
    c = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) if centred else (0.0, 0.0, 0.0)
    v = [(x - c[0], y - c[1], z - c[2]) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    me.update()
    me.materials.append(flat_material(name + '-mat', rgb))
    obj = bpy.data.objects.new(name, me)
    obj.location = c
    scene.collection.objects.link(obj)
    return statplat(obj, mass)


# ── 2. Backdrop and sand ─────────────────────────────────────────────────────
backdrop = box('backdrop', -6.0, BACKDROP_Y, -1.0, 6.0, BACKDROP_Y + 0.1, 5.0, WATER_BLUE)
sand = box('sand', -4.0, -0.4, SAND_TOP - 0.25, 4.0, 2.0, SAND_TOP, SAND, mass=75.0)   # solid: Jolt trimesh

# ── 3. The fish ──────────────────────────────────────────────────────────────
player = find_by_class('player')
assert player is not None, "snowgoons scaffold has no player"
player.name = 'Player'
parts = FISH.parts()
player.data = FISH.blender_mesh(bpy, FISH.body_mesh(clownfish.PLAYER_MESH), MATERIALS)   # hull = body shape
player.location = SPAWN if not PROBE else (-0.45, 0.0, SPAWN[2])
player.rotation_euler = (0.0, 0.0, 0.0)          # faces +X; the rig owns the visual heading
player.scale = (1.0, 1.0, 1.0)
# Invisible collision hull with Phase 1's controls and an authored symmetric box ≥ 0.25 m
# per side (the five parts are what you see; in the probe the hull IS the fish).
FISH.apply_player_fields(player, visible=PROBE)

part_objs = []
if not PROBE:
    for name, mesh, off in parts:
        obj = bpy.data.objects.new(name, FISH.blender_mesh(bpy, mesh, MATERIALS))
        obj.location = tuple(s + o for s, o in zip(SPAWN, off))    # rest pose; the Director moves it
        scene.collection.objects.link(obj)
        # Anchored PLATFORM, Mass 0 — not statplat: every StatPlat gets a Jolt static body
        # whatever its Mass (actor.cc:747-762, :543-593), and a statplat body part pinned
        # the Player's capsule (2026-09-30). See clownfish.py's docstring.
        clownfish.apply_part_actor_fields(obj)
        part_objs.append(obj)
    print(f"[aquarium_idle] clownfish ×{FISH.world_scale:g}: {FISH.length_m:.3f} m, parts "
          + ', '.join(f"{o.name} {len(o.data.polygons)}f" for o in part_objs))

# ── 3b. Probe actors (IDLE_PROBE=1) ──────────────────────────────────────────
probe_statplat = probe_platform = None
if PROBE:
    probe_statplat = box('probe-statplat', 0.13, -0.04, 0.9, 0.57, 0.04, 1.1, (0.30, 0.75, 0.95), centred=True)
    probe_platform = box('probe-platform', 0.73, -0.04, 0.9, 1.17, 0.04, 1.1, (0.95, 0.80, 0.30), centred=True)
    probe_platform['wf_schema_path'] = os.path.join(OAD_DIR, 'platform.oad')
    probe_platform['wf_Mobility'] = 'Anchored'
    probe_platform['wf_Mass'] = 0.0
    probe_platform['wf_Script'] = (
        "\\ wf\n"
        f"0 INDEXOF_ROTATION_A write-mailbox 0 INDEXOF_ROTATION_B write-mailbox "
        f"{PROBE_REV} INDEXOF_ROTATION_C write-mailbox\n")

# ── 4. Camera: parked side-on (moon's vista rig: Absolute ×3, Follow = Target) ──
target = find_by_class('target')
assert target is not None
target.name = 'CamTarget'
target.location = LOOK_AT
target['wf_Model Type'] = 'None'
camshot = find_by_class('camshot')
assert camshot is not None
camshot.name = 'cs_side'
camshot.location = (LOOK_AT[0], LOOK_AT[1] - CAM_DIST, LOOK_AT[2])
for k in ('wf_Position X', 'wf_Position Y', 'wf_Position Z'):
    camshot[k] = 'Absolute'
camshot['wf_Rotation'] = 'Fixed'
camshot['wf_Model Type'] = 'None'
# Bungee mode aims at Target − Follow + TrackObject (movecam.cc:1021-1030), so a Player
# track object would swing the "parked" camera after the fish. CamTarget keeps it static.
camshot['wf_Track Object'] = 'CamTarget'
camshot['wf_Target'] = 'CamTarget'
camshot['wf_Follow'] = 'CamTarget'
camshot['wf_Pan Time In Seconds'] = 0.5
camera = find_by_class('camera')
assert camera is not None
camera.name = 'Camera'
camera.location = camshot.location                # start where the shot lands (bungee spring)
camera['wf_Model Type'] = 'None'
camera['wf_FoggingColor'] = FOG_RGB               # per-level override, never snowgoons' grey
camera['wf_FoggingStartDistance'] = FOG_START
camera['wf_FoggingCompleteDistance'] = FOG_END

# ── 5. Lights (Directional AND Ambient), matte, levelobj, director ───────────
light = find_by_class('light')
assert light is not None
light.name = 'Sun'
light.location = (0.0, -2.0, 3.0)
# condo_639_640 wf_light_aim(): B = altitude, C = azimuth (Blender-authored meshes).
light.rotation_euler = (0.0, math.radians(SUN_ALT_DEG), math.radians(SUN_AZ_DEG))
light['wf_lightType'] = 'Directional'
light['wf_lightRed'], light['wf_lightGreen'], light['wf_lightBlue'] = 0.85, 0.85, 0.80
light['wf_Model Type'] = 'None'
ambient = light.copy()
ambient.data = light.data.copy() if light.data else None
scene.collection.objects.link(ambient)
ambient.name = 'AmbientLight'
ambient['wf_lightType'] = 'Ambient'
ambient['wf_lightRed'], ambient['wf_lightGreen'], ambient['wf_lightBlue'] = AMBIENT

matte = find_by_class('matte')
assert matte is not None
matte.name = 'Matte'
matte.location = (0.0, 0.0, 2.0)
matte['wf_Matte Type'] = 'Color'
matte['wf_Background Color'] = FOG_RGB
matte['wf_Visibility Mailbox'] = 1
matte['wf_Model Type'] = 'None'

levelobj = find_by_class('levelobj')
assert levelobj is not None
levelobj.name = 'Level'
levelobj['wf_Model Type'] = 'None'

director = find_by_class('director')
assert director is not None
director.name = 'Director'
director['wf_Model Type'] = 'None'

room = find_by_class('room')
assert room is not None
room.name = 'room_aquarium_idle'
room.location = ROOM_CENTRE
hx, hy, hz = ROOM_HALF
room['wf_original_bbox'] = (-hx, -hy, -hz, hx, hy, hz)
rv = [(sx * hx, sy * hy, sz * hz) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
rmesh = bpy.data.meshes.new('RoomBounds')
rmesh.from_pydata(rv, [], [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])
rmesh.update()
room.data = rmesh
room.display_type = 'WIRE'
room.hide_render = True

# Every snowgoons infrastructure actor imports with Mass 75 and a 1 m bbox. WF's own
# actor-vs-actor collision (Actor::CanCollide, actor.cc) then treats CamTarget — parked
# ON the fish as the look point — as a solid block: XSPEED writes read back but the
# Player never moves (measured 2026-09-30 before this line existed). None of these
# actors should collide with anything; the Camera keeps its mass (it is a physics body).
for o in (target, camshot, light, ambient, matte, levelobj, director):
    o['wf_Mass'] = 0.0

bpy.context.view_layer.update()
lo = tuple(c - h + 0.05 for c, h in zip(ROOM_CENTRE, ROOM_HALF))
hi = tuple(c + h - 0.05 for c, h in zip(ROOM_CENTRE, ROOM_HALF))
outside = [o.name for o in scene.objects if o.get('wf_schema_path') and get_class(o) != 'room'
           and not all(lo[i] < o.matrix_world.to_translation()[i] < hi[i] for i in range(3))]
assert not outside, f"actors outside room bbox: {outside}"

# ── 6. Runtime actor indices → scripts ───────────────────────────────────────
wf_objects = [o for o in scene.objects if o.get('wf_schema_path')]
idx = {o.name: wf_objects.index(o) + ACTOR_IDX_BIAS for o in wf_objects}
if PROBE:
    player['wf_Script'] = (
        "\\ wf\n0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox 0 INDEXOF_ZSPEED write-mailbox\n"
        f"0 INDEXOF_ROTATION_A write-mailbox 0 INDEXOF_ROTATION_B write-mailbox "
        f"{PROBE_REV} INDEXOF_ROTATION_C write-mailbox\n")
    director['wf_Script'] = (
        "\\ wf\n"
        f"0 INDEXOF_ROTATION_A {idx['probe-statplat']} write-actor-mailbox "
        f"0 INDEXOF_ROTATION_B {idx['probe-statplat']} write-actor-mailbox "
        f"{PROBE_REV} INDEXOF_ROTATION_C {idx['probe-statplat']} write-actor-mailbox\n")
else:
    part_idx = {o.name: idx[o.name] for o in part_objs}
    player['wf_Script'] = FISH.player_script(part_idx, idx['Player'])
    director['wf_Script'] = FISH.director_script(part_idx, idx['Player'])
for name in sorted(idx, key=idx.get):
    print(f"[aquarium_idle] actor {idx[name]:2d} = {name} ({get_class(bpy.data.objects[name])})")

# ── 7. Export ────────────────────────────────────────────────────────────────
os.makedirs(OUT_DIR, exist_ok=True)
wrapper = os.path.join(OUT_DIR, LEVEL_NAME + '-standalone.iff.txt')
if PROBE:
    with open(os.path.join(SCRIPT_DIR, 'aquarium_idle-standalone.iff.txt')) as src, open(wrapper, 'w') as dst:
        dst.write(src.read().replace('aquarium_idle', LEVEL_NAME))
    with open(os.path.join(OUT_DIR, '.gitignore'), 'w') as f:     # the probe is fully regenerable
        f.write('# generated by blender_create_aquarium_idle.py (IDLE_PROBE=1); nothing here is committed\n*\n')
print(f"[aquarium_idle] exporting {len(wf_objects)} actors → {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print("[aquarium_idle] done")
