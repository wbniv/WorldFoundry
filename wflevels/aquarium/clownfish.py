"""clownfish.py — THE clownfish of the aquarium level (canonical model + idle rig).

One definition, imported by every consumer so the level cannot drift from the
animated model:

* ``wflevels/aquarium_idle/blender_create_aquarium_idle.py`` — the idle spike;
* ``wflevels/aquarium/blender_create_aquarium.py`` — the aquarium level (Phase 3);
* ``wflevels/aquarium_idle/make_idle_mockup.py`` — the plan's mockup;
* ``tests/test_aquarium_idle.py`` — the regression guard.

What it holds
-------------
* The outline from the approved aquarium mockup
  (docs/plans/2026-09-30-aquarium-level/gameplay-states.png, drawn by
  docs/plans/2026-09-30-aquarium-level-mockups.py ``fish()``): body, forked tail,
  dorsal, pectoral, three white bands with black edging, eye.
* Five parts, each its own actor: ``clownfish-body``, ``clownfish-tail``,
  ``clownfish-dorsal``, ``clownfish-pec-near``, ``clownfish-pec-far``. Flat-colour
  materials only, one material per colour, shared across parts (``COLOURS``).
* Scale: ``FISH_REAL_LENGTH_M`` (an ocellaris, 3.5 in) × ``world_scale``. The aquarium
  plan authors at ``WORLD_SCALE = 10`` → 0.889 m; pass ``world_scale=1`` for ×1. Both
  numbers come from ``aquarium_constants.py`` (``FISH_LEN``, ``WORLD_SCALE``), the one
  source for the tank table.
  Every length tunable scales with it; angles and frequencies do not.
* Every animation tunable, the fish's global mailboxes (600..639), and the Forth:
  ``clownfish_idle.fth`` plus a generated constants header (``Clownfish.forth_header``).

Origin convention — the documented exception to the base-at-z=0 mesh rule
(CLAUDE.md, docs/level-building.md "Mesh origin"): a swimming fish never rests on
a surface, so the BODY's origin is the centre of the body (drawing point (0, 0)),
like the sphere exception. Each fin's origin is its hinge (tail: the peduncle;
pectorals: the root edge midpoint; dorsal: its base, at local z = 0, so the
dorsal's Z_SCALE lowers the tip, not the root).

Actors and who moves them (there is no parent/child hierarchy in WF)
--------------------------------------------------------------------
* ``Player`` — class ``player``, Mobility ``Physics``, Falling Acceleration 0,
  Script Controls Input, **Visibility Mailbox 0**: an invisible collision hull that
  carries the body mesh only so Jolt sizes its capsule from it. Its script runs
  ``fish-player-tick`` (swim stub + idle sense). Swim code moves it with
  X/Y/ZSPEED; nothing in the rig writes its position or rotation.
* The five parts — class ``platform``, Mobility ``Anchored``, **Mass 0**, no script,
  each with its own mesh. **Not ``statplat``**: every StatPlat gets a Jolt static body
  whatever its Mass (actor.cc:747-762 box placeholder, :543-593 trimesh), so a statplat
  body part encloses the Player's capsule and pins it — measured 2026-09-30, XSPEED
  read back but X_POS never moved. Anchored platforms get no Jolt body and Mass 0
  keeps them out of WF's own actor collision (``Actor::CanCollide``): purely visual.
  The **Director** poses them every tick with
  ``write-actor-mailbox`` by runtime actor index (``fish-rig-tick``): it reads the
  Player's X/Y/Z_POS, adds the visual bob, and places each part's pivot at
  ``body + Rz(C)·Ry(B)·offset`` (the engine's own Euler order, matrix34.cc), then
  writes ROTATION_A, B, C (always all three, in that order: A and B land in a
  static Euler shared by every actor and only the C write commits them).
  Parts follow the heading because the offsets are rotated by the body heading C
  every tick; the heading itself is the rig's visual ``fish-heading`` mailbox.

Plan: docs/plans/2026-09-30-clownfish-idle-animation.md
"""

from __future__ import annotations

import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FORTH_PATH = os.path.join(HERE, 'clownfish_idle.fth')
OAD_DIR = os.path.normpath(os.path.join(HERE, '..', '..', 'wftools', 'wf_oad', 'tests', 'fixtures'))

# The tank table (aquarium_constants.py) is the single source for the scale and the fish's
# real length. Loaded by path under a private name, so a caller that has another module called
# `aquarium_constants` on sys.path (the Phase 1 swim spike has one) cannot shadow it.
_spec = importlib.util.spec_from_file_location('_aquarium_tank_constants',
                                               os.path.join(HERE, 'aquarium_constants.py'))
