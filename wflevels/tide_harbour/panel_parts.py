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
RIVER_WIDTH = 0.018            # metres on the panel
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
    _quad(m, pn.COL_X - cw - 0.008, pn.COL_V0 - 0.008, pn.COL_X + cw + 0.008, pn.COL_V1 + 0.008, "p_ink")
    _quad(m, pn.COL_X - cw, pn.COL_V0, pn.COL_X + cw, pn.COL_V1, "p_stone")
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


def river_points() -> List[Tuple[float, float]]:
    """The river as panel metres about the map's origin (latitude MAP_LAT0, longitude MAP_LON0): x east, z north."""
    doc = json.loads(CENTRELINE.read_text())
    cosl = math.cos(math.radians(pn.MAP_LAT0))
    return [((lon - pn.MAP_LON0) * cosl * LAT_M * pn.M_PER_KM, (lat - pn.MAP_LAT0) * LAT_M * pn.M_PER_KM) for lon, lat in doc["points"]]


def map_xy(lon: float, lat: float) -> Tuple[float, float]:
    cosl = math.cos(math.radians(pn.MAP_LAT0))
    return (lon - pn.MAP_LON0) * cosl * LAT_M * pn.M_PER_KM, (lat - pn.MAP_LAT0) * LAT_M * pn.M_PER_KM


def map_mesh() -> Mesh:
    """The river as a ribbon of quads with a hexagon at each joint, the Navy's station as a small tower, the Bangkok Bar
    tide staff, and three ripples for the sea off the mouth. The place names are glyphs: Blender adds them."""
    m = Mesh("panel_map")
    pts = river_points()
    half = RIVER_WIDTH / 2
    for p, q in zip(pts, pts[1:]):
        dx, dz = q[0] - p[0], q[1] - p[1]
        n = math.hypot(dx, dz)
        if n == 0.0:
            continue
        nx, nz = -dz / n * half, dx / n * half
        a, b, c, d = (p[0] + nx, p[1] + nz), (q[0] + nx, q[1] + nz), (q[0] - nx, q[1] - nz), (p[0] - nx, p[1] - nz)
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        quad = [a, b, c, d] if area > 0 else [a, d, c, b]
        m.face([(x, 0.0, z) for x, z in quad], "p_water")
    for x, z in pts:
        m.disc_y(x, z, half, 0.0, "p_water", sides=6)
    for k in range(3):                                                     # ripples off the mouth
        x0, z0 = pts[0][0] - 0.14 + 0.03 * k, pts[0][1] - 0.07 - 0.04 * k
        for i in range(4):
            _quad(m, x0 + 0.05 * i, z0 + (0.008 if i % 2 else 0.0) - 0.003, x0 + 0.05 * i + 0.045, z0 + (0.008 if i % 2 else 0.0) + 0.003, "p_water")
    doc = json.loads(CENTRELINE.read_text())
    hx, hz = map_xy(doc["station_HD"]["lon"], doc["station_HD"]["lat"])      # the tower: this harbour
    _quad(m, hx - 0.02, hz, hx + 0.02, hz + 0.07, "p_stone")
    _tri(m, (hx - 0.03, hz + 0.07), (hx + 0.03, hz + 0.07), (hx, hz + 0.115), "p_gold")
    bx, bz = map_xy(doc["station_BB"]["lon"], doc["station_BB"]["lat"])      # Bangkok Bar: a tide staff
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
