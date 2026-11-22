#!/usr/bin/env python3
"""The Chao Phraya's real banks, and the Gulf coast at its mouth, for the river panel's map.

    python3 wflevels/tide_harbour/fetch_river_outline.py                       # one Overpass request
    python3 wflevels/tide_harbour/fetch_river_outline.py --from-json raw.json   # reuse a saved response

Writes chao_phraya_outline.json: the river as water polygons (outer rings and islands) so the map can draw both banks and
the river's true width, and the coastline as lines. Source: OpenStreetMap (natural=water + water=river relations and ways,
and natural=coastline ways), (c) OpenStreetMap contributors, Open Database License (ODbL) 1.0; the panel prints that credit
wherever the map is shown (blender_create_tide_harbour.py, CREDIT). One request, politely identified; the result is
committed so a build never needs the network. The member ways of each multipolygon are joined into closed rings, only
polygons that come within NEAR_M of the river's centreline (chao_phraya_centreline.json) are kept, which leaves out the
canals, and each ring is simplified with Douglas-Peucker to TOL_M.

The earlier river map drew only the centreline as a stroke of fixed width: no banks, no true width, no mouth.
Plan: docs/plans/2026-11-21-tide-harbour-clock.md (the river panel's map).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import polytri  # noqa: E402
OUT = HERE / "chao_phraya_outline.json"
CENTRELINE = HERE / "chao_phraya_centreline.json"
BOX = (13.40, 100.40, 13.86, 100.70)               # south, west, north, east: the map's reach and a margin
COAST_BOX = (13.40, 100.40, 13.62, 100.70)         # the coast only matters near the mouth
ENDPOINTS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
USER_AGENT = "worldfoundry-tide-harbour-map/1.0 (one-off fetch of a river outline for a game level's map)"
TOL_M = 40.0
NEAR_M = 600.0
LAT_M = 111_200.0


def query() -> str:
    s, w, n, e = BOX
    cs, cw, cn, ce = COAST_BOX
    return (f'[out:json][timeout:90];(rel["natural"="water"]["water"="river"]({s},{w},{n},{e});'
            f'way["natural"="water"]["water"="river"]({s},{w},{n},{e});'
            f'way["natural"="coastline"]({cs},{cw},{cn},{ce}););out geom;')


def fetch() -> tuple[dict, str]:
    for ep in ENDPOINTS:
        try:
            req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": query()}).encode(), headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read()), ep
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError) as e:
            print(f"{ep}: {e}", file=sys.stderr)
    raise SystemExit("no Overpass endpoint answered")


Pt = tuple[float, float]


def to_m(p: Pt, lat0: float) -> Pt:
    return p[0] * LAT_M * math.cos(math.radians(lat0)), p[1] * LAT_M


def join_rings(ways: list[list[Pt]]) -> list[list[Pt]]:
    """Chain open ways end to end (reversing where needed) into closed rings; a way already closed is a ring."""
    rings: list[list[Pt]] = []
    pool = [w[:] for w in ways if len(w) >= 2]
    while pool:
        cur = pool.pop()
        grown = True
        while grown and cur[0] != cur[-1]:
            grown = False
            for i, w in enumerate(pool):
                if w[0] == cur[-1]:
                    cur += w[1:]
                elif w[-1] == cur[-1]:
                    cur += w[::-1][1:]
                elif w[-1] == cur[0]:
                    cur = w[:-1] + cur
                elif w[0] == cur[0]:
                    cur = w[::-1][:-1] + cur
                else:
                    continue
                pool.pop(i)
                grown = True
                break
        if cur[0] == cur[-1] and len(cur) >= 4:
            rings.append(cur[:-1])
    return rings


def dp_open(points: list[Pt], tol_m: float) -> list[Pt]:
    lat0 = sum(p[1] for p in points) / len(points)
    xy = [to_m(p, lat0) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = xy[a], xy[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        far, fi = -1.0, -1
        for i in range(a + 1, b):
            px, py = xy[i]
            d = math.hypot(px - ax, py - ay) if norm == 0 else abs(dy * (px - ax) - dx * (py - ay)) / norm
            if d > far:
                far, fi = d, i
        if far > tol_m and fi >= 0:
            keep[fi] = True
            stack += [(a, fi), (fi, b)]
    return [p for p, k in zip(points, keep) if k]


def dp_ring(ring: list[Pt], tol_m: float) -> list[Pt]:
    """Simplify a closed ring: split it at its two most distant vertices so both halves are open lines."""
    lat0 = sum(p[1] for p in ring) / len(ring)
    xy = [to_m(p, lat0) for p in ring]
    i0 = 0
    j0 = max(range(len(ring)), key=lambda j: math.hypot(xy[j][0] - xy[i0][0], xy[j][1] - xy[i0][1]))
    a = dp_open(ring[i0:j0 + 1], tol_m)
    b = dp_open(ring[j0:] + ring[:i0 + 1], tol_m)
    return a[:-1] + b[:-1]


def signed_area(ring: list[Pt]) -> float:
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring))) / 2.0


def near_centreline(ring: list[Pt], centre: list[Pt]) -> bool:
    lat0 = 13.7
    cxy = [to_m(c, lat0) for c in centre]
    for p in ring[::3] or ring:
        x, y = to_m(p, lat0)
        if any(math.hypot(x - cx, y - cy) <= NEAR_M for cx, cy in cxy):
            return True
    return False


def _simple(ring: list[Pt]) -> bool:
    """No two edges of the ring cross (touching at an end does not count)."""
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if polytri._proper_cross(a, b, ring[j], ring[(j + 1) % n]):
                return False
    return True


def _polygon(outer: list[Pt], holes: list[list[Pt]]) -> dict | None:
    """Simplify the rings, finer until every ring is simple and the triangles cover exactly the polygon; None if none does."""
    cl = math.cos(math.radians(13.7))
    for tol in (TOL_M, 20.0, 10.0, 5.0, 2.0, 0.0):
        def prep(r: list[Pt]) -> list[Pt]:
            r2 = dp_ring(r, tol) if tol > 0 else r
            return [(round(lo, 5), round(la, 5)) for lo, la in r2]
        so = prep(outer)
        if len(so) < 3:
            return None
        sh = [prep(h) for h in holes]
        sh = [h for h in sh if len(h) >= 3]
        if signed_area(so) < 0:
            so = so[::-1]
        sh = [h[::-1] if signed_area(h) > 0 else h for h in sh]
        flat = lambda r: [(lo * cl, la) for lo, la in r]
        if not (_simple(flat(so)) and all(_simple(flat(h)) for h in sh)):
            continue
        try:
            pts, tris = polytri.triangulate(flat(so), [flat(h) for h in sh])
        except ValueError:
            continue
        want = polytri.ring_area(flat(so)) + sum(polytri.ring_area(flat(h)) for h in sh)
        got = sum(polytri.area2(pts[a], pts[b], pts[c]) / 2.0 for a, b, c in tris)
        if want > 0 and abs(got - want) / want < 1e-3:
            return {"pts": [[lo, la] for lo, la in so + [p for h in sh for p in h]], "rings": [len(so)] + [len(h) for h in sh], "tris": [list(t) for t in tris]}
    return None


def build(data: dict, used: str) -> dict:
    centre = [tuple(p) for p in json.loads(CENTRELINE.read_text())["points"]]
    polygons, coast = [], []
    for el in data["elements"]:
        tags = el.get("tags", {})
        if el["type"] == "way" and tags.get("natural") == "coastline" and el.get("geometry"):
            line = [(g["lon"], g["lat"]) for g in el["geometry"]]
            coast.append([[round(lo, 5), round(la, 5)] for lo, la in dp_open(line, TOL_M)])
        elif el["type"] == "relation":
            outer = join_rings([[(g["lon"], g["lat"]) for g in m["geometry"]] for m in el["members"] if m.get("role") == "outer" and m.get("geometry")])
            inner = join_rings([[(g["lon"], g["lat"]) for g in m["geometry"]] for m in el["members"] if m.get("role") == "inner" and m.get("geometry")])
            for o in outer:
                if not near_centreline(o, centre):
                    continue
                holes = [h for h in inner if near_centreline(h, centre) and _inside(h[0], o)]
                polygons.append((o, holes))
        elif el["type"] == "way" and tags.get("natural") == "water" and el.get("geometry"):
            ring = [(g["lon"], g["lat"]) for g in el["geometry"]]
            if ring[0] == ring[-1] and len(ring) >= 4 and near_centreline(ring[:-1], centre):
                polygons.append((ring[:-1], []))
    out = []
    for o, holes in polygons:
        got = _polygon(o, holes)
        if got is not None:
            out.append(got)
    return {
        "what": "The Chao Phraya's banks as water polygons and the Gulf coast at the mouth as lines. Each polygon is `pts` (the outer ring, "
                "then each island, as longitude, latitude), `rings` (how many points each ring has) and `tris` (triangles, indices into pts, counter-clockwise), simplified with "
                f"Douglas-Peucker to at most {TOL_M:.0f} m and finer where that made a ring cross itself: {len(out)} polygons, "
                f"{sum(len(p['pts']) for p in out)} points, {sum(len(p['tris']) for p in out)} triangles; {len(coast)} coastline lines.",
        "source": "OpenStreetMap: natural=water + water=river relations and ways, and natural=coastline ways, through the Overpass API "
                  f"({used}); polygons within {NEAR_M:.0f} m of chao_phraya_centreline.json",
        "osm_base": (data.get("osm3s") or {}).get("timestamp_osm_base"),
        "retrieved": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "licence": "(c) OpenStreetMap contributors, Open Database License (ODbL) 1.0. Attribution is required wherever a map made from it is shown.",
        "polygons": out,
        "coast": coast,
    }


def _inside(p: Pt, ring: list[Pt]) -> bool:
    x, y = p
    c = False
    for i in range(len(ring)):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % len(ring)]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            c = not c
    return c


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-json", type=Path, help="reuse a saved Overpass response (out geom) instead of fetching")
    args = ap.parse_args(argv)
    data, used = (json.loads(args.from_json.read_text()), str(args.from_json)) if args.from_json else fetch()
    doc = build(data, used)
    OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
    n = sum(len(p["pts"]) for p in doc["polygons"])
    print(f"{OUT.name}: {len(doc['polygons'])} polygons, {n} points, {sum(len(p['tris']) for p in doc['polygons'])} triangles, "
          f"{len(doc['coast'])} coast lines, {OUT.stat().st_size} bytes")
    return 0 if doc["polygons"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
