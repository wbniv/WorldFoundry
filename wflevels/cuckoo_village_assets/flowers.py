"""Cottage window-box flowers: petunias and geraniums, each with edelweiss, modelled with real petals and flat-coloured materials.

Plan: docs/plans/2026-11-22-cuckoo-village-flowers.md. Pure Python (no Blender), so the geometry is tested on its own
(tests/test_cuckoo_village_flowers.py) and the same code feeds the prototype renders and, later, the level build.

Two kinds of box alternate, two in every three petunia and one in three geranium (`box_kind`). A petunia box holds a few
mounded petunia plants along the back and trailing petunia stems that hang over the front. A geranium box holds upright
(zonal) geraniums and more edelweiss. Both kinds hold small edelweiss tufts. A geranium floret is a ten-point star of petals cupped towards the viewer round a yellow centre. A petunia bloom is a funnel: a five-lobed rim round a recessed throat. An edelweiss head is a flat
star of felty white bracts round a yellow heart of tiny florets, on a short stem with silvery leaves. Everything is returned
per material name as (vertices, faces); faces are triangles. Local frame of a box: x along the box, y out of the wall
(front is -y), z up; the origin is the middle of the box top. The old model put 14 cubes on each box (about 170 triangles).
"""
from __future__ import annotations

import math
import random
from collections import Counter
from typing import Dict, List, Tuple

Vec = Tuple[float, float, float]
Mesh = Tuple[List[Vec], List[Tuple[int, ...]]]

# Flat materials: name -> sRGB base colour. Colour is the only thing that distinguishes them: none has a texture.
MATERIALS: Dict[str, Tuple[float, float, float]] = {
    "bloom_red": (0.78, 0.07, 0.06),         # geraniums
    "bloom_magenta": (0.80, 0.09, 0.46),     # petunias, and the pink geraniums
    "bloom_violet": (0.43, 0.19, 0.70),
    "bloom_white": (0.96, 0.95, 0.92),
    "flower_centre": (0.97, 0.80, 0.16),     # petunia throats and the yellow heart of an edelweiss
    "edelweiss_felt": (0.86, 0.86, 0.79),    # the felty white-grey bracts
    "leaf_green": (0.17, 0.43, 0.14),
    "leaf_silver": (0.50, 0.60, 0.47),       # edelweiss leaves
    "stem_green": (0.09, 0.27, 0.09),
    "soil": (0.20, 0.12, 0.07),
}
# Thin one-sided surfaces: the engine culls back faces, so these materials are exported double-sided (flag 8,
# `wf_double_sided` on the Blender material) and a petal or leaf seen edge-on or from behind does not vanish.
DOUBLE_SIDED = {"bloom_red", "bloom_magenta", "bloom_violet", "bloom_white", "flower_centre", "edelweiss_felt", "leaf_green",
                "leaf_silver"}
PETUNIA_COLOURS = ("bloom_magenta", "bloom_violet", "bloom_white")
GERANIUM_COLOURS = ("bloom_red", "bloom_red", "bloom_magenta", "bloom_red", "bloom_white")   # mostly red, as on a real balcony

BOX_WIDTH, BOX_DEPTH, BOX_HEIGHT = 0.69, 0.22, 0.15
GERANIUM_PITCH = 0.13                     # the distance between neighbouring upright geraniums; an edelweiss tuft sits in each gap
# Quality sets. "full" is the proposal; "lean" is the fallback if the frame-time gate on cast1 fails.
QUALITY = {
    "full": dict(mounds=3, mound_blooms=3, mound_leaves=3, vines=4, vine_blooms=3, vine_leaves=2, tufts=2, heads=2,
                 g_plants=5, g_umbel=7, g_leaves=4, g_tufts=4),
    "lean": dict(mounds=2, mound_blooms=3, mound_leaves=2, vines=2, vine_blooms=2, vine_leaves=2, tufts=2, heads=1,
                 g_plants=3, g_umbel=5, g_leaves=3, g_tufts=4),
}


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a: Vec) -> Vec:
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (a[0] / n, a[1] / n, a[2] / n)


