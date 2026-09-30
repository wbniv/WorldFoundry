#!/usr/bin/env python3
"""blender_create_aquarium.py — the aquarium level: 55 gal acrylic tank, sand, rock, anemone.

Plan: docs/plans/2026-09-30-aquarium-level.md (Phase 2: a static, correct scene).
Constants: aquarium_constants.py (the plan's tank table as code; WORLD_SCALE = 10).

Builds, headless, in the shape of wflevels/aquarium_swim_spike/blender_create_swim_spike.py
(Phase 1, whose solutions are reused here) and blender_create_condo.py:

  * the snowgoons scaffold stripped to one of each infrastructure class, every survivor
    renamed and every bounding box re-authored (nothing inherits a snowgoons name or box);
  * `Player` — a PLACEHOLDER fish with the Phase 1 physics fields and per-frame script
    (Phase 3 swaps in the canonical clownfish, see the `PHASE 3` marker). It is imported
    with the scaffold, so it is created before the tank: jolt_backend.cc JoltCharacterCreate
    ignores a static body whose AABB already encloses the character, and the one-piece
    `tank-shell` encloses it;
  * `tank-shell` (bottom, back, two ends; open front and top — Plan B), the invisible
    `tank-front-collider`, `tank-rim`, `sand`, `rock`, `anemone` (static, back + front
    tentacle sets), the invisible `anemone-zone` target, `stand`, `room-backdrop`;
  * Directional + Ambient light, teal water fog, camshot A (locked, straight-on).

Plan B: nothing is translucent (the engine drops texture alpha, plan § Phase 0 verdict).
The water is the fog plus the water-coloured inner faces of the back and end walls.

Run: task aquarium-level
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

REPO          = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OAD_DIR       = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
LEVEL_NAME    = 'aquarium'
OUT_LEV       = os.path.join(SCRIPT_DIR, LEVEL_NAME + '.lev')
S = C.WORLD_SCALE
m = C.m
TAG = '[aquarium]'

# ── Look (flat colours only; tuned from captured frames, plan § Verification step 11) ──
COL = {
    'acrylic':      (0.62, 0.85, 0.90),     # outer faces of the shell: pale cyan
    'acrylic-edge': (0.82, 0.96, 1.00),     # the exposed front edges: reads as an acrylic edge
    'water':        (0.16, 0.68, 0.86),     # inner faces below the water line (the back film)
    'water-deep':   (0.10, 0.50, 0.68),     # end walls' inner faces: a shade darker than the back
    'waterline':    (0.60, 0.90, 0.97),     # the opaque band at the water line
    'air':          (0.06, 0.13, 0.19),     # inner faces above the water line
    'rim':          (0.74, 0.92, 0.97),
    'rim-shade':    (0.50, 0.72, 0.80),
    'sand-1':       (0.92, 0.78, 0.54),
    'sand-2':       (0.86, 0.71, 0.47),
    'sand-3':       (0.96, 0.84, 0.61),
    'sand-side':    (0.70, 0.56, 0.36),
    'rock-1':       (0.47, 0.46, 0.44),
    'rock-2':       (0.38, 0.37, 0.36),
    'rock-3':       (0.56, 0.54, 0.51),
    'anem-base':    (0.40, 0.20, 0.16),
    'anem-column':  (0.62, 0.40, 0.26),
    'anem-column2': (0.72, 0.50, 0.33),
    'anem-disc':    (0.55, 0.20, 0.36),
    'tent-low':     (0.72, 0.24, 0.48),
    'tent-high':    (0.96, 0.54, 0.70),
    'bulb':         (0.98, 0.62, 0.78),
    'stand':        (0.26, 0.15, 0.09),
    'stand-top':    (0.34, 0.21, 0.13),
    'backdrop':     (0.07, 0.10, 0.15),
    'fish-orange':  (0.95, 0.42, 0.05),
    'fish-white':   (0.95, 0.95, 0.95),
}
WATERLINE_BAND = 0.4                        # in: the band's height, just under the water line (≈ 3 px at 11 m)

# ── Lights (docs/level-building.md § Lighting). Aim measured, not assumed: the doc's
#    outward-wound recipe (B = −alt, C = −90°) left every face at exactly the ambient term in
#    the first capture (sand rendered ambient × colour), so this level takes the mirrored aim,
#    wf_light_aim-style (B = +alt, C = +90°): lit from above and from the camera side. ──
SUN_ALT_DEG = 65.0
SUN_RGB = (0.72, 0.74, 0.74)
AMBIENT_RGB = (0.36, 0.43, 0.50)            # cool fill

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
        ('-z', '+z', '-y', '+x', '+y', '-x') with a 'default'."""
        if isinstance(keys, str):
            keys = {'default': keys}
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for side, f in (('-z', (0, 3, 2, 1)), ('+z', (4, 5, 6, 7)), ('-y', (0, 1, 5, 4)),
                        ('+x', (1, 2, 6, 5)), ('+y', (2, 3, 7, 6)), ('-x', (3, 0, 4, 7))):
            self.face([v[i] for i in f], keys.get(side, keys['default']))

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
# 2. Player — PHASE 3: replace with wflevels/aquarium/clownfish.py
#    Placeholder: the Phase 1 fish (ellipsoid body + white tail wedge so the heading reads
#    side-on), recentred so its X extent is symmetric about the origin (then the nose reach is
#    the same both ways and one X clamp serves both headings), and its measured physics.
# ═════════════════════════════════════════════════════════════════════════════
FISH_BODY_L, FISH_W, FISH_H = 2.6, 1.0, 1.4     # in; the tail adds 0.9 in → 3.5 in total
FISH_TAIL_L = C.FISH_LEN - FISH_BODY_L
FISH_DX = (FISH_TAIL_L) / 2                     # body centre offset that centres body + tail
SWIM_SPEED = 12.0                               # in/s → 3.048 m/s at ×10 (Phase 1)
Z_MARGIN = 0.25                                 # in: keep the top of the fish this far under the water line
X_MARGIN = 0.25                                 # in: keep the nose this far off an end wall

