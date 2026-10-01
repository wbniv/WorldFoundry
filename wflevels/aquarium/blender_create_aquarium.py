#!/usr/bin/env python3
"""blender_create_aquarium.py — the aquarium level: 55 gal acrylic tank, sand, rock, anemone, clownfish.

Plan: docs/plans/2026-09-30-aquarium-level.md (Phase 2: the scene; Phase 3: fish, controls, cameras).
Constants: aquarium_constants.py (the plan's tank table as code; WORLD_SCALE = 10).
The fish: clownfish.py + clownfish_idle.fth (the canonical model and idle rig, plan
docs/plans/2026-09-30-clownfish-idle-animation.md § Hand-off). Controls and camera zones:
aquarium_swim.fth.

Builds, headless, in the shape of wflevels/aquarium_swim_spike/blender_create_swim_spike.py
(Phase 1, whose solutions are reused here) and blender_create_condo.py:

  * the snowgoons scaffold stripped to one of each infrastructure class, every survivor
    renamed and every bounding box re-authored (nothing inherits a snowgoons name or box);
  * `Player` — the canonical clownfish's invisible `Physics` collision hull (Phase 1 physics
    fields, authored symmetric box). It is imported with the scaffold, so it is created before
    the tank: jolt_backend.cc JoltCharacterCreate ignores a static body whose AABB already
    encloses the character, and the one-piece `tank-shell` encloses it. Its script is the
    level's swim controller (aq-player-tick) around the fish's idle sense;
  * the five visible fish parts (`clownfish-body`, `-tail`, `-dorsal`, `-pec-near`, `-pec-far`):
    Mass-0 anchored platforms the Director poses every tick (fish-rig-tick), never statplats;
  * `tank-shell` (bottom, back, two ends; open front and top — Plan B), the invisible
    `tank-front-collider`, `tank-rim`, `sand`, `rock`, `anemone` (static, back + front
    tentacle sets), the invisible `anemone-zone` target, `stand`, `room-backdrop`;
  * Directional + Ambient light, teal water fog, camshot A (locked, straight-on) and camshot B
    (the anemone close-up, aimed at `LookB`, which the Director leans toward the fish), switched
    by the Director on the Player's distance from the anemone zone's centre, with hysteresis.

Plan B: nothing is translucent (the engine drops texture alpha, plan § Phase 0 verdict).
The water is the fog plus the water-coloured inner faces of the back and end walls.

Profiles (build time, like the condo's CONDO_CAMERA_PROFILE): AQUARIUM_PROFILE=keyboard (default:
arrows, B/C held for depth, A darts) → wflevels/aquarium/aquarium.lev; AQUARIUM_PROFILE=touch (a
D-pad plus A/B only: A cycles Swim → Depth mode, B darts) → wflevels/aquarium_touch/ (regenerable,
git-ignored).

Run: task aquarium-level            (task aquarium-touch-level for the touch profile)
or   blender --background --python-exit-code 1 --python wflevels/aquarium/blender_create_aquarium.py
     bash wftools/wf_blender/build_level_binary.sh aquarium
"""
import math
import os
import random
import sys

import addon_utils
import bmesh
import bpy

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import aquarium_constants as C                                     # noqa: E402
import clownfish as CF                                             # noqa: E402  the canonical fish

REPO          = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OAD_DIR       = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
PROFILE       = os.environ.get('AQUARIUM_PROFILE', 'keyboard') or 'keyboard'
assert PROFILE in ('keyboard', 'touch'), f'AQUARIUM_PROFILE={PROFILE!r}: keyboard or touch'
# AQUARIUM_SCHOOL_BENCH=1 builds a benchmark level (wflevels/aquarium_bench): the same level, whose Director also
# runs school.fth (11 fish, no visible effect) every tick, to cost the Forth inside the engine
# (docs/plans/2026-10-01-swarming-poster.md, Phase E step 1). Git-ignored, regenerable.
SCHOOL_BENCH  = os.environ.get('AQUARIUM_SCHOOL_BENCH') == '1'
# AQUARIUM_SCHOOL_N=10 builds the level with that many more fish that school and swarm round the player's fish
# (school.fth + school_rig.fth, docs/plans/2026-10-01-aquarium-schooling.md) into wflevels/aquarium_school (git-ignored).
SCHOOL_N      = int(os.environ.get('AQUARIUM_SCHOOL_N', '0') or 0)
assert 0 <= SCHOOL_N <= 10, 'AQUARIUM_SCHOOL_N: 0..10 (the follower mailbox blocks and the round robin are sized for 10)'
assert not (SCHOOL_BENCH and SCHOOL_N), 'AQUARIUM_SCHOOL_BENCH and AQUARIUM_SCHOOL_N are different builds'
LEVEL_NAME    = ('aquarium_bench' if SCHOOL_BENCH else 'aquarium_school' if SCHOOL_N else
                 'aquarium' if PROFILE == 'keyboard' else 'aquarium_touch')
OUT_DIR       = SCRIPT_DIR if LEVEL_NAME == 'aquarium' else os.path.join(REPO, 'wflevels', LEVEL_NAME)
OUT_LEV       = os.path.join(OUT_DIR, LEVEL_NAME + '.lev')
SWIM_FTH      = os.path.join(SCRIPT_DIR, 'aquarium_swim.fth')
# Runtime actor index = position in the exporter's list + 1 (condo § 9c; measured by the idle
# spike with --debug-print-actors and checked at runtime by run_aquarium_checks.py).
ACTOR_IDX_BIAS = 1
AQ_MB_BASE = 700              # the level's own mailboxes: 700..719 (the fish owns 600..639)
S = C.WORLD_SCALE
m = C.m
TAG = '[aquarium]'

# ── Look (flat colours only; tuned from captured frames, plan § Verification step 11) ──
COL = {
    'acrylic':      (0.62, 0.85, 0.90),     # outer faces of the shell: pale cyan
    'acrylic-edge': (0.82, 0.96, 1.00),     # the exposed front edges: reads as an acrylic edge
    # Phase 4: the water faces are a vertical gradient (WATER_TOP → WATER_BOTTOM, below) with
    # light shafts on the back wall, not one flat colour; see § 3.
    'waterline':    (0.60, 0.90, 0.97),     # the opaque band at the water line
    'air':          (0.06, 0.13, 0.19),     # inner faces above the water line
    'rim':          (0.74, 0.92, 0.97),
    'rim-shade':    (0.50, 0.72, 0.80),
    'sand-1':       (0.92, 0.78, 0.54),
    'sand-2':       (0.86, 0.71, 0.47),
    'sand-3':       (0.96, 0.84, 0.61),
    'sand-side':    (0.84, 0.72, 0.48),     # Phase 4: at camera A's lower eye most of the sand seen is this face
    'rock-1':       (0.47, 0.46, 0.44),
    'rock-2':       (0.38, 0.37, 0.36),
    'rock-3':       (0.56, 0.54, 0.51),
    'anem-base':    (0.40, 0.20, 0.16),
    'anem-column':  (0.62, 0.40, 0.26),
    'anem-column2': (0.72, 0.50, 0.33),
    'anem-disc':    (0.55, 0.20, 0.36),
    'tent-low':     (0.62, 0.22, 0.38),     # tentacles darken toward the disc (mockup #9a4573 → #c2699b)
    'tent-mid':     (0.72, 0.30, 0.47),
    'tent-high':    (0.80, 0.40, 0.55),
    'bulb':         (0.99, 0.66, 0.74),     # mockup #f3b2d2, with a lighter upper cap (#fde0ee)
    'bulb-hi':      (1.00, 0.86, 0.88),
    'stand':        (0.15, 0.09, 0.05),     # Phase 4: darker, the lower sun lights its front face fully
    'stand-top':    (0.22, 0.14, 0.08),
    'backdrop':     (0.07, 0.10, 0.15),
}                                           # the fish's own palette is clownfish.COLOURS
WATERLINE_BAND = 0.4                        # in: the band's height, just under the water line (≈ 3 px at 11 m)
# Water gradient (Phase 4, mockup A: lighter toward the surface, darker toward the sand) on the
# back wall's and end walls' inner faces, and light shafts on the back wall: flat per-face colours
# only (the engine has no translucency, plan § Phase 0). Tuned from captures (step 19).
WATER_TOP, WATER_BOTTOM = (0.20, 0.62, 0.70), (0.05, 0.30, 0.38)   # back wall, faces the light
END_TOP, END_BOTTOM = (0.16, 0.62, 0.78), (0.05, 0.34, 0.47)       # end walls: ambient only
WATER_SLICES = 10                           # gradient steps between the sand and the water-line band
SHAFTS = [(-4.2, 0.9, 0.6, 2.2), (-0.4, 0.9, 0.6, 2.2), (3.6, 0.7, 0.5, 1.8)]   # mockup A (×10 m):
#   (x at the water line, width there, x shift at the sand, width at the sand)
SHAFT_LIFT = (0.07, 0.08, 0.06)             # added to the slice colour at the top; fades to 30 % at the sand

