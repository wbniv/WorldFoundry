#!/usr/bin/env python3
"""DFRM v1 reference evaluator and the dfrm_strand parity driver.

The maths is the tail-rig mockup's (docs/plans/2026-10-16-saltwater-seahorses/
tail-rig.html: interp, expand, fk), extended the way the engine evaluator
(wfsource/source/renderassets/dfrm_deform.cc) extends it: clip playback with
crossfade, the additive knot layer, the wrap override with the vertical-post
lead-in, the clamp, forward kinematics with re-orthonormalisation every 8
samples, rigid vertices, weighted transforms, face normals and the write-backs.
Double precision throughout; the C++ evaluator runs in float.

    dfrm_ref.py --check BINARY    the dfrm_strand ctest: writes test meshes, runs
                                  BINARY --eval on the seven mockup poses (and a
                                  clip/crossfade sequence), compares to 1e-4,
                                  then runs BINARY --unit on the generated files.
    dfrm_ref.py --write DIR       only write the test meshes.
"""
from __future__ import annotations

import argparse
import math
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'wftools' / 'wf_blender'))
import dfrm_chunk as dc  # noqa: E402

# ── The tail (mockup constants, mm; the level uses metres x WORLD_SCALE 10) ──
N = 35
KN = [0, 6, 12, 18, 24, 30, 34]
MM = 0.01                                        # 1 mm in model units
LEN = [3.75 * 0.9764 ** i for i in range(N)]     # 3.75 -> 1.67 mm, sum ~ 90 mm
WID = [9.0 + (1.4 - 9.0) * (i / N) ** 0.85 for i in range(N + 1)]


def LIM(i, n=N):
    t = i / (n - 1)
    return (12 + 28 * t, 4 + 8.5 * t, 8 + 20 * t, 3 + 5 * t)   # ventral, dorsal, lateral, twist


PRESETS = {   # tail-rig.html PRESETS: knot flex, body pitch, wrap (mode, start, radius mm, progress)
    'rest':    ([2, 3, 6, 11, 19, 28, 36], 4, ('off', 18, 4, 0)),
    'branch':  ([4, 5, 7, 8, 8, 8, 8], 8, ('h', 18, 4, 1)),
    'stem':    ([3, 4, 4, 4, 4, 4, 4], -4, ('v', 16, 6, 1)),
    'swim':    ([-2, 0, 2, 3, 5, 8, 12], -6, ('off', 18, 4, 0)),
    'probe':   ([9, 8, 6, 3, 1, 4, 12], -14, ('off', 18, 4, 0)),
    'twine':   ([3, 4, 4, 4, 4, 4, 4], -2, ('v', 16, 5.5, 1)),
    'startle': ([-3, -3, -2, -2, -1, 0, 2], 0, ('off', 18, 4, 0)),
}
MODES = {'off': 0, 'h': 1, 'v': 2}
TOL = 1e-4

# ── small vector helpers ──


def sub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def normalize(a):
    n = math.sqrt(dot(a, a))
    return [x / n for x in a] if n > 1e-12 else None


def rot(a, c, ang):
    C, S = math.cos(ang), math.sin(ang)
    return [a[k] * C + c[k] * S for k in range(3)], [c[k] * C - a[k] * S for k in range(3)]


def orthonormalize(d, v):
    d = normalize(d)
    v = normalize([v[k] - dot(v, d) * d[k] for k in range(3)])
    return d, v, cross(v, d)


def rodrigues(axis, ang, x):
    C, S = math.cos(ang), math.sin(ang)
    ax = cross(axis, x)
    k = dot(axis, x) * (1 - C)
    return [x[i] * C + ax[i] * S + axis[i] * k for i in range(3)]


def face_normal(p0, p1, p2):
    """gfx/face.hpi CalculateNormal: (v2 - v0) x (v1 - v0), normalised."""
    return normalize(cross(sub(p2, p0), sub(p1, p0)))


