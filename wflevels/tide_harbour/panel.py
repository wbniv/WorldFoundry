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
from typing import NamedTuple, Tuple

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


def camera_frame(day: int, sod: float, options=None) -> Frame:
    """The camera's position and axes at the given time: timeline.scene's cs_wide looking at its LookAt, no roll."""
    sc = tl.scene(day, sod, options)
    c, look = sc.poses["cs_wide"], sc.poses["LookAt"]
    pos = (c.x, c.y, c.z)
    f = _norm((look.x - c.x, look.y - c.y, look.z - c.z))
    r = _norm(_cross(f, (0.0, 0.0, 1.0)))
    u = _cross(r, f)
    return Frame(pos, r, f, u)


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
