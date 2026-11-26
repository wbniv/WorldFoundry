"""MRPH mesh chunk (morph targets): encode and decode, without bpy.

The exporter (export_level.py) reads a mesh's shape keys named ``morph_*`` (at
most six, in shape-key order) and, for each, an optional corner colour layer
of the same name holding the target's shade. A mesh with no such keys but
``wf_morph`` set gets a chunk with no targets: a pure tint actor. The engine
side, the byte layout and the channels are documented in
wfsource/source/renderassets/morph_deform.h; the plan is
docs/plans/2026-11-26-lava-lamp.md ("Engine addition E1").

Layout (little-endian): ``u32 version, targets, vertices``; per target a
16-byte NUL-padded name; per target per vertex ``i32 dx dy dz`` (16.16); per
target per vertex ``i16 dr dg db pad`` (1/4096 of full scale, where full
scale is a colour byte of 255).
"""
from __future__ import annotations

import math
import struct

VERSION = 1
MAX_TARGETS = 6
MAX_VERTICES = 32767
PREFIX = 'morph_'
SHADE_ONE = 4096          # i16 shade units per full scale
CHANNELS = 10             # six weights, tint R G B, glow


def target_name(key_name: str) -> str:
    """The name stored in the chunk: the shape key's name after ``morph_``."""
    if not key_name.startswith(PREFIX) or len(key_name) == len(PREFIX):
        raise ValueError(f'MRPH: shape key {key_name!r} is not morph_<name>')
    name = key_name[len(PREFIX):]
    if not name.isascii() or len(name) > 16:
        raise ValueError(f'MRPH: target name {name!r} must be ASCII, at most 16 characters')
    return name


def fixed(v: float) -> int:
    if not math.isfinite(v):
        raise ValueError('MRPH value is not finite')
    q = int(round(v * 65536))
    if not -2**31 <= q < 2**31:
        raise ValueError(f'MRPH delta {v} outside 16.16 range')
    return q


def shade(v: float) -> int:
    if not math.isfinite(v):
        raise ValueError('MRPH shade is not finite')
    q = int(round(v * SHADE_ONE))
    if not -32768 <= q <= 32767:
        raise ValueError(f'MRPH shade delta {v} outside the i16 range')
    return q


def encode(names, positions, shades, vertex_count: int) -> bytes:
    """``names``: target names; ``positions[t][i]`` = (dx, dy, dz) model units;
    ``shades[t][i]`` = (dr, dg, db), 1.0 = a colour byte of 255."""
    if len(names) > MAX_TARGETS:
        raise ValueError(f'MRPH allows at most {MAX_TARGETS} targets, got {len(names)}')
    if not 0 < vertex_count <= MAX_VERTICES:
        raise ValueError(f'MRPH needs 1..{MAX_VERTICES} vertices, got {vertex_count}')
    if len(positions) != len(names) or len(shades) != len(names):
        raise ValueError('MRPH needs one position and one shade table per target')
    out = bytearray(struct.pack('<III', VERSION, len(names), vertex_count))
    for name in names:
        raw = name.encode('ascii')
        if len(raw) > 16:
            raise ValueError(f'MRPH target name {name!r} is longer than 16 bytes')
        out += raw.ljust(16, b'\x00')
    for table in positions:
        if len(table) != vertex_count:
            raise ValueError('MRPH position table must match the vertex count')
        for d in table:
            out += struct.pack('<iii', *(fixed(c) for c in d))
    for table in shades:
        if len(table) != vertex_count:
            raise ValueError('MRPH shade table must match the vertex count')
        for d in table:
            out += struct.pack('<hhhh', *(shade(c) for c in d), 0)
    return bytes(out)


def decode(payload: bytes):
    """The inverse of :func:`encode`: ``(names, positions, shades, vertex_count)``,
    deltas as floats (16.16 and 1/4096 steps)."""
    version, targets, count = struct.unpack_from('<III', payload, 0)
    if version != VERSION or targets > MAX_TARGETS:
        raise ValueError('MRPH: bad header')
    if len(payload) != 12 + targets * (16 + count * 20):
        raise ValueError('MRPH: size does not match the header')
    p = 12
    names = []
    for _ in range(targets):
        names.append(payload[p:p + 16].rstrip(b'\x00').decode('ascii'))
        p += 16
    positions = []
    for _ in range(targets):
        table = []
        for _i in range(count):
            table.append(tuple(v / 65536 for v in struct.unpack_from('<iii', payload, p)))
            p += 12
        positions.append(table)
    shades = []
    for _ in range(targets):
        table = []
        for _i in range(count):
            r, g, b, pad = struct.unpack_from('<hhhh', payload, p)
            if pad:
                raise ValueError('MRPH: shade pad is not zero')
            table.append((r / SHADE_ONE, g / SHADE_ONE, b / SHADE_ONE))
            p += 8
        shades.append(table)
    return names, positions, shades, count


def find_chunk(iff: bytes, tag: bytes = b'MRPH'):
    """The payload of the first ``tag`` chunk inside a mesh file's MODL, or None."""
    if iff[:4] != b'MODL':
        raise ValueError('not a MODL file')
    end = 8 + struct.unpack_from('<I', iff, 4)[0]
    p = 8
    while p + 8 <= end:
        t, size = iff[p:p + 4], struct.unpack_from('<I', iff, p + 4)[0]
        if t == tag:
            return iff[p + 8:p + 8 + size]
        p += 8 + size + (4 - size % 4) % 4
    return None
