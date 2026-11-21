#!/usr/bin/env python3
"""Tide Harbour: the river panel, pinned to the screen.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (the river panel, Will 2026-11-21: a full-height side panel with
no border; it swaps sides, pans its map and dims at night). The engine cannot attach an actor to the camera (TODO:
"Engine: actors fixed to the screen"), so every part of the panel is re-posed from the camera every frame. This
module is that maths, in pure Python, so a test can project the poses back through the engine's camera and check
the panel lands where the mockup puts it. The director's zForth (forth.py) follows it one formula for one.

Measured 2026-11-21 on the desktop engine at 1280 x 720 (the dial of the tower, a known point, lands where a 60
degree vertical field of view puts it and not where the camera shot's FOV of 50 does; see the TODO item): the
picture is drawn with a vertical field of view of 60 degrees and the window's aspect (gfx/authored_view.hp).

Frame: the camera's right, forward and up vectors. A panel part is placed by (u, v, depth): u to the right and v up in
metres at the panel's depth, depth along the forward axis. The part's mesh is built facing -y (as the dial is):
its local x is the camera's right, its local y the camera's forward, its local z the camera's up, so it faces back
at the camera and is never skewed.
"""
from __future__ import annotations

import math
from typing import Dict, NamedTuple, Tuple

import timeline as tl

V3 = Tuple[float, float, float]

VFOV_DEG = 60.0                    # the engine's vertical field of view (authored_view.hp kVerticalFovDegrees)
ASPECT = 16.0 / 9.0                # the screen the panel is drawn for: a 16:9 television (the Chromecast's)
PANEL_FRAC = 0.27                  # the panel's share of the screen's width (Will, 2026-11-21)
DEPTH = 2.0                        # metres in front of the camera: past the hither plane (1.0), in front of every scene part
LAYER = 0.01                       # metres between layers of the panel, nearest the camera last

# the half extents of the view at DEPTH
TAN_V = math.tan(math.radians(VFOV_DEG / 2.0))
HALF_H = DEPTH * TAN_V
HALF_W = HALF_H * ASPECT
PANEL_W = 2.0 * HALF_W * PANEL_FRAC
PANEL_H = 2.0 * HALF_H


class Frame(NamedTuple):
    pos: V3
    right: V3
    forward: V3
    up: V3


def _norm(v: V3) -> V3:
    n = math.sqrt(sum(x * x for x in v))
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: V3, b: V3) -> V3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def frame_from(cam, look) -> Frame:
    """The camera's position and axes for a camera pose looking at a look-at pose, no roll."""
    pos = (cam.x, cam.y, cam.z)
    f = _norm((look.x - cam.x, look.y - cam.y, look.z - cam.z))
    r = _norm(_cross(f, (0.0, 0.0, 1.0)))
    u = _cross(r, f)
    return Frame(pos, r, f, u)


def camera_frame(day: int, sod: float, options=None) -> Frame:
    """The camera's position and axes at the given time: timeline.scene's cs_wide looking at its LookAt, no roll."""
    sc = tl.scene(day, sod, options)
    return frame_from(sc.poses["cs_wide"], sc.poses["LookAt"])


def place(fr: Frame, u: float, v: float, depth: float = DEPTH) -> V3:
    """The world position of the point u to the right, v up and depth along the forward axis from the camera."""
    return tuple(fr.pos[i] + depth * fr.forward[i] + u * fr.right[i] + v * fr.up[i] for i in range(3))


def euler_of(fr: Frame) -> Tuple[float, float, float]:
    """The engine's Euler angles (a, b, c), in revolutions, that turn a part built facing -y to face the camera:
    the engine's matrix (math/matrix34.cc ConstructEuler) has the images of local x, y, z as its rows, and they must be
    right, forward, up. b is zero because the camera does not roll; a is the pitch, c the heading."""
    r, f, _u = fr.right, fr.forward, fr.up
    assert abs(r[2]) < 1e-9, "the camera rolls: the panel's rotation would need b"
    a = math.asin(f[2])
    c = math.atan2(r[1], r[0])
    return a / math.tau, 0.0, c / math.tau


