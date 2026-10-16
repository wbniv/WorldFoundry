"""Longsnout seahorse (Hippocampus reidi): ring-plated body with a 35-joint DFRM
tail, fins, eight clips, one shared atlas, and the two saltwater hitching posts.

Geometry is in model units (metres x WORLD_SCALE 10, so 1 mm = 0.01). The model
faces +X (ventral), Z is up, and the origin is the tail base, the root of the
DFRM curve: in the straight bind pose the tail hangs down -Z. A held seahorse
hangs from its tail, so the "base at local z = 0" rule for resting meshes does
not apply; it is an exception, like spheres.

The tail table, joint limits and knot maths are dfrm_ref.py's (the mockup's).
Each tail ring is a rigid box bound to one bone; its plates reach 15 % under the
next ring and no vertex is shared across a joint. The trunk does not deform; the
head and eyes are weighted transforms. Clips are pure data here (clip_frames) so
tests can read them without Blender; armature() keys them as Blender actions.

docs/plans/2026-10-16-saltwater-seahorses.md, Phase 2. Anatomy and colour:
docs/reference/seahorse-research.md (the colourways are ours).
"""
import math
from pathlib import Path

from mesh import Mesh
import dfrm_ref as ref

dc = ref.dc

# ── dimensions (ours; see the plan's tail table) ──
WORLD_SCALE = 10
MM = ref.MM                                   # 1 mm in model units
N_TAIL = ref.N                                # 35 tail rings, one joint each
N_TRUNK = 11                                  # trunk rings
KNOTS = ref.KN
TAIL_LEN = [ref.LEN[i] * MM for i in range(N_TAIL)]
TAIL_WID = [ref.WID[i] * MM for i in range(N_TAIL + 1)]      # ring i is TAIL_WID[i] wide; the tip ends at [35]
TAIL_LIMITS = [ref.LIM(i) for i in range(N_TAIL)]           # (ventral, dorsal, lateral, twist) degrees
BEVEL_RINGS = 20          # rings 0..19 get chamfered corners; the narrow distal rings stay square
BEVEL = .30               # chamfer, as a fraction of the half-width
OVERLAP = .15             # each ring's plates reach 15 % under the next ring
ROOT_SLEEVE = .35         # ring 0 starts this far (x its length) inside the trunk
LIMIT_USE = .97           # clips stay inside 97 % of every joint limit
HEAD_LIMITS = (-20.0, 35.0)   # head pitch, degrees (+ = snout up)
EYE_LIMITS = (-40.0, 40.0)    # eye yaw, degrees (+ = toward the seahorse's left, +Y)
MIN_CROSS = 6.1e-5            # vector3.hpi:243: |(v2-v0)x(v1-v0)| must exceed this

TEXTURE = 'seahorse_atlas.tga'
ATLAS = 256
COLORS = dict(seahorse_body=(1, 1, 1), seahorse_fin=(1, 1, 1),
              seahorse_whip=(.60, .17, .24), seahorse_branch=(.58, .49, .37))
FIN_OPACITY = .62
SEXES = ('f', 'm')
COLOURWAY = {'f': 'yellow female', 'm': 'orange male with a brood pouch'}

# ── clips: name -> (seconds, loop) ──
CLIPS = {'rest_coil': (3.0, True), 'swim': (1.5, True), 'hold_idle': (3.0, True),
         'probe': (2.0, False), 'release': (1.0, False), 'startle': (0.5, False),
         'greet_f': (6.0, True), 'greet_m': (6.0, True)}
CLIP_IDS = {name: i + 1 for i, name in enumerate(sorted(CLIPS))}   # the exporter's 1-based name order
FPS = dc.FPS
HOLD_FREE = 11            # hold_idle moves rings 0..10 only: a stem wrap (start 16) and its lead-in cover 11..34

# ── level integration (Phase 3: behaviour, settings and visibility) ──
# Pair n (seahorses 2n, 2n+1) shows on PAIR_VISIBILITY[n] when the water is saltwater and the
# Seahorses setting (Director field 8) is >= n + 1. The posts show with pair 1: None and
# freshwater hide them too. The urchin keeps 1160.
PAIR_VISIBILITY = (1162, 1163)
POST_VISIBILITY = PAIR_VISIBILITY[0]
BLOCK_BASE, BLOCK_STRIDE = 1200, 100
GREET_BASE = 1600                       # 1600..1609: shared greeting state and the current-block pointer
SETTING_COUNT, SETTING_GREETING = 8, 9  # Director fields (settings.oas, "Seahorses" sheet)
FIN_RATE = 2.2                          # slowed, blurred wave (ours): the real beat is 20-60 Hz
SAND = .635
POSTS = [
    # name, base (x, y, z), grip segments: (mode, start, end, radius at start, radius at end), offsets from base.
    # Both stand near the front glass and rise above the mature foliage (about z 3.1), so they stay visible.
    ('seahorse-whip', (-3.10, -.70, SAND - .05), [(2, (0, 0, 0), (0, 0, 3.75), .060, .034)]),
    ('seahorse-branch', (3.00, -.65, SAND - .05), [(2, (0, 0, 0), (0, 0, 3.40), .075, .055),
                                                   (1, (0, 0, 3.00), (1.00, 0, 3.00), .045, .038)]),
]
# Grip spots (ours): (grip segment, coil-centre height in world z, yaw in turns; 0 faces +X).
# Vertical segments only. A held seahorse hangs about 0.38 above its coil and stands
# 0.6 tall, so on the arm (z 3.585) its head would reach the water surface (4.83) and
# it would have to arrive from above it; the arm stays a pose (seahorse_poses.py).
# Spots on one side of a post are >= 0.9 apart, so one seahorse's tail never reaches the
# head below it; the highest head stays under the water surface and the arm.
SEXES_BY_SEAHORSE = ('f', 'm', 'f', 'm')
SPOTS = [(0, 2.55, 0.0),     # whip, low: the female's greeting spot
         (0, 3.30, 0.5),     # whip, far side: the male's greeting spot (tails at offset heights)
         (0, 3.50, 0.0),     # whip, high
         (1, 2.50, 0.5),     # trunk, low, under the arm (head below z 3.54)
         (1, 3.40, 0.0)]     # trunk, high, on the side away from the arm
GREET_SPOTS = (0, 1)         # female, male
HOME = (2, 1, 4, 3)          # each seahorse's spot on entry
FIRST_REST = (20.0, 6.0, 48.0, 34.0)   # seconds each holds before its first swim (staggered)
GREET_SECONDS = 120.0        # about two minutes on one post (ours)
SWIM_SPEED = .15             # 1.5 cm/s real x WORLD_SCALE 10 (ours)
CRUISE_Z = 3.5               # swims stay above the foliage until they near the post
ENTRY_PROGRESS = .15         # the wrap progress the approach aims the tail tip for