_TANK = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_TANK)

FISH_REAL_LENGTH_M = _TANK.FISH_LEN * _TANK.IN   # ocellaris, 3.5 in = 0.0889 m; × WORLD_SCALE 10 = 0.889 m
DEFAULT_WORLD_SCALE = _TANK.WORLD_SCALE          # aquarium plan § "Scale decision" (10)
REAL_HALF_THICKNESS_M = 0.010    # → 0.2 m through the widest point at ×10, tapered

# ── Outline, in mockup drawing units (x forward, y DOWN: negative y = dorsal) ──
BODY_TOP = [(50, 0), (38, -13), (22, -21), (4, -27), (-16, -25), (-34, -15), (-44, -7)]
BODY_BOTTOM = [(50, 0), (38, 14), (16, 23), (-12, 25), (-34, 13), (-44, 7)]
TAIL = [(-44, -7), (-62, -23), (-73, -15), (-69, 0), (-73, 15), (-62, 23), (-44, 7)]
DORSAL = [(20, -21), (8, -38), (-6, -40), (-24, -30), (-16, -25), (4, -27)]
PECTORAL = [(14, 10), (0, 17), (-8, 13), (2, 7)]
EYE = (38.0, -6.0, 4.4, 2.2)     # x, y, white radius, pupil radius (mockup circle)

X_NOSE = 50.0
X_TAIL_TIP = float(min(x for x, _ in TAIL))
X_PEDUNCLE = -44.0
DRAWING_LENGTH = X_NOSE - X_TAIL_TIP

BANDS = [(24.0, 33.0), (-7.0, 6.0), (-40.0, -34.0)]   # white, drawing x (head, mid, tail base)
BAND_EDGE = 2.6                                     # black edging each side (the mockup's 2.6)

# Half-thickness profile: drawing x -> fraction of the maximum.
THICKNESS = [(50, 0.10), (44, 0.35), (38, 0.60), (22, 0.92), (8, 1.00),
             (-8, 0.95), (-20, 0.80), (-34, 0.45), (-44, 0.25)]

FIN_INSET = 0.72                 # inner (coloured) polygon scale; the rest is the black edge

# Pivots, in drawing units (x, z_up).
TAIL_PIVOT = (X_PEDUNCLE, 0.0)
DORSAL_PIVOT = (2.0, 18.0)       # its base (lowest vertex after the root is tucked in)
PEC_PIVOT = (8.0, -8.5)          # midpoint of the root edge (14,10)-(2,7)

# ── Colours: one flat material per colour (mockup palette) ───────────────────
COLOURS = {
    'fish-orange-hi':  (1.000, 0.616, 0.278),   # #ff9d47  upper facets
    'fish-orange':     (1.000, 0.541, 0.165),   # #ff8a2a  flank
    'fish-orange-lo':  (0.910, 0.400, 0.059),   # #e8660f  belly
    'fish-white':      (0.965, 0.957, 0.933),   # #f6f4ee
    'fish-black':      (0.067, 0.067, 0.067),   # #111111
    'fish-tail':       (0.886, 0.384, 0.055),   # #e2620e
    'fish-dorsal':     (0.957, 0.486, 0.114),   # #f47c1d
    'fish-pectoral':   (1.000, 0.690, 0.400),   # #ffb066
    'fish-eye':        (1.000, 1.000, 1.000),
}

# ── Tunables: (name, value at ×10, unit). Units 'm'/'m/s' scale with world_scale/10. ──
TUNABLES = [
    ('fish-bob-amp',       0.012,   'm',   'visual body bob; never touches physics'),
    ('fish-bob-hz',        1 / 2.8, 'Hz',  ''),
    ('fish-sway-yaw',      0.010,   'rev', 'heading sway'),
    ('fish-sway-pitch',    0.006,   'rev', 'pitch sway, + = nose down'),
    ('fish-sway-hz',       1 / 3.6, 'Hz',  ''),
    ('fish-tail-idle-amp', 0.050,   'rev', ''),
    ('fish-tail-idle-hz',  1.4,     'Hz',  ''),
    ('fish-tail-swim-amp', 0.075,   'rev', ''),
    ('fish-tail-swim-hz',  3.2,     'Hz',  ''),
    ('fish-counter-yaw',   0.20,    '',    'share of tail yaw fed back into body heading'),
    ('fish-pec-idle-amp',  0.080,   'rev', 'pectorals are the hover motor'),
    ('fish-pec-idle-hz',   2.2,     'Hz',  ''),
    ('fish-pec-swim-amp',  0.020,   'rev', 'tucked while swimming'),
    ('fish-pec-swim-hz',   3.0,     'Hz',  ''),
    ('fish-pec-flare',     0.030,   'rev', 'pectorals angled off the flank'),
    ('fish-dorsal-amp',    0.15,    '',    'share of fin height lowered at the trough'),
    ('fish-dorsal-hz',     0.7,     'Hz',  ''),
    ('fish-idle-delay',    0.35,    's',   'no input this long before idle starts'),
    ('fish-idle-in',       0.8,     's',   'ramp into idle'),
    ('fish-idle-out',      0.12,    's',   'ramp out of idle when input arrives'),
    ('fish-swim-speed',    3.048,   'm/s', 'written while a direction is held (Phase 1: 12 in/s x scale)'),
    ('fish-turn-time',     0.35,    's',   'half a turn'),
]

