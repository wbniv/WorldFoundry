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
#
# Material layout (matches arcade Q*bert's 3-tone iso shading):
#   mat 0 = top face (+Z) — state-dependent colour
#   mat 1 = lit-side material (faces toward upper-left in iso view)
#   mat 2 = shadow-side material (faces toward lower-right in iso view)
#
# Cubes are rotated 45° about Z by blender_create_qbert.py. After that
# rotation:
#   pre-rotation -X face → LEFT visible side  → LIT  (mat 1)
#   pre-rotation -Y face → RIGHT visible side → SHADOW (mat 2)
#   pre-rotation +X face → back-right (hidden) → SHADOW (mat 2, for symmetry)
#   pre-rotation +Y face → back-left  (hidden) → LIT    (mat 1, for symmetry)
# Bottom face is hidden by the staircase below it; assign it shadow.
FACES = [
    # Bottom (-Z), winding viewed from outside (below) is 0,3,2,1
    (0, 3, 2, 2),
    (0, 2, 1, 2),
    # Top (+Z)  — state-dependent colour
    (4, 5, 6, 0),
    (4, 6, 7, 0),
    # Front (-Y)  — right-visible after 45° rot → SHADOW
    (0, 1, 5, 2),
    (0, 5, 4, 2),
    # Right (+X)  — back-right (hidden) → SHADOW
    (1, 2, 6, 2),
    (1, 6, 5, 2),
    # Back (+Y)  — back-left (hidden) → LIT
    (2, 3, 7, 1),
    (2, 7, 6, 1),
    # Left (-X)  — left-visible after 45° rot → LIT
    (3, 0, 4, 1),
    (3, 4, 7, 1),
]


def build_modl(top_rgb, lit_side_rgb, shadow_side_rgb):
    """Build a complete MODL chunk for a cube with three materials.

    `top_rgb` is the +Z face colour (state-dependent). `lit_side_rgb` and
    `shadow_side_rgb` are the lit/shadow side colours (round-dependent,
    constant across states — only the top changes on hop). All three
    are 24-bit integers in 0xRRGGBB order.

    Materials use `LIGHTING_PRELIT` (Material::LIGHTING_PRELIT = 4 in
    wfsource/source/gfx/material.hp) so the renderer treats colours as
    pre-lit and skips the dynamic-lighting attenuation that was rendering
    shadow-side teal as near-black. With this flag, authored RGB reaches
    the framebuffer untouched — matching the arcade's fixed lit/shadow
    palette per face.

    Vertex colours are white (0xFFFFFF) so each face inherits its material
    colour cleanly.
    """
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

    # ── MATL chunk: 3 materials ───────────────────────────────────────────────
    # mat 0 = top face (state-dependent colour)
    # mat 1 = lit side  (constant per round, arcade #56A999 for L1R1)
    # mat 2 = shadow side (constant per round, arcade #314646 for L1R1)
    LIGHTING_PRELIT = 4
    mat_flags = LIGHTING_PRELIT
    tex_bytes = b'\x00' * 256
    matl = (
        struct.pack('<iI', mat_flags, top_rgb)         + tex_bytes +
        struct.pack('<iI', mat_flags, lit_side_rgb)    + tex_bytes +
        struct.pack('<iI', mat_flags, shadow_side_rgb) + tex_bytes
    )

    # ── Assemble MODL ─────────────────────────────────────────────────────────
    inner = (
        iff_chunk('VRTX', bytes(vrtx)) +
        iff_chunk('MATL', matl) +
        iff_chunk('FACE', bytes(face_data))
    )
    return iff_chunk('MODL', inner)


# ── Per-round palette ─────────────────────────────────────────────────────────
# 4 rounds per level cycle.  Each entry: (state0_top, state2_top, side_rgb).
# State 1 (mid-hop intermediate) is a shared orange placeholder for all rounds.
#
# Source: docs/investigations/2026-05-04-qbert-arcade-palette-all-rounds.md
#   R0 (L1R1): ROM-verified, complete.
#   R1 (L1R2): target confirmed; start is a placeholder (original not captured).
#   R2 (L1R3): start confirmed; target is a placeholder (late-round not captured).
#   R3 (L1R4): start confirmed; target is a placeholder (late-round not captured).
# Re-run scripts/research/mame/qbert_palette_capture.lua to fill gaps.
ROUND_COLORS = [
    # (state0_top,  state2_top,  lit_side,  shadow_side)
    (0x5646EF,     0xDEDE00,    0x56A999,  0x314646),  # R0 L1R1 — purple→yellow,    teal  / dark-teal  (all 4 ROM-confirmed)
    (0xAC46AC,     0xEFDE77,    0xFF7721,  0x663100),  # R1 L1R2 — magenta→golden,   orange / dark-orange (start_top placeholder)
    (0xB9CECE,     0x3399CC,    0x777777,  0x212121),  # R2 L1R3 — silver→blue,      gray   / near-black  (target_top placeholder)
    (0x0066EF,     0xCC8822,    0x778888,  0x101099),  # R3 L1R4 — blue→amber,       gray-teal / dark-blue (target_top placeholder)
]
STATE1_TOP = 0xCC7733  # intermediate orange placeholder, all rounds


if __name__ == '__main__':
    import shutil
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)
    total = 0
    for r, (s0_top, s2_top, lit_side, shadow_side) in enumerate(ROUND_COLORS):
        for state, top_rgb in [(0, s0_top), (1, STATE1_TOP), (2, s2_top)]:
            modl = build_modl(top_rgb, lit_side, shadow_side)
            proto = os.path.join(out_dir, f'cube_state{state}_r{r}.iff')
            with open(proto, 'wb') as f:
                f.write(modl)
            print(f'Wrote {len(modl):4d} bytes → {proto}  '
                  f'(top 0x{top_rgb:06X}  lit 0x{lit_side:06X}  shadow 0x{shadow_side:06X})')
            total += 1
    print(f'Generated {total} source IFFs ({len(ROUND_COLORS)} rounds × 3 states).')