# ── atlas layout (pixels; v = y / 256, as goby.py) ──
STRIP_X = {'f': 0, 'm': 96}             # body strip and head region columns, 96 px each
FIN_X = {'f': 192, 'm': 224}            # fin columns, 32 px each, full height (V is root -> tip)
TRUNK_V = (6.0, 62.0)                   # trunk top (ring boundary 11) -> bottom (boundary 0)
TAIL_V0, TAIL_BAND = 64.0, 3.48         # tail ring i: TAIL_V0 + TAIL_BAND * (i .. i + 1.15)
HEAD_V0, HEAD_SCALE, HEAD_X0, HEAD_Z0 = 194.0, 2.25, -1.0, 67.0
EYE_UV = (84.0, 246.0, 7.0)             # eye island centre (x offset in the column, y) and radius


def _hash(x, y, seed=0):
    h = (x * 374761393 + y * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) / 0xFFFFFFFF


# ── vector helpers ──
def _sub(a, b): return [a[i] - b[i] for i in range(3)]
def _add(a, b): return [a[i] + b[i] for i in range(3)]
def _scale(a, k): return [x * k for x in a]
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return [x / n for x in a]


def _newell(points):
    n = [0.0, 0.0, 0.0]
    for p, q in zip(points, points[1:] + points[:1]):
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class SeahorseMesh(Mesh):
    """Mesh with one UV and one (vertex group, weight) per emitted vertex."""

    def __init__(self, name):
        super().__init__(name)
        self.uvs, self.groups = [], []

    def face(self, points, color, uvs, group=None, inside=None):
        """Emit a polygon; with ``inside``, wound to face away from that point."""
        _face_groups(self, points, uvs, [group] * len(points), inside, color)


# ── body ──
# Trunk ring boundaries, bottom (0, at the tail base) to top (11, the neck):
# z, centre x, ventral half-depth, dorsal half-depth, half-width (mm). Ours.
TRUNK = [(0.0, 0.0, 4.6, 4.5, 4.4), (4.0, .8, 6.6, 4.8, 5.2), (8.0, 1.6, 8.6, 5.2, 5.9),
         (12.0, 2.2, 10.4, 5.6, 6.4), (16.0, 2.5, 11.6, 5.9, 6.6), (20.0, 2.5, 12.0, 6.0, 6.6),
         (24.0, 2.3, 11.4, 5.9, 6.4), (28.0, 2.0, 10.0, 5.6, 6.0), (32.0, 1.7, 8.2, 5.2, 5.5),
         (36.0, 1.6, 6.6, 4.9, 5.0), (40.0, 1.9, 5.4, 4.6, 4.6), (43.6, 2.6, 4.7, 4.3, 4.2)]
# Neck and head centreline after the trunk: x, z, ventral, dorsal, half-width (mm), head weight.
HEAD = [(3.9, 47.4, 4.5, 4.4, 4.1, 0.0), (5.6, 51.2, 4.9, 4.8, 4.3, .5), (8.2, 54.6, 5.6, 5.9, 4.6, 1.0),
        (11.6, 56.6, 5.8, 5.6, 4.7, 1.0), (15.4, 56.4, 4.6, 4.3, 3.8, 1.0), (19.4, 55.3, 2.7, 2.5, 2.3, 1.0),
        (26.8, 53.3, 2.1, 2.0, 1.9, 1.0), (33.8, 51.5, 2.4, 2.3, 2.2, 1.0)]
SNOUT_TIP = (34.6, 51.3)
EYE = (11.4, 4.25, 57.6, 2.4)            # x, |y|, z, radius (mm)
CORONET = (7.4, 60.6, 1.9)               # crown centre x, z, ring radius (mm)
SIDES = 8


def _pouch(sex, z):
    """The male's brood pouch: a ventral bulge over the lowest trunk rings (mm)."""
    return 3.4 * math.exp(-((z - 5.5) / 5.0) ** 2) if sex == 'm' else 0.0


def _strip_u(sex, frac):
    return (STRIP_X[sex] + 2 + 92 * frac) / ATLAS


def trunk_v(k):
    """Atlas V of trunk ring boundary k (0 bottom .. 11 top, fractional allowed)."""
    return (TRUNK_V[0] + (TRUNK_V[1] - TRUNK_V[0]) * (N_TRUNK - k) / N_TRUNK) / ATLAS


def tail_v(i):
    return (TAIL_V0 + TAIL_BAND * i) / ATLAS


def head_uv(sex, x_mm, z_mm):
    return ((STRIP_X[sex] + 2 + (x_mm - HEAD_X0) * HEAD_SCALE) / ATLAS,
            (HEAD_V0 + (HEAD_Z0 - z_mm) * HEAD_SCALE) / ATLAS)


def _centreline(sex):
    """Trunk boundaries and mid-ring grooves, then the neck and head: dicts in mm."""
    pts = []
    for k in range(N_TRUNK + 1):
        z, cx, af, ab, b = TRUNK[k]
        pts.append(dict(c=(cx, z), af=af + _pouch(sex, z), ab=ab, b=b, w=0.0, v=trunk_v(k), region='strip'))
        if k < N_TRUNK:
            z2, cx2, af2, ab2, b2 = TRUNK[k + 1]
            zm = (z + z2) / 2
            pts.append(dict(c=((cx + cx2) / 2, zm), af=.93 * (af + af2) / 2 + _pouch(sex, zm),
                            ab=.93 * (ab + ab2) / 2, b=.93 * (b + b2) / 2, w=0.0, v=trunk_v(k + .5), region='strip'))
    for x, z, af, ab, b, w in HEAD:
        pts.append(dict(c=(x, z), af=af, ab=ab, b=b, w=w, v=None, region='head'))
    return pts


def _sections(pts):
    """One 8-sided loop per centreline point, in model units; loop k is ordered by angle
    from the dorsal midline (theta 0) through +Y (pi/2) to ventral (pi)."""
    loops = []
    for j, p in enumerate(pts):
        a, b = pts[max(0, j - 1)]['c'], pts[min(len(pts) - 1, j + 1)]['c']
        t = _norm([b[0] - a[0], 0.0, b[1] - a[1]])
        n = [t[2], 0.0, -t[0]]                      # ventral; (1, 0, 0) on an upright trunk
        c = [p['c'][0] * MM, 0.0, p['c'][1] * MM]
        loop = []
        for k in range(SIDES):
            th = 2 * math.pi * k / SIDES
            cs, sn = math.cos(th), math.sin(th)
            cs = math.copysign(abs(cs) ** .8, cs)
            sn = math.copysign(abs(sn) ** .8, sn)
            rn = (p['ab'] if cs > 0 else p['af']) * MM
            loop.append([c[0] - cs * rn * n[0], p['b'] * MM * sn, c[2] - cs * rn * n[2]])
        loops.append((c, loop))
    return loops


def _group_of(w):
    return ('head', w) if w > 0 else None


