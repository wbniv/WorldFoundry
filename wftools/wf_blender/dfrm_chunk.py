"""DFRM v1 mesh chunk: build, encode and decode, without bpy.

The exporter (export_level.py, ``wf_dfrm_rig``) gathers a 35-bone tail chain,
the head/eye bones, vertex groups and actions from Blender, then calls
:func:`build_chunk`. Tests build the same inputs by hand. The engine side, the
byte layout and the control block are documented in
wfsource/source/renderassets/dfrm_deform.h; the plan is
docs/plans/2026-10-16-saltwater-seahorses.md (Phase 1, E1).

Conventions (they match the engine's forward kinematics):

* A chain bone's local axes: Y runs along the bone (the engine's ``d``), Z is
  ventral (``v``) and ``s = v x d = -X``.
* A joint's local pose rotation is ``Rx(flex) . Rz(lateral) . Ry(-twist)``:
  flex turns ``d`` toward ``v``, lateral turns ``d`` toward ``s``, twist turns
  ``v`` toward ``s``. :func:`decompose` is its exact inverse: the swing (flex,
  lateral) is read from where the bone axis goes, and the twist is the
  remaining rotation about the bone axis.
* The bind pose is a straight chain: every bone has the root's axes.
* A transform bone (head, eyes) turns about its local X axis.
"""
from __future__ import annotations

import math
import struct

VERSION = 1
FPS = 30
MAX_SAMPLES = 64
MAX_KNOTS = 7
MAX_TRANSFORMS = 3
NONE, ON_SAMPLE, ON_TRANSFORM = 0, 1, 2


def fnv1a(name: str) -> int:
    h = 0x811C9DC5
    for b in name.encode('utf-8'):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def _fixed(v: float) -> int:
    if not math.isfinite(v):
        raise ValueError('DFRM value is not finite')
    f = int(round(v * 65536))
    if not -2**31 <= f < 2**31:
        raise ValueError(f'DFRM value {v} outside 16.16 range')
    return f


def _centi(deg: float) -> int:
    c = int(round(deg * 100))
    if not -32768 <= c <= 32767:
        raise ValueError(f'DFRM angle {deg} outside int16 centidegrees')
    return c


# ── rotations (3x3 row-major nested lists) ────────────────────────────────