# ── Lights (docs/level-building.md § Lighting). Aim measured, not assumed: the doc's
#    outward-wound recipe (B = −alt, C = −90°) left every face at exactly the ambient term in
#    the first capture (sand rendered ambient × colour), so this level takes the mirrored aim,
#    wf_light_aim-style (B = +alt, C = +90°): lit from above and from the camera side. ──
# Phase 4: the sun came down from 65° to 40° and the ambient went up. At 65° a face toward the
# camera (the fish's flanks, the back wall) got only cos 65° = 0.42 of the sun, so the #ff8a2a
# flank rendered at ≈ 0.66 and read brown; at 40° it gets 0.77 and the flank ≈ 1.0, while the
# sand (a top face, sin 40° = 0.64) comes down toward the mockup's sand.
SUN_ALT_DEG = 40.0
SUN_RGB = (0.72, 0.74, 0.74)
AMBIENT_RGB = (0.45, 0.50, 0.55)            # cool fill

KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light', 'room', 'camshot',
                'target', 'player'}
INFRA_BBOX = (-0.5, -0.5, 0.0, 0.5, 0.5, 1.0)   # the generic box every infrastructure actor carries

_mats = {}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


def find_by_class(cn):
    return next((o for o in bpy.data.objects if get_class(o) == cn), None)


def attach_schema(obj, oad):
    obj['wf_schema_path'] = os.path.join(OAD_DIR, oad + '.oad')


def colour(name, rgb):
    """Register a computed colour (gradient slices, shafts) as a key for mat()."""
    COL[name] = tuple(max(0.0, min(1.0, c)) for c in rgb)
    return name


