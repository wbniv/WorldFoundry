"""The clocks' shared mesh builder: faces, boxes, prisms, cylinders and discs as plain Python.

Hoisted from wflevels/minute_machine/parts.py (plan docs/plans/2026-11-21-tide-harbour-clock.md,
"Shared code"), so every clock level builds its geometry with one class and the Blender scripts
only turn it into objects. Pure Python, no Blender, so tests can check winding and budgets.

Conventions: metres, z up, x right, y into the screen. A face is wound counter-clockwise seen from
its visible side (Blender's exterior winding), because the engine culls back faces. A face's colour
is a key; the Blender script turns each key into one material, in the order the keys first appear,
so a mesh's material slots are known (the colour mailboxes 3037 to 3039 address slots 0 to 2).
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

V3 = Tuple[float, float, float]
BOX_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


class Mesh:
    def __init__(self, name: str):
        self.name = name
        self.vertices: List[V3] = []
        self.faces: List[Tuple[int, ...]] = []
        self.colors: List[str] = []

    def face(self, points: Sequence[V3], color: str) -> None:
        start = len(self.vertices)
        self.vertices.extend(tuple(p) for p in points)
        self.faces.append(tuple(range(start, len(self.vertices))))
        self.colors.append(color)

    def box(self, lo: V3, hi: V3, color: str) -> None:
        a, b, c = lo
        x, y, z = hi
        v = [(a, b, c), (x, b, c), (x, y, c), (a, y, c), (a, b, z), (x, b, z), (x, y, z), (a, y, z)]
        for f in BOX_FACES:
            self.face([v[i] for i in f], color)

    def prism_xz(self, poly: Sequence[Tuple[float, float]], y0: float, y1: float, color: str) -> None:
        """A closed prism: a convex polygon in x-z (counter-clockwise seen from -y) extruded along y."""
        n = len(poly)
        front = [(x, y0, z) for x, z in poly]
        back = [(x, y1, z) for x, z in poly]
        self.face(front, color)                       # counter-clockwise seen from -y: normal toward -y
        self.face(list(reversed(back)), color)        # normal toward +y
        for i in range(n):
            j = (i + 1) % n
            self.face([front[j], front[i], back[i], back[j]], color)

    def beam(self, p0: Tuple[float, float], p1: Tuple[float, float], thick: float, y0: float, y1: float, color: str) -> None:
        """A bar between two points in x-z, `thick` across, extruded along y."""
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        n = math.hypot(dx, dz)
        nx, nz = -dz / n * thick / 2, dx / n * thick / 2
        self.prism_xz([(p0[0] - nx, p0[1] - nz), (p1[0] - nx, p1[1] - nz), (p1[0] + nx, p1[1] + nz), (p0[0] + nx, p0[1] + nz)],
                      y0, y1, color)

    def sphere(self, center: V3, r: float, color: str, segments: int = 12, rings: int = 8) -> None:
        def pt(i, j):
            a, b = math.tau * i / segments, math.pi * j / rings
            return (center[0] + r * math.sin(b) * math.cos(a), center[1] + r * math.sin(b) * math.sin(a), center[2] + r * math.cos(b))
        for j in range(rings):
            for i in range(segments):
                quad = [pt(i, j), pt(i, j + 1), pt(i + 1, j + 1), pt(i + 1, j)]
                quad = list(dict.fromkeys(tuple(round(v, 9) for v in p) for p in quad))
                if len(quad) >= 3:
                    self.face(quad, color)

    def cylinder_y(self, cx: float, cz: float, r: float, y0: float, y1: float, color: str, sides: int = 14) -> None:
        """A cylinder whose axis runs along y (a pulley)."""
        ring0 = [(cx + r * math.cos(math.tau * i / sides), y0, cz + r * math.sin(math.tau * i / sides)) for i in range(sides)]
        ring1 = [(x, y1, z) for x, _, z in ring0]
        self.face(list(ring0), color)
        self.face(list(reversed(ring1)), color)
        for i in range(sides):
            j = (i + 1) % sides
            self.face([ring0[j], ring0[i], ring1[i], ring1[j]], color)

    def column_z(self, cx: float, cy: float, z0: float, z1: float, r: float, color: str, sides: int = 10) -> None:
        """A cylinder whose axis runs along z (a screw shaft)."""
        lo = [(cx + r * math.cos(math.tau * i / sides), cy + r * math.sin(math.tau * i / sides), z0) for i in range(sides)]
        hi = [(x, y, z1) for x, y, _ in lo]
        self.face(list(reversed(lo)), color)
        self.face(hi, color)
        for i in range(sides):
            j = (i + 1) % sides
            self.face([lo[i], lo[j], hi[j], hi[i]], color)

    def disc_y(self, cx: float, cz: float, r: float, y: float, color: str, sides: int = 16) -> None:
        """A flat disc in the plane y, facing -y (the camera). One face: a disc never needs a back."""
        self.face([(cx + r * math.cos(math.tau * i / sides), y, cz + r * math.sin(math.tau * i / sides)) for i in range(sides)], color)

    def quad_y(self, x0: float, z0: float, x1: float, z1: float, y: float, color: str) -> None:
        """A rectangle in the plane y, facing -y."""
        self.face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], color)

    def bounds(self) -> Tuple[V3, V3]:
        xs, ys, zs = zip(*self.vertices)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def material_keys(self) -> List[str]:
        """The material slots, in order: each colour key where it first appears."""
        return list(dict.fromkeys(self.colors))


def face_normal(points: Sequence[V3]) -> V3:
    """Newell's normal of a polygon: its direction says which side is visible."""
    nx = ny = nz = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return nx, ny, nz


def signed_volume(mesh: Mesh) -> float:
    """Six times the enclosed volume, positive when a closed mesh's faces point outward."""
    total = 0.0
    for f in mesh.faces:
        p0 = mesh.vertices[f[0]]
        for i in range(1, len(f) - 1):
            a, b = mesh.vertices[f[i]], mesh.vertices[f[i + 1]]
            total += (p0[0] * (a[1] * b[2] - a[2] * b[1]) - p0[1] * (a[0] * b[2] - a[2] * b[0]) + p0[2] * (a[0] * b[1] - a[1] * b[0]))
    return total