def engine_matrix(a: float, b: float, c: float):
    """Matrix34::ConstructEuler for angles in revolutions: rows are the images of local x, y, z."""
    A, B, C = (math.tau * x for x in (a, b, c))
    sa, sb, sc_ = math.sin(A), math.sin(B), math.sin(C)
    ca, cb, cc = math.cos(A), math.cos(B), math.cos(C)
    return [[cb * cc, cb * sc_, -sb],
            [sb * sa * cc - ca * sc_, sb * sa * sc_ + ca * cc, cb * sa],
            [sb * ca * cc + sa * sc_, sb * ca * sc_ - sa * cc, cb * ca]]


def project(fr: Frame, p: V3, width: int = 1280, height: int = 720) -> Tuple[float, float]:
    """Where a world point lands on a screen of the given size, as the engine's projection puts it (pixels, y down)."""
    d = tuple(p[i] - fr.pos[i] for i in range(3))
    depth = sum(d[i] * fr.forward[i] for i in range(3))
    x = sum(d[i] * fr.right[i] for i in range(3))
    y = sum(d[i] * fr.up[i] for i in range(3))
    focal = (height / 2.0) / TAN_V
    return width / 2.0 + focal * x / depth, height / 2.0 - focal * y / depth


def panel_u_range(side: int) -> Tuple[float, float]:
    """The panel's left and right edges in u at DEPTH. side 0: the right edge of the screen; 1: the left."""
    return (-HALF_W, -HALF_W + PANEL_W) if side else (HALF_W - PANEL_W, HALF_W)


# ---------------------------------------------------------------------------------------------
# The three burn-in measures (Will, 2026-11-21: "swap sides, pan the map, dim at night") and the layout.
SWAP_S = 600.0                     # the panel changes side on every ten-minute mark of the clock
SLIDE_S = 2.6                      # and takes this long to leave one side and arrive at the other
SCALE_AT_PANEL = 0.74              # the harbour is drawn at this scale beside the panel (the camera pulls back to 1/0.74): the whole
                                   # picture, houses to tower, must fit the 73 % of the screen the panel leaves (captured 2026-11-21: 0.82 clipped the pier)
PAN_S = 900.0                      # the map's view goes once along its range in this many seconds, and back
PAN_KM = 11.0                      # the range, in kilometres of latitude
DIM = 1.0 / 6.0                    # the panel's brightness at night, against day

W, H = PANEL_W, PANEL_H            # the panel, in metres at DEPTH: 1.109 x 2.309
BAND_H = 0.62                      # the wood band at the top: two rows of readings
ROW_H = BAND_H / 2.0
WIN_W, WIN_H = 0.095, 0.20         # a digit's window
PITCH = 0.26                       # the drum's spacing between digits: more than a window, so neighbours stay hidden
GLYPH_H = 0.17                     # a digit's height on the drum
SLOT_REV = 0.1                     # a drum carries ten digits round its axis: 36 degrees apart
R_DRUM = PITCH / (2.0 * math.sin(math.pi * SLOT_REV))   # ten digits PITCH apart on a ring: its radius (0.42 m)
M_PER_KM = 0.066                   # the map's scale: the river and Bangkok Bar, 12.1 km across, fit between the margin and the column
COL_X = W / 2 - 0.095              # the level column, right of the map, in panel coordinates
COL_V0, COL_V1, COL_MAX_M = -0.80, 0.40, 3.5    # its foot and head in v, and the tide at its head
SCALE_KM = 2.0                     # the scale bar, under the column where no map reaches (the map ends 0.09 m left of it)
SCALE_X1, SCALE_V = W / 2.0 - 0.015, -H / 2.0 + 0.07       # its right end and its height

# depths from the camera: nearer is smaller. Back to front: paper, map, the column and its water and pointer, the band's
# plate, the drums, the band's mask and its marks, the arrows
# plate, the mask and its marks, the arrows, and in front of all of them the front digit of each drum. The drums are
# cylinders (below): their other digits turn away behind the plate, which hides them, so nothing needs clipping.
LAYER_OFFSET = {"digit": 0.0, "arrow": 0.006, "mask": 0.010, "plate": 0.014, "pointer": 0.016, "fill": 0.018, "column": 0.020,
                "map": 0.022, "paper": 0.024}
