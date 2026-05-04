#!/usr/bin/env python3
"""Generate cube_state{0,1,2}.iff for qbert_practice.

Three colour variants of a 2×2×2 cube centred on its own origin. Each
variant is a flat-shaded mesh with one solid material colour. The
qbert_practice level instantiates 28 cubes × 3 variants = 84 mesh
actors; per-tick Forth scripts gate visibility based on
INDEXOF_CUBE_STATE_BASE+N value matching the variant.

Format mirrors gen_ramp.py — MODL chunk containing VRTX, MATL, FACE.
Vertex stride: 24 bytes (u, v, color, x, y, z) all 16.16 fixed-point
except color which is a packed RGB uint32. Face stride: 8 bytes
(v1, v2, v3, mat_idx) signed 16-bit each.
"""

import os
import struct
import sys


def fx(v):
    """Float to 1.15.16 fixed-point integer."""
    return int(round(v * 65536))


def iff_chunk(tag, payload):
    """Serialise one IFF chunk: 4-byte ASCII tag + LE uint32 size + payload + pad to 4-byte alignment."""
    tag_bytes = tag.encode('ascii')[:4].ljust(4, b'\x00')
    size = len(payload)
    pad = (4 - size % 4) % 4
    return tag_bytes + struct.pack('<I', size) + payload + b'\x00' * pad


# ── Cube geometry: 2×2×2 cube centred on object origin ────────────────────────
S = 1.0  # half-extent

# 8 corners
CORNERS = [
    (-S, -S, -S),  # 0
    ( S, -S, -S),  # 1
    ( S,  S, -S),  # 2
    (-S,  S, -S),  # 3
    (-S, -S,  S),  # 4
    ( S, -S,  S),  # 5
    ( S,  S,  S),  # 6
    (-S,  S,  S),  # 7
]

# Each face is two triangles, CCW from outside. UV doesn't matter for
# flat-shaded so we use (0,0) on every vertex.
FACES = [
    # Bottom (-Z), winding viewed from outside (below) is 0,3,2,1  — mat 1 (side)
    (0, 3, 2, 1),
    (0, 2, 1, 1),
    # Top (+Z)  — mat 0 (top, state-dependent colour)
    (4, 5, 6, 0),
    (4, 6, 7, 0),
    # Front (-Y)  — mat 1 (side)
    (0, 1, 5, 1),
    (0, 5, 4, 1),
    # Right (+X)  — mat 1 (side)
    (1, 2, 6, 1),
    (1, 6, 5, 1),
    # Back (+Y)  — mat 1 (side)
    (2, 3, 7, 1),
    (2, 7, 6, 1),
    # Left (-X)  — mat 1 (side)
    (3, 0, 4, 1),
    (3, 4, 7, 1),
]


def build_modl(top_rgb, side_rgb=None):
    """Build a complete MODL chunk for a cube with two materials.

    `top_rgb` is the +Z face colour (state-dependent). `side_rgb` is the
    colour for all other faces (constant across states). Both are 24-bit
    integers in 0xRRGGBB order.

    Vertex colours are white (0xFFFFFF) so each face inherits its material
    colour cleanly under the engine's multiplicative lighting model.
    """
    if side_rgb is None:
        side_rgb = SIDE_RGB

    # ── VRTX chunk ────────────────────────────────────────────────────────────
    vrtx = bytearray()
    for x, y, z in CORNERS:
        vrtx += struct.pack(
            '<iiIiii',
            fx(0.0), fx(0.0), 0xFFFFFF,
            fx(x), fx(y), fx(z),
        )

    # ── FACE chunk ────────────────────────────────────────────────────────────
    face_data = bytearray()
    for v1, v2, v3, mat in FACES:
        face_data += struct.pack('<hhhh', v1, v2, v3, mat)

    # ── MATL chunk: 2 materials ───────────────────────────────────────────────
    # mat 0 = top face (state-dependent colour)
    # mat 1 = all side faces (arcade lit teal; engine lighting darkens oblique faces)
    mat_flags = 0
    tex_bytes = b'\x00' * 256
    matl = (
        struct.pack('<iI', mat_flags, top_rgb) + tex_bytes +
        struct.pack('<iI', mat_flags, side_rgb) + tex_bytes
    )

    # ── Assemble MODL ─────────────────────────────────────────────────────────
    inner = (
        iff_chunk('VRTX', bytes(vrtx)) +
        iff_chunk('MATL', matl) +
        iff_chunk('FACE', bytes(face_data))
    )
    return iff_chunk('MODL', inner)


# ── Palette — Arcade Q*bert level 1 round 1 (ROM-verified) ───────────────────
# All values pixel-sampled from lossless MAME 0.264 PNG against the vendored
# qbert.zip ROM. Source: docs/plans/screenshots/qbert-arcade-attract-gameplay-reference.png
# (240×256 attract-mode frame, 13 unique colours — matches Gottlieb 16-colour CLUT).
#
# Side: arcade fakes 3D with two baked shades (lit #56A999, shadow #314646).
# We use the lit value and let engine multiplicative lighting darken oblique faces.
SIDE_RGB = 0x56A999   # arcade lit teal

VARIANTS = [
    (0, 0x5646EF),  # state 0 — untouched: purple (ROM-verified; NOT teal)
    (1, 0xCC7733),  # state 1 — intermediate: orange placeholder (L2+ only; unused under L1 rule)
    (2, 0xDEDE00),  # state 2 — target: yellow (ROM-verified)
]


if __name__ == '__main__':
    import glob, shutil
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)
    for state, top_rgb in VARIANTS:
        modl = build_modl(top_rgb)
        proto = os.path.join(out_dir, f'cube_state{state}.iff')
        with open(proto, 'wb') as f:
            f.write(modl)
        print(f'Wrote {len(modl):4d} bytes → {proto}  (top 0x{top_rgb:06X}  side 0x{SIDE_RGB:06X})')
        # Propagate to per-instance IFFs (cube_NN_sS.iff) so the build is
        # always in sync without needing a full Blender re-export.
        copied = 0
        for dst in sorted(glob.glob(os.path.join(out_dir, f'cube_??_s{state}.iff'))):
            shutil.copyfile(proto, dst)
            copied += 1
        if copied:
            print(f'  → propagated to {copied} per-instance IFFs')
