"""The lava lamp's shared numbers: scale, the lamp's proportions, cells and palettes.

generate.py (the scene), forth.py (the director) and the tests import these, so the
geometry the model's globe heights map onto is written down once.
docs/plans/2026-11-26-lava-lamp.md (D2, D3, D7, D8).
"""
from __future__ import annotations

SCALE = 48.0          # the 48x lesson: author big enough that the smallest triangle keeps a sound normal

# A 1963-style Astro, in metres before SCALE: a conical perforated base, a tapered globe widest a
# quarter of the way up, a conical cap. The globe's inside is the model's unit height.
BASE_H = 0.140        # the base cone, from the sideboard to the globe's foot
BASE_R0 = 0.108       # base radius at the sideboard
BASE_R1 = 0.063       # base radius at the top
GLOBE_Z0 = 0.146      # the globe's inside: bottom
GLOBE_H = 0.240       # the globe's inside: height (one "globe height")
CAP_H = 0.080         # the cap cone above the globe
CAP_R0 = 0.043
CAP_R1 = 0.008
LAMP_H = GLOBE_Z0 + GLOBE_H + CAP_H

G = GLOBE_H * SCALE           # one globe height in world units
GZ0 = GLOBE_Z0 * SCALE        # the globe's bottom in world units


def globe_r(y: float) -> float:
    """R(y) in globe heights (model.globe_r, in doubles for meshes)."""
    return 0.27 - 0.72 * (0.25 - y) ** 2 if y < 0.25 else 0.27 - 0.2 * (y - 0.25) ** 2


# Cells (level-wide user mailboxes, as Tide Harbour's director keeps its state).
BLOB0, BLOB_STRIDE = 100, 10
BLOB_FIELDS = ("x", "y", "vx", "vy", "r", "T", "stuck", "a", "b")
P1, P2, P3, ACC = 190, 191, 192, 193
STARTED = BLOB0 + 9          # the director has run ll-start (blob 0's tenth cell, after its nine fields)
BLOCK_BLOB0 = 400             # deform blocks, 10 cells each: six weights, tint R G B, glow
BLOCK_MERGED0 = 480
BLOCK_POOL = 520
BLOCK_TINT0 = 530             # liquid, glass, wall glow, table light
TINTED = ("Liquid", "Glass", "WallGlow", "TableLight")
SET_LAVA, SET_WATER, SET_TIME, SET_INIT, TIME_KEY = 600, 601, 602, 603, 604
WAX_RGB = 605                 # 605..607, the wax tint the blobs and the pool carry
DIGITS = 690                  # 690..693, the four digits of the time
TAKEN0 = 670                  # 670..677, a blob already shown in a merged pair this frame
MERGES = 678                  # merged meshes used this frame
LAVA_TABLE, WATER_TABLE = 620, 644   # 8 x RGB each, written once at start
VIS_BLOB0, VIS_MERGED0 = 700, 708
VIS_DIGIT0, VIS_COLON, VIS_DASH = 720, 760, 761
N_MERGED = 4

CLOCK_SET_DAY = 9497          # WALL_DAY of 2026-01-01 (days since 2000-01-01): before it, the clock was never set

# D8: the colour fields' names, in field order, and their sRGB.
LAVA = [("Red", "#e0281e"), ("Orange", "#ff6516"), ("Yellow", "#ffc417"), ("Pink", "#ff4fa0"),
        ("Purple", "#9b3cf0"), ("Turquoise", "#18d2c4"), ("Green", "#49d23a"), ("White", "#f4efe6")]
WATER = [("Clear", "#d9d3c4"), ("Yellow", "#ffd23a"), ("Orange", "#ff8a1e"), ("Pink", "#ff5aa8"),
         ("Violet", "#7a2cff"), ("Blue", "#1f6bff"), ("Turquoise", "#14c8c0"), ("Green", "#2fbf4f")]
DEFAULT_LAVA, DEFAULT_WATER, DEFAULT_TIME = 1, 4, 0
WAX_WATER_MIX = 0.14          # the wax seen through the liquid: 14 % water colour


def rgb(h: str):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