def body(sex):
    """Trunk, neck, head, snout, coronet and eyes, then the 35-ring tail."""
    m = SeahorseMesh(f'seahorse_{sex}_body')
    pts = _centreline(sex)
    loops = _sections(pts)
    # Bottom cap (the male's pouch bulges below the tail base, ours).
    c0, l0 = loops[0]
    tip = [c0[0] + (.8 if sex == 'm' else .2) * MM, 0.0, -(1.8 if sex == 'm' else .6) * MM]
    for k in range(SIDES):
        a, b = l0[k], l0[(k + 1) % SIDES]
        fa, fb = k / SIDES, (k + 1) / SIDES
        m.face([a, b, tip], 'seahorse_body', [(_strip_u(sex, fa), trunk_v(0)), (_strip_u(sex, fb), trunk_v(0)),
                                              (_strip_u(sex, (fa + fb) / 2), trunk_v(-.25))],
               inside=[c0[0], 0.0, c0[2] + 2 * MM])
    # The loft: strip mapping up to the neck, then the head's side projection.
    for j in range(len(loops) - 1):
        (ca, la), (cb, lb) = loops[j], loops[j + 1]
        pa, pb = pts[j], pts[j + 1]
        inside = [(ca[i] + cb[i]) / 2 for i in range(3)]
        for k in range(SIDES):
            quad = [la[k], la[(k + 1) % SIDES], lb[(k + 1) % SIDES], lb[k]]
            if pb['region'] == 'strip' or (pa['region'] == 'strip' and pb['w'] == 0):
                fa, fb = k / SIDES, (k + 1) / SIDES
                va = pa['v'] if pa['v'] is not None else trunk_v(N_TRUNK)
                vb = pb['v'] if pb['v'] is not None else trunk_v(N_TRUNK) - 4.0 / ATLAS
                uvs = [(_strip_u(sex, fa), va), (_strip_u(sex, fb), va), (_strip_u(sex, fb), vb), (_strip_u(sex, fa), vb)]
            else:
                uvs = [head_uv(sex, p[0] / MM, p[2] / MM) for p in quad]
            groups = [_group_of(pa['w'])] * 2 + [_group_of(pb['w'])] * 2
            _face_groups(m, quad, uvs, groups, inside)
    # Snout tip: a fan, mouth slightly open.
    cl, ll = loops[-1]
    tipc = [SNOUT_TIP[0] * MM, 0.0, SNOUT_TIP[1] * MM]
    for k in range(SIDES):
        tri = [ll[k], ll[(k + 1) % SIDES], tipc]
        _face_groups(m, tri, [head_uv(sex, p[0] / MM, p[2] / MM) for p in tri], [('head', 1.0)] * 3, cl)
    _coronet(m, sex)
    for side in (1, -1):
        _eye(m, sex, side)
    _tail(m, sex)
    return m


def _face_groups(m, points, uvs, groups, inside, color='seahorse_body'):
    """Emit a polygon wound to face away from ``inside`` (None: as given), keeping
    each vertex's UV and group attached through the flip."""
    points, uvs, groups = list(points), list(uvs), list(groups)
    centroid = [sum(p[i] for p in points) / len(points) for i in range(3)]
    if inside is not None and _dot(_newell([list(p) for p in points]), _sub(centroid, inside)) < 0:
        points.reverse()
        uvs.reverse()
        groups.reverse()
    Mesh.face(m, [tuple(p) for p in points], color)
    m.uvs.extend(uvs)
    m.groups.extend(groups)


def _coronet(m, sex):
    """A stellate crown of five knobs on top of the head (bound to the head)."""
    cx, cz, r = CORONET
    for j in range(5):
        a = 2 * math.pi * j / 5 + .3
        kx, ky = cx + r * math.cos(a) * .8, r * math.sin(a)
        base = [[(kx + .95 * math.cos(b)) * MM, (ky + .95 * math.sin(b)) * MM, (cz - .6) * MM]
                for b in (a, a + 2.094, a + 4.189)]
        apex = [(kx + .5 * math.cos(a)) * MM, ky * 1.25 * MM, (cz + 2.6 + .5 * (j % 2)) * MM]
        inside = [kx * MM, ky * MM, (cz - .4) * MM]
        for q in range(3):
            tri = [base[q], base[(q + 1) % 3], apex]
            _face_groups(m, tri, [head_uv(sex, p[0] / MM, p[2] / MM) for p in tri], [('head', 1.0)] * 3, inside)


def _eye(m, sex, side, segments=6, rings=4):
    """A bulging eye, bound to its eye transform; the island shows iris and pupil."""
    ex, ey, ez, r = EYE
    c = [ex * MM, side * ey * MM, ez * MM]
    cu, cv, cr = EYE_UV
    name = 'eye_l' if side > 0 else 'eye_r'

    def point(i, j):
        a, b = 2 * math.pi * i / segments, math.pi * j / rings
        return [c[0] + r * MM * math.cos(b), c[1] + r * MM * math.sin(b) * math.cos(a) * side,
                c[2] + r * MM * math.sin(b) * math.sin(a)]

    def uv(p):
        return ((STRIP_X[sex] + cu + cr * (p[0] - c[0]) / (r * MM)) / ATLAS,
                (cv + cr * (c[2] - p[2]) / (r * MM)) / ATLAS)
    for j in range(rings):
        for i in range(segments):
            pts = [point(i, j), point(i, j + 1), point(i + 1, j + 1), point(i + 1, j)]
            uniq = []
            for p in pts:
                if all(max(abs(p[q] - u[q]) for q in range(3)) > 1e-9 for u in uniq):
                    uniq.append(p)
            if len(uniq) >= 3:
                _face_groups(m, uniq, [uv(p) for p in uniq], [(name, 1.0)] * len(uniq), c)


def ring_section(i):
    """Ring i's cross-section corners in its (ventral v, side s) plane, model units,
    ordered by angle from the dorsal midline (-v) through +s. Bevelled when wide."""
    h = TAIL_WID[i] / 2
    if i < BEVEL_RINGS:
        e = h * (1 - BEVEL)
        pts = [(-h, e), (-e, h), (e, h), (h, e), (h, -e), (e, -h), (-e, -h), (-h, -e)]
    else:
        pts = [(-h, h), (h, h), (h, -h), (-h, -h)]
    return sorted(pts, key=lambda q: math.atan2(q[1], -q[0]) % (2 * math.pi))


def ring_heads():
    """Joint positions down the straight bind pose: head of ring i at z = -sum(len[<i])."""
    z, out = 0.0, []
    for i in range(N_TAIL):
        out.append(z)
        z -= TAIL_LEN[i]
    out.append(z)
    return out


