"""Bavaria mode's geometry for Cuckoo Village (plan docs/plans/2026-11-21-cuckoo-village.md, "Bavaria mode").

Pure Python, so it is tested without Blender (tests/test_cuckoo_village_bavaria_art.py). blender_create_cuckoo_village.py turns
each Part into a static mesh actor: the four figures keep the Classic figures' pivots (their meshes are in pivot-local
coordinates and the director poses them with the same formulas), everything else is in world coordinates and only switches
on with the Bavaria visibility cell (timeline.BAVARIA_CELL).

All colours are tiles of the village atlas (a new texture would cost the device a VRAM slot): the white-and-blue lozenge is
built from small diamonds of the cream and slate-blue tiles. The art is original: a cooper (Schaffler), a dirndl figure, a
lederhosen figure with an Alpine hat, and a brewer with a stein.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

Vec = Tuple[float, float, float]

# atlas tiles (wflevels/cuckoo_village_assets/atlas.py)
WOOD, PLASTER, ROOFTILE, STONE, PINE, DARKWOOD, GOLD, SKIN, BROWN, SAGE, STRAW, DARK, GOLDEN, RED, BLUE, CREAM = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)


class Part:
    """Vertices, faces (index tuples, counter-clockwise seen from outside) and one atlas tile per face."""

    def __init__(self, name: str):
        self.name = name
        self.verts: List[Vec] = []
        self.faces: List[Tuple[int, ...]] = []
        self.tiles: List[int] = []

    def add(self, tile: int, verts: List[Vec], faces: List[Tuple[int, ...]]) -> None:
        off = len(self.verts)
        self.verts.extend(verts)
        self.faces.extend(tuple(off + i for i in f) for f in faces)
        self.tiles.extend([tile] * len(faces))

    def box(self, tile: int, x: float, y: float, z: float, sx: float, sy: float, sz: float) -> None:
        self.add(tile, [(x + dx * sx / 2, y + dy * sy / 2, z + dz * sz / 2) for dx, dy, dz in
                        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]],
                 [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])

    def beam(self, tile: int, a: Vec, b: Vec, width: float, depth: float) -> None:
        """An extruded segment in the front elevation (x, z), `depth` thick in y."""
        x1, y1, z1 = a
        x2, y2, z2 = b
        dx, dz = x2 - x1, z2 - z1
        length = math.hypot(dx, dz)
        if length == 0:
            return
        nx, nz = -dz / length * width / 2, dx / length * width / 2
        v = [(x1 + nx, y1 - depth / 2, z1 + nz), (x1 - nx, y1 - depth / 2, z1 - nz), (x2 - nx, y2 - depth / 2, z2 - nz), (x2 + nx, y2 - depth / 2, z2 + nz),
             (x1 + nx, y1 + depth / 2, z1 + nz), (x1 - nx, y1 + depth / 2, z1 - nz), (x2 - nx, y2 + depth / 2, z2 - nz), (x2 + nx, y2 + depth / 2, z2 + nz)]
        self.add(tile, v, [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])

    def ring(self, tile: int, x: float, y: float, z: float, outer: float, inner: float, n: int = 24) -> None:
        """A flat ring in the x-z plane facing -y."""
        v = [(x + r * math.sin(2 * math.pi * i / n), y, z + r * math.cos(2 * math.pi * i / n)) for r in (outer, inner) for i in range(n)]
        self.add(tile, v, [(n + i, n + (i + 1) % n, (i + 1) % n, i) for i in range(n)])

    def sphere(self, tile: int, x: float, y: float, z: float, rx: float, ry: float, rz: float, n: int = 10, m: int = 6) -> None:
        v = []
        for j in range(m + 1):
            t = math.pi * j / m
            for i in range(n):
                a = 2 * math.pi * i / n
                v.append((x + rx * math.sin(t) * math.cos(a), y + ry * math.sin(t) * math.sin(a), z + rz * math.cos(t)))
        self.add(tile, v, [((j + 1) * n + i, (j + 1) * n + (i + 1) % n, j * n + (i + 1) % n, j * n + i) for j in range(m) for i in range(n)])

    def cone(self, tile: int, x: float, y: float, z: float, r1: float, r2: float, h: float, n: int = 10) -> None:
        """A frustum standing on z, radius r1 at the foot and r2 at the top. A radius of 0 is a point (one apex vertex, no cap); the
        other end is capped."""
        ring = lambda r, zz: [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n), zz) for i in range(n)]
        v: List[Vec] = []
        lo = hi = None                       # the index of the first vertex of each end's ring, or of its apex
        if r1 > 0:
            lo = len(v)
            v += ring(r1, z)
        else:
            lo = len(v)
            v.append((x, y, z))
        if r2 > 0:
            hi = len(v)
            v += ring(r2, z + h)
        else:
            hi = len(v)
            v.append((x, y, z + h))
        faces: List[Tuple[int, ...]] = []
        for i in range(n):
            j = (i + 1) % n
            if r1 > 0 and r2 > 0:
                faces.append((lo + i, lo + j, hi + j, hi + i))
            elif r1 > 0:                      # a point at the top
                faces.append((lo + i, lo + j, hi))
            elif r2 > 0:                      # a point at the foot
                faces.append((lo, hi + j, hi + i))
        if r1 > 0:
            faces.append(tuple(lo + i for i in range(n - 1, -1, -1)))
        if r2 > 0:
            faces.append(tuple(hi + i for i in range(n)))
        self.add(tile, v, faces)

    def diamond(self, tile: int, x: float, y: float, z: float, w: float, h: float, depth: float = 0.012) -> None:
        """A flat rhombus (a lozenge) facing -y, `w` wide and `h` high, a little thick so it stands off the wall."""
        v = [(x, y - depth, z + h / 2), (x + w / 2, y - depth, z), (x, y - depth, z - h / 2), (x - w / 2, y - depth, z),
             (x, y, z + h / 2), (x + w / 2, y, z), (x, y, z - h / 2), (x - w / 2, y, z)]
        self.add(tile, v, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])

    def triangles(self) -> int:
        return sum(len(f) - 2 for f in self.faces)


# --- the four figures, in pivot-local coordinates: x across, y toward the viewer is negative, z up from the balcony floor ---------
# The Classic figures stand on the same pivots (timeline.FIG_X, FIG_HOME_Y, FIG_Z0) and are about 0.8 tall and 0.3 across.

def _legs(p: Part, sock: int, shoe: int = DARK) -> None:
    for dx in (-0.065, 0.065):
        p.box(shoe, dx, -0.025, 0.01, 0.10, 0.18, 0.10)
        p.box(sock, dx, 0.0, 0.14, 0.075, 0.10, 0.24)


def _head(p: Part, z: float = 0.60) -> None:
    p.sphere(SKIN, 0.0, 0.0, z, 0.115, 0.085, 0.13)


def _arms(p: Part, sleeve: int, z: float = 0.45, x: float = 0.165) -> None:
    for side in (-1, 1):
        p.box(sleeve, side * x, 0.0, z, 0.08, 0.10, 0.27)
        p.sphere(SKIN, side * x, -0.01, z - 0.16, 0.045, 0.045, 0.05)


def cooper() -> Part:
    """The Schaffler: green jacket, dark breeches and white stockings, a red cap with a feather, and the hoop held overhead."""
    p = Part("tower_figure_b1")
    _legs(p, CREAM)
    for dx in (-0.065, 0.065):
        p.box(DARK, dx, 0.0, 0.265, 0.09, 0.11, 0.12)                    # breeches
    p.box(PINE, 0.0, 0.0, 0.43, 0.26, 0.16, 0.30)                       # jacket
    p.box(GOLD, 0.0, -0.085, 0.43, 0.03, 0.02, 0.28)                     # a gold braid down the front
    p.box(BROWN, 0.0, -0.095, 0.30, 0.22, 0.02, 0.22)                    # the leather apron
    _arms(p, PINE, 0.43)
    _head(p)
    p.cone(RED, 0.0, 0.0, 0.66, 0.12, 0.085, 0.07)                      # the cap
    p.cone(RED, 0.0, 0.0, 0.72, 0.085, 0.04, 0.06)
    p.beam(GOLD, (0.07, 0.0, 0.74), (0.11, 0.0, 0.88), 0.022, 0.02)      # the feather
    p.ring(GOLDEN, 0.0, -0.10, 0.82, 0.185, 0.16, 20)                    # the hoop of the dance, held overhead
    for side in (-1, 1):
        p.beam(DARKWOOD, (side * 0.165, -0.06, 0.58), (side * 0.18, -0.10, 0.80), 0.03, 0.03)   # the arms reach up to it
    return p


def dirndl() -> Part:
    """The dirndl figure: a blue skirt with a white apron, a red bodice and puffed white sleeves, plaits."""
    p = Part("tower_figure_b2")
    _legs(p, CREAM)
    p.cone(BLUE, 0.0, 0.0, 0.19, 0.20, 0.10, 0.30, 14)                  # the skirt
    p.box(CREAM, 0.0, -0.15, 0.31, 0.15, 0.03, 0.26)                     # the apron
    p.box(RED, 0.0, 0.0, 0.52, 0.21, 0.14, 0.15)                        # the bodice
    p.box(CREAM, 0.0, -0.075, 0.57, 0.15, 0.02, 0.05)                    # the blouse at the neckline
    for side in (-1, 1):
        p.sphere(CREAM, side * 0.15, 0.0, 0.55, 0.075, 0.07, 0.075)      # puffed sleeves
        p.box(CREAM, side * 0.165, 0.0, 0.43, 0.06, 0.08, 0.15)
        p.sphere(SKIN, side * 0.165, -0.01, 0.34, 0.04, 0.04, 0.045)
    _head(p, 0.665)
    p.sphere(STRAW, 0.0, 0.02, 0.715, 0.125, 0.09, 0.10)                 # hair
    for side in (-1, 1):
        p.cone(STRAW, side * 0.10, 0.04, 0.56, 0.035, 0.02, 0.17, 8)     # plaits
    p.sphere(RED, 0.07, -0.07, 0.73, 0.03, 0.02, 0.03, 8, 5)             # a flower
    return p


def lederhosen() -> Part:
    """The lederhosen figure: leather shorts on braces over a white shirt, and an Alpine hat with a feather and a tuft."""
    p = Part("tower_figure_b3")
    _legs(p, CREAM)
    for dx in (-0.065, 0.065):
        p.box(BROWN, dx, 0.0, 0.245, 0.10, 0.13, 0.15)                   # leather shorts
    p.box(CREAM, 0.0, 0.0, 0.46, 0.25, 0.155, 0.28)                      # the shirt
    for dx in (-0.075, 0.075):
        p.box(PINE, dx, -0.082, 0.47, 0.03, 0.02, 0.24)                  # the braces
    p.box(PINE, 0.0, -0.085, 0.41, 0.17, 0.02, 0.03)                     # and the cross-piece between them
    _arms(p, CREAM, 0.46)
    _head(p)
    p.cone(PINE, 0.0, 0.0, 0.665, 0.17, 0.15, 0.03)                      # the hat's brim
    p.cone(PINE, 0.0, 0.0, 0.69, 0.105, 0.075, 0.12)                     # the crown
    p.cone(GOLD, 0.0, 0.0, 0.70, 0.108, 0.108, 0.025)                    # the band
    p.beam(GOLD, (0.07, -0.02, 0.70), (0.13, -0.02, 0.84), 0.022, 0.02)  # the feather
    p.cone(DARKWOOD, 0.085, -0.02, 0.77, 0.012, 0.03, 0.08, 6)           # the tuft
    return p


def brewer() -> Part:
    """The brewer: a red waistcoat over a white shirt, a long leather apron, a flat cap, and a foaming stein."""
    p = Part("tower_figure_b4")
    _legs(p, BROWN)
    p.box(BROWN, 0.0, -0.095, 0.30, 0.25, 0.03, 0.40)                    # the long apron
    p.box(CREAM, 0.0, 0.0, 0.50, 0.26, 0.16, 0.25)                       # the shirt
    p.box(RED, 0.0, -0.01, 0.50, 0.215, 0.16, 0.22)                      # the waistcoat
    for z in (0.44, 0.50, 0.56):
        p.sphere(GOLD, 0.0, -0.092, z, 0.014, 0.01, 0.014, 6, 4)         # buttons
    for side in (-1, 1):
        p.box(CREAM, side * 0.165, 0.0, 0.50, 0.08, 0.10, 0.22)
    p.sphere(SKIN, 0.165, -0.01, 0.36, 0.045, 0.045, 0.05)
    p.sphere(SKIN, -0.205, -0.09, 0.50, 0.045, 0.045, 0.05)             # the hand that holds the stein (on the side away from the tower's post)
    p.box(CREAM, -0.185, -0.045, 0.52, 0.08, 0.10, 0.08)                 # the forearm
    p.cone(STRAW, -0.235, -0.115, 0.50, 0.062, 0.058, 0.15, 12)          # the stein
    p.cone(GOLDEN, -0.235, -0.115, 0.65, 0.066, 0.066, 0.02, 12)         # its lid rim
    p.sphere(CREAM, -0.235, -0.115, 0.67, 0.07, 0.07, 0.04, 10, 4)       # the foam
    p.ring(GOLDEN, -0.29, -0.115, 0.575, 0.04, 0.02, 10)                 # the handle
    _head(p, 0.665)
    p.cone(DARK, 0.0, 0.0, 0.715, 0.15, 0.13, 0.05)                      # a flat cap
    p.cone(DARK, 0.0, -0.05, 0.715, 0.12, 0.10, 0.025)                   # with its peak
    p.sphere(BROWN, 0.0, -0.085, 0.63, 0.07, 0.03, 0.035, 8, 4)          # and a moustache
    return p


def figures() -> List[Part]:
    return [cooper(), dirndl(), lederhosen(), brewer()]


# --- the reversed dial: Roman numerals that run anti-clockwise, 12 still at the top, the digits upright and unmirrored --------

NUMERALS = ('XII', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI')
DIAL_Z, NUMERAL_Y, NUMERAL_R = 4.08, -1.088, 0.35        # the dial's centre height above the tower foot, the plane of the marks, their radius


def numeral_angle(i: int, reverse: bool) -> float:
    """The angle of mark i from twelve, clockwise in revolutions (anti-clockwise, so negative, on the reversed dial)."""
    return (-1.0 if reverse else 1.0) * i / 12.0


def dial_numerals(tower_z: float, reverse: bool = True) -> Part:
    """The twelve hour marks as strokes (so they stay crisp at close range), laid out clockwise or, reversed, anti-clockwise.
    The strokes are the Classic dial's own (tower_art.py): only where each mark stands changes, never how it is drawn."""
    p = Part("dial_numerals_bavaria" if reverse else "dial_numerals_classic")
    for i, numeral in enumerate(NUMERALS):
        a = math.tau * numeral_angle(i, reverse)
        cx, cz = NUMERAL_R * math.sin(a), DIAL_Z + NUMERAL_R * math.cos(a) + tower_z
        step = 0.026
        total = (len(numeral) - 1) * step
        for j, ch in enumerate(numeral):
            x, y, h, w = cx - total / 2 + j * step, NUMERAL_Y, 0.052, 0.019
            if ch == 'I':
                p.beam(GOLDEN, (x, y, cz - h / 2), (x, y, cz + h / 2), 0.007, 0.009)
            elif ch == 'V':
                p.beam(GOLDEN, (x - w / 2, y, cz + h / 2), (x, y, cz - h / 2), 0.007, 0.009)
                p.beam(GOLDEN, (x, y, cz - h / 2), (x + w / 2, y, cz + h / 2), 0.007, 0.009)
            else:
                p.beam(GOLDEN, (x - w / 2, y, cz - h / 2), (x + w / 2, y, cz + h / 2), 0.007, 0.009)
                p.beam(GOLDEN, (x - w / 2, y, cz + h / 2), (x + w / 2, y, cz - h / 2), 0.007, 0.009)
    return p