fb = MeshBuilder('fish_placeholder')
orange, white = fb.slot('fish-orange'), fb.slot('fish-white')
body = bmesh.ops.create_uvsphere(fb.bm, u_segments=12, v_segments=8, radius=1.0)
for v in body['verts']:                          # ellipsoid, nose at +X, base at local z = 0
    v.co.x = v.co.x * m(FISH_BODY_L) / 2 + m(FISH_DX)
    v.co.y *= m(FISH_W) / 2
    v.co.z = (v.co.z + 1.0) * m(FISH_H) / 2
fb.closed_shell(list({f for v in body['verts'] for f in v.link_faces}), 'fish-orange')
tx0 = -m(C.FISH_LEN) / 2
tx1 = m(FISH_DX) - m(FISH_BODY_L) / 2 + m(0.2)
fb.box(tx0, -m(0.15), m(0.1), tx1, m(0.15), m(FISH_H) - m(0.1), 'fish-white')
fme = fb.finish()

player = bpy.data.objects['Player']
player.data = fme
player.location = C.FISH_SPAWN
player.rotation_euler = (0.0, 0.0, 0.0)          # C = 0 → currentDir = +X (nose right)
player.scale = (1.0, 1.0, 1.0)
player['wf_Mesh Name'] = 'fish_placeholder.iff'
player['wf_original_mesh_name'] = 'fish_placeholder.iff'
# Authored, symmetric, ≥ 0.25 m on every axis: levcomp takes it verbatim, so its 0.25 m
# thin-span rule (lvl_writer.rs expand_thin_bbox) never shifts the capsule toward the glass,
# and it replaces snowgoons' 2 m capsule (plan § Phase 1 verdict).
FISH_HALF_X, FISH_HALF_Y = m(C.FISH_LEN) / 2, 0.13
author_bbox(player, (-FISH_HALF_X, -FISH_HALF_Y, 0.0, FISH_HALF_X, FISH_HALF_Y, m(FISH_H)))
player['wf_Mobility']              = 'Physics'
player['wf_Mass']                  = 1.0
player['wf_Model Type']            = 'Mesh'
player['wf_Visibility Mailbox']    = 1
player['wf_Falling Acceleration']  = 0.0         # neutral buoyancy
player['wf_Script Controls Input'] = 'True'
player['wf_Turn Rate']             = 0.0
player['wf_Air Acceleration']      = 0.0
player['wf_Max Air Speed']         = m(2 * SWIM_SPEED)   # 6.096; must not be 0 (AirHandler cap)
player['wf_Horiz Air Drag']        = 2.0         # glide: v × 0.9 per tick once released
player['wf_Vert Air Drag']         = 2.0
player['wf_Running Acceleration']  = 0.0
player['wf_Running Deceleration']  = 0.05        # MarbleHandler friction decel·dt·30; 0.85 would zero XY
player['wf_Max Ground Speed']      = m(2 * SWIM_SPEED)
player['wf_Jumping Acceleration']  = 0.0

JOY = 'INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox'


def held(button):
    return f'{JOY} JOYSTICK_BUTTON_{button} & 0 <>'