def _tail(m, sex):
    heads = ring_heads()
    for i in range(N_TAIL):
        sec = ring_section(i)
        n = len(sec)
        z0 = heads[i] + (ROOT_SLEEVE * TAIL_LEN[i] if i == 0 else 0.0)
        last = i == N_TAIL - 1
        z1 = heads[i] - TAIL_LEN[i] * (1.0 if last else 1 + OVERLAP)
        shrink = TAIL_WID[N_TAIL] / TAIL_WID[i] if last else 1.0
        near = [[v, s, z0] for v, s in sec]
        far = [[v * shrink, s * shrink, z1] for v, s in sec]
        group = (f'tail_{i:02d}', 1.0)
        v0, v1 = tail_v(i), tail_v(i + (1.0 if last else 1 + OVERLAP))
        for k in range(n):
            th0 = math.atan2(sec[k][1], -sec[k][0]) % (2 * math.pi)
            th1 = math.atan2(sec[(k + 1) % n][1], -sec[(k + 1) % n][0]) % (2 * math.pi) or 2 * math.pi
            if th1 <= th0:
                th1 += 2 * math.pi
            fa, fb = th0 / (2 * math.pi), th1 / (2 * math.pi)
            quad = [near[k], near[(k + 1) % n], far[(k + 1) % n], far[k]]
            uvs = [(_strip_u(sex, fa), v0), (_strip_u(sex, fb), v0), (_strip_u(sex, fb), v1), (_strip_u(sex, fa), v1)]
            _face_groups(m, quad, uvs, [group] * 4, [0.0, 0.0, (z0 + z1) / 2])
        if last:                                  # the tip cap
            tipz = z1 - .8 * TAIL_LEN[i]              # pointed, so the cap keeps a 2x area margin
            for k in range(n):
                tri = [far[k], far[(k + 1) % n], [0.0, 0.0, tipz]]
                fa = k / n
                _face_groups(m, tri, [(_strip_u(sex, fa), v1), (_strip_u(sex, fa + 1 / n), v1),
                                      (_strip_u(sex, fa + .5 / n), v1)], [group] * 3, [0.0, 0.0, z1 + TAIL_LEN[i] * .3])
    return m


# ── fins ──
def _back_x(z):
    """x of the dorsal surface at height z (mm), for the dorsal fin root."""
    if z <= 0:
        return -TAIL_WID[0] / 2 / MM
    for k in range(N_TRUNK):
        z0, cx0, _af0, ab0, _b0 = TRUNK[k]
        z1, cx1, _af1, ab1, _b1 = TRUNK[k + 1]
        if z <= z1:
            t = (z - z0) / (z1 - z0)
            return (cx0 - ab0) * (1 - t) + (cx1 - ab1) * t
    return TRUNK[-1][1] - TRUNK[-1][3]


def fin_rays(sex):
    """(name, roots, tips, us) per fin, in model units; V runs root (0) -> tip (1)."""
    x0 = FIN_X[sex]
    out = []
    zs = [-3.0 + 12.0 * j / 7 for j in range(8)]
    lengths = [4.2, 6.0, 7.2, 7.8, 7.8, 7.2, 6.0, 4.2]
    ang = math.radians(16)
    roots = [[(_back_x(z) + .5) * MM, 0.0, z * MM] for z in zs]
    tips = [[r[0] - L * math.cos(ang) * MM, 0.0, r[2] + L * math.sin(ang) * MM] for r, L in zip(roots, lengths)]
    out.append(('dorsal', roots, tips, [(x0 + 2 + 2.6 * j) / ATLAS for j in range(8)]))
    for side, ux, du in ((1, 22.0, 1.2), (-1, 27.5, 1.0)):
        roots, tips = [], []
        for j in range(5):
            z = 49.4 + 3.2 * j / 4
            phi = math.radians(-35 + 70 * j / 4)     # a fan: the lowest ray points down
            roots.append([4.3 * MM, side * 4.2 * MM, z * MM])
            d = _norm([-math.cos(phi), side * .3, math.sin(phi)])
            tips.append([roots[-1][q] + 4.5 * MM * d[q] for q in range(3)])
        out.append(('pectoral_' + ('l' if side > 0 else 'r'), roots, tips, [(x0 + ux + du * j) / ATLAS for j in range(5)]))
    return out


def fins(sex):
    m = SeahorseMesh(f'seahorse_{sex}_fins')
    for name, roots, tips, us in fin_rays(sex):
        strips = 3 if name == 'dorsal' else 2
        for k in range(len(roots) - 1):
            for j in range(strips):
                t0, t1 = j / strips, (j + 1) / strips

                def p(r, t):
                    return [roots[r][q] * (1 - t) + tips[r][q] * t for q in range(3)]
                m.face([p(k, t0), p(k + 1, t0), p(k + 1, t1), p(k, t1)], 'seahorse_fin',
                       [(us[k], t0), (us[k + 1], t0), (us[k + 1], t1), (us[k], t1)])
    m.groups = [None] * len(m.vertices)
    return m


# ── skeleton ──
def skeleton():
    """Bones in model space: the straight tail chain, then head and eyes."""
    heads = ring_heads()
    bones = []
    for i in range(N_TAIL):
        bones.append(dict(name=f'tail_{i:02d}', head=(0.0, 0.0, heads[i]), tail=(0.0, 0.0, heads[i + 1]),
                          z_axis=(1.0, 0.0, 0.0), limits=TAIL_LIMITS[i], half_width=TAIL_WID[i] / 2))
    ex, ey, ez, _r = EYE
    bones.append(dict(name='head', head=(ex * MM, 0.0, ez * MM), tail=((ex + 10) * MM, 0.0, ez * MM),
                      z_axis=(0.0, 0.0, 1.0), limits=HEAD_LIMITS))        # local X = -Y: + pitches the snout up
    for name, side in (('eye_l', 1), ('eye_r', -1)):
        bones.append(dict(name=name, head=(ex * MM, side * ey * MM, ez * MM), tail=((ex + 3) * MM, side * ey * MM, ez * MM),
                          z_axis=(0.0, 1.0, 0.0), limits=EYE_LIMITS))     # local X = +Z: + yaws toward +Y
    return bones


# ── clips (degrees, per frame: 35 x (flex, lateral, twist), then head, eye L, eye R) ──
def _knots(vals, i):
    return ref.hermite(KNOTS, vals, i)