D = {name: DEPTH + off for name, off in LAYER_OFFSET.items()}
PTR_DU = 0.036                     # the pointer's tip sits this far right of the column's centre
PTEXT_DIM = 0.5                    # the readings dim to this at night, so they stay legible
# the map's centre of view, and the river's middle: latitude of the map's origin (the map is built about it)
MAP_LAT0, MAP_LON0 = 13.6745, 100.5591    # chosen so the river fills the window over the whole pan (test_tide_harbour_panel_parts)


def smooth(x: float) -> float:
    x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    return x * x * (3.0 - 2.0 * x)


def slide(sod: float) -> Tuple[bool, float]:
    """(the panel is at the left, how much of it is on screen 0..1) at second of day sod. It sits on one side for
    ten minutes, then slides off that edge, and in at the other: visible = |1 - 2 e| with e the eased position."""
    k = math.floor(sod / SWAP_S)
    want = k % 2
    since = sod - k * SWAP_S
    pos = float(want) if since >= SLIDE_S else (1 - want) + (2 * want - 1) * (since / SLIDE_S)
    e = smooth(pos)
    return e >= 0.5, abs(1.0 - 2.0 * e)


def harbour_scale(vis: float) -> float:
    """The harbour's scale on the screen: 0.82 with the panel in, 1 with it out."""
    return 1.0 - (1.0 - SCALE_AT_PANEL) * vis


def panel_centre_u(left: bool, vis: float) -> float:
    """The panel centre's u at DEPTH: its near edge is at the screen's edge when vis is 1, outside it when 0."""
    return (-HALF_W + vis * W - W / 2.0) if left else (HALF_W - vis * W + W / 2.0)


def camera_shift_m(left: bool, vis: float, dist: float) -> float:
    """How far the camera and its look-at move along x so that the harbour is centred in what the panel leaves:
    the harbour moves away from the panel by half its visible width."""
    view_w = 2.0 * dist * TAN_V * ASPECT
    return (-1.0 if left else 1.0) * (PANEL_FRAC * vis / 2.0) * view_w


def pan_dlat_km(sod: float) -> float:
    """The map view's offset from the middle, in kilometres of latitude: a slow back and forth, -PAN_KM/2 to +PAN_KM/2."""
    u = (sod % (2.0 * PAN_S)) / PAN_S
    tri = u if u < 1.0 else 2.0 - u
    return PAN_KM * ((1.0 - math.cos(math.pi * tri)) / 2.0 - 0.5)


def dim(lit: float) -> float:
    """The panel's brightness: 1 by day, DIM at night. lit is the director's night amount (timeline's lit ramp, 0 to 1)."""
    return 1.0 - (1.0 - DIM) * lit


# the readings band: widths along a row, left to right (metres), and the drum each digit belongs to
ROW = (("margin", 0.04), ("icon", 0.10), ("gap", 0.02), ("h10", WIN_W), ("h1", WIN_W), ("colon", 0.04), ("m10", WIN_W),
       ("m1", WIN_W), ("gap", 0.03), ("t1", WIN_W), ("dot", 0.035), ("t01", WIN_W), ("gap", 0.02), ("unit", 0.10),
       ("arrow", 0.09))
assert sum(w for _n, w in ROW) < W, "the readings row must fit the panel"
DRUMS = ("h10", "h1", "m10", "t1", "t01")          # the minute units digit is always 0 (times are shown to ten minutes)


def row_u(name: str) -> float:
    """The centre of a named cell of a readings row, in panel coordinates (u from the panel's centre)."""
    u = -W / 2.0
    for n, w in ROW:
        if n == name:
            return u + w / 2.0
        u += w
    raise KeyError(name)


def row_v(row: int) -> float:
    """The centre of readings row 0 (the next high water) or 1 (the next low), in panel coordinates."""
    return H / 2.0 - ROW_H * (row + 0.5)