# ── Physics controls measured in aquarium Phase 1 (×10, placeholder fish), adopted here ──
# docs/plans/2026-09-30-aquarium-level.md § 4 and § "Phase 1 verdict". Lengths/speeds
# are at ×10 and scale with world_scale. The idle rig never writes any of these.
PHYSICS = {
    'wf_Mass': 1.0,
    'wf_Falling Acceleration': 0.0,      # neutral buoyancy: 0 drift in 10 s
    'wf_Air Acceleration': 0.0,
    'wf_Running Acceleration': 0.0,
    'wf_Jumping Acceleration': 0.0,
    'wf_Running Deceleration': 0.05,     # MarbleHandler friction decel·dt·30 must stay < 1 on the sand
    'wf_Horiz Air Drag': 2.0,            # the glide: × 0.9 per 20 Hz tick after release
    'wf_Vert Air Drag': 2.0,
    'wf_Max Air Speed': 6.096,           # 2 × swim speed; NEVER 0 (AirHandler scales velocity to it)
    'wf_Max Ground Speed': 6.096,        # MarbleHandler caps XY to it
    'wf_Turn Rate': 0.0,                 # heading belongs to the rig
}
SCALED_PHYSICS = ('wf_Max Air Speed', 'wf_Max Ground Speed')
MIN_COLLISION_SPAN_M = 0.25              # levcomp expand_thin_bbox: a thinner side is grown from its MIN face
ENGINE_MIN_TRIANGLE_M2 = 3.05e-5         # math/vector3.hpi:243 asserts |(v2-v0)x(v1-v0)| > Scalar(0,4)

# Global user mailboxes the fish owns (2..1900 are shared by every actor).
FISH_MB_BASE = 600
MAILBOXES = [
    ('fish-w', 'idle weight: 0 swimming .. 1 idle'),
    ('fish-idle-t', 's since the last input'),
    ('fish-heading', 'visual heading, rev (0 faces +X, -0.5 faces -X)'),
    ('fish-heading-target', 'rev'),
    ('fish-input', '1 while a direction is held'),
    ('fish-ph-bob', 'phase accumulators, rev in [0,1)'),
    ('fish-ph-sway', ''),
    ('fish-ph-tail', ''),
    ('fish-ph-pec', ''),
    ('fish-ph-dorsal', ''),
    ('fish-sc', 'sin/cos of body heading C and pitch B'),
    ('fish-cc', ''),
    ('fish-sb', ''),
    ('fish-cb', ''),
    ('fish-bx', 'visual body origin, world m'),
    ('fish-by', ''),
    ('fish-bz', ''),
    ('fish-tail', 'tail yaw, rev'),
    ('fish-pec', 'pectoral swing, rev'),
    ('fish-dorsal', 'dorsal Z_SCALE'),
    ('fish-dx', 'swim stub: held direction this tick, -1/0/1'),
    ('fish-dz', ''),
    ('fish-ox', 'scratch: part offset, then world position'),
    ('fish-oy', ''),
    ('fish-oz', ''),
    ('fish-body-c', 'body heading this tick, rev'),
    ('fish-body-b', 'body pitch this tick, rev'),
    ('fish-ws', 'smoothstep(fish-w)'),
]
MB = {name: FISH_MB_BASE + i for i, (name, _) in enumerate(MAILBOXES)}
assert FISH_MB_BASE + len(MAILBOXES) <= 640

PART_NAMES = ['clownfish-body', 'clownfish-tail', 'clownfish-dorsal',
              'clownfish-pec-near', 'clownfish-pec-far']
ROLES = {n: n.split('clownfish-', 1)[1] for n in PART_NAMES}
PLAYER_MESH = 'clownfish-hull'   # the invisible Player's mesh (a copy of the body)
ENTRY_PLAYER = 'fish-player-tick'
ENTRY_DIRECTOR = 'fish-rig-tick'