def hermite(knots, vals, x):
    """tail-rig.html interp(): non-uniform cubic Hermite, Catmull-Rom tangents."""
    n = len(knots)
    k = 0
    while k < n - 2 and x > knots[k + 1]:
        k += 1

    def m(j):
        if j <= 0:
            return (vals[1] - vals[0]) / (knots[1] - knots[0])
        if j >= n - 1:
            return (vals[j] - vals[j - 1]) / (knots[j] - knots[j - 1])
        return (vals[j + 1] - vals[j - 1]) / (knots[j + 1] - knots[j - 1])
    x0, x1, y0, y1 = knots[k], knots[k + 1], vals[k], vals[k + 1]
    h = x1 - x0
    s = (x - x0) / h
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * y0 + (s3 - 2 * s2 + s) * h * m(k) + (-2 * s3 + 3 * s2) * y1 + (s3 - s2) * h * m(k + 1)


# ── the reference evaluator ──

class Rig:
    """A decoded DFRM chunk plus the rest mesh, as RenderObject3D loads it."""

    def __init__(self, chunk: dict, rest, faces):
        self.c = chunk
        cv = chunk['curves'][0]
        self.d0, self.v0, self.s0 = orthonormalize(normalize(cv['d']), normalize(cv['v']))
        self.root = cv['root']
        self.knots = cv['knots']
        self.rest = rest
        self.faces = faces
        self.rest_normals = [face_normal(rest[a], rest[b], rest[c]) for a, b, c in faces]
        self.pitch = math.degrees(math.atan2(-self.d0[0], -self.d0[2]))
        self.rest_joints = [self.root[:]]
        for smp in chunk['samples']:
            self.rest_joints.append([self.rest_joints[-1][k] + self.d0[k] * smp['length'] for k in range(3)])

    def bound_rest(self, influence):
        """Where the rig places a sample-bound vertex at rest (joint + offset)."""
        _kind, i, a, b, c = influence
        return [self.rest_joints[i][k] + a * self.d0[k] + b * self.v0[k] + c * self.s0[k] for k in range(3)]


