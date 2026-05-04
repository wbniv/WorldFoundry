#!/usr/bin/env python3
"""Generate qbert_player.iff — placeholder Q*bert character mesh.

Stack of two boxes: a wider 'body' bottom box and a narrower 'head' top box.
Both flat-shaded, single material colour each. Total height ~2 units, footprint
~1.4×1.4 units — visible at the MVP camera distance (~17 units from look-at)
without dwarfing the 2×2 cube top it sits on.

The previous placeholder (inherited from mm_practice/player.iff) was a
0.5×0.5×2.5 thin pencil that rendered as a few pixels at this camera distance.

Format mirrors gen_cube.py — one MODL per file with one VRTX, one MATL, one
FACE chunk. Uses the same int24-packed RGB material colour convention.
"""

import os
import struct
import sys


def fx(v):
    return int(round(v * 65536))


def iff_chunk(tag, payload):
    tag_bytes = tag.encode('ascii')[:4].ljust(4, b'\x00')
    size = len(payload)
    pad = (4 - size % 4) % 4
    return tag_bytes + struct.pack('<I', size) + payload + b'\x00' * pad


# Body: 1.4 × 1.4 × 1.0, sits at z=0..1
BODY_HX, BODY_HY, BODY_HZ_LOW, BODY_HZ_HIGH = 0.7, 0.7, 0.0, 1.0
# Head: 1.0 × 1.0 × 1.0, sits at z=1..2
HEAD_HX, HEAD_HY, HEAD_HZ_LOW, HEAD_HZ_HIGH = 0.5, 0.5, 1.0, 2.0


def box_corners(hx, hy, zlo, zhi):
    return [
        (-hx, -hy, zlo), (hx, -hy, zlo), (hx, hy, zlo), (-hx, hy, zlo),
        (-hx, -hy, zhi), (hx, -hy, zhi), (hx, hy, zhi), (-hx, hy, zhi),
    ]


def box_faces(vert_offset, mat_idx):
    o = vert_offset
    return [
        # Bottom (-Z): 0,3,2 / 0,2,1 — CCW from outside (below)
        (o+0, o+3, o+2, mat_idx), (o+0, o+2, o+1, mat_idx),
        # Top (+Z)
        (o+4, o+5, o+6, mat_idx), (o+4, o+6, o+7, mat_idx),
        # Front (-Y)
        (o+0, o+1, o+5, mat_idx), (o+0, o+5, o+4, mat_idx),
        # Right (+X)
        (o+1, o+2, o+6, mat_idx), (o+1, o+6, o+5, mat_idx),
        # Back (+Y)
        (o+2, o+3, o+7, mat_idx), (o+2, o+7, o+6, mat_idx),
        # Left (-X)
        (o+3, o+0, o+4, mat_idx), (o+3, o+4, o+7, mat_idx),
    ]


# Two materials — bright orange body, lighter peach head (Q*bert palette nod).
MATERIALS = [
    0xFF8800,  # body — vivid orange
    0xFFAA66,  # head — peach
]


def build_modl():
    body_v = box_corners(BODY_HX, BODY_HY, BODY_HZ_LOW, BODY_HZ_HIGH)
    head_v = box_corners(HEAD_HX, HEAD_HY, HEAD_HZ_LOW, HEAD_HZ_HIGH)
    all_verts = body_v + head_v

    # ── VRTX ──────────────────────────────────────────────────────────────────
    vrtx = bytearray()
    for x, y, z in all_verts:
        vrtx += struct.pack(
            '<iiIiii',
            fx(0.0), fx(0.0), 0xFFFFFF,
            fx(x), fx(y), fx(z),
        )

    # ── FACE ──────────────────────────────────────────────────────────────────
    face_data = bytearray()
    for v1, v2, v3, mat in box_faces(0, 0) + box_faces(8, 1):
        face_data += struct.pack('<hhhh', v1, v2, v3, mat)

    # ── MATL: 2 entries, both flat-shaded ─────────────────────────────────────
    matl = bytearray()
    for rgb in MATERIALS:
        mat_flags = 0  # FLAT_SHADED | SOLID_COLOR
        tex_bytes = b'\x00' * 256
        matl += struct.pack('<iI', mat_flags, rgb) + tex_bytes

    inner = (
        iff_chunk('VRTX', bytes(vrtx)) +
        iff_chunk('MATL', bytes(matl)) +
        iff_chunk('FACE', bytes(face_data))
    )
    return iff_chunk('MODL', inner)


if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)
    modl = build_modl()
    path = os.path.join(out_dir, 'qbert_player.iff')
    with open(path, 'wb') as f:
        f.write(modl)
    print(f'Wrote {len(modl)} bytes → {path}')