# ── Geometry helpers ─────────────────────────────────────────────────────────
def _interp(points, x):
    pts = sorted(points)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else y0
    return pts[-1][1]


def z_top(x):
    return -_interp(BODY_TOP, x)


def z_bottom(x):
    return -_interp(BODY_BOTTOM, x)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class Mesh:
    """Indexed polygon mesh: verts (metres), faces (index tuples, CCW = outward), mats (colour names)."""

    def __init__(self, name):
        self.name = name
        self.verts, self.faces, self.mats = [], [], []

    def v(self, p):
        self.verts.append(tuple(float(c) for c in p))
        return len(self.verts) - 1

    def f(self, idx, colour, outward):
        idx = tuple(idx)
        a, b, c = (self.verts[i] for i in idx[:3])
        if _dot(_cross(_sub(b, a), _sub(c, a)), outward) < 0:
            idx = tuple(reversed(idx))
        self.faces.append(idx)
        self.mats.append(colour)

    @property
    def materials(self):
        return sorted(set(self.mats), key=list(COLOURS).index)

    def bbox(self):
        xs, ys, zs = zip(*self.verts)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def signed_volume(self):
        vol = 0.0
        for face in self.faces:
            a = self.verts[face[0]]
            for i in range(1, len(face) - 1):
                vol += _dot(a, _cross(self.verts[face[i]], self.verts[face[i + 1]])) / 6.0
        return vol


def _band_colour(x):
    for x0, x1 in BANDS:
        if x0 <= x <= x1:
            return 'fish-white'
        if x0 - BAND_EDGE <= x < x0 or x1 < x <= x1 + BAND_EDGE:
            return 'fish-black'
    return None