def world_rotation(pitch=0.0, roll=0.0):
    """An actor's world rotation as the engine passes it: 9 floats, row i = model
    axis i in world. Pitch turns about the model's side axis (Y), roll about X."""
    p, r = math.radians(pitch), math.radians(roll)
    ry = [[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]]
    rx = [[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]]
    m = [[sum(rx[i][k] * ry[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return [m[j][i] for i in range(3) for j in range(3)]   # columns (axis images) as rows


def evaluate(rig: Rig, block, now, world=None, chain_only=False):
    """chain_only skips vertices and face normals (the joints, angles and write-backs
    are unchanged): the behaviour tests and pose traces step it thousands of times."""
    c = rig.c
    S, T = c['samples'], c['transforms']
    n, nt = len(S), len(T)
    stride = 3 * n + nt
    frames, clips = c['frames'], c['clips']

    def clip_of(cid):
        k = int(math.floor(cid + 0.5)) if cid >= 0 else -int(math.floor(-cid + 0.5))
        return clips[k - 1] if 1 <= k <= len(clips) and abs(cid - k) < 1e-3 else None

    def sample(cl, start):
        f = max(0.0, now - start) * cl['fps']
        cnt = cl['frames']
        if cl['loop']:
            f = math.fmod(f, cnt)
            i0 = min(int(math.floor(f)), cnt - 1)
            i1, a = (i0 + 1) % cnt, f - i0
        elif f >= cnt - 1:
            i0 = i1 = cnt - 1
            a = 0.0
        else:
            i0 = int(math.floor(f))
            i1, a = i0 + 1, f - i0
        p0, p1 = frames[cl['first'] + i0], frames[cl['first'] + i1]
        return [p0[k] if a == 0 else p0[k] + (p1[k] - p0[k]) * a for k in range(stride)]

    A = [0.0] * stride
    ca, cb = clip_of(block[25]), clip_of(block[27])
    if ca:
        A = sample(ca, block[26])
    if cb:
        B = sample(cb, block[28])
        fade = block[29]
        w = (now - block[28]) / fade if fade > 0 else (1.0 if now >= block[28] else 0.0)
        w = min(1.0, max(0.0, w))
        if w >= 1:
            A = B
        elif w > 0:
            A = [A[k] + (B[k] - A[k]) * w for k in range(stride)]

    nk = len(rig.knots)
    kf = [block[3 * k] for k in range(nk)]
    kl = [block[3 * k + 1] for k in range(nk)]
    kt = [block[3 * k + 2] for k in range(nk)]
    F = [A[3 * i] + hermite(rig.knots, kf, i) for i in range(n)]
    L = [A[3 * i + 1] + hermite(rig.knots, kl, i) for i in range(n)]
    Tw = [A[3 * i + 2] + hermite(rig.knots, kt, i) for i in range(n)]

    mode = int(math.floor(block[21] + 0.5))
    radius, progress = block[23], min(1.0, max(0.0, block[24]))
    wrapping = mode in (1, 2) and progress > 0 and radius > 0
    start = min(float(n), max(0.0, block[22]))
    s = n - (n - start) * progress
    if wrapping and mode == 2:
        # World-vertical post: flex phi makes d horizontal with v up when
        # d0.u cos phi + v0.u sin phi = 0 and v.u > 0 (u = world up in model axes).
        pitch = rig.pitch
        if world is not None:
            u = normalize([world[2], world[5], world[8]])
            if u:
                a, cc = dot(rig.d0, u), dot(rig.v0, u)
                if a * a + cc * cc > 1e-8:
                    phi = math.degrees(math.atan2(cc, a)) - 90
                    while phi > 180:
                        phi -= 360
                    while phi <= -180:
                        phi += 360
                    pitch = phi - 90
        i0 = max(0, int(math.floor(s)) - 5)
        acc = -pitch + sum(F[:i0])
        per, w = (90 - acc) / 5, min(1.0, progress * 4)
        for i in range(i0, min(n, i0 + 5)):
            F[i] = F[i] * (1 - w) + per * w
            L[i] *= (1 - w)
    if wrapping:
        for i in range(n):
            w = max(0.0, min(1.0, i + 1 - s))
            if w == 0:
                continue
            kap = math.degrees(S[i]['length'] / (radius + S[i]['half_width']))
            if mode == 1:
                F[i] = F[i] * (1 - w) + kap * w
                L[i] *= (1 - w)
            else:
                L[i] = L[i] * (1 - w) + kap * w
                F[i] *= (1 - w)
            Tw[i] *= (1 - w)

    clamped = False
    for i in range(n):
        ven, dor, lat, tw = S[i]['limits']
        if F[i] > ven:
            F[i], clamped = ven, True
        if F[i] < -dor:
            F[i], clamped = -dor, True
        if abs(L[i]) > lat:
            L[i], clamped = math.copysign(lat, L[i]), True
        if abs(Tw[i]) > tw:
            Tw[i], clamped = math.copysign(tw, Tw[i]), True
    xf = []
    for t in range(nt):
        a = A[3 * n + t] + block[30 + t]
        v = min(T[t]['hi'], max(T[t]['lo'], a))
        clamped = clamped or v != a
        xf.append(v)

    d, v, sv, p = rig.d0[:], rig.v0[:], rig.s0[:], rig.root[:]
    joints, fr = [p[:]], []
    for i in range(n):
        d, v = rot(d, v, math.radians(F[i]))
        d, sv = rot(d, sv, math.radians(L[i]))
        v, sv = rot(v, sv, math.radians(Tw[i]))
        if (i + 1) % 8 == 0:
            d, v, sv = orthonormalize(d, v)
        fr.append((d[:], v[:], sv[:]))
        p = [p[k] + d[k] * S[i]['length'] for k in range(3)]
        joints.append(p[:])

    pos = []
    for vi, (kind, index, a, b, cc) in enumerate([] if chain_only else c['influences']):
        r = rig.rest[vi]
        if kind == dc.ON_SAMPLE:
            dd, vv, ss = fr[index]
            pos.append([joints[index][k] + a * dd[k] + b * vv[k] + cc * ss[k] for k in range(3)])
        elif kind == dc.ON_TRANSFORM:
            tr = T[index]
            axis = normalize(tr['axis'])
            o = rodrigues(axis, math.radians(xf[index] * a), sub(r, tr['pivot']))
            pos.append([o[k] + tr['pivot'][k] for k in range(3)])
        else:
            pos.append(list(r))

    infl = c['influences']
    normals = []
    for fi, (ia, ib, ic) in enumerate([] if chain_only else rig.faces):
        ka, kb, kc = infl[ia], infl[ib], infl[ic]
        same = ka[0] == kb[0] == kc[0] and ka[1] == kb[1] == kc[1]
        rn = rig.rest_normals[fi]
        if same and ka[0] == dc.NONE:
            normals.append(rn)
        elif same and ka[0] == dc.ON_SAMPLE:
            rn = face_normal(*(rig.bound_rest(k) for k in (ka, kb, kc))) or rn
            co = (dot(rn, rig.d0), dot(rn, rig.v0), dot(rn, rig.s0))
            dd, vv, ss = fr[ka[1]]
            normals.append([co[0] * dd[k] + co[1] * vv[k] + co[2] * ss[k] for k in range(3)])
        elif same and ka[0] == dc.ON_TRANSFORM and ka[2] == kb[2] == kc[2]:
            normals.append(rodrigues(normalize(T[ka[1]]['axis']), math.radians(xf[ka[1]] * ka[2]), rn))
        else:
            normals.append(face_normal(pos[ia], pos[ib], pos[ic]) or rn)

    centre = [0.0, 0.0, 0.0]
    if wrapping:
        j = min(n - 1, max(0, int(math.ceil(s))))
        dd, vv, ss = fr[j]
        nrm = vv if mode == 1 else ss
        theta = math.radians(F[j] if mode == 1 else L[j])
        if abs(theta) > 1e-4:
            h = S[j]['length'] * 0.5 / math.tan(theta * 0.5)
            centre = [0.5 * (joints[j][k] + joints[j + 1][k]) + nrm[k] * h for k in range(3)]
        else:
            centre = [joints[j][k] + nrm[k] * (radius + S[j]['half_width']) for k in range(3)]
    return {'status': 3 if clamped else 0, 'positions': pos, 'normals': normals,
            'outputs': centre + joints[n], 'joints': joints, 'angles': (F, L, Tw)}


# ── test meshes ──

def _fixed(x):
    return int(round(x * 65536))


def modl(positions, faces, dfrm_payload, extra_vertices=0):
    """A MODL IFF the engine's RenderObject3D loads: VRTX, MATL, FACE, DFRM."""
    def chunk(tag, payload):
        return tag.encode() + struct.pack('<I', len(payload)) + payload + b'\0' * ((4 - len(payload) % 4) % 4)
    verts = list(positions) + [positions[-1]] * extra_vertices
    vrtx = b''.join(struct.pack('<iiIiii', 0, 0, 0xFFFFFF, *(_fixed(x) for x in p)) for p in verts)
    matl = struct.pack('<iI', 0, 0xC08040) + b'\0' * 256
    face = b''.join(struct.pack('<hhhh', a, b, c, 0) for a, b, c in faces)
    inner = chunk('VRTX', vrtx) + chunk('MATL', matl) + chunk('FACE', face) + chunk('DFRM', dfrm_payload)
    return chunk('MODL', inner)


def quantized(positions):
    return [[_fixed(x) / 65536 for x in p] for p in positions]


def strand(pitch=0.0, n=N, lengths=None, half=None, limits=None, sides=4, knots=KN, transforms=True,
           extras=True, clips=()):
    """A test tail: square (or n-gon) rings with 15 % plate overlap, rigid per ring,
    plus head/eye transform faces, an unbound face and a face spanning two rings."""
    lengths = lengths or [LEN[i] * MM for i in range(n)]
    half = half or [WID[i] / 2 * MM for i in range(n)]
    limits = limits or [LIM(i, n) for i in range(n)]
    b = math.radians(pitch)
    d, v = [-math.sin(b), 0.0, -math.cos(b)], [math.cos(b), 0.0, -math.sin(b)]
    s = cross(v, d)
    heads, p = [], [0.0, 0.0, 0.0]
    for i in range(n):
        heads.append(p[:])
        p = [p[k] + d[k] * lengths[i] for k in range(3)]
    chain = [{'head': heads[i], 'tail': [heads[i][k] + d[k] * lengths[i] for k in range(3)], 'z_axis': v,
              'limits': limits[i], 'half_width': half[i]} for i in range(n)]
    positions, faces, bindings = [], [], []

    def add(pt, binding):
        positions.append(pt)
        bindings.append(binding)
        return len(positions) - 1

    def tri(a, bb, c, outward):
        pa, pb, pc = positions[a], positions[bb], positions[c]
        nrm = face_normal(pa, pb, pc)
        centroid = [(pa[k] + pb[k] + pc[k]) / 3 for k in range(3)]
        faces.append((a, bb, c) if nrm and dot(nrm, sub(centroid, outward)) >= 0 else (a, c, bb))

    for i in range(n):
        ring = []
        for end in (0.0, 1.15 * lengths[i]):
            for k in range(sides):
                ang = 2 * math.pi * k / sides + math.pi / sides
                r = half[i] * math.sqrt(2) if sides == 4 else half[i]
                ov, os_ = r * math.cos(ang), r * math.sin(ang)
                ring.append(add([heads[i][j] + end * d[j] + ov * v[j] + os_ * s[j] for j in range(3)], (dc.ON_SAMPLE, i, 1.0)))
        mid = [heads[i][k] + d[k] * lengths[i] * 0.575 for k in range(3)]
        for k in range(sides):
            a0, a1, e0, e1 = ring[k], ring[(k + 1) % sides], ring[sides + k], ring[sides + (k + 1) % sides]
            tri(a0, a1, e1, mid)
            tri(a0, e1, e0, mid)
    xfs = []
    if transforms:
        xfs = [{'pivot': [0.0, 0.0, 0.6], 'axis': [0.0, 1.0, 0.0], 'lo': -30.0, 'hi': 30.0},
               {'pivot': [0.03, 0.02, 0.7], 'axis': [0.0, 0.0, 1.0], 'lo': -40.0, 'hi': 40.0},
               {'pivot': [0.03, -0.02, 0.7], 'axis': [0.0, 0.0, 1.0], 'lo': -40.0, 'hi': 40.0}]
    if extras and transforms:
        for t, w in ((0, 1.0), (0, 0.5), (1, 1.0), (2, 1.0)):
            pv = xfs[t]['pivot']
            a = add([pv[0] + 0.05, pv[1] + 0.01, pv[2] + 0.02], (dc.ON_TRANSFORM, t, w))
            bb = add([pv[0] + 0.06, pv[1] - 0.01, pv[2] + 0.03], (dc.ON_TRANSFORM, t, w))
            c = add([pv[0] + 0.04, pv[1], pv[2] + 0.05], (dc.ON_TRANSFORM, t, w))
            faces.append((a, bb, c))
    if extras:
        a = add([0.2, 0.0, 0.3], (dc.NONE, 0, 0.0))
        bb = add([0.25, 0.01, 0.3], (dc.NONE, 0, 0.0))
        c = add([0.22, 0.0, 0.35], (dc.NONE, 0, 0.0))
        faces.append((a, bb, c))
        span = 3 if n > 4 else 0
        faces.append((span * 2 * sides + sides, (span + 1) * 2 * sides, (span + 1) * 2 * sides + 1))  # spans two rings
    payload = dc.build_chunk(chain, positions, bindings, xfs, list(clips), knots)
    return positions, faces, payload


def preset_block(name):
    f, _pitch, (mode, start, r, p) = PRESETS[name]
    block = [0.0] * 40
    for k in range(7):
        block[3 * k] = float(f[k])
    block[21], block[22], block[23], block[24] = MODES[mode], start, r * MM, p
    return block


def clip_set():
    """Clips for the parity sequence and the C++ clip tests (stride 3 x 35 + 3)."""
    stride = 3 * N + 3
    sway = []
    for k in range(30):
        row = []
        for i in range(N):
            ph = 2 * math.pi * k / 30 + 0.2 * i
            row += [3 * math.sin(ph), 2 * math.cos(ph), math.sin(ph)]
        sway.append(row + [10 * math.sin(2 * math.pi * k / 30), 15.0, -15.0])
    flick = [[(-1.5 * k if j % 3 == 0 else 0.0) for j in range(3 * N)] + [k * 4.0, 0, 0] for k in range(10)]
    ramp = [[(2.0 * k if j % 3 == 0 else 0.0) for j in range(stride)] for k in range(4)]   # flex 0, 2, 4, 6
    wave = [[(x if j % 3 == 0 else 0.0) for j in range(stride)] for x in (1.0, -1.0, 3.0)]
    hold = [[(5.0 if j % 3 == 0 else 0.0) for j in range(stride)]]
    return [{'name': 'sway', 'loop': True, 'frames': sway}, {'name': 'flick', 'loop': False, 'frames': flick},
            {'name': 'ramp', 'loop': False, 'frames': ramp}, {'name': 'wave', 'loop': True, 'frames': wave},
            {'name': 'hold', 'loop': False, 'frames': hold}]


def write_files(out: Path):
    """The meshes BINARY --unit reads."""
    out.mkdir(parents=True, exist_ok=True)
    pos, faces, payload = strand()
    (out / 'strand.iff').write_bytes(modl(pos, faces, payload))
    (out / 'bad_count.iff').write_bytes(modl(pos, faces, payload, extra_vertices=1))
    bad = bytearray(payload)
    bad[0:4] = struct.pack('<I', 2)
    (out / 'bad_version.iff').write_bytes(modl(pos, faces, bytes(bad)))
    bad = bytearray(payload)
    _v, _f, _nc, ns, nt = struct.unpack_from('<5I', payload, 0)
    struct.pack_into('<H', bad, 32 + 52 + 16 * ns + 28 * nt + 2, 99)    # first influence -> sample 99
    (out / 'bad_index.iff').write_bytes(modl(pos, faces, bytes(bad)))
    # Two full coils: 40 uniform samples, 18 degrees each at the holdfast radius.
    n = 40
    pos, faces, payload = strand(n=n, lengths=[0.02] * n, half=[0.003] * n, limits=[(90, 90, 90, 30)] * n,
                                 knots=(0, 6, 13, 19, 26, 32, 39), transforms=False, extras=False)
    (out / 'coil.iff').write_bytes(modl(pos, faces, payload))
    pos, faces, payload = strand(clips=clip_set())
    (out / 'clips.iff').write_bytes(modl(pos, faces, payload))
    pos, faces, payload = strand(sides=13)   # ~900 vertices, seahorse-sized, for timing
    (out / 'dense.iff').write_bytes(modl(pos, faces, payload))


# ── parity driver ──

def run_eval(binary, mesh: Path, blocks):
    """BINARY --eval MESH BLOCKS -> one result per block line."""
    bpath = mesh.with_suffix('.blocks')
    bpath.write_text(''.join(' '.join(repr(float(x)) for x in [e[0]] + list(e[1]) + (list(e[2]) if len(e) > 2 else []))
                             + '\n' for e in blocks))
    out = subprocess.run([str(binary), '--eval', str(mesh), str(bpath)], check=True, capture_output=True, text=True).stdout
    results, cur = [], None
    for line in out.splitlines():
        tag, *vals = line.split()
        if tag == 'S':
            cur = {'status': int(vals[0]), 'positions': [], 'normals': [], 'outputs': []}
            results.append(cur)
        elif tag == 'V':
            cur['positions'].append([float(x) for x in vals[1:]])
        elif tag == 'N':
            cur['normals'].append([float(x) for x in vals[1:]])
        elif tag == 'O':
            cur['outputs'] = [float(x) for x in vals]
    return results


def compare(name, got, want):
    worst = 0.0
    for key in ('positions', 'normals'):
        if len(got[key]) != len(want[key]):
            return f'{name}: {key} count {len(got[key])} != {len(want[key])}', worst
        for a, b in zip(got[key], want[key]):
            worst = max(worst, max(abs(x - y) for x, y in zip(a, b)))
    worst = max(worst, max(abs(x - y) for x, y in zip(got['outputs'], want['outputs'])))
    if got['status'] != want['status']:
        return f"{name}: status {got['status']} != {want['status']}", worst
    if worst > TOL:
        return f'{name}: max difference {worst:.3g} > {TOL}', worst
    return None, worst


def check(binary: Path) -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix='dfrm-') as tmp:
        tmp = Path(tmp)
        cases = []
        for name in PRESETS:
            pos, faces, payload = strand(pitch=PRESETS[name][1])
            cases.append((name, pos, faces, payload, [(0.0, preset_block(name))]))
        # Clip playback and crossfade: sway (loop) fading into flick (one-shot), knots on top.
        pos, faces, payload = strand(clips=clip_set())
        seq = []
        for now in (0.0, 0.37, 1.0, 1.5, 1.83, 2.6, 4.0):
            b = preset_block('swim')
            b[25], b[26], b[27], b[28], b[29] = 1, 0.1, 2, 1.0, 1.2
            b[30], b[31], b[32] = 5.0, -3.0, 50.0
            seq.append((now, b))
        cases.append(('clips', pos, faces, payload, seq))
        # Vertical posts are world-vertical: the same poses on a pitched and rolled actor.
        for name, pitch, roll in (('stem', 15.0, 0.0), ('stem', -15.0, 0.0), ('twine', 10.0, 6.0)):
            pos, faces, payload = strand(pitch=PRESETS[name][1])
            cases.append((f'{name}-world{pitch:+g}{roll:+g}', pos, faces, payload,
                          [(0.0, preset_block(name), world_rotation(pitch, roll))]))
        for name, pos, faces, payload, blocks in cases:
            mesh = tmp / f'{name}.iff'
            mesh.write_bytes(modl(pos, faces, payload))
            rig = Rig(dc.decode(payload), quantized(pos), faces)
            got = run_eval(binary, mesh, blocks)
            if len(got) != len(blocks):
                print(f'FAIL {name}: {len(got)} results for {len(blocks)} blocks')
                failures += 1
                continue
            for step, (entry, result) in enumerate(zip(blocks, got)):
                now, block, *world = entry
                err, worst = compare(f'{name}[{step}]', result, evaluate(rig, block, now, world[0] if world else None))
                print(('FAIL ' + err) if err else f'ok   parity {name}[{step}] max |C++ - Python| = {worst:.2e}')
                failures += bool(err)
        write_files(tmp / 'unit')
        unit = subprocess.run([str(binary), '--unit', str(tmp / 'unit')], text=True)
        failures += unit.returncode != 0
    print(f"dfrm_strand: {'PASS' if not failures else f'FAIL ({failures})'}")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--check', type=Path, metavar='BINARY')
    ap.add_argument('--write', type=Path, metavar='DIR')
    args = ap.parse_args()
    if args.write:
        write_files(args.write)
    if args.check:
        return check(args.check)
    return 0


if __name__ == '__main__':
    sys.exit(main())