def _frame(normal: Vec) -> Tuple[Vec, Vec, Vec]:
    """A right-handed orthonormal (u, v, n) with n the given direction: u to v turns anticlockwise seen from +n."""
    n = _unit(normal)
    helper = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(helper, n))
    return u, _cross(n, u), n


class Builder:
    """Accumulates triangles per material."""

    def __init__(self) -> None:
        self.parts: Dict[str, Mesh] = {name: ([], []) for name in MATERIALS}
        self.pieces: Counter = Counter()          # (material, piece kind) -> how many were built, for the plan's budget table

    def tri(self, material: str, a: Vec, b: Vec, c: Vec) -> None:
        verts, faces = self.parts[material]
        i = len(verts)
        verts += [a, b, c]
        faces.append((i, i + 1, i + 2))

    def stem(self, base: Vec, top: Vec, r0: float, r1: float, sides: int, segments: int = 1,
             bow: Vec = (0.0, 0.0, 0.0)) -> List[Vec]:
        """A tapered prism from base to top, bowed sideways by `bow` at the top; sides*2 triangles per segment, no caps.
        Returns the centre line (one point per ring) so blooms can sit on it."""
        self.pieces[("stem_green", "stem")] += 1
        rings, centres = [], []
        for s in range(segments + 1):
            t = s / segments
            c = _add(_add(_scale(base, 1 - t), _scale(top, t)), _scale(bow, math.sin(t * math.pi / 2) ** 2))
            r = r0 + (r1 - r0) * t
            centres.append(c)
            rings.append([(c[0] + r * math.cos(math.tau * k / sides), c[1] + r * math.sin(math.tau * k / sides), c[2])
                          for k in range(sides)])
        for s in range(segments):
            for k in range(sides):
                a, b = rings[s][k], rings[s][(k + 1) % sides]
                c, d = rings[s + 1][(k + 1) % sides], rings[s + 1][k]
                self.tri("stem_green", a, b, c)
                self.tri("stem_green", a, c, d)
        return centres

    def leaf(self, material: str, base: Vec, yaw: float, length: float, width: float, droop: float, ring: int = 6) -> None:
        """A leaf: a fan of `ring` triangles round a raised centre, an ellipse `length` long and `width` either side,
        growing from `base` towards heading `yaw` and sagging by `droop` (0 flat, 1 steep) towards its tip."""
        self.pieces[(material, "leaf")] += 1
        fx, fy = math.cos(yaw), math.sin(yaw)
        sx, sy = -fy, fx

        def at(f: float, s: float, up: float) -> Vec:
            return (base[0] + fx * f + sx * s, base[1] + fy * f + sy * s, base[2] + up)

        centre = at(length * 0.5, 0.0, width * 0.18 - droop * length * 0.15)
        pts = []
        for k in range(ring):
            a = math.tau * k / ring
            f = length * 0.5 * (1 - math.cos(a))                      # 0 at the root, `length` at the tip
            pts.append(at(f, width * math.sin(a), -droop * f * 0.5))
        for k in range(ring):
            self.tri(material, centre, pts[k], pts[(k + 1) % ring])

    def petunia(self, material: str, centre: Vec, facing: Vec, radius: float) -> None:
        """A petunia bloom seen as a funnel: ten rim points (five lobe tips between five notches), a yellow throat
        recessed behind the rim. Ten triangles of petal and five of throat."""
        self.pieces[(material, "petunia bloom")] += 1
        self.pieces[("flower_centre", "petunia throat")] += 1
        u, v, n = _frame(facing)
        rim = []
        for k in range(10):
            a = math.tau * k / 10
            r = radius if k % 2 == 0 else radius * 0.80
            rim.append(_add(centre, _add(_scale(u, r * math.cos(a)), _scale(v, r * math.sin(a)))))
        bottom = _add(centre, _scale(n, -radius * 0.70))
        for k in range(10):
            self.tri(material, bottom, rim[k], rim[(k + 1) % 10])
        throat = _add(centre, _scale(n, -radius * 0.40))
        ring = [_add(throat, _add(_scale(u, radius * 0.30 * math.cos(math.tau * k / 5)), _scale(v, radius * 0.30 * math.sin(math.tau * k / 5))))
                for k in range(5)]
        for k in range(5):
            self.tri("flower_centre", ring[k], ring[(k + 1) % 5], _add(bottom, _scale(n, 0.001)))

    def floret(self, material: str, centre: Vec, facing: Vec, radius: float) -> None:
        """One small geranium floret: five petals as a cupped pentagon (five triangles), looking along `facing`."""
        self.pieces[(material, "geranium floret")] += 1
        u, v, n = _frame(facing)
        rim = [_add(centre, _add(_add(_scale(u, radius * math.cos(math.tau * k / 5)), _scale(v, radius * math.sin(math.tau * k / 5))),
                                 _scale(n, -radius * 0.30))) for k in range(5)]
        heart = _add(centre, _scale(n, radius * 0.15))
        for k in range(5):
            self.tri(material, heart, rim[k], rim[(k + 1) % 5])

    def umbel(self, material: str, centre: Vec, axis: Vec, radius: float, count: int, floret_radius: float,
              rng: random.Random) -> None:
        """A geranium's flower head: `count` small florets packed on a dome of `radius` round `centre`, one on top and the
        rest in a ring below it, each facing outwards. Seen from a distance it is one round ball of colour."""
        u, v, n = _frame(axis)
        for i in range(count):
            if i == 0:
                polar, azimuth = 0.0, 0.0
            else:
                polar = math.radians(58 + rng.uniform(-6, 6))
                azimuth = math.tau * (i - 1) / (count - 1) + rng.uniform(-0.2, 0.2)
            d = _add(_add(_scale(u, math.sin(polar) * math.cos(azimuth)), _scale(v, math.sin(polar) * math.sin(azimuth))),
                     _scale(n, math.cos(polar)))
            self.floret(material, _add(centre, _scale(d, radius)), d, floret_radius * (0.9 + 0.2 * rng.random()))

    def edelweiss_head(self, centre: Vec, facing: Vec, radius: float) -> None:
        """An edelweiss head: a flat star of seven pointed felt bracts (14 triangles) round a five-triangle yellow heart."""
        self.pieces[("edelweiss_felt", "edelweiss head")] += 1
        self.pieces[("flower_centre", "edelweiss heart")] += 1
        u, v, n = _frame(facing)
        hub = _add(centre, _scale(n, radius * 0.12))
        rim = []
        for k in range(14):
            a = math.tau * k / 14
            r = radius if k % 2 == 0 else radius * 0.42
            rim.append(_add(centre, _add(_scale(u, r * math.cos(a)), _scale(v, r * math.sin(a)))))
        for k in range(14):
            self.tri("edelweiss_felt", hub, rim[k], rim[(k + 1) % 14])
        top = _add(centre, _scale(n, radius * 0.30))
        ring = [_add(hub, _add(_scale(u, radius * 0.22 * math.cos(math.tau * k / 5)), _scale(v, radius * 0.22 * math.sin(math.tau * k / 5))))
                for k in range(5)]
        for k in range(5):
            self.tri("flower_centre", ring[k], ring[(k + 1) % 5], top)