class Clownfish:
    """The canonical clownfish at one world scale (default ×10 → 0.889 m)."""

    def __init__(self, world_scale=DEFAULT_WORLD_SCALE):
        self.world_scale = float(world_scale)
        self.length_m = FISH_REAL_LENGTH_M * self.world_scale
        self.s = self.length_m / DRAWING_LENGTH                 # metres per drawing unit
        self.max_half_thickness = REAL_HALF_THICKNESS_M * self.world_scale
        self.fin_thickness = 0.0011 * self.world_scale
        self.fin_gap = 0.0006 * self.world_scale
        k = self.world_scale / 10.0
        self.tunables = [(n, v * (k if unit in ('m', 'm/s') else 1.0), unit, note)
                         for n, v, unit, note in TUNABLES]
        self.T = {n: v for n, v, _, _ in self.tunables}

    # ---- geometry ------------------------------------------------------
    def half_thickness(self, x):
        return self.max_half_thickness * _interp(THICKNESS, x)

    def body_mesh(self, name='clownfish-body'):
        """Lofted six-sided sections; one strip per colour band; eye discs on both flanks."""
        S = self.s
        m = Mesh(name)
        stations = {44.0, 38.0, 30.0, 16.0, 4.0, -12.0, -16.0, -25.0, X_PEDUNCLE}
        for x0, x1 in BANDS:
            stations |= {x0, x1, x0 - BAND_EDGE, x1 + BAND_EDGE}
        stations = sorted((s for s in stations if X_PEDUNCLE <= s <= 44.0), reverse=True)
        # section vertex -> facet colour of the strip face that starts at it (top→ -y side → bottom → +y side)
        facet = ['fish-orange-hi', 'fish-orange', 'fish-orange-lo', 'fish-orange-lo', 'fish-orange', 'fish-orange-hi']
        rings = []
        for xd in stations:
            top, bot = z_top(xd), z_bottom(xd)
            mid, h = (top + bot) / 2.0, (top - bot) / 2.0
            w, x = self.half_thickness(xd), xd * S
            ring = [m.v((x, 0.0, top * S)), m.v((x, -w, (mid + 0.50 * h) * S)),
                    m.v((x, -w, (mid - 0.45 * h) * S)), m.v((x, 0.0, bot * S)),
                    m.v((x, +w, (mid - 0.45 * h) * S)), m.v((x, +w, (mid + 0.50 * h) * S))]
            rings.append((xd, mid * S, ring))
        for (xa, ma, ra), (xb, mb, rb) in zip(rings, rings[1:]):
            band = _band_colour((xa + xb) / 2.0)
            for k in range(6):
                quad = (ra[k], ra[(k + 1) % 6], rb[(k + 1) % 6], rb[k])
                c = [sum(m.verts[i][j] for i in quad) / 4.0 for j in range(3)]
                m.f(quad, band or facet[k], _sub(c, ((xa + xb) / 2.0 * S, 0.0, (ma + mb) / 2.0)))
        apex = m.v((X_NOSE * S, 0.0, 0.0))
        first = rings[0][2]
        for k in range(6):
            tri = (first[k], first[(k + 1) % 6], apex)
            c = [sum(m.verts[i][j] for i in tri) / 3.0 for j in range(3)]
            m.f(tri, facet[k], (1.0, c[1] * 20.0, c[2] * 20.0))
        last = rings[-1][2]
        for k in range(1, 5):
            m.f((last[0], last[k], last[k + 1]), 'fish-orange', (-1.0, 0.0, 0.0))
        # Eye: black rim, white, black pupil nudged forward (the mockup's two circles).
        ex, ey, r_white, r_pupil = EYE
        ez = -ey
        for side in (-1.0, 1.0):
            y = side * (self.half_thickness(ex) + 0.0003 * self.world_scale)
            for radius, colour, dy, dx in ((r_white + 0.9, 'fish-black', 0.0, 0.0),
                                           (r_white, 'fish-eye', 0.00015, 0.0),
                                           (r_pupil, 'fish-black', 0.0003, 1.2)):
                yy = y + side * dy * self.world_scale
                ring = [m.v(((ex + dx) * S + radius * S * math.cos(a), yy, ez * S + radius * S * math.sin(a)))
                        for a in (i * math.tau / 10 for i in range(10))]
                centre = m.v(((ex + dx) * S, yy, ez * S))
                for i in range(10):
                    m.f((centre, ring[i], ring[(i + 1) % 10]), colour, (0.0, side, 0.0))
        return m

    def fin_slab(self, name, poly_xz, colour, y_centre=0.0, thickness=None, inset=FIN_INSET):
        """Thin slab from a fin outline in local x/z metres (star-shaped about its vertex mean):
        coloured centre, black edge on both faces, black rim."""
        t = self.fin_thickness if thickness is None else thickness
        m = Mesh(name)
        cx = sum(p[0] for p in poly_xz) / len(poly_xz)
        cz = sum(p[1] for p in poly_xz) / len(poly_xz)
        inner = [(cx + (x - cx) * inset, cz + (z - cz) * inset) for x, z in poly_xz]
        n = len(poly_xz)
        outer = {}
        for side in (-1.0, 1.0):
            y = y_centre + side * t / 2.0
            oi = [m.v((x, y, z)) for x, z in poly_xz]
            ii = [m.v((x, y, z)) for x, z in inner]
            c = m.v((cx, y, cz))
            for i in range(n):
                j = (i + 1) % n
                m.f((c, ii[i], ii[j]), colour, (0.0, side, 0.0))
                m.f((oi[i], oi[j], ii[j], ii[i]), 'fish-black', (0.0, side, 0.0))
            outer[side] = oi
        for i in range(n):
            j = (i + 1) % n
            a, b = poly_xz[i], poly_xz[j]
            m.f((outer[-1][i], outer[-1][j], outer[1][j], outer[1][i]), 'fish-black',
                ((a[0] + b[0]) / 2 - cx, 0.0, (a[1] + b[1]) / 2 - cz))
        return m

    def _local(self, points, pivot):
        px, pz = pivot
        return [((x - px) * self.s, (-y - pz) * self.s) for x, y in points]

    def tail_mesh(self, name='clownfish-tail'):
        pts = list(TAIL)
        pts[0], pts[-1] = (-40.5, -7.8), (-40.5, 7.8)          # root tucked into the peduncle
        return self.fin_slab(name, self._local(pts, TAIL_PIVOT), 'fish-tail')

    def dorsal_mesh(self, name='clownfish-dorsal'):
        pts = [(20, -18), (8, -38), (-6, -40), (-24, -30), (-16, -22), (4, -24)]   # root 3 units into the body
        return self.fin_slab(name, self._local(pts, DORSAL_PIVOT), 'fish-dorsal')

    def pectoral_mesh(self, name):
        return self.fin_slab(name, self._local(PECTORAL, PEC_PIVOT), 'fish-pectoral',
                             thickness=self.fin_thickness * 0.8)

    def pec_offset_y(self, side):
        return side * (self.half_thickness(PEC_PIVOT[0]) + self.fin_gap)

    def parts(self):
        """[(actor name, Mesh, pivot offset from the body origin in metres)] in rig order."""
        S = self.s
        return [
            ('clownfish-body', self.body_mesh(), (0.0, 0.0, 0.0)),
            ('clownfish-tail', self.tail_mesh(), (TAIL_PIVOT[0] * S, 0.0, TAIL_PIVOT[1] * S)),
            ('clownfish-dorsal', self.dorsal_mesh(), (DORSAL_PIVOT[0] * S, 0.0, DORSAL_PIVOT[1] * S)),
            ('clownfish-pec-near', self.pectoral_mesh('clownfish-pec-near'),
             (PEC_PIVOT[0] * S, self.pec_offset_y(-1), PEC_PIVOT[1] * S)),
            ('clownfish-pec-far', self.pectoral_mesh('clownfish-pec-far'),
             (PEC_PIVOT[0] * S, self.pec_offset_y(+1), PEC_PIVOT[1] * S)),
        ]

    # ---- extents, collision, sanity ---------------------------------------
    def extents(self):
        """Rest-pose extents of the whole visible fish, metres from the body origin (for the
        level's X/Z clamps): nose_x, tail_x, top_z, bottom_z, half_width (incl. pectorals)."""
        xs, ys, zs = [], [], []
        for _, mesh, off in self.parts():
            lo, hi = mesh.bbox()
            xs += [lo[0] + off[0], hi[0] + off[0]]
            ys += [lo[1] + off[1], hi[1] + off[1]]
            zs += [lo[2] + off[2], hi[2] + off[2]]
        return dict(nose_x=max(xs), tail_x=min(xs), top_z=max(zs), bottom_z=min(zs),
                    half_width=max(abs(min(ys)), abs(max(ys))))

    def collision_box(self):
        """Authored, symmetric Player bbox (x0, y0, z0, x1, y1, z1) about the body origin, every
        side >= MIN_COLLISION_SPAN_M, so levcomp's thin-span rule leaves it alone and the Jolt
        capsule stays centred on the body (Phase 1 verdict). Capsule radius = min(hx, hy)."""
        lo, hi = self.body_mesh().bbox()
        m = MIN_COLLISION_SPAN_M / 2.0
        hx = max(m, abs(lo[0]), abs(hi[0]))
        hy = max(m, abs(lo[1]), abs(hi[1]))
        hz = max(m, abs(lo[2]), abs(hi[2]))
        return (-hx, -hy, -hz, hx, hy, hz)

    def physics(self):
        k = self.world_scale / 10.0
        return {key: (v * k if key in SCALED_PHYSICS else v) for key, v in PHYSICS.items()}

    def min_triangle_area(self):
        """Smallest triangle (m²) the exporter will emit, over every part (fan triangulation)."""
        best = float('inf')
        for _, mesh, _ in self.parts():
            for face in mesh.faces:
                a = mesh.verts[face[0]]
                for i in range(1, len(face) - 1):
                    n = _cross(_sub(mesh.verts[face[i]], a), _sub(mesh.verts[face[i + 1]], a))
                    best = min(best, 0.5 * math.sqrt(_dot(n, n)))
        return best

    def apply_player_fields(self, player, visible=False):
        """The Physics Player: Phase 1's measured controls, authored symmetric collision box,
        invisible hull by default. Its mesh must be ``PLAYER_MESH`` (a copy of the body)."""
        player['wf_Mobility'] = 'Physics'
        player['wf_Model Type'] = 'Mesh'
        player['wf_original_mesh_name'] = mesh_file(PLAYER_MESH)
        player['wf_Visibility Mailbox'] = 1 if visible else 0
        player['wf_Script Controls Input'] = 'True'
        for key, value in self.physics().items():
            player[key] = float(value)
        # levcomp takes an authored box verbatim; the snowgoons 2 m box would otherwise win.
        player['wf_original_bbox'] = self.collision_box()
        player['wf_had_authored_bbox'] = True

    # ---- Forth -----------------------------------------------------------
    def forth_header(self, actor_indices, player_index):
        """Named constants for clownfish_idle.fth. actor_indices: {part name: runtime actor index}."""
        out = ['\\ ---- generated by wflevels/aquarium/clownfish.py: edit there, not here ----',
               f'\\ clownfish at world scale x{self.world_scale:g}: {self.length_m:.3f} m long']
        for name, value, unit, note in self.tunables:
            out.append(f': {name} {_fmt(value)} ;' + (f'   \\ {unit} {note}'.rstrip() if unit or note else ''))
        for name, note in MAILBOXES:
            out.append(f': {name} {MB[name]} ;' + (f'   \\ {note}' if note else ''))
        for name, _, off in self.parts():
            for axis, v in zip('xyz', off):
                out.append(f': fish-off-{ROLES[name]}-{axis} {_fmt(v)} ;')
            out.append(f': fish-actor-{ROLES[name]} {int(actor_indices[name])} ;')
        out.append(f': fish-actor-player {int(player_index)} ;')
        return '\n'.join(out) + '\n'

    def forth_library(self, actor_indices, player_index):
        with open(FORTH_PATH) as f:
            return self.forth_header(actor_indices, player_index) + f.read()

    # The zForth host compiles everything up to the script's LAST `;` once, at load, and runs
    # only what follows it every tick (engine/stubs/scripting_zforth.cc). So extra word
    # definitions go in `defs` (before the entry call); `extra` must hold calls only.
    def player_script(self, actor_indices, player_index, extra='', defs='', entry=ENTRY_PLAYER):
        """Complete `wf_Script` for the Physics Player. A level with its own swim controller
        passes its words in `defs` and its tick word as `entry` (it replaces fish-swim-tick)."""
        return ('\\ wf\n' + self.forth_library(actor_indices, player_index) + defs
                + f'\n{entry}\n' + extra)

    def director_script(self, actor_indices, player_index, extra='', defs=''):
        """Complete `wf_Script` for the Director: `defs` (definitions), then `fish-rig-tick`,
        then `extra` (calls only)."""
        return ('\\ wf\n' + self.forth_library(actor_indices, player_index) + defs
                + f'\n{ENTRY_DIRECTOR}\n' + extra)

    # ---- Blender -----------------------------------------------------------
    def blender_mesh(self, bpy, mesh, materials):
        """Mesh → bpy mesh datablock. `materials`: shared {colour name: bpy material} cache."""
        me = bpy.data.meshes.new(mesh.name)
        me.from_pydata(mesh.verts, [], [list(f) for f in mesh.faces])
        me.update()
        slots = mesh.materials
        for colour in slots:
            if colour not in materials:
                mat = bpy.data.materials.new(colour)
                mat.use_nodes = True
                bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if bsdf:
                    bsdf.inputs['Base Color'].default_value = (*COLOURS[colour], 1.0)
                mat.diffuse_color = (*COLOURS[colour], 1.0)
                materials[colour] = mat
            me.materials.append(materials[colour])
        for poly, colour in zip(me.polygons, mesh.mats):
            poly.material_index = slots.index(colour)
            poly.use_smooth = False
        return me


