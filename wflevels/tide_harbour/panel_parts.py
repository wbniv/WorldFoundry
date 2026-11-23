"""Tide Harbour: the river panel's geometry.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (the river panel). Pure Python on the clocks' shared mesh builder,
so tests can check winding, fit and budgets. Every mesh is in panel coordinates (x = u to the right, z = v up, in
metres at the panel's depth) and faces -y, the camera, as the dial does (panel.py explains how each part is posed
from the camera). The glyphs (the Thai digits of the drums, the map's place names, the unit label and the column's
numerals) come from a font, so only Blender can draw them: blender_create_tide_harbour.py adds them to these meshes.

Layers from the back: paper, map, column, the band's plate, the drums, the band's mask (panel.D_*). The mask has a
window in front of each drum, so only one digit of a drum shows; the band's plate hides the map where it runs up
under the band.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import panel as pn

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clock_common"))
from clock_mesh import Mesh  # noqa: E402

HERE = Path(__file__).resolve().parent
# The river: OpenStreetMap contributors (ODbL), 74 points; the copy the mockup reads is docs/plans/2026-11-21-tide-harbour-clock/ (a test keeps them equal)
CENTRELINE = HERE / "chao_phraya_centreline.json"
OUTLINE = HERE / "chao_phraya_outline.json"     # the banks as water polygons (fetch_river_outline.py): (c) OpenStreetMap contributors, ODbL
RIVER_WIDTH = 0.018            # metres on the panel: only the station markers' offset now (the river is drawn at its true width)
COAST_WIDTH = 0.006            # the coast's stroke, metres on the panel
STATION_DX = RIVER_WIDTH / 2 + 0.035      # a station marker stands this far east of the river's centreline, on the bank
WIN_BASE = pn.WIN_H / 2 - 0.02     # the decimal point sits at a digit's foot
LAT_M = 111.2                  # kilometres per degree of latitude

# The panel's material keys: (kind, day colour). "panel" dims at night with the panel; "ptext" dims less, so the readings stay legible.
PANEL_MATERIALS: Dict[str, Tuple[str, Tuple[float, float, float]]] = {
    "p_paper": ("panel", (0.92, 0.87, 0.76)),
    "p_wood": ("panel", (0.42, 0.28, 0.16)),
    "p_water": ("panel", (0.17, 0.37, 0.55)),
    "p_stone": ("panel", (0.96, 0.93, 0.84)),
    "p_gold": ("panel", (0.79, 0.63, 0.29)),
    "p_text": ("ptext", (0.97, 0.94, 0.84)),
    "p_up": ("ptext", (0.38, 0.78, 0.36)),
    "p_dn": ("ptext", (0.95, 0.52, 0.30)),
    "p_ink": ("fixed", (0.11, 0.08, 0.05)),
    "p_ptr": ("ptext", (0.88, 0.35, 0.18)),
}


def _tri(m: Mesh, a, b, c, color: str) -> None:
    """A triangle in the panel plane, wound counter-clockwise seen from -y whatever order the points come in."""
    area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    pts = [a, b, c] if area > 0 else [a, c, b]
    m.face([(x, 0.0, z) for x, z in pts], color)


def _quad(m: Mesh, x0: float, z0: float, x1: float, z1: float, color: str) -> None:
    if x1 > x0 and z1 > z0:
        m.quad_y(x0, z0, x1, z1, 0.0, color)


def paper_mesh() -> Mesh:
    m = Mesh("panel_paper")
    _quad(m, -pn.W / 2, -pn.H / 2, pn.W / 2, pn.H / 2, "p_paper")
    return m


def band_back_mesh() -> Mesh:
    m = Mesh("panel_band_back")
    _quad(m, -pn.W / 2, pn.H / 2 - pn.BAND_H, pn.W / 2, pn.H / 2, "p_wood")
    return m


def windows() -> List[Tuple[int, str, float, float]]:
    """Every digit window: (row, drum name, centre u, centre v)."""
    return [(row, name, pn.row_u(name), pn.row_v(row)) for row in (0, 1) for name in pn.DRUMS]


def band_mask_mesh() -> Mesh:
    """What sits on the band's wood: the high and low icons, the colons and decimal points, a dark plate behind each digit,
    and a rule under the band. (The unit label and the minute units' zero are glyphs: Blender adds them.) The wood itself is
    band_back_mesh, solid: a drum's other digits are turned away behind it, so no window needs cutting."""
    m = Mesh("panel_band_mask")
    for row in (0, 1):                                              # the marks first, so p_text is this mesh's first material
        v = pn.row_v(row)
        iu = pn.row_u("icon")
        if row == 0:                                                # a triangle over a water line: high water
            _tri(m, (iu - 0.045, v - 0.01), (iu + 0.045, v - 0.01), (iu, v + 0.075), "p_text")
            _quad(m, iu - 0.05, v - 0.065, iu + 0.05, v - 0.045, "p_text")
        else:                                                       # under one: low water
            _tri(m, (iu - 0.045, v + 0.01), (iu + 0.045, v + 0.01), (iu, v - 0.075), "p_text")
            _quad(m, iu - 0.05, v + 0.045, iu + 0.05, v + 0.065, "p_text")
        cu = pn.row_u("colon")
        for dv in (-0.045, 0.045):
            _quad(m, cu - 0.012, v + dv - 0.012, cu + 0.012, v + dv + 0.012, "p_text")
        du = pn.row_u("dot")
        _quad(m, du - 0.013, v - WIN_BASE - 0.013, du + 0.013, v - WIN_BASE + 0.013, "p_text")
    for _row, _name, u, v in windows():                             # the plate each digit shows on
        _quad(m, u - pn.WIN_W / 2, v - pn.WIN_H / 2, u + pn.WIN_W / 2, v + pn.WIN_H / 2, "p_ink")
    _quad(m, -pn.W / 2, pn.H / 2 - pn.BAND_H - 0.012, pn.W / 2, pn.H / 2 - pn.BAND_H, "p_ink")        # a rule under the band
    return m


def _arrow(name: str, up: bool) -> Mesh:
    """An arrow centred on the band's two rows: up for a rising tide, down for a falling one."""
    m = Mesh(name)
    k = 1.0 if up else -1.0
    head, shaft, hw, sw, half = 0.20, 0.14, 0.045, 0.016, 0.21
    key = "p_up" if up else "p_dn"
    _tri(m, (-hw, k * (half - head)), (hw, k * (half - head)), (0.0, k * half), key)
    lo, hi = sorted((-half, k * (half - head)))
    _quad(m, -sw, lo, sw, hi, key)
    return m


def arrow_up_mesh() -> Mesh:
    return _arrow("panel_arrow_up", True)


def arrow_dn_mesh() -> Mesh:
    return _arrow("panel_arrow_dn", False)


def column_body_mesh() -> Mesh:
    """The level column's tube and ticks (1, 2 and 3 m), and the north arrow and scale bar, which stay on the paper
    while the map slides under them."""
    m = Mesh("panel_col_body")
    cw = 0.026
    x0, x1, z0, z1, t = pn.COL_X - cw, pn.COL_X + cw, pn.COL_V0, pn.COL_V1, 0.008
    _quad(m, x0, z0, x1, z1, "p_stone")                                    # the tube; its frame is four strips round it, not a quad under it:
    _quad(m, x0 - t, z0 - t, x0, z1 + t, "p_ink")                          # two quads of one depth z-fight (the column looked garbled on cast1)
    _quad(m, x1, z0 - t, x1 + t, z1 + t, "p_ink")
    _quad(m, x0, z0 - t, x1, z0, "p_ink")
    _quad(m, x0, z1, x1, z1 + t, "p_ink")
    for metres in (1.0, 2.0, 3.0):
        v = pn.level_v(metres)
        _quad(m, pn.COL_X - cw - 0.03, v - 0.003, pn.COL_X - cw, v + 0.003, "p_ink")
    nx, nz = -pn.W / 2 + 0.07, pn.H / 2 - pn.BAND_H - 0.12                       # north arrow, under the band at the left
    _tri(m, (nx, nz + 0.07), (nx + 0.03, nz - 0.03), (nx - 0.03, nz - 0.03), "p_ink")
    km = pn.SCALE_KM * pn.M_PER_KM                                               # the scale bar, right of where the map reaches
    bx, bz = pn.SCALE_X1 - km, pn.SCALE_V
    _quad(m, bx, bz - 0.004, bx + km, bz + 0.004, "p_ink")
    _quad(m, bx - 0.004, bz - 0.02, bx + 0.004, bz + 0.02, "p_ink")
    _quad(m, bx + km - 0.004, bz - 0.02, bx + km + 0.004, bz + 0.02, "p_ink")
    return m


def column_fill_mesh() -> Mesh:
    """The water in the column, from its foot up (z = 0 at the foot): scaled in z to the tide."""
    m = Mesh("panel_col_fill")
    _quad(m, -0.02, 0.0, 0.02, pn.COL_V1 - pn.COL_V0, "p_water")
    return m


def column_pointer_mesh() -> Mesh:
    """A pointer to the right of the column, its tip at the tide (z = 0)."""
    m = Mesh("panel_col_ptr")
    _tri(m, (0.0, 0.0), (0.05, 0.028), (0.05, -0.028), "p_ptr")
    return m


def outline() -> dict:
    return json.loads(OUTLINE.read_text())


def river_points() -> List[Tuple[float, float]]:
    """The river as panel metres about the map's origin (latitude MAP_LAT0, longitude MAP_LON0): x east, z north."""
    doc = json.loads(CENTRELINE.read_text())
    cosl = math.cos(math.radians(pn.MAP_LAT0))
    return [((lon - pn.MAP_LON0) * cosl * LAT_M * pn.M_PER_KM, (lat - pn.MAP_LAT0) * LAT_M * pn.M_PER_KM) for lon, lat in doc["points"]]


def map_xy(lon: float, lat: float) -> Tuple[float, float]:
    cosl = math.cos(math.radians(pn.MAP_LAT0))
    return (lon - pn.MAP_LON0) * cosl * LAT_M * pn.M_PER_KM, (lat - pn.MAP_LAT0) * LAT_M * pn.M_PER_KM


def _clip_segment(p: Tuple[float, float], q: Tuple[float, float], x0: float, x1: float, z0: float, z1: float):
    """Liang-Barsky: the part of the segment p-q inside the rectangle, or None."""
    t0, t1 = 0.0, 1.0
    dx, dz = q[0] - p[0], q[1] - p[1]
    for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dz, p[1] - z0), (dz, z1 - p[1])):
        if pk == 0:
            if qk < 0:
                return None
        else:
            r = qk / pk
            if pk < 0:
                if r > t1:
                    return None
                t0 = max(t0, r)
            else:
                if r < t0:
                    return None
                t1 = min(t1, r)
    return (p[0] + t0 * dx, p[1] + t0 * dz), (p[0] + t1 * dx, p[1] + t1 * dz)