def mound(b: Builder, root: Vec, rng: random.Random, colour: str, q: dict) -> None:
    """A mounded petunia plant: a short stem, a tuft of round leaves and a ring of blooms looking out and up."""
    height = 0.085 + rng.uniform(0.0, 0.025)
    top = (root[0], root[1], root[2] + height)
    b.stem(root, top, 0.008, 0.006, 4)
    for i in range(q["mound_leaves"]):
        yaw = -math.pi * (0.12 + 0.76 * i / max(q["mound_leaves"] - 1, 1)) + rng.uniform(-0.15, 0.15)   # fanned across the front
        b.leaf("leaf_green", (root[0], root[1], root[2] + height * (0.4 + 0.15 * (i % 2))), yaw,
               rng.uniform(0.05, 0.065), rng.uniform(0.026, 0.032), 0.30)
    for i in range(q["mound_blooms"]):
        a = math.tau * i / q["mound_blooms"] + rng.uniform(-0.4, 0.4)
        c = (top[0] + 0.040 * math.cos(a), top[1] - 0.010 + 0.012 * math.sin(a), top[2] + 0.010 * (i % 2))
        b.petunia(colour, c, (0.30 * math.cos(a), -0.75, 0.55), 0.034 + 0.004 * rng.random())


def trailing(b: Builder, start: Vec, rng: random.Random, colour: str, q: dict, drop: float, sway: float) -> None:
    """A trailing petunia stem: leaves the box top at `start`, arches over the front rim and hangs `drop` down the
    front, with leaves and blooms along it and a bloom at its tip."""
    out = -0.026                                                        # how far it bows away from the box front
    end = (start[0] + sway, start[1] - 0.05, start[2] - drop)
    centres = b.stem(start, end, 0.0055, 0.0035, 3, segments=3, bow=(0.0, out, 0.0))
    for i in range(q["vine_leaves"]):
        p = centres[1 + i % 2]
        b.leaf("leaf_green", (p[0], p[1] - 0.004, p[2]), math.pi * 1.5 + rng.uniform(-1.0, 1.0), 0.046, 0.024, 0.45)
    for i in range(q["vine_blooms"]):
        p = centres[min(1 + i, 3)]
        side = (-1.0 if i % 2 else 1.0)
        b.petunia(colour, (p[0] + side * 0.018, p[1] - 0.026, p[2] + 0.004), (side * 0.35, -0.85, 0.30), 0.031 + 0.004 * rng.random())