V = m(SWIM_SPEED)
ZMAX = C.WATER_LINE_M - m(FISH_H + Z_MARGIN)     # feet Z at which the top of the fish is at the margin
XMAX = C.INNER_X_M - FISH_HALF_X - m(X_MARGIN)   # origin X at which the nose is at the margin
player['wf_Script'] = '\n'.join([
    '\\ wf',
    '\\ aquarium placeholder fish (Phase 1 script + X clamp): joystick → X/Y/ZSPEED; glide = air drag',
    '0 INDEXOF_INPUT write-mailbox',
    f'{held("RIGHT")} if {V:.4f} INDEXOF_XSPEED write-mailbox 0 INDEXOF_ROTATION_C write-mailbox then',
    f'{held("LEFT")} if {-V:.4f} INDEXOF_XSPEED write-mailbox 0.5 INDEXOF_ROTATION_C write-mailbox then',
    f'{held("UP")} if {V:.4f} INDEXOF_ZSPEED write-mailbox then',
    f'{held("DOWN")} if {-V:.4f} INDEXOF_ZSPEED write-mailbox then',
    f'{held("C")} if {V:.4f} INDEXOF_YSPEED write-mailbox then',
    f'{held("B")} if {-V:.4f} INDEXOF_YSPEED write-mailbox then',
    # water-line clamp; end-wall clamps (the capsule is only as wide as the fish is thick,
    # so side-on the nose would otherwise enter an end wall — Phase 1 step 6)
    f'INDEXOF_Z_POS read-mailbox {ZMAX:.4f} > if 0 INDEXOF_ZSPEED write-mailbox {ZMAX:.4f} INDEXOF_Z_POS write-mailbox then',
    f'INDEXOF_X_POS read-mailbox {XMAX:.4f} > if 0 INDEXOF_XSPEED write-mailbox {XMAX:.4f} INDEXOF_X_POS write-mailbox then',
    f'INDEXOF_X_POS read-mailbox {-XMAX:.4f} < if 0 INDEXOF_XSPEED write-mailbox {-XMAX:.4f} INDEXOF_X_POS write-mailbox then',
]) + '\n'

# ═════════════════════════════════════════════════════════════════════════════
# 3. Tank: one-piece shell (bottom, back, two ends), invisible front collider, rim.
#    Each wall is three stacked boxes (below the water line / the band / above) so its inner
#    face can carry water, water-line and air colours without coplanar overlays (no z-fight).
# ═════════════════════════════════════════════════════════════════════════════
HX, HY, IX, IY, W = C.HX, C.HY, C.IX, C.IY, C.WALL
BANDS = ((W, C.WATER_Z - WATERLINE_BAND, 'water'),
         (C.WATER_Z - WATERLINE_BAND, C.WATER_Z, 'waterline'),
         (C.WATER_Z, C.EXT_Z, 'air'))

tb = MeshBuilder('tank_shell')
tb.box(m(-HX), m(-HY), 0.0, m(HX), m(HY), m(W), {'default': 'acrylic', '-y': 'acrylic-edge'})
for z0, z1, inner in BANDS:
    deep = 'water-deep' if inner == 'water' else inner
    tb.box(m(-HX), m(IY), m(z0), m(HX), m(HY), m(z1),                       # back
           {'default': 'acrylic', '-y': inner, '+z': 'acrylic-edge'})
    tb.box(m(-HX), m(-HY), m(z0), m(-IX), m(IY), m(z1),                     # left end
           {'default': 'acrylic', '+x': deep, '-y': 'acrylic-edge', '+z': 'acrylic-edge'})
    tb.box(m(IX), m(-HY), m(z0), m(HX), m(IY), m(z1),                       # right end
           {'default': 'acrylic', '-x': deep, '-y': 'acrylic-edge', '+z': 'acrylic-edge'})
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
# 6. Anemone (static bubble-tip, plan § 5): base disc, column, oral disc, 17 tentacles, each a
#    two-tone tapered strip with a bulb tip. Tentacles are split into a BACK set (y > 0) and a
#    FRONT set (y < 0) with a gap at y = 0, so a fish between them is overlapped by the front
#    set by plain depth, no layering. Base at local z = 0; sits on the rock's flat top.
#    Strips face the camera (−Y) and are wound counter-clockwise from there (backface cull).
# ═════════════════════════════════════════════════════════════════════════════
BASE_R, BASE_H = 0.042 * S, 0.006 * S
COL_R0, COL_R1, COL_H = 0.034 * S, 0.027 * S, 0.042 * S
# Back set at +TENT_Y, front set at −TENT_Y. The gap must clear the fish's capsule (radius
# 0.13 m + 0.02 m padding) plus Jolt's 0.1 m predictive contact distance, or a fish swimming
# through the crown is deflected (first capture: at ±0.22 m it was pushed 0.27 m in y and rode
# 0.6 m up over the bulbs).
TENT_Y = 0.036 * S
BULB_R = 0.008 * S
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
frustum(COL_R1 * 1.05, COL_R1 * 0.8, top_z, top_z + 0.004 * S, 10, 'anem-disc')

