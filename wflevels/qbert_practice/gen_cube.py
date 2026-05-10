#!/usr/bin/env python3
"""Generate a single cube.iff for qbert_practice (Phase 1 cube consolidation).

One 2×2×2 flat-shaded cube with three placeholder materials. The level
director writes per-cube colors at runtime via the new EMAILBOX_FACE_COLOR_*
mailboxes (see docs/plans/2026-05-10-qbert-cube-consolidation.md), so the
mesh on disk carries no per-round/per-state color information — only the
geometry and the three material slots.

  mat 0 = TOP   (state-dependent; flips on hop)
  mat 1 = LIT   (constant per level; written on level transition)
  mat 2 = SHADOW (constant per level; written on level transition)

Materials use LIGHTING_PRELIT (Material::LIGHTING_PRELIT = 4 in
wfsource/source/gfx/material.hp) so the renderer treats colors as pre-lit
and skips dynamic-light attenuation.

Per-round palette tables (`ROUND_COLORS`, `LEVEL_SIDE_COLORS`) live here as
data so blender_create_qbert.py can import them and emit Forth lookup
tables in the director script.
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

# Each face is two triangles, CCW from outside, with material index per face.
# Cubes are rotated 45° about Z by blender_create_qbert.py. After that
# rotation:
#   pre-rotation -X face → LEFT visible side  → LIT  (mat 1)
#   pre-rotation -Y face → RIGHT visible side → SHADOW (mat 2)
#   pre-rotation +X face → back-right (hidden) → SHADOW (mat 2)
#   pre-rotation +Y face → back-left  (hidden) → LIT    (mat 1)
# Bottom is hidden by the staircase below; assigned shadow.
FACES = [
    # Bottom (-Z)
    (0, 3, 2, 2),
    (0, 2, 1, 2),
    # Top (+Z) — state-dependent color via mat 0
    (4, 5, 6, 0),
    (4, 6, 7, 0),
    # Front (-Y) → SHADOW
    (0, 1, 5, 2),
    (0, 5, 4, 2),
    # Right (+X) → SHADOW
    (1, 2, 6, 2),
    (1, 6, 5, 2),
    # Back (+Y) → LIT
    (2, 3, 7, 1),
    (2, 7, 6, 1),
    # Left (-X) → LIT
    (3, 0, 4, 1),
    (3, 4, 7, 1),
]

# ── Placeholder material colors ───────────────────────────────────────────────
# These are the load-time defaults baked into cube.iff. The director overrides
# them per-cube and per-level via EMAILBOX_FACE_COLOR_TOP/LIT/SHADOW writes
# before the first frame is rendered. White is a sentinel ("not-yet-set");
# if you see a white cube on screen, the director's color-write path didn't
# fire for that material slot.
PLACEHOLDER_TOP    = 0xFFFFFF
PLACEHOLDER_LIT    = 0xFFFFFF
PLACEHOLDER_SHADOW = 0xFFFFFF


def build_modl(top_rgb=PLACEHOLDER_TOP,
               lit_side_rgb=PLACEHOLDER_LIT,
               shadow_side_rgb=PLACEHOLDER_SHADOW):
    """Build a complete MODL chunk for the cube with its three materials."""
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


# ── Per-round top colors (state 0 / 1 / 2) ────────────────────────────────────
# 16 rounds × 3 states = 48 RGB top-face values. State 1 (mid-hop) only
# differs on L2/L4 (2-hop levels); on L1/L3 (1-hop levels) state-1 is set
# equal to state-2 since the cube transitions 0→2 directly.
#
# Imported by blender_create_qbert.py and embedded into the director's Forth
# script as a 48-entry lookup table indexed by (round * 3 + state).
ROUND_TOP_COLORS = [
    # (state0, state1, state2)
    (0x5646EF, 0xDEDE00, 0xDEDE00),  # R00 L1R1 purple→yellow              (1-hop)
    (0xEFDE77, 0x0046DE, 0x0046DE),  # R01 L1R2 golden→blue                (1-hop)
    (0xB9CECE, 0x464646, 0x464646),  # R02 L1R3 silver→dark-gray           (1-hop)
    (0x0066EF, 0xA9B910, 0xA9B910),  # R03 L1R4 blue→olive                 (1-hop)
    (0x0046DE, 0xEFDE77, 0x21B931),  # R04 L2R1 blue→golden→green
    (0x990066, 0x0066EF, 0xA9B910),  # R05 L2R2 magenta→blue→olive
    (0xFF6666, 0x5646EF, 0xDEDE00),  # R06 L2R3 red→purple→yellow
    (0xCECE00, 0x0046EF, 0xFF6666),  # R07 L2R4 yellow→blue→red
    (0x2188CE, 0x003199, 0x003199),  # R08 L3R1 blue→dark-blue             (1-hop)
    (0x464646, 0xB9CECE, 0xB9CECE),  # R09 L3R2 dark-gray→light-gray       (1-hop)
    (0x0046DE, 0xEFDE77, 0xEFDE77),  # R10 L3R3 blue→golden                (1-hop)
    (0xDEDE00, 0x5646EF, 0x5646EF),  # R11 L3R4 yellow→purple              (1-hop)
    (0x21B931, 0xEFDE77, 0x0046DE),  # R12 L4R1 green→golden→blue
    (0x0046EF, 0xFF6666, 0xCECE00),  # R13 L4R2 blue→red→yellow
    (0xDEDE00, 0xFF6666, 0x5646EF),  # R14 L4R3 yellow→red→purple
    (0x990066, 0x0066EF, 0xA9B910),  # R15 L4R4 magenta→blue→olive
]

# ── Per-level side colors (lit, shadow) ───────────────────────────────────────
# Sides only change on level boundary (rounds 0/4/8/12). Within a level the
# lit/shadow material colors are constant. L2R4 and L4R2 are "flat" rounds
# in the arcade — black sides matching the background; entries below cover the
# level palette as a whole, so the per-round flat exceptions are handled by the
# director writing the alternate side colors on those specific rounds.
LEVEL_SIDE_COLORS = [
    # (lit, shadow)
    (0x56A999, 0x314646),  # L1
    (0x663100, 0xFF7721),  # L2
    (0xB9B921, 0xEF1021),  # L3
    (0x56A999, 0x314646),  # L4 (defaults to L1 palette per existing capture)
]

# Per-round side overrides — keyed by 0-based round index — for the few rounds
# whose sides differ from their level's default (the "flat" rounds and other
# arcade quirks). Director consults this on every round transition before
# writing LIT/SHADOW; if the round is here, it uses these values, else it uses
# LEVEL_SIDE_COLORS[round // 4].
ROUND_SIDE_OVERRIDES = {
    1:  (0x663100, 0xFF7721),  # L1R2: golden/orange instead of L1's teal/dark
    2:  (0x777777, 0x212121),  # L1R3: silver/dark
    3:  (0x778888, 0x101099),  # L1R4: gray/blue
    5:  (0x778888, 0x101099),  # L2R2: gray/blue
    6:  (0x56A999, 0x314646),  # L2R3: teal/dark (L1-like)
    7:  (0x000000, 0x000000),  # L2R4: flat black sides
    9:  (0x777777, 0x212121),  # L3R2: silver/dark
    10: (0x663100, 0xFF7721),  # L3R3: golden/orange
    11: (0x56A999, 0x314646),  # L3R4: teal/dark
    13: (0x000000, 0x000000),  # L4R2: flat black sides
    14: (0x56A999, 0x314646),  # L4R3: teal/dark
    15: (0x778888, 0x101099),  # L4R4: gray/blue
}


if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)
    modl = build_modl()
    out_path = os.path.join(out_dir, 'cube.iff')
    with open(out_path, 'wb') as f:
        f.write(modl)
    print(f'Wrote {len(modl)} bytes → {out_path}')
    print(f'(Per-round/per-level colors live in ROUND_TOP_COLORS, '
          f'LEVEL_SIDE_COLORS, ROUND_SIDE_OVERRIDES; '
          f'imported by blender_create_qbert.py at director-script generation.)')