def mat(key):
    """One Blender material per colour key, shared across meshes."""
    if key not in _mats:
        rgb = COL[key]
        mt = bpy.data.materials.new(key)
        mt.use_nodes = True
        bsdf = next(n for n in mt.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
        mt.diffuse_color = (*rgb, 1.0)
        _mats[key] = mt
    return _mats[key]


class MeshBuilder:
    """bmesh + a per-mesh material slot table. Faces are wound by construction
    (Blender's rule: counter-clockwise seen from the visible side); closed shells made by
    bmesh primitives are recalculated per shell, never across open strips."""

    def __init__(self, name):
        self.me = bpy.data.meshes.new(name)
        self.bm = bmesh.new()
        self.slots = {}

    def slot(self, key):
        if key not in self.slots:
            self.slots[key] = len(self.slots)
            self.me.materials.append(mat(key))
        return self.slots[key]

    def face(self, pts, key):
        f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        f.material_index = self.slot(key)
        return f

    def box(self, x0, y0, z0, x1, y1, z1, keys):
        """Exterior box. `keys`: one colour key, or a dict by side
        ('-z', '+z', '-y', '+x', '+y', '-x') with a 'default'. A side keyed None is left out
        (the caller tessellates it itself, e.g. the back wall's shafts)."""
        if isinstance(keys, str):
            keys = {'default': keys}
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for side, f in (('-z', (0, 3, 2, 1)), ('+z', (4, 5, 6, 7)), ('-y', (0, 1, 5, 4)),
                        ('+x', (1, 2, 6, 5)), ('+y', (2, 3, 7, 6)), ('-x', (3, 0, 4, 7))):
            key = keys.get(side, keys['default'])
            if key is not None:
                self.face([v[i] for i in f], key)

    def closed_shell(self, faces, key):
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        for f in faces:
            f.material_index = self.slot(key)

    def finish(self):
        bmesh.ops.triangulate(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(self.me)
        self.bm.free()
        self.me.update()
        return self.me


def statplat(name, me, location=(0.0, 0.0, 0.0), visible=True):
    """A static Mesh actor: Jolt builds its trimesh from the raw local verts, so every mesh here
    is authored at its final size and orientation (scale/rotation baked, identity transform)."""
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.location = location
    attach_schema(obj, 'statplat')
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Visibility Mailbox'] = 1 if visible else 0
    obj['wf_Mass'] = 0.0
    slug = name.replace('-', '_') + '.iff'
    assert len(slug) <= 30, f'mesh name {slug} > 30 chars (assets.cc 31-byte asset map)'
    obj['wf_Mesh Name'] = slug
    obj['wf_original_mesh_name'] = slug
    return obj


def author_bbox(obj, box):
    obj['wf_original_bbox'] = tuple(float(v) for v in box)
    obj['wf_had_authored_bbox'] = True


# ═════════════════════════════════════════════════════════════════════════════
# 1. Scaffold: snowgoons stripped to one of each infrastructure class, survivors renamed.
# ═════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable('wf_blender', default_set=False, persistent=False)
if not hasattr(bpy.ops.wf, 'import_level'):
    raise SystemExit(f'{TAG} wf_blender add-on not available')
scene = bpy.context.scene
bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)
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
for cn, new in (('director', 'Director'), ('camera', 'Camera'), ('levelobj', 'LevelObj'),
                ('matte', 'Matte'), ('room', 'Room'), ('camshot', 'cs_front'),
                ('target', 'LookAt'), ('player', 'Player'), ('light', 'SunLight')):
    o = find_by_class(cn)
    assert o is not None, f'no {cn} in the snowgoons scaffold'
    o.name = new
    if o.data is not None:
        o.data.name = new                  # the mesh datablock too: no `player_33` survives anywhere
    if cn not in ('player', 'room'):       # those two get their own boxes below
        author_bbox(o, INFRA_BBOX)
print(f'{TAG} scaffold survivors:', sorted(o.name for o in bpy.data.objects))

# ═════════════════════════════════════════════════════════════════════════════
# 2. The fish: the canonical clownfish (clownfish.py, § Hand-off of the idle plan).
#    `Player` is the invisible Physics collision hull (a copy of the body mesh, Phase 1
#    controls, authored symmetric box); the five visible parts are Mass-0 anchored platforms
#    created right after the scaffold, so both come before the tank in actor order. The
#    Director poses the parts every tick; nothing writes the Player's ROTATION_C.
# ═════════════════════════════════════════════════════════════════════════════
FISH = CF.Clownfish(world_scale=S)
assert abs(FISH.length_m - m(C.FISH_LEN)) < 1e-9, 'clownfish.py and aquarium_constants.py disagree on the fish'
fish_mats = {}                                   # the fish's own material cache (clownfish.COLOURS)

player = bpy.data.objects['Player']
player.data = FISH.blender_mesh(bpy, FISH.body_mesh(CF.PLAYER_MESH), fish_mats)
player.location = C.FISH_SPAWN                   # the body centre (a swimming fish's origin)
player.rotation_euler = (0.0, 0.0, 0.0)          # C = 0; the rig owns the visual heading
player.scale = (1.0, 1.0, 1.0)
FISH.apply_player_fields(player)                 # invisible hull, Phase 1 physics, authored box
player['wf_Mesh Name'] = CF.mesh_file(CF.PLAYER_MESH)
# Phase 4 steer-and-swim: the script writes speed × facing every tick and owns the speed (its
# own burst/coast/glide time constants), so the engine's air drag is off. With drag 2.0 the
# AirHandler scaled every write by (1 − 2·dt), which also depends on the frame rate.
player['wf_Horiz Air Drag'] = 0.0
player['wf_Vert Air Drag'] = 0.0

part_objs = []
for name, mesh, off in FISH.parts():
    obj = bpy.data.objects.new(name, FISH.blender_mesh(bpy, mesh, fish_mats))
    obj.location = tuple(p + o for p, o in zip(C.FISH_SPAWN, off))   # rest pose; the Director moves it
    scene.collection.objects.link(obj)
    CF.apply_part_actor_fields(obj)              # anchored platform, Mass 0: no Jolt body
    obj['wf_Mesh Name'] = CF.mesh_file(name)
    part_objs.append(obj)

# The followers (AQUARIUM_SCHOOL_N): the same five parts per fish, named clownfish-<part>-<k>, k = 1..N. They sit in the
# actor list before the tank like the player's, the Director poses them every tick (school_rig.fth).
follower_objs = {}                               # k -> {part name: object}
for k in range(1, SCHOOL_N + 1):
    follower_objs[k] = {}
    for (name, mesh, off), shared in zip(FISH.parts(), part_objs):     # the same five meshes as the player's parts: no new assets, so no new room memory
        assert shared.name == name
        obj = bpy.data.objects.new(f'{name}-{k}', shared.data)
        obj.location = tuple(p + o for p, o in zip(C.FISH_SPAWN, off))
        scene.collection.objects.link(obj)
        CF.apply_part_actor_fields(obj)
        obj['wf_Mesh Name'] = CF.mesh_file(name)
        obj['wf_original_mesh_name'] = CF.mesh_file(name)
        follower_objs[k][name] = obj

# Clamps: the level's job (the capsule is only as wide as the fish is thick and never turns).
# Phase 4: the fish can face any way, so the swim script turns the visible fish's box (below)
# with its facing each tick and keeps it CLAMP_MARGIN inside the inner faces, the sand and the
# water line (aquarium_swim.fth aq-limits). The floor clamp ZMIN still keeps the capsule
# GROUND_CLEARANCE over the sand, so Jolt never treats the fish as standing. Physics is the backstop.
EXT = FISH.extents()
BOB = FISH.T['fish-bob-amp']
HULL = FISH.collision_box()
# the visible fish's box in its own frame: nose/tail, fins (+ flare, tail beat), dorsal/belly (+ bob)
BOX_X0, BOX_X1 = EXT['tail_x'], EXT['nose_x']
BOX_Z0, BOX_Z1 = EXT['bottom_z'] - BOB, EXT['top_z'] + BOB
BOX_HY = max(EXT['half_width'], C.FIN_HALF_WIDTH)
BOX_C = ((BOX_X0 + BOX_X1) / 2, (BOX_Z0 + BOX_Z1) / 2)
BOX_H = ((BOX_X1 - BOX_X0) / 2, BOX_HY, (BOX_Z1 - BOX_Z0) / 2)
ZMIN = C.SAND_TOP_M - HULL[2] + C.GROUND_CLEARANCE
# The loosest body-origin bounds over every facing (the box's smallest reach per axis): for the
# docs and the camera-B clearance test; the script's per-tick limits are always inside these.
XMAX = C.INNER_X_M - C.CLAMP_MARGIN - BOX_HY
YMAX = C.INNER_Y_M - C.CLAMP_MARGIN - BOX_HY
ZMAX = C.WATER_LINE_M - C.CLAMP_MARGIN - BOX_Z1
V = FISH.T['fish-swim-speed']
assert abs(V - C.SWIM_SPEED) < 1e-9, 'the fish and the tank disagree on the swim speed'

# ═════════════════════════════════════════════════════════════════════════════
# 3. Tank: one-piece shell (bottom, back, two ends), invisible front collider, rim.
#    Each wall is three stacked boxes (below the water line / the band / above) so its inner
#    face can carry water, water-line and air colours without coplanar overlays (no z-fight).
# ═════════════════════════════════════════════════════════════════════════════
HX, HY, IX, IY, W = C.HX, C.HY, C.IX, C.IY, C.WALL
# Phase 4: the water band is WATER_SLICES stacked boxes (plus one hidden behind the sand), each
# inner face one step of a vertical gradient; the back wall's inner face in each slice is cut into
# trapezoids along the light shafts' slanted edges. Everything stays in the wall's own inner-face
# plane (no overlay quad, so nothing z-fights), and it is all part of the one tank-shell statplat:
# no new actor, no new collision body.
WL0 = C.WATER_Z - WATERLINE_BAND
SLICE_Z = [W, C.SAND_TOP] + [C.SAND_TOP + (WL0 - C.SAND_TOP) * (k + 1) / WATER_SLICES for k in range(WATER_SLICES)]
BANDS = [(za, zb, max(0.0, ((za + zb) / 2 - C.SAND_TOP) / (WL0 - C.SAND_TOP))) for za, zb in zip(SLICE_Z, SLICE_Z[1:])]
BANDS += [(WL0, C.WATER_Z, 'waterline'), (C.WATER_Z, C.EXT_Z, 'air')]


def lerp3(a, b, t):
    return tuple(p + (q - p) * t for p, q in zip(a, b))


def shaft_lines(z_m):
    """x (m) of every shaft edge at height z (m), left to right: [l0, r0, l1, r1, ...]."""
    u = (z_m - C.SAND_TOP_M) / (C.WATER_LINE_M - C.SAND_TOP_M)      # 1 at the water line, 0 at the sand
    k = S / 10.0
    out = []
    for x_top, w_top, shift, w_bot in SHAFTS:
        xl = (x_top + (1.0 - u) * shift) * k
        out += [xl, xl + (w_top + (1.0 - u) * (w_bot - w_top)) * k]
    return [max(-m(IX), min(m(IX), x)) for x in out]


def back_face_with_shafts(builder, za, zb, base_rgb, t):
    """The back wall's inner face (y = IY, facing −Y) between za and zb (inches): trapezoids between
    the wall's ends and the shafts' edges, wound counter-clockwise seen from the camera."""
    y = m(IY)
    lo = [-m(IX)] + shaft_lines(m(za)) + [m(IX)]
    hi = [-m(IX)] + shaft_lines(m(zb)) + [m(IX)]
    shaft_rgb = tuple(c + d * (0.3 + 0.7 * t) for c, d in zip(base_rgb, SHAFT_LIFT))
    base_key = colour(f'water-{t:.3f}', base_rgb)
    shaft_key = colour(f'shaft-{t:.3f}', shaft_rgb)
    for i in range(len(lo) - 1):
        if lo[i + 1] - lo[i] < 1e-4 and hi[i + 1] - hi[i] < 1e-4:
            continue
        builder.face([(lo[i], y, m(za)), (lo[i + 1], y, m(za)), (hi[i + 1], y, m(zb)), (hi[i], y, m(zb))],
                     shaft_key if i % 2 else base_key)


tb = MeshBuilder('tank_shell')
tb.box(m(-HX), m(-HY), 0.0, m(HX), m(HY), m(W), {'default': 'acrylic', '-y': 'acrylic-edge'})
for z0, z1, inner in BANDS:
    if isinstance(inner, float):                                            # a water slice: gradient step
        back_rgb, end_key = lerp3(WATER_BOTTOM, WATER_TOP, inner), colour(f'end-{inner:.3f}', lerp3(END_BOTTOM, END_TOP, inner))
        tb.box(m(-HX), m(IY), m(z0), m(HX), m(HY), m(z1), {'default': 'acrylic', '-y': None, '+z': 'acrylic-edge'})
        if z0 >= C.SAND_TOP:
            back_face_with_shafts(tb, z0, z1, back_rgb, inner)
        else:                                                               # behind the sand: hidden, plain
            tb.face([(m(-IX), m(IY), m(z0)), (m(IX), m(IY), m(z0)), (m(IX), m(IY), m(z1)), (m(-IX), m(IY), m(z1))],
                    colour('water-sand', back_rgb))
        # (the strips |x| > IX of this box's −y side are shared with the end walls: interior, left out)
    else:
        end_key = inner
        tb.box(m(-HX), m(IY), m(z0), m(HX), m(HY), m(z1),                   # back
               {'default': 'acrylic', '-y': inner, '+z': 'acrylic-edge'})
    tb.box(m(-HX), m(-HY), m(z0), m(-IX), m(IY), m(z1),                     # left end
           {'default': 'acrylic', '+x': end_key, '-y': 'acrylic-edge', '+z': 'acrylic-edge'})
    tb.box(m(IX), m(-HY), m(z0), m(HX), m(IY), m(z1),                       # right end
           {'default': 'acrylic', '-x': end_key, '-y': 'acrylic-edge', '+z': 'acrylic-edge'})
shell = statplat('tank-shell', tb.finish())

# Plan B has no front face, so the fish would swim out: an invisible slab in the front-glass
# plane. An invisible Mesh statplat still gets its trimesh (Phase 1: 6 of 6 slabs MESH_STATIC).
fc = MeshBuilder('tank_front_collider')
fc.box(m(-IX), m(-HY), m(W), m(IX), m(-IY), m(C.EXT_Z), 'acrylic')
statplat('tank-front-collider', fc.finish(), visible=False)

# Rim: a closed ring round the top, chamfered on its outer-top edge. It overhangs the walls
# (outer +0.25 in, inner −0.25 in past the walls' faces), so no rim face is coplanar with a
# wall face. Profile = (offset from the exterior rectangle, z) in inches.
RIM = [(-0.75, C.EXT_Z - 0.5), (0.25, C.EXT_Z - 0.5), (0.25, C.EXT_Z), (0.0, C.EXT_Z + 0.25),
       (-0.75, C.EXT_Z + 0.25)]
rb = MeshBuilder('tank_rim')
corners = ((1, 1), (-1, 1), (-1, -1), (1, -1))
ring = [[rb.bm.verts.new((sx * m(HX + d), sy * m(HY + d), m(z))) for sx, sy in corners] for d, z in RIM]
rim_faces = []
for a in range(len(RIM)):
    b = (a + 1) % len(RIM)
    for c in range(4):
        e = (c + 1) % 4
        f = rb.bm.faces.new((ring[a][c], ring[a][e], ring[b][e], ring[b][c]))
        rim_faces.append(f)
rb.closed_shell(rim_faces, 'rim')
for f in rim_faces:                              # the chamfer and the underside a shade darker
    f.normal_update()
    if f.normal.z < -0.5 or (0.1 < f.normal.z < 0.9):
        f.material_index = rb.slot('rim-shade')
statplat('tank-rim', rb.finish())

# ═════════════════════════════════════════════════════════════════════════════
# 4. Sand: 2 in deep, top at 2.5 in; a grid of flat quads in three shades fakes facets.
#    Inset EPS from the walls so no face is coplanar with a wall's inner face.
# ═════════════════════════════════════════════════════════════════════════════
EPS = 0.02                                       # in
NX, NY = 24, 6
rnd = random.Random(55)
sx0, sx1, sy0, sy1 = m(-IX + EPS), m(IX - EPS), m(-IY + EPS), m(IY - EPS)
sz0, sz1 = m(W + EPS), m(C.SAND_TOP)
xs = [sx0 + (sx1 - sx0) * i / NX for i in range(NX + 1)]
ys = [sy0 + (sy1 - sy0) * j / NY for j in range(NY + 1)]
sb = MeshBuilder('sand')
for i in range(NX):
    for j in range(NY):
        sb.face([(xs[i], ys[j], sz1), (xs[i + 1], ys[j], sz1), (xs[i + 1], ys[j + 1], sz1),
                 (xs[i], ys[j + 1], sz1)], rnd.choice(('sand-1', 'sand-2', 'sand-3')))
for i in range(NX):                              # front (−Y) and back (+Y) sides, one quad per column
    sb.face([(xs[i], sy0, sz0), (xs[i + 1], sy0, sz0), (xs[i + 1], sy0, sz1), (xs[i], sy0, sz1)], 'sand-side')
    sb.face([(xs[i + 1], sy1, sz0), (xs[i], sy1, sz0), (xs[i], sy1, sz1), (xs[i + 1], sy1, sz1)], 'sand-side')
for j in range(NY):                              # ends (−X, +X)
    sb.face([(sx0, ys[j + 1], sz0), (sx0, ys[j], sz0), (sx0, ys[j], sz1), (sx0, ys[j + 1], sz1)], 'sand-side')
    sb.face([(sx1, ys[j], sz0), (sx1, ys[j + 1], sz0), (sx1, ys[j + 1], sz1), (sx1, ys[j], sz1)], 'sand-side')
sb.face([(sx0, sy0, sz0), (sx0, sy1, sz0), (sx1, sy1, sz0), (sx1, sy0, sz0)], 'sand-side')   # underside
statplat('sand', sb.finish())

# ═════════════════════════════════════════════════════════════════════════════
# 5. Rock: flat-shaded low-poly convex hull, base at local z = 0, a flat top for the anemone.
# ═════════════════════════════════════════════════════════════════════════════
ROCK_H = 0.055 * S                               # 0.55 m at ×10 (2.2 in)
ROCK_RX, ROCK_RY = 0.085 * S, 0.065 * S          # footprint half-extents
ROCK_TOP_R = 0.045 * S                           # flat top the anemone's base sits on
rnd = random.Random(7)
pts = []
for k in range(9):                               # base ring
    a = 2 * math.pi * (k + rnd.uniform(-0.2, 0.2)) / 9
    pts.append((ROCK_RX * math.cos(a) * rnd.uniform(0.85, 1.0), ROCK_RY * math.sin(a) * rnd.uniform(0.85, 1.0), 0.0))
for k in range(8):                               # shoulder
    a = 2 * math.pi * (k + 0.5 + rnd.uniform(-0.2, 0.2)) / 8
    pts.append((0.8 * ROCK_RX * math.cos(a), 0.8 * ROCK_RY * math.sin(a), ROCK_H * rnd.uniform(0.45, 0.7)))
for k in range(6):                               # flat top ring (all at ROCK_H)
    a = 2 * math.pi * (k + 0.25) / 6
    pts.append((ROCK_TOP_R * math.cos(a), ROCK_TOP_R * 0.85 * math.sin(a), ROCK_H))
rk = MeshBuilder('rock')
hull = bmesh.ops.convex_hull(rk.bm, input=[rk.bm.verts.new(p) for p in pts])
for g in hull['geom_interior'] + hull['geom_unused']:
    if isinstance(g, bmesh.types.BMVert) and g.is_valid and not g.link_faces:
        rk.bm.verts.remove(g)
rock_faces = [f for f in rk.bm.faces]
rk.closed_shell(rock_faces, 'rock-1')
for f in rock_faces:
    f.normal_update()
    f.material_index = rk.slot('rock-3' if f.normal.z > 0.7 else rnd.choice(('rock-1', 'rock-2', 'rock-1')))
rock_pos = (C.ANEMONE_X, C.ANEMONE_Y, C.SAND_TOP_M)
statplat('rock', rk.finish(), location=rock_pos)

# ═════════════════════════════════════════════════════════════════════════════
# 6. Anemone (bubble-tip, plan § 5): pedal disc, column, flared oral disc, and 18 tentacles, each a
#    three-segment tapered strip (darker toward the disc) with a bulb tip. Base at local z = 0; it
#    sits on the rock's flat top. Phase 4: a large E. quadricolor, C.ANEMONE_SPAN (12 in) across
#    the crown, with a taller column; still small at the base, so it does not block swimming.
#    Tentacles are in a BACK row (y > 0) and a FRONT row (y < 0) with a gap at y = 0, so a fish
#    between them is overlapped by the front row by plain depth, no layering. Strips face the
#    camera (−Y) and are wound counter-clockwise from there (backface cull).
#    `anemone` (pedal disc, column, oral disc) is a statplat and solid. The tentacles are SIX
#    CLUMPS (row × left / centre / right, C.ANEMONE_CLUMPS), each a Mass-0 anchored platform with
#    no Jolt body, so the fish nestles among them from any depth (Phase 3: with colliding tentacles
#    the real hull entered only within |y| < 0.035 m of the gap, and the bulbs stair-stepped it).
#    Each clump's origin is its pivot: the mean of its tentacles' bases, inside the oral disc's rim,
#    so the Director's sway (aq-sway-tick: a rotation about that origin) swings it about its base
#    and the bases stay hidden inside the rim (±5° moves a base ≤ 0.18 m from the pivot by ≤ 16 mm;
#    the bases sit 20 mm under the rim's top and the rim is 40 mm deep).
# ═════════════════════════════════════════════════════════════════════════════
BASE_R, BASE_H = 0.040 * S, 0.006 * S            # pedal disc on the rock
COL_R0, COL_R1, COL_H = 0.030 * S, 0.027 * S, 0.060 * S   # column: 0.6 m tall (Phase 3: 0.42)
FLARE_H, RIM_H, DISC_R = 0.006 * S, 0.004 * S, 0.050 * S  # the oral disc flares out to a 0.5 m rim (1 m, ~4 in, across)
TENT_Y = 0.040 * S                               # back row at +TENT_Y, front row at −TENT_Y
TENT_BASE_X = 0.018 * S                          # bases spread |x| ≤ 0.18 m: inside the rim at |y| 0.4
BULB_R = (0.0085 * S, 0.0100 * S)
# Cost (plan step 18): the tentacle meshes were almost all of Phase 4's added frame time. With 27
# tentacles and 8 × 5 uv-sphere bulbs (40 faces each) the level took 14.7 ms/frame; the same level with
# the six clump meshes swapped for a box took 9.1 ms (Phase 3: 9.7). The bulbs were 93 % of those faces,
# so: 18 tentacles (10 back, 8 front; the mockup draws about 16) and 6 × 4 bulbs (24 faces).
N_BACK, N_FRONT = 10, 8
BULB_SEG = (6, 4)                                # uv-sphere u, v segments
ab = MeshBuilder('anemone')


def frustum(r0, r1, z0, z1, n, key, alt_key=None):
    res = bmesh.ops.create_cone(ab.bm, cap_ends=True, cap_tris=False, segments=n,
                                radius1=r0, radius2=r1, depth=z1 - z0)
    for v in res['verts']:
        v.co.z += (z0 + z1) / 2
    faces = list({f for v in res['verts'] for f in v.link_faces})
    ab.closed_shell(faces, key)
    if alt_key:                                  # alternate side faces: faceted column
        for k, f in enumerate(sorted((f for f in faces if len(f.verts) == 4),
                                     key=lambda f: math.atan2(f.calc_center_median().y, f.calc_center_median().x))):
            if k % 2:
                f.material_index = ab.slot(alt_key)
    return faces


frustum(BASE_R, BASE_R * 0.9, 0.0, BASE_H, 12, 'anem-base')
frustum(COL_R0, COL_R1, BASE_H, BASE_H + COL_H, 10, 'anem-column', 'anem-column2')
top_z = BASE_H + COL_H
frustum(COL_R1, DISC_R, top_z, top_z + FLARE_H, 12, 'anem-column2')                    # the flare
frustum(DISC_R, DISC_R * 0.97, top_z + FLARE_H, top_z + FLARE_H + RIM_H, 12, 'anem-disc')  # the rim
DISC_TOP = top_z + FLARE_H + RIM_H
TENT_BASE_Z = DISC_TOP - 0.002 * S                # 20 mm under the rim's top
assert math.hypot(TENT_BASE_X, TENT_Y) < DISC_R * 0.97 - 0.004 * S, 'tentacle bases must be inside the rim'

rnd = random.Random(17)
TENTACLES = []                                   # (row, angle from vertical, deg; length m)
for k in range(N_BACK):
    TENTACLES.append(('back', -80 + 160 * k / (N_BACK - 1) + rnd.uniform(-3, 3), rnd.uniform(0.105, 0.125) * S))
for k in range(N_FRONT):
    TENTACLES.append(('front', -76 + 152 * k / (N_FRONT - 1) + rnd.uniform(-3, 3), rnd.uniform(0.095, 0.115) * S))


def clump_side(ang_deg):
    return 'l' if ang_deg < -27 else ('r' if ang_deg > 27 else 'c')


def tentacle(builder, pivot, row, ang_deg, length, bulb_r):
    """Three segments bending outward (darker toward the disc), then a bulb with a lighter cap.
    Built in the clump's local frame (anemone-local minus `pivot`); returns the tip, anemone-local."""
    y = TENT_Y if row == 'back' else -TENT_Y
    a = [math.radians(ang_deg * f) for f in (1.0, 1.12, 1.25)]
    pts = [(TENT_BASE_X * math.sin(a[0]), TENT_BASE_Z)]
    for ak in a:
        pts.append((pts[-1][0] + length / 3 * math.sin(ak), pts[-1][1] + length / 3 * math.cos(ak)))
    widths = (0.0036 * S, 0.0030 * S, 0.0024 * S, 0.0019 * S)
    for k, key in enumerate(('tent-low', 'tent-mid', 'tent-high')):
        (px_, pz_), (qx_, qz_) = pts[k], pts[k + 1]
        wp, wq = widths[k], widths[k + 1]
        ln = math.hypot(qx_ - px_, qz_ - pz_)
        nx, nz = (qz_ - pz_) / ln, -(qx_ - px_) / ln          # in-plane perpendicular, "right" seen from −Y
        q = [(px_ - nx * wp, pz_ - nz * wp), (px_ + nx * wp, pz_ + nz * wp),
             (qx_ + nx * wq, qz_ + nz * wq), (qx_ - nx * wq, qz_ - nz * wq)]
        builder.face([(x - pivot[0], y - pivot[1], z - pivot[2]) for x, z in q], key)
    tip = (pts[-1][0], y, pts[-1][1])
    bulb = bmesh.ops.create_uvsphere(builder.bm, u_segments=BULB_SEG[0], v_segments=BULB_SEG[1], radius=bulb_r)
    for v in bulb['verts']:
        v.co.x += tip[0] - pivot[0]
        v.co.y += tip[1] - pivot[1]
        v.co.z += tip[2] - pivot[2]
    faces = list({f for v in bulb['verts'] for f in v.link_faces})
    builder.closed_shell(faces, 'bulb')
    for f in faces:                              # the upper cap a shade lighter (mockup highlight)
        f.normal_update()
        if f.normal.z > 0.45:
            f.material_index = builder.slot('bulb-hi')
    return tip


anemone_pos = (C.ANEMONE_X, C.ANEMONE_Y, C.SAND_TOP_M + ROCK_H)
statplat('anemone', ab.finish(), location=anemone_pos)
ANEMONE_DISC_TOP = anemone_pos[2] + DISC_TOP
tips, bulb_rs, clump_objs, clump_pivots = [], [], {}, {}
for row, side, *_ in C.ANEMONE_CLUMPS:
    members = [(ang, ln) for r, ang, ln in TENTACLES if r == row and clump_side(ang) == side]
    assert members, f'clump {row}-{side} is empty'
    pivot = (sum(TENT_BASE_X * math.sin(math.radians(ang)) for ang, _ in members) / len(members),
             TENT_Y if row == 'back' else -TENT_Y, TENT_BASE_Z)
    name = C.clump_name(row, side)
    cb = MeshBuilder(name.replace('-', '_'))
    for ang, ln in members:
        br = rnd.uniform(*BULB_R)
        tips.append(tentacle(cb, pivot, row, ang, ln, br))
        bulb_rs.append(br)
    obj = statplat(name, cb.finish(), location=tuple(a + p for a, p in zip(anemone_pos, pivot)))
    attach_schema(obj, 'platform')               # anchored platform, Mass 0: drawn, no Jolt body
    clump_objs[name], clump_pivots[name] = obj, pivot
assert len(tips) == len(TENTACLES) == N_BACK + N_FRONT, 'every tentacle belongs to exactly one clump'
crown_top = max(t[2] + r for t, r in zip(tips, bulb_rs))
crown_span = max(t[0] + r for t, r in zip(tips, bulb_rs)) - min(t[0] - r for t, r in zip(tips, bulb_rs))
assert abs(crown_span - m(C.ANEMONE_SPAN)) < 0.05 * m(C.ANEMONE_SPAN), \
    f'crown {crown_span:.3f} m vs ANEMONE_SPAN {m(C.ANEMONE_SPAN):.3f} m'

# ═════════════════════════════════════════════════════════════════════════════
# 7. anemone-zone: an invisible `target` that only carries the zone's bbox (condo room-outline
#    pattern). Camshot B and the Director switch that read it are Phase 3.
# ═════════════════════════════════════════════════════════════════════════════
look = bpy.data.objects['LookAt']
look['wf_Model Type'] = 'None'
look['wf_Script'] = ''
zone = look.copy()
zone.data = None
zone.name = 'anemone-zone'
R = C.ANEMONE_ZONE_RADIUS
zone.location = (C.ANEMONE_X, C.ANEMONE_Y, anemone_pos[2] + crown_top / 2)
zone.rotation_euler = (0.0, 0.0, 0.0)
zone.scale = (1.0, 1.0, 1.0)
author_bbox(zone, (-R, -R, -R, R, R, R))
zone['wf_original_mesh_name'] = ''
zone['wf_Model Type'] = 'None'
scene.collection.objects.link(zone)

# ═════════════════════════════════════════════════════════════════════════════
# 8. Room: the stand under the tank and a backdrop behind it, so the camera never sees the void.
# ═════════════════════════════════════════════════════════════════════════════
st = MeshBuilder('stand')
st.box(-C.EXT_X_M / 2 - 0.2, -C.EXT_Y_M / 2 - 0.2, -0.9 * S, C.EXT_X_M / 2 + 0.2, C.EXT_Y_M / 2 + 0.2,
       -0.01, {'default': 'stand', '+z': 'stand-top'})
statplat('stand', st.finish())
BD_Y = 0.4 * S                                   # 4 m behind the tank's centre
bd = MeshBuilder('room_backdrop')
bd.face([(-2.0 * S, BD_Y, -0.9 * S), (2.0 * S, BD_Y, -0.9 * S), (2.0 * S, BD_Y, 1.6 * S),
         (-2.0 * S, BD_Y, 1.6 * S)], 'backdrop')           # CCW seen from −Y: faces the camera
statplat('room-backdrop', bd.finish())

# ═════════════════════════════════════════════════════════════════════════════
# 9. Lights: Directional (overhead, from the camera side) + cool Ambient.
# ═════════════════════════════════════════════════════════════════════════════
sun = bpy.data.objects['SunLight']
sun.location = (0.0, -0.3 * S, 1.0 * S)
sun.rotation_euler = (0.0, math.radians(SUN_ALT_DEG), math.radians(90.0))
sun['wf_lightType'] = 'Directional'
for ch, v in zip(('Red', 'Green', 'Blue'), SUN_RGB):
    sun[f'wf_light{ch}'] = v
amb = sun.copy()
if sun.data is not None:
    amb.data = sun.data.copy()
    amb.data.name = 'AmbientLight'
scene.collection.objects.link(amb)
amb.name = 'AmbientLight'
amb['wf_lightType'] = 'Ambient'
for ch, v in zip(('Red', 'Green', 'Blue'), AMBIENT_RGB):
    amb[f'wf_light{ch}'] = v

# ═════════════════════════════════════════════════════════════════════════════
# 10. Camshot A: locked, straight-on from outside the front. Bungee aim = Target − Follow +
#     Track Object, so all three are LookAt (docs/level-building.md § CamShot).
#     Fog = the water (plan § 7), overriding snowgoons' 0x888888 20→30 m.
# ═════════════════════════════════════════════════════════════════════════════
look.location = C.CAM_A_LOOK
cs = bpy.data.objects['cs_front']
cs.location = C.CAM_A_POS
for axis in ('X', 'Y', 'Z'):
    cs[f'wf_Position {axis}'] = 'Absolute'
cs['wf_Rotation'] = 'Fixed'
cs['wf_Follow'] = 'LookAt'
cs['wf_Target'] = 'LookAt'
cs['wf_Track Object'] = 'LookAt'
cs['wf_Model Type'] = 'None'
cs['wf_Script'] = ''          # the Director writes INDEXOF_CAMSHOT every tick (aq-camera-tick)

# Camshot B — the anemone close-up (Phase 3). Parked outside the front glass like A (a bungee
# camera climbs while its bbox overlaps a Mass > 0 actor, and the Player has Mass 1). It aims at
# LookB (Follow = Target = Track Object, the bungee aim rule), an anchored Mass-0 platform with no
# mesh that the Director moves each tick: from CAM_B_LOOK a share CAM_B_LOOK_FOLLOW of the way
# toward the fish, so a fish anywhere in the zone stays in frame.
look_b = bpy.data.objects.new('LookB', bpy.data.meshes.new('LookB'))
scene.collection.objects.link(look_b)
attach_schema(look_b, 'platform')
look_b.location = C.CAM_B_LOOK
look_b['wf_Mobility'] = 'Anchored'
look_b['wf_Model Type'] = 'None'
look_b['wf_Mass'] = 0.0
author_bbox(look_b, INFRA_BBOX)
cs_b = cs.copy()
cs_b.data = None
cs_b.name = 'cs_anemone'
cs_b.location = C.CAM_B_POS
for key in ('wf_Follow', 'wf_Target', 'wf_Track Object'):
    cs_b[key] = 'LookB'
cs_b['wf_Script'] = ''
scene.collection.objects.link(cs_b)

cam = bpy.data.objects['Camera']
cam.location = C.CAM_A_POS
cam['wf_Model Type'] = 'None'
h = C.CAMERA_HALF                                # small, so B can sit close to the glass (see above)
author_bbox(cam, (-h, -h, -h, h, h, h))
cam['wf_FoggingColor'] = C.FOG_COLOR
cam['wf_FoggingStartDistance'] = C.FOG_START
cam['wf_FoggingCompleteDistance'] = C.FOG_COMPLETE
assert C.FOG_COMPLETE < 1000.0, 'fog past the 1000 m far clip is off'

# ═════════════════════════════════════════════════════════════════════════════
# 11. Scaffold leftovers out of frame, behind the camera; Matte off; the Room box.
# ═════════════════════════════════════════════════════════════════════════════
director = bpy.data.objects['Director']
director['wf_Script'] = ''
director.location = (-0.4 * S, -2.0 * S, 0.1 * S)
bpy.data.objects['LevelObj'].location = (0.4 * S, -2.0 * S, 0.1 * S)
matte = bpy.data.objects['Matte']
matte.location = (0.0, -2.0 * S, 0.1 * S)
matte['wf_Matte Type'] = 'Color'
matte['wf_Background Color'] = 0x0a0f16
matte['wf_Model Type'] = 'None'
room = bpy.data.objects['Room']
room.location = (0.0, 0.0, 0.0)
author_bbox(room, (-2.2 * S, -3.0 * S, -1.0 * S, 2.2 * S, 2.0 * S, 2.0 * S))

# Every snowgoons infrastructure actor imports with Mass 75, and WF's own actor-vs-actor
# collision (Actor::CanCollide, actor.cc) treats any Mass > 0 bbox as solid: the idle spike
# measured a Mass-75 look target pinning the Player. LookAt sits at the tank's centre, in the
# fish's water, so none of these may collide. The Camera keeps its mass (it is a physics body).
for name in ('Director', 'LevelObj', 'Matte', 'cs_front', 'cs_anemone', 'LookAt', 'LookB',
             'anemone-zone', 'SunLight', 'AmbientLight'):
    bpy.data.objects[name]['wf_Mass'] = 0.0

for o in scene.objects:                          # nothing may carry an inherited box
    if o.get('wf_schema_path'):
        assert o.get('wf_had_authored_bbox') is not True or o.name in (
            'Director', 'Camera', 'LevelObj', 'Matte', 'Room', 'cs_front', 'cs_anemone', 'LookAt',
            'LookB', 'Player', 'SunLight', 'AmbientLight', 'anemone-zone'), o.name

# ═════════════════════════════════════════════════════════════════════════════
# 12. Scripts. Runtime actor index = export position + ACTOR_IDX_BIAS. The Player runs the
#     swim controller (aquarium_swim.fth) around the fish's idle sense; the Director runs
#     fish-rig-tick (it must: it runs after every main-loop actor, so the parts never lag the
#     body) and then the camera zones. Definitions go before the entry call: the zForth host
#     compiles up to the script's last `;` once and runs only what follows it every tick.
# ═════════════════════════════════════════════════════════════════════════════
wf_objects = [o for o in scene.objects if o.get('wf_schema_path')]
idx = {o.name: wf_objects.index(o) + ACTOR_IDX_BIAS for o in wf_objects}
assert idx['Player'] < idx['tank-shell'], 'Player must be created before the one-piece tank'
part_idx = {o.name: idx[o.name] for o in part_objs}
ZONE_C = tuple(zone.location)
AQ_MAILBOXES = ['aq-prev', 'aq-mode', 'aq-dart-t', 'aq-dart-req', 'aq-in-b', 'aq-dx', 'aq-dy', 'aq-dz',
                'aq-vx', 'aq-vy', 'aq-vz',
                # Phase 4 steer-and-swim scratch / state, continued in 740..759 below
                'aq-t1', 'aq-cap', 'aq-brake', 'aq-flat', 'aq-was-moving']
AQ_STEER_BASE = 740           # 740..759: the steer-and-swim state (720..739 is the anemone sway)
AQ_STEER = ['aq-yaw', 'aq-yaw-w', 'aq-yaw-t', 'aq-pitch', 'aq-pitch-w', 'aq-pitch-t', 'aq-roll', 'aq-speed',
            'aq-cyc', 'aq-burst', 'aq-fx', 'aq-fy', 'aq-fz', 'aq-pushed', 'aq-lox', 'aq-hix', 'aq-loy', 'aq-hiy',
            'aq-loz', 'aq-hiz']
assert AQ_MB_BASE >= CF.FISH_MB_BASE + 40 and len(AQ_MAILBOXES) <= 20 and len(AQ_STEER) <= 20


def fnum(v):
    return f'{v:.6f}'.rstrip('0').rstrip('.') if v else '0'


aq_consts = [
    ('aq-touch', int(PROFILE == 'touch'), 'build profile: 1 = touch (A cycles Swim/Depth, B darts)'),
    ('aq-xmax', XMAX, 'loosest |x| of the body origin over every facing (docs/tests; the script is tighter)'),
    ('aq-ymax', YMAX, 'loosest |y|'),
    ('aq-zmax', ZMAX, 'loosest z (a level fish: dorsal + bob 0.25 in under the water line)'),
    ('aq-zmin', ZMIN, f'capsule {C.GROUND_CLEARANCE:g} m over the sand: never standing on it (Jolt floor contact)'),
    ('aq-ix', C.INNER_X_M - C.CLAMP_MARGIN, 'end walls less the 0.25 in margin'),
    ('aq-iy', C.INNER_Y_M - C.CLAMP_MARGIN, 'back wall / front glass less the margin'),
    ('aq-zlo', C.SAND_TOP_M + C.CLAMP_MARGIN, 'sand top plus the margin'),
    ('aq-zhi', C.WATER_LINE_M - C.CLAMP_MARGIN, 'water line less the margin'),
    ('aq-box-cx', BOX_C[0], 'visible fish box, fish frame: centre x (the tail reaches further than the nose)'),
    ('aq-box-cz', BOX_C[1], 'centre z'),
    ('aq-box-hx', BOX_H[0], 'half-sizes: nose-to-tail'),
    ('aq-box-hy', BOX_H[1], 'fins'),
    ('aq-box-hz', BOX_H[2], 'dorsal-to-belly with the bob'),
    ('aq-v', C.SWIM_SPEED, 'm/s mean swim speed (3.4 BL/s)'),
    ('aq-burst-v', C.BURST_SPEED, 'm/s burst target'),
    ('aq-cycle', C.GAIT_CYCLE, 's per burst+coast cycle'),
    ('aq-duty', C.GAIT_DUTY, 'burst share of a cycle'),
    ('aq-tau-a', C.TAU_ACCEL, 's'), ('aq-tau-c', C.TAU_COAST, 's'), ('aq-tau-glide', C.TAU_GLIDE, 's'),
    ('aq-tau-dart', C.TAU_DART, 's'),
    ('aq-dart-v', C.DART_SPEED, 'm/s, the dart (= Max Air Speed)'),
    ('aq-dart-time', C.DART_TIME, 's of dart, then the glide'),
    ('aq-yaw-wn', C.YAW_WN, ''), ('aq-yaw-zeta', C.YAW_ZETA, ''), ('aq-yaw-wmax', C.YAW_WMAX, 'rev/s'),
    ('aq-pitch-wn', C.PITCH_WN, ''), ('aq-pitch-zeta', C.PITCH_ZETA, ''), ('aq-pitch-wmax', C.PITCH_WMAX, 'rev/s'),
    ('aq-pitch-max', C.PITCH_MAX, 'rev'), ('aq-pitch-diag', C.PITCH_DIAG, 'rev'),
    ('aq-bank', C.BANK_GAIN, 'rev per rev/s'), ('aq-bank-max', C.BANK_MAX, 'rev'),
    ('aq-turn-dip', C.TURN_DIP, ''), ('aq-tau-wall', C.TAU_WALL, 's'), ('aq-flatten-d', C.FLATTEN_D, 'm'),
    ('aq-zone-x', ZONE_C[0], 'anemone-zone centre'),
    ('aq-zone-y', ZONE_C[1], ''),
    ('aq-zone-z', ZONE_C[2], ''),
    ('aq-zone-in', C.ANEMONE_ZONE_RADIUS, 'm: closer than this selects camshot B'),
    ('aq-zone-out', C.ANEMONE_ZONE_RADIUS + C.ANEMONE_ZONE_HYST, 'm: farther than this returns to A'),
    ('aq-shot-a', idx['cs_front'], 'camshot A actor index'),
    ('aq-shot-b', idx['cs_anemone'], 'camshot B actor index'),
    ('aq-look-b', idx['LookB'], 'camshot B aim actor index'),
    ('aq-look-b-x', C.CAM_B_LOOK[0], ''),
    ('aq-look-b-z', C.CAM_B_LOOK[2], ''),
    ('aq-look-follow', C.CAM_B_LOOK_FOLLOW, ''),
] + [(n, AQ_MB_BASE + i, 'mailbox') for i, n in enumerate(AQ_MAILBOXES)] \
  + [(n, AQ_STEER_BASE + i, 'mailbox') for i, n in enumerate(AQ_STEER)] \
  + [('aq-sway-b', C.SWAY_MB_BASE + len(C.ANEMONE_CLUMPS), 'mailbox: sway scratch (the B angle)')]
# Anemone sway (Phase 4): one phase accumulator per clump in 720.., then the scratch cell above.
assert C.SWAY_MB_BASE >= AQ_MB_BASE + 20 and len(C.ANEMONE_CLUMPS) + 1 <= 20
SWAY = []                                        # (clump name, actor, amp_a rev, amp_b rev, phase rev, hz, mailbox)
for k, (row, side, amp_b, amp_a, period, phase) in enumerate(C.ANEMONE_CLUMPS):
    assert abs(period / 0.05 - round(period / 0.05)) < 1e-9, 'sway periods are whole 20 Hz ticks'
    name = C.clump_name(row, side)
    SWAY.append((name, idx[name], amp_a / 360.0, amp_b / 360.0, phase, 1.0 / period, C.SWAY_MB_BASE + k))
sway_tick = (': aq-sway-tick   \\ generated: amp-a amp-b phase hz phase-mailbox actor, per clump\n'
             + '\n'.join(f'  {fnum(aa)} {fnum(ab_)} {fnum(ph)} {fnum(hz)} {mb} {a} aq-sway-clump   \\ {n}'
                         for n, a, aa, ab_, ph, hz, mb in SWAY) + '\n;\n')   # `;` on its own line: not in a comment
aq_defs = ('\\ ---- generated by wflevels/aquarium/blender_create_aquarium.py ----\n'
           + '\n'.join(f': {n} {fnum(v)} ;' + (f'   \\ {note}' if note else '') for n, v, note in aq_consts)
           + '\n' + open(SWIM_FTH).read() + sway_tick)
player['wf_Script'] = FISH.player_script(part_idx, idx['Player'], defs=aq_defs, entry='aq-player-tick')
director = bpy.data.objects['Director']
dir_defs, dir_extra = aq_defs, 'aq-camera-tick\naq-sway-tick\n'
if SCHOOL_N:            # the followers: school.fth's model, school_rig.fth's glue, and the generated constants they are built on
    BLm = FISH.length_m
    hx = C.INNER_X_M / BLm - 0.6
    hy = C.INNER_Y_M / BLm - 0.3
    hz = (C.WATER_LINE_M - C.SAND_TOP_M) / 2 / BLm - 0.6
    sd_gen = (': sch-base 800 ; : sch-par 960 ; : sch-scr 985 ;\n'
              f': sch-n {SCHOOL_N + 1} ;\n'
              f': sd-cx 0 ; : sd-cy 0 ; : sd-cz {fnum((C.WATER_LINE_M + C.SAND_TOP_M) / 2)} ; : sd-bl {fnum(BLm)} ;\n'
              f': sd-hx {fnum(hx)} ; : sd-hy {fnum(hy)} ; : sd-hz {fnum(hz)} ;\n'
              ': sd-actors   \\ the 50 follower part actors, k = 1..N, in clownfish.PART_NAMES order\n'
              + ''.join(f'  {int(idx[follower_objs[k][nm].name])} {1040 + 5 * (k - 1) + j} write-mailbox\n'
                        for k in range(1, SCHOOL_N + 1) for j, nm in enumerate(CF.PART_NAMES))
              + ';\n')
    dir_defs = (aq_defs + sd_gen + open(os.path.join(SCRIPT_DIR, 'school.fth')).read()
                + open(os.path.join(SCRIPT_DIR, 'school_rig.fth')).read())
    dir_extra += 'sd-tick\n'
if SCHOOL_BENCH:        # the Forth core, with its mailbox blocks, and one call per tick; see docs/plans/2026-10-01-swarming-poster.md
    SB_PRE = ': sch-base 800 ; : sch-par 960 ; : sch-scr 985 ; : sch-n 11 ;\n'
    SB_INIT = '''
: sb-flag 1015 ;
: sb-fish ( i -- ) dup MB_ME sc!
  me 5 - 1.1 * MB_X me sch!
  me 3 mod 1 - 0.8 * MB_Y me sch!
  me 4 mod 1.5 - MB_Z me sch!
  me 0.13 * fish-cos MB_VX me sch!
  me 0.13 * fish-sin MB_VY me sch!
  0 MB_VZ me sch! ;
: sb-setup
  1 MB_RR par!  5 MB_DRO par!  6 MB_DRA par!  -0.7071 MB_COSB par!
  3 MB_LEADW par!  0.6 MB_WALL par!  0.5 MB_STARTLE_T par!
  -6.71 MB_LOX par!  -1.71 MB_LOX 1 + par!  -2.36 MB_LOX 2 + par!
  6.71 MB_HIX par!  1.71 MB_HIX 1 + par!  2.36 MB_HIX 2 + par!
  0.1 120 2 sch-set-dt
  sch-n 0 do i sb-fish loop ;
: sb-init sb-flag read-mailbox 0 = if sb-setup 1 sb-flag write-mailbox then ;
'''
    dir_defs = aq_defs + SB_PRE + open(os.path.join(SCRIPT_DIR, 'school.fth')).read() + SB_INIT
    dir_extra += 'sb-init\nsch-tick\n'
director['wf_Script'] = FISH.director_script(part_idx, idx['Player'], defs=dir_defs, extra=dir_extra, followers=bool(SCHOOL_N))

print(f'{TAG} WORLD_SCALE={S} profile={PROFILE} fish {FISH.length_m:.3f} m spawn '
      f'{tuple(round(v, 3) for v in player.location)} V={V:.4f} dart {C.DART_SPEED:.3f} m/s × {C.DART_TIME:g} s '
      f'XMAX={XMAX:.4f} YMAX={YMAX:.4f} ZMIN={ZMIN:.4f} ZMAX={ZMAX:.4f} inner x ±{C.INNER_X_M:.4f} '
      f'y ±{C.INNER_Y_M:.4f} sand {C.SAND_TOP_M:.4f} water {C.WATER_LINE_M:.4f}')
print(f'{TAG} rock top z {anemone_pos[2]:.3f}; oral disc top z {ANEMONE_DISC_TOP:.3f} (host at z ≥ '
      f'{ANEMONE_DISC_TOP - HULL[2] + C.GROUND_CLEARANCE:.3f}); anemone crown top z {anemone_pos[2] + crown_top:.3f}, '
      f'span {crown_span:.3f} m ({crown_span / (C.IN * S):.1f} in); zone r {R:.2f} m (leave at '
      f'{R + C.ANEMONE_ZONE_HYST:.2f}) at {tuple(round(v, 3) for v in zone.location)}')
print(f'{TAG} fog 0x{C.FOG_COLOR:06x} {C.FOG_START:g}→{C.FOG_COMPLETE:g} m; camera A {C.CAM_A_POS} → {C.CAM_A_LOOK}; '
      f'camera B {C.CAM_B_POS} → {C.CAM_B_LOOK} (+{C.CAM_B_LOOK_FOLLOW:g} × fish offset)')
for n, a, aa, ab_, ph, hz, mb in SWAY:
    print(f'{TAG} sway {n}: actor {a}, B ±{ab_ * 360:.1f}°, A ±{aa * 360:.1f}°, period {1 / hz:.2f} s, '
          f'phase {ph:.2f} rev, mailbox {mb}; pivot (anemone-local) {tuple(round(v, 3) for v in clump_pivots[n])}')
tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in wf_objects
        if o.data is not None and hasattr(o.data, 'polygons') and o.get('wf_Model Type') == 'Mesh'}
