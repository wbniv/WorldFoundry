"""The river panel's map: the river's real banks (wflevels/tide_harbour/chao_phraya_outline.json) and the triangulator.

OpenStreetMap data (ODbL): the credit is printed by the panel (test_tide_harbour_glyph_coverage.py pins it). Plan:
docs/plans/2026-11-21-tide-harbour-clock.md. Pure Python; no network.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))
import polytri  # noqa: E402

OUTLINE = json.loads((ROOT / "wflevels" / "tide_harbour" / "chao_phraya_outline.json").read_text())
CENTRE = json.loads((ROOT / "wflevels" / "tide_harbour" / "chao_phraya_centreline.json").read_text())["points"]
COSL = math.cos(math.radians(13.7))


def rings(poly):
    out, i = [], 0
    for n in poly["rings"]:
        out.append([(x * COSL, y) for x, y in poly["pts"][i:i + n]])
        i += n
    return out


def test_the_outline_carries_its_licence_and_source():
    assert "ODbL" in OUTLINE["licence"] and "OpenStreetMap" in OUTLINE["licence"]
    assert "Overpass" in OUTLINE["source"] and OUTLINE["retrieved"] and OUTLINE["polygons"] and OUTLINE["coast"]


def test_each_polygons_triangles_cover_it_exactly_and_all_face_one_way():
    for k, poly in enumerate(OUTLINE["polygons"]):
        outer, *holes = rings(poly)
        pts = [(x * COSL, y) for x, y in poly["pts"]]
        assert polytri.ring_area(outer) > 0 and all(polytri.ring_area(h) < 0 for h in holes), f"polygon {k}: ring orientation"
        want = polytri.ring_area(outer) + sum(polytri.ring_area(h) for h in holes)
        areas = [polytri.area2(pts[a], pts[b], pts[c]) / 2.0 for a, b, c in poly["tris"]]
        assert all(a > 0 for a in areas), f"polygon {k}: a triangle faces the wrong way or is flat"
        assert abs(sum(areas) - want) / want < 1e-3, f"polygon {k}: the triangles do not cover the polygon"


def test_no_triangle_centre_lies_in_an_island():
    for k, poly in enumerate(OUTLINE["polygons"]):
        _outer, *holes = rings(poly)
        pts = [(x * COSL, y) for x, y in poly["pts"]]
        for a, b, c in poly["tris"]:
            cx, cy = (pts[a][0] + pts[b][0] + pts[c][0]) / 3, (pts[a][1] + pts[b][1] + pts[c][1]) / 3
            assert not any(polytri._inside_ring((cx, cy), h) for h in holes), f"polygon {k}: water over an island"


def test_the_water_polygons_cover_the_whole_centreline():
    """Why the centreline stroke could go: every 50 m along the river's centreline is inside a water polygon."""
    tris = []
    for poly in OUTLINE["polygons"]:
        pts = [(x * COSL, y) for x, y in poly["pts"]]
        for a, b, c in poly["tris"]:
            xs, ys = [pts[a][0], pts[b][0], pts[c][0]], [pts[a][1], pts[b][1], pts[c][1]]
            tris.append((pts[a], pts[b], pts[c], min(xs), max(xs), min(ys), max(ys)))
    total = outside = 0
    for p, q in zip(CENTRE, CENTRE[1:]):
        n = max(1, int(math.hypot((q[0] - p[0]) * COSL * 111.2, (q[1] - p[1]) * 111.2) / 0.05))
        for k in range(n + 1):
            t = k / n
            pt = ((p[0] + (q[0] - p[0]) * t) * COSL, p[1] + (q[1] - p[1]) * t)
            total += 1
            if not any(x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 and polytri._in_triangle(pt, a, b, c) for a, b, c, x0, x1, y0, y1 in tris):
                outside += 1
    assert outside / total < 0.005, f"{outside} of {total} centreline samples are outside the water"


def test_the_triangulator_on_a_square_with_a_hole_and_a_concave_c():
    sq, hole = [(0, 0), (10, 0), (10, 10), (0, 10)], [(3, 3), (3, 7), (7, 7), (7, 3)]
    pts, tris = polytri.triangulate(sq, [hole])
    assert abs(sum(polytri.area2(pts[a], pts[b], pts[c]) / 2 for a, b, c in tris) - 84.0) < 1e-9
    c_shape = [(0, 0), (10, 0), (10, 3), (3, 3), (3, 7), (10, 7), (10, 10), (0, 10)]
    pts, tris = polytri.triangulate(c_shape, [])
    assert abs(sum(polytri.area2(pts[a], pts[b], pts[c]) / 2 for a, b, c in tris) - polytri.ring_area(c_shape)) < 1e-9 and len(tris) == 6