def _lerp(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


def _saccade(keys, t, period):
    """Eye yaw: holds, with quick (80 ms) moves between targets; loops over period."""
    t %= period
    value = keys[-1][1]
    for start, target in keys:
        if t >= start:
            value = target
    prev = keys[-1][1]
    for start, target in keys:
        if start <= t < start + .08:
            return prev + (target - prev) * smoothstep(start, start + .08, t)
        prev = target
    return value


REST = [2, 3, 6, 11, 19, 28, 36]
SWIM = [-2, 0, 2, 3, 5, 8, 12]
PROBE = [9, 8, 6, 3, 1, 4, 12]
BRANCH = [4, 5, 7, 8, 8, 8, 8]
STARTLE = [-3, -3, -2, -2, -1, 0, 2]


def _pose(name, t):
    """(flex[35], lateral[35], twist[35], head, eye L, eye R) at clip time t."""
    n = N_TAIL
    us = [i / (n - 1) for i in range(n)]
    F, L, T = [0.0] * n, [0.0] * n, [0.0] * n
    head = eyel = eyer = 0.0
    dur = CLIPS[name][0]
    w = 2 * math.pi * t / dur
    if name == 'rest_coil':
        for i, u in enumerate(us):
            F[i] = _knots(REST, i) * (1 + .05 * u * math.sin(w)) + 1.2 * u * math.sin(w - 1.5 * u)
            L[i] = 2.6 * u * (1 - .3 * u) * math.sin(w + .8)
            T[i] = 1.2 * u * math.sin(w - .4)
        head = -2 + 3 * math.sin(w)
        eyel = _saccade([(0.0, 0.0), (.6, 14.0), (1.7, -6.0), (2.6, 0.0)], t, dur)
        eyer = _saccade([(0.0, 0.0), (1.1, -12.0), (2.1, 8.0), (2.85, 0.0)], t, dur)
    elif name == 'swim':
        for i, u in enumerate(us):
            F[i] = _knots(SWIM, i) + 2.5 * u * math.sin(w - 2 * u)
            L[i] = 3.0 * u * math.sin(w - 2.2 * u)            # the tail as a rudder: a travelling wave
            T[i] = 2.0 * u * math.sin(w - 1.0)
        head = -3 + 1.5 * math.sin(w)
        eyel, eyer = 5 * math.sin(w), -5 * math.sin(w + 1)
    elif name == 'hold_idle':
        for i, u in enumerate(us):
            g = 1.0 - smoothstep(6.0, HOLD_FREE - .01, i) if i < HOLD_FREE else 0.0
            F[i] = (2.5 + 2.0 * math.sin(w)) * g             # the body rocks on its holdfast
            L[i] = 3.5 * math.sin(w + .15 * i) * g
            T[i] = 1.0 * math.sin(w) * g
        head = -3 + 4 * math.sin(w + .5)
        eyel = _saccade([(0.0, 0.0), (.4, -10.0), (1.5, 12.0), (2.4, 0.0)], t, dur)
        eyer = _saccade([(0.0, 0.0), (.9, 9.0), (1.9, -14.0), (2.7, 0.0)], t, dur)
    elif name == 'probe':
        e = smoothstep(0.0, 1.2, t)
        base = _lerp(SWIM, PROBE, e)
        for i, u in enumerate(us):
            F[i] = _knots(base, i) + 8 * u ** 3 * (.5 + .5 * math.sin(2 * math.pi * .7 * t - 1.2)) * e
            L[i] = 14 * u * u * math.sin(2 * math.pi * .9 * t) * e        # the tip sweeps for a holdfast
            T[i] = 2.0 * u * math.sin(2 * math.pi * .9 * t) * e
        head, eyel, eyer = -10 * e, -10 * e, 10 * e
    elif name == 'release':
        e = smoothstep(0.0, 1.0, t)
        base = _lerp(BRANCH, SWIM, e)
        for i, u in enumerate(us):
            F[i] = _knots(base, i) - 16 * u * u * math.sin(math.pi * t)      # the tip flicks open as it unwinds
            L[i] = -5 * u * math.sin(math.pi * t)
        head = 4 * math.sin(math.pi * t)
    elif name == 'startle':
        snap, back = smoothstep(0.0, .1, t), smoothstep(.15, .5, t)
        rest, after = [2, 3, 5, 8, 12, 18, 24], [0, 1, 2, 4, 7, 10, 14]
        for i, u in enumerate(us):
            f0 = _knots(rest, i)
            f1 = _knots(STARTLE, i) - 9 * u * u                  # dorsal snap, the tip straightens out
            F[i] = (f0 + (f1 - f0) * snap) * (1 - back) + _knots(after, i) * back
            L[i] = 8 * u * math.sin(math.pi * min(1.0, t / .25)) * (1 - back)
        head = 12 * snap * (1 - back) + 3 * back
        eyel, eyer = 18 * snap * (1 - back), -18 * snap * (1 - back)
    elif name in ('greet_f', 'greet_m'):
        male = name == 'greet_m'
        wp = w + (math.pi / 4 if male else 0.0)                  # the male leads by 0.75 s
        c = .5 - .5 * math.cos(2 * wp)                           # coil, uncoil: twice per 6 s
        sign = -1.0 if male else 1.0                             # tails curl toward each other
        for i, u in enumerate(us):
            F[i] = _knots([2, 3, 5, 8, 12, 16, 20], i) + c * _knots([0, 1, 3, 6, 10, 14, 16], i)
            if male:
                F[i] += 3.0 * (1 - smoothstep(0, 7, i)) * math.sin(4 * wp) ** 2   # pouch display pulses
            L[i] = sign * (6 + 10 * c) * u * math.sin(wp)
            T[i] = 3.0 * u * math.sin(2 * wp)
        head = (4 if male else 2) - 6 * c
        eyel, eyer = 10 * math.sin(wp) * sign, 10 * math.sin(wp) * sign
    for i in range(n):
        ven, dor, lat, tw = TAIL_LIMITS[i]
        F[i] = max(-dor * LIMIT_USE, min(ven * LIMIT_USE, F[i]))
        L[i] = max(-lat * LIMIT_USE, min(lat * LIMIT_USE, L[i]))
        T[i] = max(-tw * LIMIT_USE, min(tw * LIMIT_USE, T[i]))
    head = max(HEAD_LIMITS[0] * LIMIT_USE, min(HEAD_LIMITS[1] * LIMIT_USE, head))
    eyel = max(EYE_LIMITS[0] * LIMIT_USE, min(EYE_LIMITS[1] * LIMIT_USE, eyel))
    eyer = max(EYE_LIMITS[0] * LIMIT_USE, min(EYE_LIMITS[1] * LIMIT_USE, eyer))
    return F, L, T, head, eyel, eyer


def clip_frames(name):
    """Keyed frames at 30 fps. A loop has duration x 30 frames plus a closing key equal
    to the first; a one-shot has duration x 30 + 1 (both ends)."""
    dur, _loop = CLIPS[name]
    count = int(round(dur * FPS))
    rows = []
    for k in range(count + 1):
        F, L, T, head, eyel, eyer = _pose(name, k / FPS)
        row = []
        for i in range(N_TAIL):
            row += [F[i], L[i], T[i]]
        rows.append(row + [head, eyel, eyer])
    return rows


# ── Blender: armature and actions ──
def armature(bpy, name, target, actions=None):
    """An armature at the target mesh object's transform, driving it through an
    Armature modifier, with every clip as an action (muted NLA strips; no active
    action, so the exported rest mesh is unposed). Pass the first rig's actions
    to share them. Returns (rig object, {clip name: action})."""
    import mathutils
    scene = bpy.context.scene
    scene.render.fps, scene.render.fps_base = FPS, 1.0
    data = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, data)
    scene.collection.objects.link(rig)
    rig.matrix_world = target.matrix_world.copy()
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    prev = None
    for b in skeleton():
        eb = data.edit_bones.new(b['name'])
        eb.head, eb.tail = b['head'], b['tail']
        eb.align_roll(b['z_axis'])
        if b['name'].startswith('tail_'):
            if prev is not None:
                eb.parent, eb.use_connect = prev, True
            prev = eb
    bpy.ops.object.mode_set(mode='OBJECT')
    for b in skeleton():
        pb = rig.pose.bones[b['name']]
        pb.rotation_mode = 'QUATERNION'
        con = pb.constraints.new('LIMIT_ROTATION')
        con.owner_space = 'LOCAL'
        if b['name'].startswith('tail_'):
            ven, dor, lat, tw = b['limits']
            data.bones[b['name']]['wf_half_width'] = b['half_width']
            con.use_limit_x = con.use_limit_y = con.use_limit_z = True
            con.min_x, con.max_x = math.radians(-dor), math.radians(ven)
            con.min_y, con.max_y = math.radians(-tw), math.radians(tw)
            con.min_z, con.max_z = math.radians(-lat), math.radians(lat)
        else:
            lo, hi = b['limits']
            con.use_limit_x, con.use_limit_y, con.use_limit_z = True, True, True
            con.min_x, con.max_x = math.radians(lo), math.radians(hi)
    mod = target.modifiers.new('Armature', 'ARMATURE')
    mod.object = rig
    rig.animation_data_create()
    names = [b['name'] for b in skeleton()]
    if actions is None:
        actions = {}
        for clip in sorted(CLIPS):
            dur, loop = CLIPS[clip]
            act = bpy.data.actions.new(clip)
            act.use_fake_user = True
            act['wf_loop'] = loop
            rig.animation_data.action = act
            rows = clip_frames(clip)
            keys = {bn: [] for bn in names}
            for row in rows:
                for i in range(N_TAIL):
                    q = mathutils.Matrix(dc.compose(*row[3 * i:3 * i + 3])).to_quaternion()
                    keys[names[i]].append(q)
                for j, bn in enumerate(names[N_TAIL:]):
                    a = math.radians(row[3 * N_TAIL + j])
                    keys[bn].append(mathutils.Quaternion((math.cos(a / 2), math.sin(a / 2), 0.0, 0.0)))
            for bn in names:
                path = f'pose.bones["{bn}"].rotation_quaternion'
                for idx in range(4):
                    fc = act.fcurve_ensure_for_datablock(rig, path, index=idx, group_name=bn)
                    fc.keyframe_points.add(len(rows))
                    co = []
                    for k, q in enumerate(keys[bn]):
                        co += [1.0 + k, q[idx]]
                    fc.keyframe_points.foreach_set('co', co)
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                    fc.update()
            act.use_frame_range = True
            act.frame_start, act.frame_end = 1.0, 1.0 + round(dur * FPS)
            actions[clip] = act
        rig.animation_data.action = None
    for clip in sorted(actions):
        track = rig.animation_data.nla_tracks.new()
        track.name = clip
        track.strips.new(clip, 1, actions[clip])
        track.mute = True
    target['wf_dfrm_rig'] = True
    for b in skeleton():
        if b['name'] not in target.vertex_groups:
            target.vertex_groups.new(name=b['name'])
    return rig, actions