def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _t(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def compose(flex: float, lateral: float, twist: float):
    """Joint rotation from degrees, in the bone's local frame."""
    r = math.radians
    return _mul(_mul(rx(r(flex)), rz(r(lateral))), ry(-r(twist)))


def decompose(m) -> tuple[float, float, float]:
    """(flex, lateral, twist) in degrees from a bone-local joint rotation."""
    y = [m[0][1], m[1][1], m[2][1]]                       # where the bone axis goes
    lateral = math.asin(max(-1.0, min(1.0, -y[0])))
    flex = math.atan2(y[2], y[1])
    rest = _mul(_t(_mul(rx(flex), rz(lateral))), m)       # what is left: about the bone axis
    twist = -math.atan2(rest[0][2], rest[0][0])
    return math.degrees(flex), math.degrees(lateral), math.degrees(twist)


def angle_about_x(m) -> float:
    """Degrees of a transform bone's rotation about its local X."""
    return math.degrees(math.atan2(m[2][1], m[1][1]))


# ── building ──────────────────────────────────────────────────────────────

def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    n = math.sqrt(_dot(a, a))
    if n < 1e-12:
        raise ValueError('DFRM: zero-length axis')
    return [x / n for x in a]


def bind_vertices(weights, chain_names, transform_names):
    """Per vertex, its max-weight bone among the chain and the transforms.

    weights: one dict {group name: weight} per vertex. Returns
    (kind, index, weight) per vertex: a chain bone binds rigidly (weight 1),
    a transform bone keeps its weight, no matching group binds to nothing.
    """
    chain = {n: i for i, n in enumerate(chain_names)}
    xf = {n: i for i, n in enumerate(transform_names)}
    out = []
    for groups in weights:
        best = None
        for name, w in sorted(groups.items()):
            if (name in chain or name in xf) and w > 0 and (best is None or w > best[1]):
                best = (name, w)
        if best is None:
            out.append((NONE, 0, 0.0))
        elif best[0] in chain:
            out.append((ON_SAMPLE, chain[best[0]], 1.0))
        else:
            out.append((ON_TRANSFORM, xf[best[0]], min(1.0, best[1])))
    return out


def build_chunk(chain, positions, bindings, transforms=(), clips=(), knots=(0, 6, 12, 18, 24, 30, 34)):
    """Encode a DFRM v1 payload.

    chain: rest bones in mesh space, root first; each a dict with ``head``,
      ``tail``, ``z_axis`` (ventral) and ``limits`` = (ventral, dorsal, lateral,
      twist) degrees; optional ``half_width`` (else the widest bound vertex).
    positions: mesh-space vertex positions in VRTX order.
    bindings: (kind, index, weight) per vertex, in VRTX order.
    transforms: dicts with ``pivot``, ``axis``, ``lo``, ``hi`` (degrees).
    clips: dicts with ``name``, ``loop`` and ``frames``; each frame lists
      3 x len(chain) curve angles (flex, lateral, twist per bone) and then one
      angle per transform, in degrees.
    """
    n = len(chain)
    if not 1 <= n <= MAX_SAMPLES:
        raise ValueError(f'DFRM chain needs 1..{MAX_SAMPLES} bones, got {n}')
    if len(transforms) > MAX_TRANSFORMS:
        raise ValueError('DFRM allows at most 3 transforms')
    knots = [k for k in knots if k < n]
    if knots[-1] != n - 1:
        knots.append(n - 1)
    if not 2 <= len(knots) <= MAX_KNOTS:
        raise ValueError('DFRM needs 2..7 knots')
    if len(positions) != len(bindings):
        raise ValueError('DFRM bindings must match the vertex count')
    root = list(chain[0]['head'])
    d = _norm(_sub(chain[0]['tail'], chain[0]['head']))
    v = _norm(chain[0]['z_axis'])
    if abs(_dot(d, v)) > 1e-3:
        raise ValueError('DFRM root bone Z axis is not perpendicular to the bone')
    s = _cross(v, d)
    lengths = []
    joint = root
    for i, bone in enumerate(chain):          # the bind pose must be a straight chain
        axis = _sub(bone['tail'], bone['head'])
        length = math.sqrt(_dot(axis, axis))
        if length <= 0:
            raise ValueError(f'DFRM bone {i} has zero length')
        if max(abs(a - b) for a, b in zip(bone['head'], joint)) > 1e-4:
            raise ValueError(f'DFRM bone {i} does not start at the end of bone {i - 1}')
        if _dot(_norm(axis), d) < 1 - 1e-5 or abs(_dot(_norm(bone['z_axis']), v)) < 1 - 1e-5:
            raise ValueError(f'DFRM bone {i} is not aligned with the root: the bind pose must be straight')
        lengths.append(length)
        joint = list(bone['tail'])
    heads = [list(b['head']) for b in chain]

    infl = []
    widest = [0.0] * n
    for p, (kind, index, weight) in zip(positions, bindings):
        if kind == ON_SAMPLE:
            rel = _sub(p, heads[index])
            off = (_dot(rel, d), _dot(rel, v), _dot(rel, s))
            widest[index] = max(widest[index], abs(off[1]), abs(off[2]))
            infl.append(struct.pack('<BBHiii', ON_SAMPLE, 0, index, *(_fixed(x) for x in off)))
        elif kind == ON_TRANSFORM:
            if not 0 <= index < len(transforms) or not 0 <= weight <= 1:
                raise ValueError('DFRM transform binding out of range')
            infl.append(struct.pack('<BBHiii', ON_TRANSFORM, 0, index, _fixed(weight), 0, 0))
        else:
            infl.append(struct.pack('<BBHiii', NONE, 0, 0, 0, 0, 0))

    stride = 3 * n + len(transforms)
    clip_rows, frame_rows = [], []
    for c in clips:
        frames = c['frames']
        if not frames or len(frames) > 65535:
            raise ValueError(f"DFRM clip {c['name']} needs 1..65535 frames")
        clip_rows.append(struct.pack('<IHHHHI', fnv1a(c['name']), FPS, len(frames),
                                     1 if c.get('loop') else 0, 0, len(frame_rows)))
        for f in frames:
            if len(f) != stride:
                raise ValueError(f"DFRM clip {c['name']} frame has {len(f)} angles, expected {stride}")
            frame_rows.append(struct.pack('<%dh' % stride, *(_centi(a) for a in f)))

    out = bytearray(struct.pack('<8I', VERSION, 0, 1, n, len(transforms), len(positions),
                                len(clip_rows), len(frame_rows)))
    out += struct.pack('<9i', *(_fixed(x) for x in root + d + v))
    out += struct.pack('<HHB3x', 0, n, len(knots)) + bytes(knots + [0] * (8 - len(knots)))
    for i, bone in enumerate(chain):
        half = bone.get('half_width', widest[i])
        out += struct.pack('<ii4h', _fixed(lengths[i]), _fixed(half), *(_centi(a) for a in bone['limits']))
    for t in transforms:
        axis = _norm(t['axis'])
        out += struct.pack('<6i2h', *(_fixed(x) for x in list(t['pivot']) + axis), _centi(t['lo']), _centi(t['hi']))
    out += b''.join(infl) + b''.join(clip_rows) + b''.join(frame_rows)
    out += b'\0' * ((4 - len(out) % 4) % 4)
    return bytes(out)


def decode(payload: bytes) -> dict:
    """Parse a DFRM v1 payload into plain Python values (for tests and tools)."""
    version, flags, nc, ns, nt, ni, nk, nf = struct.unpack_from('<8I', payload, 0)
    o = 32
    curves = []
    for _ in range(nc):
        vals = struct.unpack_from('<9i', payload, o)
        first, count, nknots = struct.unpack_from('<HHB', payload, o + 36)
        knots = list(payload[o + 44:o + 44 + nknots])
        curves.append({'root': [x / 65536 for x in vals[0:3]], 'd': [x / 65536 for x in vals[3:6]],
                       'v': [x / 65536 for x in vals[6:9]], 'first': first, 'count': count, 'knots': knots})
        o += 52
    samples = []
    for _ in range(ns):
        length, half, *lim = struct.unpack_from('<ii4h', payload, o)
        samples.append({'length': length / 65536, 'half_width': half / 65536, 'limits': [x / 100 for x in lim]})
        o += 16
    transforms = []
    for _ in range(nt):
        vals = struct.unpack_from('<6i2h', payload, o)
        transforms.append({'pivot': [x / 65536 for x in vals[0:3]], 'axis': [x / 65536 for x in vals[3:6]],
                           'lo': vals[6] / 100, 'hi': vals[7] / 100})
        o += 28
    influences = []
    for _ in range(ni):
        kind, _pad, index, a, b, c = struct.unpack_from('<BBHiii', payload, o)
        influences.append((kind, index, a / 65536, b / 65536, c / 65536))
        o += 16
    clips = []
    for _ in range(nk):
        h, fps, count, cflags, _pad, first = struct.unpack_from('<IHHHHI', payload, o)
        clips.append({'hash': h, 'fps': fps, 'frames': count, 'loop': bool(cflags & 1), 'first': first})
        o += 16
    stride = 3 * ns + nt
    frames = [[x / 100 for x in struct.unpack_from('<%dh' % stride, payload, o + 2 * stride * i)] for i in range(nf)]
    return {'version': version, 'flags': flags, 'curves': curves, 'samples': samples, 'transforms': transforms,
            'influences': influences, 'clips': clips, 'frames': frames}