def _clip_rect(poly: List[Tuple[float, float]], x0: float, x1: float, z0: float, z1: float) -> List[Tuple[float, float]]:
    """Sutherland-Hodgman: a convex polygon cut to the rectangle, vertices in the same turning order."""
    def cut(pts, inside, cross):
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            if inside(p):
                out.append(p)
                if not inside(q):
                    out.append(cross(p, q))
            elif inside(q):
                out.append(cross(p, q))
        return out
    at_x = lambda xv: (lambda p, q: (xv, p[1] + (q[1] - p[1]) * (xv - p[0]) / (q[0] - p[0])))
    at_z = lambda zv: (lambda p, q: (p[0] + (q[0] - p[0]) * (zv - p[1]) / (q[1] - p[1]), zv))
    for inside, cross in ((lambda p: p[0] >= x0, at_x(x0)), (lambda p: p[0] <= x1, at_x(x1)),
                          (lambda p: p[1] >= z0, at_z(z0)), (lambda p: p[1] <= z1, at_z(z1))):
        poly = cut(poly, inside, cross) if poly else poly
    return poly


def map_mesh() -> Mesh:
    """The river as the water polygons of its real banks (chao_phraya_outline.json: OpenStreetMap, ODbL; fetch_river_outline.py),
    the Gulf's coast either side of the mouth as a thin stroke, the Navy's station as a small tower, the Bangkok Bar tide staff,
    and three ripples for the sea off the mouth. The place names are glyphs: Blender adds them."""
    m = Mesh("panel_map")
    pts = river_points()                                                   # the centreline: only where the window's extent comes from
    left, right = -pn.W / 2 + 0.03, pn.COL_X - 0.09                         # the window the map may fill (the fit test pins it)
    south, north = min(z for _x, z in pts) - 0.3, max(z for _x, z in pts) + 0.1
    for poly in outline()["polygons"]:                                     # the river's real banks and width, under the stroke
        xy = [map_xy(lon, lat) for lon, lat in poly["pts"]]
        used: Dict[int, int] = {}                                         # a polygon's vertex -> its index in the mesh, added when first used

        def vertex(i: int) -> int:
            if i not in used:
                used[i] = len(m.vertices)
                m.vertices.append((xy[i][0], 0.0, xy[i][1]))
            return used[i]

        for a, b, c in poly["tris"]:                                      # counter-clockwise in (x, z): faces the camera
            tri = [xy[a], xy[b], xy[c]]
            if all(left <= x <= right and south <= z <= north for x, z in tri):
                m.faces.append((vertex(a), vertex(b), vertex(c)))
                m.colors.append("p_water")
                continue
            piece = _clip_rect(tri, left, right, south, north)            # a triangle over the window's edge: cut to it
            for k in range(1, len(piece) - 1):
                p0, p1, p2 = piece[0], piece[k], piece[k + 1]
                if (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]) > 1e-9:
                    start = len(m.vertices)
                    m.vertices.extend((x, 0.0, z) for x, z in (p0, p1, p2))
                    m.faces.append((start, start + 1, start + 2))
                    m.colors.append("p_water")
    for line in outline()["coast"]:                                        # the Gulf's coast either side of the mouth: a thin stroke
        pts_c = [map_xy(lon, lat) for lon, lat in line]
        for p, q in zip(pts_c, pts_c[1:]):
            h = COAST_WIDTH / 2 + 1e-6                                     # the stroke's own half-width stays inside the window
            seg = _clip_segment(p, q, left + h, right - h, south + h, north - h)
            if seg is None:
                continue
            (x0, z0), (x1, z1) = seg
            dx, dz = x1 - x0, z1 - z0
            n = math.hypot(dx, dz)
            if n < 1e-6:
                continue
            nx, nz = -dz / n * COAST_WIDTH / 2, dx / n * COAST_WIDTH / 2
            quad = [(x0 + nx, z0 + nz), (x1 + nx, z1 + nz), (x1 - nx, z1 - nz), (x0 - nx, z0 - nz)]
            area = (quad[1][0] - quad[0][0]) * (quad[2][1] - quad[0][1]) - (quad[1][1] - quad[0][1]) * (quad[2][0] - quad[0][0])
            m.face([(x, 0.0, z) for x, z in (quad if area > 0 else [quad[0], quad[3], quad[2], quad[1]])], "p_water")
    for k in range(3):                                                     # ripples off the mouth
        x0, z0 = pts[0][0] - 0.14 + 0.03 * k, pts[0][1] - 0.07 - 0.04 * k
        for i in range(4):
            _quad(m, x0 + 0.05 * i, z0 + (0.008 if i % 2 else 0.0) - 0.003, x0 + 0.05 * i + 0.045, z0 + (0.008 if i % 2 else 0.0) + 0.003, "p_water")
    doc = json.loads(CENTRELINE.read_text())
    hx, hz = map_xy(doc["station_HD"]["lon"], doc["station_HD"]["lat"])      # the tower: this harbour
    hx += STATION_DX                                                          # on the east bank: on the ribbon it would z-fight with the water
    _quad(m, hx - 0.02, hz, hx + 0.02, hz + 0.07, "p_stone")
    _tri(m, (hx - 0.03, hz + 0.07), (hx + 0.03, hz + 0.07), (hx, hz + 0.115), "p_gold")
    bx, bz = map_xy(doc["station_BB"]["lon"], doc["station_BB"]["lat"])      # Bangkok Bar: a tide staff
    bx += STATION_DX
    _quad(m, bx - 0.004, bz - 0.04, bx + 0.004, bz + 0.04, "p_ink")
    for dz in (-0.02, 0.01):
        _quad(m, bx - 0.02, bz + dz - 0.003, bx + 0.02, bz + dz + 0.003, "p_ink")
    return m