def add_vertex_groups(obj, mesh):
    """Vertex groups from SeahorseMesh.groups (one entry per emitted vertex)."""
    by_name = {}
    for vi, g in enumerate(mesh.groups):
        if g is None:
            continue
        by_name.setdefault(g[0], {}).setdefault(g[1], []).append(vi)
    for name in sorted(by_name):
        vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        for weight, verts in sorted(by_name[name].items()):
            vg.add(verts, weight, 'REPLACE')


# ── hitching posts ──
def post_segments():
    """World-space grip segments: (mode, start, end, r0, r1); mode 2 vertical, 1 horizontal."""
    out = []
    for _name, base, segs in POSTS:
        for mode, a, b, r0, r1 in segs:
            out.append((mode, tuple(base[i] + a[i] for i in range(3)), tuple(base[i] + b[i] for i in range(3)), r0, r1))
    return out


def post_mesh(index):
    """Tapered 8-sided tubes along each grip segment, capped at the far end (the
    base sits in the sand). Local to the post's base."""
    name, _base, segs = POSTS[index]
    m = Mesh(name.replace('-', '_'))
    key = 'seahorse_whip' if 'whip' in name else 'seahorse_branch'
    sides = 8
    for mode, a, b, r0, r1 in segs:
        d = _norm(_sub(b, a))
        ref_axis = [0.0, 0.0, 1.0] if abs(d[2]) < .9 else [1.0, 0.0, 0.0]
        u = _norm(_cross(d, ref_axis))
        v = _cross(d, u)
        length = math.sqrt(_dot(_sub(b, a), _sub(b, a)))
        rows = max(2, int(math.ceil(length / .35)))
        rings = []
        for j in range(rows + 1):
            t = j / rows
            c = [a[q] + (b[q] - a[q]) * t for q in range(3)]
            r = r0 + (r1 - r0) * t
            rings.append((c, [[c[q] + r * (math.cos(2 * math.pi * k / sides) * u[q] + math.sin(2 * math.pi * k / sides) * v[q])
                               for q in range(3)] for k in range(sides)]))
        for (ca, ra), (cb, rb) in zip(rings, rings[1:]):
            inside = [(ca[q] + cb[q]) / 2 for q in range(3)]
            for k in range(sides):
                quad = [ra[k], ra[(k + 1) % sides], rb[(k + 1) % sides], rb[k]]
                _plain_face(m, quad, key, inside)
        rend = rings[-1][1]
        for k in range(sides):
            _plain_face(m, [rend[k], rend[(k + 1) % sides], list(b)], key, rings[-2][0])
    return m


def _plain_face(m, points, key, inside):
    centroid = [sum(p[i] for p in points) / len(points) for i in range(3)]
    if _dot(_newell([list(p) for p in points]), _sub(centroid, inside)) < 0:
        points = list(reversed(points))
    m.face([tuple(p) for p in points], key)


def _num(v):
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return s if s not in ('', '-0') else '0'


def posts_forth():
    """The grip segments as Forth, in world units: sh-seg ( k -- x0 y0 z0 x1 y1 z1 r0 r1 mode )."""
    segs = post_segments()
    out = ['\\ Seahorse hitching posts, generated by wflevels/aquarium_tanks/seahorse.py (posts_forth).',
           '\\ Grip segments in world units: axis start and end, radius at each end, wrap mode',
           '\\ (2 = vertical holdfast, 1 = horizontal). docs/plans/2026-10-16-saltwater-seahorses.md, D4.',
           f': sh-seg-count {len(segs)} ;',
           ': sh-seg ( k -- x0 y0 z0 x1 y1 z1 r0 r1 mode )']
    for k, (mode, a, b, r0, r1) in enumerate(segs):
        vals = ' '.join(_num(x) for x in (*a, *b, r0, r1, mode))
        if k < len(segs) - 1:
            out.append(f'  dup {k} = if drop {vals} exit then')
        else:
            out.append(f'  drop {vals} ;')
    return '\n'.join(out) + '\n'


def clips_forth():
    """Clip ids (the exporter's 1-based name order) and the block layout."""
    out = ['\\ Seahorse clip ids and DFRM blocks, generated by seahorse.py (clips_forth).']
    for name in sorted(CLIPS):
        out.append(f': sh-clip-{name.replace("_", "-")} {CLIP_IDS[name]} ;')
    out.append(f': sh-block ( s -- mailbox ) {BLOCK_STRIDE} * {BLOCK_BASE} + ;')
    return '\n'.join(out) + '\n'


