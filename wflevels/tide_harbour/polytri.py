"""Triangulate a polygon with holes: ear clipping after bridging each hole into the outer ring. Pure Python.

    triangulate(outer, holes) -> (points, triangles)

`outer` is a counter-clockwise ring and each hole a clockwise ring, as (x, y) tuples in any planar units (the caller uses
longitude scaled by cos(latitude), and latitude). `points` is the outer ring followed by every hole's points, and each
triangle is three indices into it, counter-clockwise. The bridge points are repeated in the walk but not in `points`.
Used by fetch_river_outline.py for the river panel's map (the river's banks as water polygons); tests/test_tide_harbour_outline.py
checks the area of the triangles equals the polygon's, and that none lies in a hole.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

Pt = Tuple[float, float]
EPS = 1e-12


def area2(a: Pt, b: Pt, c: Pt) -> float:
    """Twice the signed area of the triangle a, b, c (> 0 when counter-clockwise)."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def ring_area(ring: Sequence[Pt]) -> float:
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring))) / 2.0


def _on_segment(a: Pt, b: Pt, p: Pt) -> bool:
    return abs(area2(a, b, p)) <= EPS and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS


def _proper_cross(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    """Segments a-b and c-d cross at a point interior to both (touching at an end does not count)."""
    d1, d2, d3, d4 = area2(c, d, a), area2(c, d, b), area2(a, b, c), area2(a, b, d)
    return ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and ((d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS))


def _in_triangle(p: Pt, a: Pt, b: Pt, c: Pt) -> bool:
    """p inside or on the edge of the counter-clockwise triangle a, b, c."""
    return area2(a, b, p) >= -EPS and area2(b, c, p) >= -EPS and area2(c, a, p) >= -EPS


def _inside_ring(p: Pt, ring: Sequence[Pt]) -> bool:
    x, y = p
    inside = False
    for i in range(len(ring)):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % len(ring)]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def _visible(m: Pt, v: Pt, rings: Sequence[Sequence[Pt]]) -> bool:
    """The bridge m-v crosses no ring edge."""
    for ring in rings:
        n = len(ring)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            if _proper_cross(m, v, a, b):
                return False
    return True


def triangulate(outer: List[Pt], holes: List[List[Pt]]) -> Tuple[List[Pt], List[Tuple[int, int, int]]]:
    points: List[Pt] = list(outer)
    walk: List[int] = list(range(len(outer)))
    rings: List[List[Pt]] = [list(outer)]
    base = len(outer)
    hole_idx: List[List[int]] = []
    for h in holes:
        hole_idx.append(list(range(base, base + len(h))))
        points.extend(h)
        rings.append(list(h))
        base += len(h)
    # bridge the holes in, the one reaching furthest right first
    for hi in sorted(range(len(holes)), key=lambda k: -max(points[i][0] for i in hole_idx[k])):
        idx = hole_idx[hi]
        m_pos = max(range(len(idx)), key=lambda k: points[idx[k]][0])
        m = points[idx[m_pos]]
        candidates = sorted(range(len(walk)), key=lambda k: (points[walk[k]][0] - m[0]) ** 2 + (points[walk[k]][1] - m[1]) ** 2)
        for k in candidates:
            if _visible(m, points[walk[k]], rings):
                rot = idx[m_pos:] + idx[:m_pos]
                walk = walk[:k + 1] + rot + [idx[m_pos], walk[k]] + walk[k + 1:]
                break
        else:
            raise ValueError("a hole sees no vertex of the outer ring")
    return points, _ear_clip(points, walk)


def _ear_clip(points: List[Pt], walk: List[int]) -> List[Tuple[int, int, int]]:
    tris: List[Tuple[int, int, int]] = []
    ring = walk[:]
    guard = 0
    while len(ring) > 3:
        n = len(ring)
        ear = -1
        reflex = [j for j in range(n) if area2(points[ring[j - 1]], points[ring[j]], points[ring[(j + 1) % n]]) < -EPS]
        for i in range(n):
            a, b, c = ring[i - 1], ring[i], ring[(i + 1) % n]
            pa, pb, pc = points[a], points[b], points[c]
            if area2(pa, pb, pc) <= EPS:
                continue                                   # reflex or flat: not an ear
            ok = True
            for j in reflex:
                q = ring[j]
                if q in (a, b, c) or points[q] in (pa, pb, pc):
                    continue
                if _in_triangle(points[q], pa, pb, pc):
                    ok = False
                    break
            if ok:
                ear = i
                break
        if ear < 0:                                        # a degenerate sliver: drop the flattest vertex and go on
            flat = min(range(n), key=lambda j: abs(area2(points[ring[j - 1]], points[ring[j]], points[ring[(j + 1) % n]])))
            ring.pop(flat)
            guard += 1
            if guard > len(walk):
                raise ValueError("ear clipping did not finish")
            continue
        a, b, c = ring[ear - 1], ring[ear], ring[(ear + 1) % n]
        tris.append((a, b, c))
        ring.pop(ear)
    if len(ring) == 3 and area2(points[ring[0]], points[ring[1]], points[ring[2]]) > EPS:
        tris.append((ring[0], ring[1], ring[2]))
    return tris