print(f'{TAG} cost: {len(wf_objects)} actors, {len(tris)} mesh actors, {sum(tris.values())} triangles '
      f'(anemone body {tris["anemone"]}, clumps {sum(tris[n] for n in clump_objs)}, tank-shell {tris["tank-shell"]})')
for name in sorted(idx, key=idx.get):
    print(f'{TAG} actor {idx[name]:2d} = {name} ({get_class(bpy.data.objects[name])})')

os.makedirs(OUT_DIR, exist_ok=True)
if LEVEL_NAME != 'aquarium':                     # its own wrapper; the whole directory is regenerable
    with open(os.path.join(SCRIPT_DIR, 'aquarium-standalone.iff.txt')) as src, \
            open(os.path.join(OUT_DIR, LEVEL_NAME + '-standalone.iff.txt'), 'w') as dst:
        txt = src.read().replace('"../aquarium.iff"', f'"../{LEVEL_NAME}.iff"')
        if SCHOOL_N:                             # 50 more part actors: more room and object memory than the one-fish level's wrapper gives
            txt = txt.replace("'ROOM' 1000000l", "'ROOM' 3000000l").replace("'OBJD' 200000l", "'OBJD' 400000l")
            assert "3000000l" in txt and "400000l" in txt
        dst.write(txt)
    with open(os.path.join(OUT_DIR, '.gitignore'), 'w') as f:
        f.write('# generated by blender_create_aquarium.py (AQUARIUM_PROFILE=touch or AQUARIUM_SCHOOL_BENCH=1); nothing here is committed\n*\n')
print(f'{TAG} exporting {os.path.relpath(OUT_LEV, REPO)}')
bpy.ops.wf.export_level(filepath=OUT_LEV)
print(f'{TAG} done')