def geranium(b: Builder, root: Vec, rng: random.Random, colour: str, q: dict) -> None:
    """An upright (zonal) geranium: a thick stem, big round leaves spiralling up it, and a dense round umbel of florets."""
    height = 0.125 + rng.uniform(0.0, 0.03)
    lean = (rng.uniform(-0.008, 0.008), -rng.uniform(0.0, 0.012), 0.0)
    top = (root[0], root[1], root[2] + height)
    b.stem(root, top, 0.009, 0.006, 4, segments=2, bow=lean)
    crown = _add(top, lean)
    for i in range(q["g_leaves"]):
        yaw = -math.pi * (0.10 + 0.80 * i / max(q["g_leaves"] - 1, 1)) + rng.uniform(-0.15, 0.15)
        b.leaf("leaf_green", (root[0], root[1], root[2] + height * (0.22 + 0.42 * i / max(q["g_leaves"] - 1, 1))), yaw,
               rng.uniform(0.060, 0.074), rng.uniform(0.032, 0.038), 0.22, ring=8)
    b.umbel(colour, (crown[0], crown[1] - 0.012, crown[2] + 0.018), (0.0, -0.55, 0.83), 0.034, q["g_umbel"], 0.017, rng)


def box_kind(index: int) -> str:
    """One box in three is a geranium box (indices 0, 3, 6 ...: 9 of the 26), the rest are petunia boxes."""
    return "geranium" if index % 3 == 0 else "petunia"


def tuft(b: Builder, root: Vec, rng: random.Random, q: dict) -> None:
    """An edelweiss tuft: narrow silvery leaves at the foot and `heads` short stems, each ending in a star."""
    for i in range(3):
        b.leaf("leaf_silver", root, -math.pi * (0.12 + 0.38 * i) + rng.uniform(-0.15, 0.15), 0.052, 0.008, 0.20, ring=4)
    for i in range(q["heads"]):
        a = math.pi * (0.4 + 0.5 * i) + rng.uniform(-0.3, 0.3)
        base = (root[0] + 0.02 * math.cos(a), root[1] + 0.012 * math.sin(a), root[2])
        top = (base[0] + 0.012 * math.cos(a), base[1] - 0.010, base[2] + 0.070 + 0.025 * rng.random())
        b.stem(base, top, 0.0035, 0.0028, 4)
        b.edelweiss_head((top[0], top[1], top[2] + 0.004), (0.25 * math.cos(a), -0.40, 0.88), 0.030)