# --- the village: cottages, a dome, a maypole (world coordinates; the caller passes where the terrain is) ---------------------

HOUSE_X, HOUSE_Y, HOUSE_RIDGE = 1.45, 1.25, 3.39         # the cottage asset's half-width, half-depth and ridge height (village_assets.blend), at scale 1
HOUSE_FRONT_Y = -1.12                                     # its front wall (the glowing windows sit on it)
FRIEZE_Z = 2.30                                           # the painted band runs just above the window tops (2.12)
FRIEZE_HOUSES = (0, 2, 4, 6, 8, 10)                       # which of the thirteen cottages carry the lozenge frieze (zero-based)
DOME_HOUSE = 4                                            # the cottage whose ridge carries the green onion dome
MAYPOLE_AT = (2.30, -2.45)                                # in the square, right of the tower's front


def to_world(part: Part, loc: Vec, angle_deg: float, scale: float) -> None:
    """Move a part built in a cottage's local frame to the world: scale, turn about z, then translate."""
    a = math.radians(angle_deg)
    c, s_ = math.cos(a), math.sin(a)
    part.verts = [(loc[0] + scale * (c * x - s_ * y), loc[1] + scale * (s_ * x + c * y), loc[2] + scale * z) for x, y, z in part.verts]


def cottage_trim(index: int, loc: Vec, angle_deg: float, scale: float) -> Part:
    """The Bavarian painting of one cottage: a white-and-blue lozenge frieze under the eaves, a timber belt and corner posts."""
    p = Part(f"bavaria_trim_{index + 1:02d}")
    p.box(DARKWOOD, 0.0, HOUSE_FRONT_Y - 0.03, FRIEZE_Z - 0.17, 2.30, 0.05, 0.07)                    # the belt under the frieze
    p.box(DARKWOOD, 0.0, HOUSE_FRONT_Y - 0.03, FRIEZE_Z + 0.17, 2.30, 0.05, 0.07)                    # and the one over it
    for k in range(9):                                                                             # nine lozenges across the front, blue and white in turn
        p.diamond(BLUE if k % 2 == 0 else CREAM, -1.0 + k * 0.25, HOUSE_FRONT_Y - 0.035, FRIEZE_Z, 0.24, 0.30)
    for sx in (-1, 1):
        p.box(DARKWOOD, sx * 1.10, HOUSE_FRONT_Y - 0.03, 1.25, 0.09, 0.06, 2.35)                      # corner posts of the timber frame
    to_world(p, loc, angle_deg, scale)
    return p