# ── behaviour (Phase 3) ──
def rig_chunk():
    """The DFRM chain as dfrm_ref reads it, built from this module's tables and clips
    (no Blender, no exported file); a test checks it against the exported chunk."""
    clips, frames = [], []
    for name in sorted(CLIPS):
        _dur, loop = CLIPS[name]
        rows = clip_frames(name)
        if loop:
            rows = rows[:-1]                     # the closing key equals the first: the exporter drops it
        clips.append(dict(first=len(frames), frames=len(rows), fps=float(FPS), loop=loop))
        frames += rows
    samples = [dict(length=TAIL_LEN[i], half_width=TAIL_WID[i] / 2, limits=list(TAIL_LIMITS[i])) for i in range(N_TAIL)]
    transforms = [dict(lo=HEAD_LIMITS[0], hi=HEAD_LIMITS[1]), dict(lo=EYE_LIMITS[0], hi=EYE_LIMITS[1]),
                  dict(lo=EYE_LIMITS[0], hi=EYE_LIMITS[1])]
    return dict(curves=[dict(d=[0.0, 0.0, -1.0], v=[1.0, 0.0, 0.0], root=[0.0, 0.0, 0.0], knots=list(KNOTS))],
                samples=samples, transforms=transforms, frames=frames, clips=clips, influences=[])


_RIG = []


def rig():
    if not _RIG:
        _RIG.append(ref.Rig(rig_chunk(), [], []))
    return _RIG[0]


def wrap_start(radius):
    """The first wrap start (>= 16, which hold_idle assumes) at which no wrapped ring's
    lateral holdfast curvature exceeds LIMIT_USE of its limit (a vertical post)."""
    for start in range(16, N_TAIL - 4):
        if all(math.degrees(TAIL_LEN[i] / (radius + TAIL_WID[i] / 2)) <= LIMIT_USE * TAIL_LIMITS[i][2]
               for i in range(start, N_TAIL)):
            return start
    raise ValueError(f'post radius {radius} is too thin to grip')


def wrap_block(clip, mode, start, radius, progress, clip_start=0.0):
    block = [0.0] * 40
    block[21:25] = [float(mode), float(start), radius, progress]
    block[25], block[26] = float(CLIP_IDS[clip]), clip_start
    return block


def spot(n):
    """Grip spot n: the axis point on its segment, holdfast radius, wrap start, yaw (turns),
    and the body-local wrap centre at entry (ENTRY_PROGRESS, on the probe clip's final reach)
    and when held (progress 1, hold_idle at t = 0), through the reference evaluator."""
    k, z, yaw = SPOTS[n]
    mode, a, b, r0, r1 = post_segments()[k]
    assert mode == 2, 'grip spots are on vertical segments'
    t = (z - a[2]) / (b[2] - a[2])
    assert .05 <= t <= .95, (n, t)
    radius = r0 + (r1 - r0) * t
    start = wrap_start(radius)
    entry = ref.evaluate(rig(), wrap_block('probe', 2, start, radius, ENTRY_PROGRESS), CLIPS['probe'][0],
                         chain_only=True)
    hold = ref.evaluate(rig(), wrap_block('hold_idle', 2, start, radius, 1.0), 0.0, chain_only=True)
    return dict(segment=k, axis=(a[0], a[1], z), radius=radius, start=start, yaw=yaw,
                entry=entry['outputs'][:3], hold=hold['outputs'][:3], hold_velocity=_hold_velocity(start, radius))


def _hold_velocity(start, radius, h=.01):
    """d/dt of the held wrap centre (x, y) at hold_idle t = 0, per second: the Director seeds
    its extrapolation with it when a seahorse appears."""
    a, b = (ref.evaluate(rig(), wrap_block('hold_idle', 2, start, radius, 1.0), t, chain_only=True)['outputs']
            for t in (h, 3.0 - h))      # hold_idle loops at 3 s, so t = -h is t = 3 - h
    return [(a[k] - b[k]) / (2 * h) for k in range(2)]


def body_at(n):
    """Where a seahorse holding spot n stands (world position of its tail base), and its yaw."""
    s = spot(n)
    c, si = math.cos(2 * math.pi * s['yaw']), math.sin(2 * math.pi * s['yaw'])
    hx, hy, hz = s['hold']
    ax, ay, az = s['axis']
    return (ax - (c * hx - si * hy), ay - (si * hx + c * hy), az - hz), s['yaw']


def placements():
    """(sex, position, yaw in radians, clip, clip start) per seahorse: each starts holding its HOME spot."""
    out = []
    for s, sex in enumerate(SEXES_BY_SEAHORSE):
        pos, yaw = body_at(HOME[s])
        out.append((sex, tuple(round(v, 4) for v in pos), 2 * math.pi * yaw, 'hold_idle', -.7 * s))
    return out


def behaviour_forth(director):
    """The generated half of the behaviour: spots and settings. The state machine is
    seahorse_behaviour.fth."""
    out = ['\\ Seahorse grip spots and settings, generated by seahorse.py (behaviour_forth).',
           f': sh-director {director} ;',
           f': sh-spot-count {len(SPOTS)} ;',
           f': sh-swim-speed {_num(SWIM_SPEED)} ; : sh-cruise-z {_num(CRUISE_Z)} ; : sh-greet-time {_num(GREET_SECONDS)} ;',
           f': sh-count sh-director {SETTING_COUNT} property@ if else drop 2 then ;',
           f': sh-greeting sh-director {SETTING_GREETING} property@ if else drop 1 then ;']
    out.append(': sh-first-rest ( s -- seconds ) ' + ' '.join(f'dup {s} = if drop {_num(v)} exit then' for s, v in enumerate(FIRST_REST[:-1]))
               + f' drop {_num(FIRST_REST[-1])} ;')
    out.append(': sh-home ( s -- spot ) ' + ' '.join(f'dup {s} = if drop {n} exit then' for s, n in enumerate(HOME[:-1]))
               + f' drop {HOME[-1]} ;')
    rows = [spot(n) for n in range(len(SPOTS))]
    for name, fn in (('sh-spot ( n -- ax ay az r start yaw )', lambda s: (*s['axis'], s['radius'], s['start'], s['yaw'])),
                     ('sh-spot-off ( n -- ex ey hx hy hz )', lambda s: (*s['entry'][:2], *s['hold'])),
                     ('sh-spot-vel ( n -- vx vy )', lambda s: tuple(s['hold_velocity'])),
                     ('sh-spot-post ( n -- segment )', lambda s: (s['segment'],))):
        out.append(f': {name}')
        for n, s in enumerate(rows):
            vals = ' '.join(_num(v) for v in fn(s))
            out.append(f'  dup {n} = if drop {vals} exit then' if n < len(rows) - 1 else f'  drop {vals} ;')
    return '\n'.join(out) + '\n'


TRIG_WORDS = ('tk-frac', 'tk-sin', 'tk-cos', 'tk-wrap', 'tk-atan-oct', 'tk-atan2')


def forth_definitions(text, names):
    """The named colon definitions from a Forth source, in the order given."""
    import re
    out = []
    for name in names:
        m = re.search(r'^: ' + re.escape(name) + r'\s.*?;$', text, re.S | re.M)
        assert m, name
        out.append(m.group(0))
    return '\n'.join(out) + '\n'


def behaviour_source(director, here=None):
    """Everything the Director needs after the posts and clip ids: the shared trig words
    (controller.fth's; the planted tank's own core lacks them), the generated spots and
    settings, and the state machine (seahorse_behaviour.fth)."""
    here = Path(here) if here else Path(__file__).resolve().parent
    trig = forth_definitions((here / 'controller.fth').read_text(), TRIG_WORDS)
    return trig + behaviour_forth(director) + (here / 'seahorse_behaviour.fth').read_text()