def _fmt(v):
    s = f'{float(v):.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def mesh_file(actor_name):
    """Asset file name the exporter writes for an actor's mesh."""
    return actor_name.lower().replace('-', '_') + '.iff'


# ── Actor fields (Blender custom properties the WF exporter reads) ────────────
def apply_part_actor_fields(obj):
    """A rig part: anchored platform, Mass 0, visible mesh, no script (see module docstring)."""
    obj['wf_schema_path'] = os.path.join(OAD_DIR, 'platform.oad')
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_original_mesh_name'] = mesh_file(obj.name)
    for key in ('wf_Script', 'wf_original_bbox', 'wf_had_authored_bbox'):
        if key in obj:
            del obj[key]


# ── Python mirror of the per-tick maths (mockup + test expectations; the engine runs Forth) ──
def smoothstep(w):
    return w * w * (3.0 - 2.0 * w)


def lerp(a, b, t):
    return a + (b - a) * t


class RigState:
    """Mirror of fish-player-tick + fish-rig-tick (exact sine instead of Bhaskara)."""

    def __init__(self, fish=None):
        self.T = (fish or Clownfish()).T
        self.w = self.idle_t = self.heading = self.heading_target = 0.0
        self.ph = dict(bob=0.0, sway=0.0, tail=0.0, pec=0.0, dorsal=0.0)
        self.vx = self.vz = 0.0

    def copy(self):
        other = RigState.__new__(RigState)
        other.__dict__.update({k: (dict(v) if isinstance(v, dict) else v) for k, v in self.__dict__.items()})
        return other

    def step(self, dt, dx=0, dz=0, drag=PHYSICS['wf_Horiz Air Drag']):
        """One tick. vx/vz model the Player: the AirHandler drags the written speed before
        Jolt integrates it, and nothing is written after release (the glide)."""
        T = self.T
        moving = dx != 0 or dz != 0
        if dx:
            self.vx = dx * T['fish-swim-speed']
        if dz:
            self.vz = dz * T['fish-swim-speed']
        self.vx *= max(0.0, 1.0 - drag * dt)
        self.vz *= max(0.0, 1.0 - drag * dt)
        if dx > 0:
            self.heading_target = 0.0
        elif dx < 0:
            self.heading_target = -0.5
        stepmax = 0.5 * dt / T['fish-turn-time']
        self.heading += max(-stepmax, min(stepmax, self.heading_target - self.heading))
        self.idle_t = 0.0 if moving else self.idle_t + dt
        if self.idle_t >= T['fish-idle-delay']:
            self.w = min(1.0, self.w + dt / T['fish-idle-in'])
        else:
            self.w = max(0.0, self.w - dt / T['fish-idle-out'])
        ws = smoothstep(self.w)
        for ch, hz in (('bob', T['fish-bob-hz']), ('sway', T['fish-sway-hz']),
                       ('tail', lerp(T['fish-tail-swim-hz'], T['fish-tail-idle-hz'], ws)),
                       ('pec', lerp(T['fish-pec-swim-hz'], T['fish-pec-idle-hz'], ws)),
                       ('dorsal', T['fish-dorsal-hz'])):
            self.ph[ch] = (self.ph[ch] + hz * dt) % 1.0

    def channels(self):
        T = self.T
        ws = smoothstep(self.w)
        s = lambda r: math.sin(math.tau * r)
        tail = lerp(T['fish-tail-swim-amp'], T['fish-tail-idle-amp'], ws) * s(self.ph['tail'])
        pec = lerp(T['fish-pec-swim-amp'], T['fish-pec-idle-amp'], ws) * s(self.ph['pec'])
        return dict(
            ws=ws, tail=tail, pec=pec,
            bob=ws * T['fish-bob-amp'] * s(self.ph['bob']),
            body_c=self.heading + ws * T['fish-sway-yaw'] * s(self.ph['sway']) - T['fish-counter-yaw'] * tail,
            body_b=ws * T['fish-sway-pitch'] * s(self.ph['sway'] + 0.25),
            dorsal=1.0 - ws * T['fish-dorsal-amp'] * (0.5 - 0.5 * math.cos(math.tau * self.ph['dorsal'])),
        )