def on_ring(x: float, z: float, slot: int):
    """A point (x, z) of the front digit's plane, carried to digit slot `slot` of a drum whose axis is the mesh's origin:
    the front is y = -R_DRUM, and slot k is the front turned back by k * 36 degrees about the x axis."""
    a = -math.tau * slot * pn.SLOT_REV
    y0 = -pn.R_DRUM
    return (x, y0 * math.cos(a) - z * math.sin(a), y0 * math.sin(a) + z * math.cos(a))


def drum_mesh(row: int, name: str) -> Mesh:
    """One drum: a ring of ten digit slots about the mesh's origin (its axis). Turning the drum about the camera's right
    axis by k slots brings slot k to the front, facing the camera (panel.panel_poses). A small tick marks each slot, which
    also gives the mesh its p_text material; the digits themselves are glyphs of the Thai font, so Blender adds them."""
    m = Mesh(f"panel_drum_{row}_{name}")
    for k in range(10):
        pts = [on_ring(x, z, k) for x, z in ((-pn.WIN_W / 2, -0.003), (-pn.WIN_W / 2 + 0.012, -0.003),
                                              (-pn.WIN_W / 2 + 0.012, 0.003), (-pn.WIN_W / 2, 0.003))]
        m.face(pts, "p_text")
    return m


DRUM_NAMES = [f"panel_drum_{row}_{name}" for row in (0, 1) for name in pn.DRUMS]


def panel_meshes() -> Dict[str, Mesh]:
    """Every panel actor's mesh that Python draws, in the order the level places them (the same order panel.panel_poses
    poses them). The digits, the unit label and the map's place names are glyphs Blender adds to these."""
    out = {m.name: m for m in (paper_mesh(), map_mesh(), column_body_mesh(), column_fill_mesh(), column_pointer_mesh(),
                               band_back_mesh())}
    for row in (0, 1):
        for name in pn.DRUMS:
            out[f"panel_drum_{row}_{name}"] = drum_mesh(row, name)
    for m in (band_mask_mesh(), arrow_up_mesh(), arrow_dn_mesh()):
        out[m.name] = m
    return out