def digits(seconds_ahead: float, rsec: float, metres: float) -> Tuple[int, int, int, int, int]:
    """The five drum values of one row: hour tens and units, minute tens (time to the nearest ten minutes), and the
    height's units and tenths (to 0.1 m, never below zero). seconds_ahead counts from the scan's start second rsec."""
    t = rsec + seconds_ahead
    slot = int(math.floor(t / 600.0 + 0.5)) % 144          # ten-minute slots in a day
    tenths = max(0, int(math.floor(metres * 10.0 + 0.5)))
    hour = slot // 6
    return hour // 10, hour % 10, slot % 6, tenths // 10, tenths % 10


def level_v(metres: float) -> float:
    """The v of the water level on the column, in panel coordinates."""
    m = 0.0 if metres < 0.0 else COL_MAX_M if metres > COL_MAX_M else metres
    return COL_V0 + (COL_V1 - COL_V0) * m / COL_MAX_M


def map_v(sod: float) -> float:
    """Where the map actor sits in v, in panel coordinates. The map is built about the point at latitude MAP_LAT0 with
    north up; the window is the panel below the band, whose centre is at -BAND_H/2. To show the latitude the pan has
    reached in the window's centre, the map's origin sits below it by that many kilometres at the map's scale."""
    return -BAND_H / 2.0 - pan_dlat_km(sod) * M_PER_KM


def panel_poses(fr: Frame, sod: float, left: bool, vis: float, reading, tide: float) -> Dict[str, "tl.Pose"]:
    """The pose of every panel actor, from the camera's frame: the part's mesh origin is placed at its (u, v) in panel
    coordinates at its layer's depth, scaled by depth / DEPTH so that it lands on the screen where the panel's plane would
    put it, and turned to face the camera. reading is turns.panel_reading's; tide the water level (m) now."""
    a, b, c = euler_of(fr)
    cu = panel_centre_u(left, vis)
    out: Dict[str, tl.Pose] = {}

    def put(name: str, layer: str, u: float, v: float, sz: float = 1.0) -> None:
        d = D[layer]
        s = d / DEPTH
        x, y, z = place(fr, s * (cu + u), s * v, d)
        out[name] = tl.Pose(x, y, z, a, b, c, s, s, s * sz)

    put("panel_paper", "paper", 0.0, 0.0)
    put("panel_map", "map", 0.0, map_v(sod))
    put("panel_col_body", "column", 0.0, 0.0)
    put("panel_col_fill", "fill", COL_X, COL_V0, max(0.01, min(1.0, tide / COL_MAX_M)))
    put("panel_col_ptr", "pointer", COL_X + PTR_DU, level_v(tide))
    put("panel_band_back", "plate", 0.0, 0.0)
    for row, turn in ((0, reading.high), (1, reading.low)):
        values = dict(zip(DRUMS, digits(turn.t, reading.mark, turn.h)))
        for name in DRUMS:
            # a drum's origin is its axis, R_DRUM behind its front digit, which is turned to face the camera by
            # turning the drum about the camera's right axis: that is a larger pitch (a), SLOT_REV for each digit
            x, y, z = place(fr, cu + row_u(name), row_v(row), DEPTH + R_DRUM)
            out[f"panel_drum_{row}_{name}"] = tl.Pose(x, y, z, a + values[name] * SLOT_REV, b, c)
    put("panel_band_mask", "mask", 0.0, 0.0)
    put("panel_arrow_up", "arrow", row_u("arrow"), H / 2.0 - ROW_H)
    put("panel_arrow_dn", "arrow", row_u("arrow"), H / 2.0 - ROW_H)
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--at", metavar="YYYY-MM-DDTHH:MM:SS", default="2026-11-21T12:00:00")
    args = ap.parse_args()
    day, sod = tl.parse_when(args.at)
    fr = camera_frame(day, sod)
    print("camera", [round(x, 3) for x in fr.pos], "forward", [round(x, 4) for x in fr.forward])
    print("euler (revolutions)", [round(x, 5) for x in euler_of(fr)])
    print(f"panel {PANEL_W:.3f} x {PANEL_H:.3f} m at {DEPTH} m")
    for side in (0, 1):
        lo, hi = panel_u_range(side)
        print("side", side, "edges at pixels", [round(project(fr, place(fr, u, 0.0))[0]) for u in (lo, hi)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
