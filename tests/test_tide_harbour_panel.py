"""The river panel's pinning to the screen (wflevels/tide_harbour/panel.py).

The engine cannot attach an actor to the camera, so the panel is re-posed from the camera every frame. These tests
project the poses back through the engine's camera (60 degree vertical field of view, measured 2026-11-21 against a
capture of the level: the tower's dial lands at pixel (948, 268) in a 1280 x 720 picture, which 60 degrees predicts
as (948, 270) and the camera shot's 50 degrees as (1021, 270)) and check the panel lands where the mockup puts it,
for every drift of the camera over a day.
"""
import datetime as dt
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import level_modules  # noqa: E402

pn, tl, _parts = level_modules.load("tide_harbour", "panel", "timeline", "parts")   # parts sets timeline.PARTS (the recolour table)

DAY = tl.wall_day(dt.date(2026, 11, 21))
TIMES = [k * 600.0 for k in range(144)]          # a day, ten minutes apart: the camera drifts through its whole swing


def test_the_engines_field_of_view_puts_the_dial_where_the_capture_shows_it():
    sod = 12 * 3600.0 + 0.5 * pn.SLIDE_S         # halfway through a swap the panel is off screen and the camera is at its usual place
    assert pn.slide(sod)[1] < 1e-6
    fr = pn.camera_frame(DAY, sod, {"drift": 1})
    x, y = pn.project(fr, tl.DIAL)
    assert abs(x - 948) < 3 and abs(y - 268) < 5, (x, y)     # the capture: about (948, 268)


def test_a_camera_facing_part_is_not_skewed():
    for sod in TIMES[::9]:
        fr = pn.camera_frame(DAY, sod)
        m = pn.engine_matrix(*pn.euler_of(fr))
        for row, want in zip(m, (fr.right, fr.forward, fr.up)):
            assert all(abs(row[i] - want[i]) < 1e-9 for i in range(3)), (sod, row, want)


def test_the_panel_fills_the_screen_edge_to_edge_on_both_sides():
    for sod in TIMES:
        fr = pn.camera_frame(DAY, sod)
        for side, (px0, px1) in ((0, (1280 * (1 - pn.PANEL_FRAC), 1280)), (1, (0, 1280 * pn.PANEL_FRAC))):
            lo, hi = pn.panel_u_range(side)
            for u, want_x in ((lo, px0), (hi, px1)):
                x, _ = pn.project(fr, pn.place(fr, u, 0.0))
                assert abs(x - want_x) < 0.01, (sod, side, x, want_x)
            _, top = pn.project(fr, pn.place(fr, lo, pn.HALF_H))
            _, bottom = pn.project(fr, pn.place(fr, lo, -pn.HALF_H))
            assert abs(top) < 0.01 and abs(bottom - 720) < 0.01, (sod, top, bottom)


def test_the_television_is_unchanged_and_every_other_screen_gets_its_own_edge():
    # plan docs/plans/2026-11-22-display-mailboxes.md: half_w() defaults are the 16:9 television, exactly today's HALF_W
    assert pn.half_w() == pn.HALF_W and pn.half_w(16.0 / 9.0, 60.0) == pn.HALF_W
    for aspect, w, h in ((1520 / 680, 1520, 680), (21 / 9, 2520, 1080), (4 / 3, 1440, 1080), (0.45, 450, 1000), (1.0, 900, 900)):
        hw = pn.half_w(aspect, 60.0)
        for sod in TIMES:
            fr = pn.camera_frame(DAY, sod)
            lo, hi = pn.panel_u_range(1, hw)          # the panel at the left: its near edge is the screen's left edge
            x, _ = pn.project(fr, pn.place(fr, lo, 0.0), w, h)
            assert abs(x) < 0.01, (aspect, sod, x)
            lo, hi = pn.panel_u_range(0, hw)          # at the right: its near edge is the screen's right edge
            x, _ = pn.project(fr, pn.place(fr, hi, 0.0), w, h)
            assert abs(x - w) < 0.01, (aspect, sod, x, w)


def test_a_part_keeps_its_place_on_the_screen_as_the_camera_drifts():
    spots = []
    for sod in TIMES:
        fr = pn.camera_frame(DAY, sod)
        spots.append(pn.project(fr, pn.place(fr, 0.3, -0.4)))
    assert max(abs(s[0] - spots[0][0]) for s in spots) < 0.01 and max(abs(s[1] - spots[0][1]) for s in spots) < 0.01


def test_the_panel_is_nearer_than_anything_in_the_scene_and_past_the_hither_plane():
    assert 1.0 < pn.DEPTH < 5.0
    nearest = min(math.dist(pn.camera_frame(DAY, s).pos, (x, y, 0.0)) for s in TIMES[::20] for x, y in ((-30.0, -13.0), (-1.0, -13.0)))
    assert pn.DEPTH + 5 * pn.LAYER < nearest