def onion_dome(loc: Vec, angle_deg: float, scale: float) -> Part:
    """A green onion dome on a short drum, with a gold ball and spire, standing on a cottage's ridge."""
    p = Part("bavaria_dome")
    z0 = HOUSE_RIDGE - 0.10
    p.cone(DARKWOOD, 0.0, 0.0, z0, 0.34, 0.30, 0.28, 12)                       # the drum
    p.cone(GOLD, 0.0, 0.0, z0 + 0.28, 0.40, 0.40, 0.04, 12)                    # a gold ring where the dome begins
    p.sphere(SAGE, 0.0, 0.0, z0 + 0.52, 0.40, 0.40, 0.30, 12, 8)               # the bulb of the dome
    p.cone(SAGE, 0.0, 0.0, z0 + 0.74, 0.20, 0.0, 0.46, 12)                     # tapering to a point
    p.sphere(GOLD, 0.0, 0.0, z0 + 1.22, 0.07, 0.07, 0.07, 8, 5)                # the ball
    p.cone(GOLD, 0.0, 0.0, z0 + 1.27, 0.025, 0.0, 0.28, 6)                     # and the spire
    to_world(p, loc, angle_deg, scale)
    return p


def maypole(x: float, y: float, z: float) -> Part:
    """A painted maypole: a tall pole spiralled white and blue, a green wreath, ribbons, crests, and a low stone ring."""
    p = Part("bavaria_maypole")
    p.cone(STONE, x, y, z, 0.42, 0.40, 0.10, 14)                              # the footing
    height, r = 3.4, 0.07
    segs = 12
    for k in range(segs):                                                      # the spiral: alternate tiles, each segment a short drum
        p.cone(BLUE if k % 2 == 0 else CREAM, x, y, z + 0.10 + k * height / segs, r, r, height / segs, 8)
    top = z + 0.10 + height
    p.ring(PINE, x, y - 0.02, top - 0.20, 0.36, 0.27, 20)                      # the wreath, facing the front
    p.sphere(GOLD, x, y, top + 0.08, 0.09, 0.09, 0.09, 8, 5)                   # the ball on top
    for i, tile in enumerate((BLUE, CREAM, BLUE, CREAM, BLUE, CREAM)):         # ribbons falling from the wreath
        a = math.tau * i / 6
        p.beam(tile, (x + 0.06 * math.sin(a), y - 0.06 * math.cos(a), top - 0.20), (x + 0.32 * math.sin(a), y - 0.32 * math.cos(a) - 0.05, top - 1.30), 0.045, 0.01)
    for j, zc in enumerate((z + 1.45, z + 2.05)):                              # carved crests, the craftsmen's signs, on the pole
        p.box(GOLDEN, x, y - 0.075, zc, 0.20, 0.03, 0.20)
        p.diamond(BLUE if j == 0 else RED, x, y - 0.095, zc, 0.13, 0.15, 0.01)
    return p