def rot_matrix(a, b, c):
    """Engine Euler (revolutions) → 3×3 whose ROWS are the world images of local X, Y, Z (matrix34.cc:106-114)."""
    A, B, C = (math.tau * v for v in (a, b, c))
    sA, cA, sB, cB, sC, cC = math.sin(A), math.cos(A), math.sin(B), math.cos(B), math.sin(C), math.cos(C)
    return ((cB * cC, cB * sC, -sB),
            (sB * sA * cC - cA * sC, sB * sA * sC + cA * cC, cB * sA),
            (sB * cA * cC + sA * sC, sB * cA * sC - sA * cC, cB * cA))


def apply(rows, p):
    return tuple(p[0] * rows[0][i] + p[1] * rows[1][i] + p[2] * rows[2][i] for i in range(3))


def part_poses(fish, ch, player_pos):
    """{part: (pivot world position, (a, b, c), z_scale)} for one tick's channels — what fish-rig-tick writes."""
    body = (player_pos[0], player_pos[1], player_pos[2] + ch['bob'])
    rows = rot_matrix(0.0, ch['body_b'], ch['body_c'])
    flare = fish.T['fish-pec-flare']
    rot = {
        'clownfish-body': (0.0, ch['body_b'], ch['body_c']),
        'clownfish-tail': (0.0, ch['body_b'], ch['body_c'] + ch['tail']),
        'clownfish-dorsal': (0.0, ch['body_b'], ch['body_c']),
        'clownfish-pec-near': (0.0, ch['body_b'] + ch['pec'], ch['body_c'] + flare),
        'clownfish-pec-far': (0.0, ch['body_b'] - ch['pec'], ch['body_c'] - flare),
    }
    out = {}
    for name, _, off in fish.parts():
        wo = apply(rows, off)
        out[name] = (tuple(b + o for b, o in zip(body, wo)), rot[name],
                     ch['dorsal'] if name == 'clownfish-dorsal' else 1.0)
    return out


if __name__ == '__main__':
    fish = Clownfish()
    for name, mesh, off in fish.parts():
        lo, hi = mesh.bbox()
        print(f"{name:20s} {len(mesh.verts):4d} v {len(mesh.faces):4d} f  vol {mesh.signed_volume():+.6f} m³  "
              f"mats {mesh.materials}  bbox {tuple(round(v, 3) for v in lo)}..{tuple(round(v, 3) for v in hi)}  "
              f"pivot {tuple(round(v, 3) for v in off)}")
    print(f"world ×{fish.world_scale:g}: length {fish.length_m:.3f} m, {fish.s * 1000:.3f} mm per drawing unit")
    print("extents", {k: round(v, 3) for k, v in fish.extents().items()})
    print("collision box", tuple(round(v, 3) for v in fish.collision_box()))
    for scale in (10, 1):
        a = Clownfish(scale).min_triangle_area()
        print(f"×{scale}: smallest triangle {a:.2e} m² (engine floor {ENGINE_MIN_TRIANGLE_M2:.2e}) "
              f"→ {'OK' if a > 2 * ENGINE_MIN_TRIANGLE_M2 else 'TOO SMALL: this mesh cannot load at this scale'}")