def _build(seed: int, quality_name: str) -> Builder:
    """The flowers of one window box in its local frame, by `box_kind(seed)`: a petunia box (mounded and trailing
    petunias) or a geranium box (upright geraniums and extra edelweiss), each with a soil bed and edelweiss tufts."""
    q = QUALITY[quality_name]
    kind = box_kind(seed)
    rng = random.Random(seed)
    b = Builder()
    half, depth = BOX_WIDTH / 2 - 0.045, BOX_DEPTH / 2 - 0.03
    soil_z = 0.003                                                           # just above the box top: a dark bed
    ring = [(-half, -depth, soil_z), (half, -depth, soil_z), (half, depth, soil_z), (-half, depth, soil_z)]
    mid = (0.0, 0.0, soil_z + 0.014)                                         # a gentle mound
    for k in range(4):
        b.tri("soil", ring[k], ring[(k + 1) % 4], mid)
    b.pieces[("soil", "soil bed")] += 1
    # Edelweiss tufts nearer the ends of every box; the plants go between them, forward of the window's glazing bars.
    # A geranium box spreads its tufts across the whole width, one in each gap between the plants, a little forward of them.
    if kind == "petunia":
        spots = [(-0.27 + 0.54 * i / max(q["tufts"] - 1, 1), -0.050) for i in range(q["tufts"])]
    else:
        spots = [(-GERANIUM_PITCH / 2, -0.076), (GERANIUM_PITCH / 2, -0.076),
                 (-GERANIUM_PITCH * 1.5, -0.076), (GERANIUM_PITCH * 1.5, -0.076)][:q["g_tufts"]]
    for x, y in spots:
        tuft(b, (x + rng.uniform(-0.012, 0.012), y, soil_z + 0.004), rng, q)
    if kind == "petunia":
        colours = [PETUNIA_COLOURS[(seed + i) % 3] for i in range(8)]
        for i in range(q["mounds"]):
            x = (i - (q["mounds"] - 1) / 2) * 0.17 + rng.uniform(-0.02, 0.02)
            mound(b, (x, -0.060, soil_z + 0.004), rng, colours[i], q)
        for i in range(q["vines"]):
            x = (-0.255 + 0.51 * i / max(q["vines"] - 1, 1)) if q["vines"] > 1 else 0.0
            trailing(b, (x + rng.uniform(-0.02, 0.02), -depth - 0.012, soil_z + 0.014), rng, colours[(i + 3) % 8], q,
                     0.11 + 0.07 * rng.random(), rng.uniform(-0.04, 0.04))
    else:
        offset = seed // 3
        colours = [GERANIUM_COLOURS[(offset + i) % len(GERANIUM_COLOURS)] for i in range(8)]
        n = q["g_plants"]
        for i in range(n):
            x = (i - (n - 1) / 2) * GERANIUM_PITCH + rng.uniform(-0.008, 0.008)
            geranium(b, (x, -0.060, soil_z + 0.004), rng, colours[i], q)
    return b


def box_flowers(seed: int, quality_name: str = "full") -> Dict[str, Mesh]:
    """The per-material triangle meshes of window box number `seed` (see `_build`)."""
    return _build(seed, quality_name).parts


def box_pieces(seed: int, quality_name: str = "full") -> Counter:
    """How many of each (material, piece) the box holds: blooms, florets, buds, heads, leaves, stems, the soil bed."""
    return _build(seed, quality_name).pieces


def triangle_count(parts: Dict[str, Mesh]) -> int:
    return sum(len(faces) for _, faces in parts.values())


def counts(parts: Dict[str, Mesh]) -> Dict[str, int]:
    return {name: len(faces) for name, (_, faces) in parts.items() if faces}


def placed(parts: Dict[str, Mesh], origin: Vec, yaw: float, scale: float) -> Dict[str, Mesh]:
    """The same meshes moved into the world: rotated by `yaw` about z, scaled, then moved to `origin`."""
    c, s = math.cos(yaw), math.sin(yaw)
    out: Dict[str, Mesh] = {}
    for name, (verts, faces) in parts.items():
        out[name] = ([(origin[0] + scale * (x * c - y * s), origin[1] + scale * (x * s + y * c), origin[2] + scale * z)
                      for x, y, z in verts], list(faces))
    return out


def merge(many: List[Dict[str, Mesh]]) -> Dict[str, Mesh]:
    """Several per-material meshes joined into one per-material mesh (face indices shifted)."""
    out: Dict[str, Mesh] = {name: ([], []) for name in MATERIALS}
    for parts in many:
        for name, (verts, faces) in parts.items():
            base = len(out[name][0])
            out[name][0].extend(verts)
            out[name][1].extend(tuple(i + base for i in f) for f in faces)
    return out