# --- the tower, chalet style (world coordinates: tower_z is added to every height) ---------------------------------------------

def tower_chalet(tower_z: float) -> Part:
    """What turns the plain tower into a carved chalet case: a steep front gable with carved fascia boards, a vine of carved leaves
    round the dial, a pair of deer over the cuckoo door, a carved balcony rail, and pinecone weights on chains at each side."""
    p = Part("bavaria_chalet")
    tz = tower_z
    # a steep gable in front of the roof, with fascia boards along its two slopes
    gy, g0, g1, gw = -1.38, 5.13 + tz, 6.02 + tz, 0.82
    p.add(WOOD, [(-gw, gy, g0), (gw, gy, g0), (0.0, gy, g1)], [(0, 1, 2)])
    p.add(ROOFTILE, [(-gw - 0.10, gy - 0.04, g0 - 0.03), (0.0, gy - 0.04, g1 + 0.07), (0.0, -0.62, g1 - 0.15), (-gw - 0.10, -0.62, g0 - 0.03)], [(0, 1, 2, 3)])
    p.add(ROOFTILE, [(gw + 0.10, gy - 0.04, g0 - 0.03), (gw + 0.10, -0.62, g0 - 0.03), (0.0, -0.62, g1 - 0.15), (0.0, gy - 0.04, g1 + 0.07)], [(0, 1, 2, 3)])
    for sx in (-1, 1):
        p.beam(DARKWOOD, (sx * (gw + 0.07), gy - 0.05, g0 - 0.02), (0.0, gy - 0.05, g1 + 0.06), 0.085, 0.05)      # the carved fascia boards
        for k in range(1, 6):                                                                                   # with a scalloped edge
            t = k / 6.0
            p.sphere(GOLDEN, sx * (gw + 0.07) * (1 - t), gy - 0.085, g0 - 0.02 + (g1 + 0.06 - g0 + 0.02) * t - 0.07, 0.035, 0.02, 0.035, 6, 4)
    p.box(DARKWOOD, 0.0, gy - 0.03, g0 + 0.02, 2 * gw + 0.2, 0.06, 0.08)                                     # the tie beam
    p.diamond(BLUE, 0.0, gy - 0.02, g0 + 0.34, 0.30, 0.38, 0.015)                                            # a lozenge in the gable
    p.diamond(CREAM, 0.0, gy - 0.04, g0 + 0.34, 0.15, 0.19, 0.012)
    # the vine: carved leaves in a ring round the dial's case
    for k in range(20):
        a = math.tau * k / 20
        cx, cz = 0.66 * math.sin(a), 4.08 + tz + 0.66 * math.cos(a)
        d = (math.cos(a) * 0.075, -math.sin(a) * 0.075)
        p.beam(SAGE if k % 2 == 0 else GOLDEN, (cx - d[0], -1.10, cz + d[1]), (cx + d[0], -1.10, cz - d[1]), 0.045, 0.02)
    p.ring(GOLDEN, 0.0, -1.093, 4.08 + tz, 0.60, 0.575, 28)
    # two stags, facing each other, standing on the gable's tie beam in front of its board
    for sx in (-1, 1):
        x0, y0, z0 = sx * 0.50, gy - 0.07, g0 + 0.06
        p.box(DARKWOOD, x0, y0, z0 + 0.10, 0.20, 0.06, 0.09)                                            # the body
        for dx in (-0.07, 0.07):
            p.box(DARKWOOD, x0 + dx, y0, z0 + 0.02, 0.025, 0.04, 0.10)                                  # legs
        p.box(DARKWOOD, x0 - sx * 0.12, y0, z0 + 0.20, 0.06, 0.05, 0.14)                                # the neck
        p.sphere(DARKWOOD, x0 - sx * 0.14, y0, z0 + 0.29, 0.045, 0.035, 0.04, 6, 4)                     # the head
        for dx in (0.0, 0.035):                                                                          # antlers
            p.beam(GOLDEN, (x0 - sx * (0.14 - dx), y0, z0 + 0.31), (x0 - sx * (0.14 + 0.02 + dx), y0, z0 + 0.40), 0.012, 0.012)
    # a carved balcony rail in front of the Classic one: a scalloped top rail and a row of hearts
    p.box(DARKWOOD, 0.0, -1.95, 2.80 + tz, 2.62, 0.05, 0.06)
    for k in range(-5, 6):
        x = k * 0.23
        p.sphere(RED, x - 0.035, -1.955, 2.66 + tz, 0.035, 0.015, 0.035, 6, 4)                          # each heart is two lobes and a point
        p.sphere(RED, x + 0.035, -1.955, 2.66 + tz, 0.035, 0.015, 0.035, 6, 4)
        p.cone(RED, x, -1.955, 2.59 + tz, 0.055, 0.0, 0.07, 6)
    # pinecone weights on chains, one each side of the tower
    for sx in (-1, 1):
        x = sx * 1.62
        p.box(DARKWOOD, x, -1.0, 4.75 + tz, 0.025, 0.025, 1.50)                                         # the chain, from the roof's edge
        p.cone(DARKWOOD, x, -1.0, 3.55 + tz, 0.0, 0.12, 0.12, 8)                                        # the cone's tip pointing down
        p.cone(DARKWOOD, x, -1.0, 3.67 + tz, 0.12, 0.10, 0.18, 8)
        p.cone(GOLDEN, x, -1.0, 3.85 + tz, 0.10, 0.0, 0.12, 8)
        p.sphere(DARKWOOD, x, -1.0, 3.55 + tz, 0.03, 0.03, 0.03, 6, 4)
    return p


def all_parts(tower_z: float, cottages: List[Tuple[Vec, float, float]] = None, ground=None) -> Dict[str, Part]:
    """Everything Bavaria mode adds, by actor name. The four figures are pivot-local; the rest are in world coordinates.
    cottages: each cottage's (location, angle in degrees about z, scale), in order; ground(x, y): the terrain's height there.
    Without them only the tower's parts are made (the tests that do not need the village)."""
    out = {f.name: f for f in figures()}
    out["dial_numerals_bavaria"] = dial_numerals(tower_z, True)
    out["bavaria_chalet"] = tower_chalet(tower_z)
    if cottages is not None:
        for i in FRIEZE_HOUSES:
            out[f"bavaria_trim_{i + 1:02d}"] = cottage_trim(i, *cottages[i])
        out["bavaria_dome"] = onion_dome(*cottages[DOME_HOUSE])
    if ground is not None:
        out["bavaria_maypole"] = maypole(MAYPOLE_AT[0], MAYPOLE_AT[1], ground(*MAYPOLE_AT) + 0.09)
    return out