rnd = random.Random(17)
TENTACLES = []                                   # (set, angle from vertical, deg; length)
for k in range(9):
    TENTACLES.append(('back', -62 + 124 * k / 8 + rnd.uniform(-4, 4), rnd.uniform(0.060, 0.075) * S))
for k in range(8):
    TENTACLES.append(('front', -56 + 112 * k / 7 + rnd.uniform(-4, 4), rnd.uniform(0.056, 0.072) * S))
assert len(TENTACLES) == 17


def tentacle(y, ang_deg, length):
    """Two segments (lower dark, upper pink), bending outward, then a bulb."""
    a0 = math.radians(ang_deg)
    a1 = math.radians(ang_deg * 1.15)                          # the upper half leans out more
    base = (COL_R1 * 0.85 * math.sin(a0), y, top_z)
    mid = (base[0] + 0.5 * length * math.sin(a0), y, base[2] + 0.5 * length * math.cos(a0))
    tip = (mid[0] + 0.5 * length * math.sin(a1), y, mid[2] + 0.5 * length * math.cos(a1))
    widths = (0.0050 * S, 0.0040 * S, 0.0030 * S)
    for (p, q, wp, wq, key) in ((base, mid, widths[0], widths[1], 'tent-low'),
                                (mid, tip, widths[1], widths[2], 'tent-high')):
        dx, dz = q[0] - p[0], q[2] - p[2]
        ln = math.hypot(dx, dz)
        px, pz = dz / ln, -dx / ln                             # in-plane perpendicular, "right" seen from −Y
        ab.face([(p[0] - px * wp, y, p[2] - pz * wp), (p[0] + px * wp, y, p[2] + pz * wp),
                 (q[0] + px * wq, y, q[2] + pz * wq), (q[0] - px * wq, y, q[2] - pz * wq)], key)
    bulb = bmesh.ops.create_uvsphere(ab.bm, u_segments=8, v_segments=5, radius=BULB_R)
    for v in bulb['verts']:
        v.co.x += tip[0]
        v.co.y += y
        v.co.z += tip[2]
    ab.closed_shell(list({f for v in bulb['verts'] for f in v.link_faces}), 'bulb')
    return tip


tips = [tentacle(TENT_Y if s == 'back' else -TENT_Y, ang, ln) for s, ang, ln in TENTACLES]
anemone_pos = (C.ANEMONE_X, C.ANEMONE_Y, C.SAND_TOP_M + ROCK_H)
statplat('anemone', ab.finish(), location=anemone_pos)
crown_top = max(t[2] for t in tips)
crown_span = max(t[0] for t in tips) - min(t[0] for t in tips) + 2 * BULB_R

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
cs['wf_Script'] = '\\ wf\nINDEXOF_ACTOR_INDEX read-mailbox INDEXOF_CAMSHOT write-mailbox\n'
cam = bpy.data.objects['Camera']
cam.location = C.CAM_A_POS
cam['wf_Model Type'] = 'None'
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

for o in scene.objects:                          # nothing may carry an inherited box
    if o.get('wf_schema_path'):
        assert o.get('wf_had_authored_bbox') is not True or o.name in (
            'Director', 'Camera', 'LevelObj', 'Matte', 'Room', 'cs_front', 'LookAt', 'Player',
            'SunLight', 'AmbientLight', 'anemone-zone'), o.name

print(f'{TAG} WORLD_SCALE={S} fish spawn {tuple(round(v, 3) for v in player.location)} '
      f'V={V:.4f} ZMAX={ZMAX:.4f} XMAX={XMAX:.4f} inner x ±{C.INNER_X_M:.4f} y ±{C.INNER_Y_M:.4f} '
      f'sand {C.SAND_TOP_M:.4f} water {C.WATER_LINE_M:.4f}')
print(f'{TAG} rock top z {anemone_pos[2]:.3f}; anemone crown top z {anemone_pos[2] + crown_top:.3f}, '
      f'span {crown_span:.3f} m ({crown_span / (C.IN * S):.1f} in); zone ±{R:.2f} m at {tuple(round(v, 3) for v in zone.location)}')
print(f'{TAG} fog 0x{C.FOG_COLOR:06x} {C.FOG_START:g}→{C.FOG_COMPLETE:g} m; camera {C.CAM_A_POS} → {C.CAM_A_LOOK}')
print(f'{TAG} actor order:', [o.name for o in scene.objects if o.get('wf_schema_path')])
print(f'{TAG} exporting {os.path.relpath(OUT_LEV, REPO)}')
bpy.ops.wf.export_level(filepath=OUT_LEV)
print(f'{TAG} done')
