"""Christmas candle geometry for the village pines (plan docs/plans/2026-11-21-cuckoo-village.md, "Christmas candles").

Pure Python, so it is tested without Blender (tests/test_cuckoo_village_candles.py). blender_create_cuckoo_village.py
turns the positions into two kinds of static mesh actor: every candle stick in ONE mesh (visible with cell
timeline.CANDLE_CELL) and the flames of each tree in their own mesh (visible with cell FLAME_CELL0 + tree index, so the
glow of each tree follows the day, dusk and night blend on its own stagger, like the windows).

A candle is a small cream prism standing on a branch tier, with a warm diamond flame above it. "A single tree never
carries more than a dozen" (plan): TIERS x PER_TIER = 10.
"""
from __future__ import annotations

import math
from typing import List, Tuple

Vec = Tuple[float, float, float]
Face = Tuple[int, ...]

PINE_HEIGHT = 3.755                      # the pine asset's height at scale 1 (measured in Blender, village_assets.blend)
PINE_RADIUS = [1.02, 0.979, 0.87, 0.835, 0.72, 0.55, 0.528, 0.421, 0.297, 0.02]    # radius by tenth of that height
TIERS = (0.14, 0.28, 0.42, 0.56, 0.70)   # candle heights as fractions of the pine's height
PER_TIER = 2
PER_TREE = len(TIERS) * PER_TIER
STICK_RADIUS, STICK_HEIGHT = 0.03, 0.12  # world units, not scaled with the tree: they are tiny decorations
FLAME_RADIUS, FLAME_HEIGHT = 0.022, 0.075
INSET = 0.93                             # the candle stands this fraction of the way out to the branch tip
GOLDEN = 2.399963229728653               # radians: successive candles never line up above one another
STICK_TILE, FLAME_TILE = 15, 6           # the atlas: pale cream, and the warm yellow of the windows' glow


def pine_radius(frac: float) -> float:
    """The pine's radius at `frac` of its height (0 at the foot, 1 at the tip), linear between the measured tenths."""
    x = min(max(frac, 0.0), 1.0) * 10.0
    lo = min(int(x), len(PINE_RADIUS) - 1)
    hi = min(lo + 1, len(PINE_RADIUS) - 1)
    return PINE_RADIUS[lo] + (PINE_RADIUS[hi] - PINE_RADIUS[lo]) * (x - lo)


def candle_bases(tree: int, location: Vec, rot_z: float, scale: float) -> List[Vec]:
    """World positions of the candle feet on one tree: `tree` is its index from 0, `location` its origin, `rot_z` its
    heading in radians and `scale` its size. Deterministic: the angles come from the tree's index."""
    out: List[Vec] = []
    c, s = math.cos(rot_z), math.sin(rot_z)
    for t, frac in enumerate(TIERS):
        r = pine_radius(frac) * INSET * scale
        for j in range(PER_TIER):
            a = tree * GOLDEN + t * 1.7 + j * math.pi
            lx, ly = r * math.cos(a), r * math.sin(a)
            out.append((location[0] + lx * c - ly * s, location[1] + lx * s + ly * c, location[2] + frac * PINE_HEIGHT * scale))
    return out


def prism(base: Vec, radius: float, height: float, sides: int = 8) -> Tuple[List[Vec], List[Face]]:
    """An upright prism standing on `base`: the stick. Faces are quads round the side and a cap on top."""
    verts = [(base[0] + radius * math.cos(math.tau * k / sides), base[1] + radius * math.sin(math.tau * k / sides), base[2] + z)
             for z in (0.0, height) for k in range(sides)]
    faces: List[Face] = [(k, (k + 1) % sides, sides + (k + 1) % sides, sides + k) for k in range(sides)]
    faces.append(tuple(range(sides, 2 * sides)))
    return verts, faces


def flame(base: Vec, radius: float, height: float, sides: int = 4, lean: float = 0.0) -> Tuple[List[Vec], List[Face]]:
    """A diamond (two pyramids) whose widest ring is a third of the way up: the flame, standing on `base`. `lean` moves the tip that
    far along DRAUGHT (world +X) and the ring a third of it, so the flame bends rather than slides (0: today's upright flame)."""
    ring_z = height / 3.0
    verts = [(base[0] + radius * math.cos(math.tau * k / sides) + lean / 3.0, base[1] + radius * math.sin(math.tau * k / sides), base[2] + ring_z)
             for k in range(sides)]
    verts += [(base[0], base[1], base[2]), (base[0] + lean, base[1], base[2] + height)]
    foot, tip = sides, sides + 1
    faces: List[Face] = [(k, (k + 1) % sides, foot) for k in range(sides)] + [((k + 1) % sides, k, tip) for k in range(sides)]
    return verts, faces


def merge(parts) -> Tuple[List[Vec], List[Face]]:
    """Several (verts, faces) in one mesh: the faces' indices are shifted past the vertices before them."""
    verts: List[Vec] = []
    faces: List[Face] = []
    for v, f in parts:
        faces += [tuple(i + len(verts) for i in face) for face in f]
        verts += v
    return verts, faces


# The flicker's two flame shapes (plan docs/plans/2026-11-22-cuckoo-village-candle-flicker.md): (height, ring radius, lean toward DRAUGHT),
# metres. Today's flame is (FLAME_HEIGHT, FLAME_RADIUS, 0). Every shape is the same 8 triangles.
DRAUGHT = (1.0, 0.0)
FLAME_SHAPES = {1: (0.090, 0.020, 0.014), 2: (0.060, 0.024, -0.010)}


def tree_flame_shapes(tree: int, location: Vec, rot_z: float, scale: float):
    """{(group, shape): parts}: the tree's flames split into group 0 (the candles with j = 0) and group 1 (j = 1), each built in both
    shapes. Every group holds PER_TREE / PER_TIER candles; the stick under each is the one tree_candles builds."""
    out = {(g, s): [] for g in range(PER_TIER) for s in FLAME_SHAPES}
    for n, base in enumerate(candle_bases(tree, location, rot_z, scale)):
        for shape, (h, r, lean) in FLAME_SHAPES.items():
            out[(n % PER_TIER, shape)].append(flame((base[0], base[1], base[2] + STICK_HEIGHT), r, h, lean=lean))
    return out


def tree_candles(tree: int, location: Vec, rot_z: float, scale: float):
    """(stick parts, flame parts) for one tree, each a list of (verts, faces) ready for merge()."""
    sticks, flames = [], []
    for base in candle_bases(tree, location, rot_z, scale):
        sticks.append(prism(base, STICK_RADIUS, STICK_HEIGHT))
        flames.append(flame((base[0], base[1], base[2] + STICK_HEIGHT), FLAME_RADIUS, FLAME_HEIGHT))
    return sticks, flames