def director_tick(indices):
    """Director tick fragments: (every frame, inside the saltwater branch). Settings and
    visibility run every frame; each visible pair runs its state machines
    (body fins sex s sh-tick; sex 0 = female, 1 = male)."""
    inside = ' shg-tick\n'
    for pair, mb in enumerate(PAIR_VISIBILITY):
        calls = ' '.join(f'{indices[f"seahorse-{s}-body"]} {indices[f"seahorse-{s}-fins"]} '
                         f'{1 if SEXES_BY_SEAHORSE[s] == "m" else 0} {s} sh-tick' for s in (2 * pair, 2 * pair + 1))
        inside += f' {mb} tk@ if {calls} then\n'
    return ' sh-settings\n', inside


# ── atlas ──
def _ring_line(frac, width):
    return math.exp(-(frac / width) ** 2) + math.exp(-((1 - frac) / width) ** 2)


def write_texture(folder):
    """One deterministic 256-square atlas: both colourways' body strips and heads,
    the eye islands, and the fin columns (V root -> tip)."""
    from PIL import Image
    image = Image.new('RGB', (ATLAS, ATLAS))
    px = image.load()
    palette = {
        'f': dict(base=(236, 192, 48), dark=(150, 92, 22), belly=(250, 224, 120), saddle=(252, 236, 170),
                  spot=(168, 104, 34), fin=(250, 236, 172), ray=(204, 160, 60), pouch=None),
        'm': dict(base=(230, 116, 34), dark=(122, 50, 14), belly=(244, 164, 84), saddle=(246, 176, 104),
                  spot=(140, 58, 18), fin=(250, 204, 150), ray=(206, 112, 44), pouch=(248, 196, 126)),
    }
    for sex in SEXES:
        col = palette[sex]
        x0 = STRIP_X[sex]
        for y in range(ATLAS):
            for x in range(x0, x0 + 96):
                grain = (_hash(x, y, 1) - .5) * 14
                if y < 192:
                    rgb = _strip_pixel(sex, col, x - x0, y)
                else:
                    rgb = _head_pixel(sex, col, x - x0, y)
                px[x, y] = tuple(int(max(0, min(255, round(c + grain)))) for c in rgb)
        _fin_column(px, sex, col)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    image.save(folder / TEXTURE)
    return image


def _mix(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]


def _dots(x, y, density, seed):
    return _hash(x, y, seed) < density


def _strip_pixel(sex, col, x, y):
    th = ((x - 2) / 92.0) * 2 * math.pi
    dorsal = math.cos(th)                     # +1 dorsal midline, -1 ventral
    rgb = list(col['base'])
    rgb = _mix(rgb, col['belly'], max(0.0, -dorsal) ** 1.5 * .7)
    if y < TRUNK_V[1] + 1:
        k = N_TRUNK - (y - TRUNK_V[0]) * N_TRUNK / (TRUNK_V[1] - TRUNK_V[0])
        frac = k - math.floor(k)
        ring = int(math.floor(k))
        line = _ring_line(frac, .10)
        if col['pouch'] and ring <= 2 and dorsal < -.2:
            rgb = _mix(rgb, col['pouch'], min(1.0, (-dorsal - .2) * 2.5))
            line *= .4
        if ring in (2, 5, 8) and dorsal > .55:
            rgb = _mix(rgb, col['saddle'], .7)
        rgb = _mix(rgb, col['dark'], min(1.0, line * .8))
        ridge = math.exp(-((abs(math.sin(th * 3.5))) / .18) ** 2) * .25
        rgb = _mix(rgb, col['dark'], ridge)
        if _dots(x // 3, y // 3, .05, 7) and line < .3:
            rgb = _mix(rgb, col['spot'], .8)
    else:
        r = (y - TAIL_V0) / TAIL_BAND
        frac = r - math.floor(r)
        ring = int(math.floor(r))
        rgb = _mix(rgb, col['dark'], min(1.0, _ring_line(frac, .16) * .75))
        corner = math.exp(-((abs(math.cos(2 * th))) / .25) ** 2)
        rgb = _mix(rgb, col['dark'], .30 * (1 - corner))      # plate corners raised, faces darker
        if ring % 5 == 2 and dorsal > .3:
            rgb = _mix(rgb, col['saddle'], .6)
        rgb = _mix(rgb, col['dark'], .25 * min(1.0, ring / 34.0))
    if _dots(x, y, .045 if y >= TAIL_V0 else .03, 3):
        rgb = _mix(rgb, (252, 250, 240), .9)                  # many tiny white dots (Lourie p. 72)
    return rgb


def _head_pixel(sex, col, x, y):
    cu, cv, cr = EYE_UV
    r = math.hypot(x - cu, y - cv) / cr
    if r <= 1.15:
        ang = math.atan2(y - cv, x - cu)
        if r < .42:
            return [12, 12, 14] if math.hypot(x - cu + 1.2, y - cv + 1.2) > 1.0 else [235, 240, 236]
        if r < .82:
            streak = 18 * math.sin(ang * 13)
            return [200 + streak, 150 + streak, 40 + .5 * streak] if sex == 'f' else [210 + streak, 120 + streak, 36]
        if r < .95:
            return list(col['dark'])
        return list(col['base'])
    x_mm = (x - 2) / HEAD_SCALE + HEAD_X0
    z_mm = HEAD_Z0 - (y - HEAD_V0) / HEAD_SCALE
    rgb = list(col['base'])
    if x_mm > 19.0:                           # snout bands
        band = .5 + .5 * math.cos(2 * math.pi * (x_mm - 19.0) / 3.4)
        rgb = _mix(rgb, col['dark'], .35 * band ** 3)
    if z_mm < 53.5 and x_mm < 18:             # pale throat
        rgb = _mix(rgb, col['belly'], .6)
    stripe = math.exp(-((z_mm - (57.6 - .25 * (x_mm - 11.4))) / .9) ** 2) * (1.0 if 4 < x_mm < 19 else 0.0)
    rgb = _mix(rgb, col['dark'], .45 * stripe)            # a dark line through the eye
    if _dots(x, y, .05, 11):
        rgb = _mix(rgb, (252, 250, 240), .9)
    return rgb


def _fin_column(px, sex, col):
    x0 = FIN_X[sex]
    ray_us = [round(u * ATLAS) for _n, _r, _t, us in fin_rays(sex) for u in us]
    for y in range(ATLAS):
        v = y / ATLAS
        for x in range(x0, x0 + 32):
            near = min(abs(x - ru) for ru in ray_us)
            rgb = _mix(col['fin'], (255, 252, 240), v * .6)
            rgb = _mix(rgb, col['ray'], .65 * math.exp(-(near / .7) ** 2) * (1 - .5 * v))
            if abs(v - .93) < .04:
                rgb = _mix(rgb, col['dark'], .35)
            px[x, y] = tuple(int(max(0, min(255, round(c)))) for c in rgb)
