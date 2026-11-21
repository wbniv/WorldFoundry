"""Tide Harbour's model (wflevels/tide_harbour/timeline.py): the tide, the sun, the clock, the look, the options.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md, Phase 2 and Verification 1. Pure Python, no engine.
"""
import datetime as dt
import math
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))
sys.path.insert(0, str(ROOT / "tests"))

import parts  # noqa: E402
import timeline as tl  # noqa: E402
from test_tide_constants import PUBLISHED  # noqa: E402  (events read by eye from the department's printed 2026 table)

TODAY = tl.wall_day(dt.date(2026, 11, 21))

# Sunrise and sunset for Bangkok, as published by timeanddate.com ("Sunrise and sunset times in Bangkok",
# https://www.timeanddate.com/sun/thailand/bangkok?month=M&year=2026, read 2026-11-21), local time.
PUBLISHED_SUN = {
    (2026, 1, 1): ("06:41", "18:01"),
    (2026, 3, 20): ("06:22", "18:28"),
    (2026, 6, 21): ("05:51", "18:47"),
    (2026, 9, 22): ("06:07", "18:14"),
    (2026, 11, 21): ("06:20", "17:47"),
}


def minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def test_wall_day_matches_the_engine():
    assert TODAY == 9821                      # E1's record: 2026-11-21 is WALL_DAY 9821
    assert tl.EPOCH_DAY == tl.wall_day(dt.date(2026, 1, 1))


def test_the_scene_is_a_pure_function_of_date_time_and_options():
    a = tl.scene(TODAY, 61234.5)
    tl.scene(TODAY + 3, 100.0, {"drift": 1})
    b = tl.scene(TODAY, 61234.5)
    assert a == b


def test_the_director_form_of_the_tide_sum_is_the_plain_sum():
    for k in range(200):
        day, sod = tl.EPOCH_DAY - 400 + 13 * k, (k * 7919.3) % 86400
        assert abs(tl.tide_split_m(day, sod) - tl.tide_m(day, sod)) < 1e-9


def test_the_tide_reproduces_the_departments_printed_table():
    errors = []
    for (y, m, d), hhmm, h in PUBLISHED:
        day = tl.wall_day(dt.date(y, m, d))
        errors.append(abs(tl.tide_m(day, int(hhmm[:2]) * 3600 + int(hhmm[2:]) * 60) - h))
    # the research document's validated error: about 5 cm median, about 22 cm at worst on an unseen year
    assert statistics.median(errors) < 0.08, errors
    assert max(errors) < 0.30, errors


def test_the_water_and_everything_afloat_ride_the_tide():
    for sod in (3600 * 3.0, 3600 * 11.5, 3600 * 20.25):
        sc = tl.scene(TODAY, sod)
        h = sc.tide
        assert sc.poses["gauge_pointer"].z == h
        mean = statistics.mean(sc.poses[f"bar_{k:02d}"].z for k in range(tl.N_BARS))
        assert abs(mean - h) < 0.30
        assert abs(sc.poses["raft"].z - h) < 0.05 and abs(sc.poses["boat_0"].z - h) < 0.1


def test_the_tide_is_evaluated_once_per_whole_second():
    assert tl.scene(TODAY, 4000.0).tide == tl.scene(TODAY, 4000.95).tide
    assert tl.scene(TODAY, 4000.0).tide != tl.scene(TODAY, 4001.0).tide


def test_sunrise_and_sunset_match_five_published_times():
    """D12: no tables; a formula, checked against five published times (rounded to the minute there)."""
    worst = 0.0
    for (y, m, d), (rise, sett) in PUBLISHED_SUN.items():
        r, s = tl.sunrise_sunset(tl.wall_day(dt.date(y, m, d)))
        worst = max(worst, abs(r - minutes(rise)), abs(s - minutes(sett)))
    assert worst < 2.5, worst


def test_the_sun_is_at_the_horizon_at_sunrise_and_sunset():
    r, s = tl.sunrise_sunset(TODAY)
    for minute in (r, s):
        alt = tl.sun(TODAY, minute * 60.0).alt_deg
        assert abs(alt - (90.0 - tl.SUNRISE_ZENITH_DEG)) < 0.05, alt
    assert tl.sun(TODAY, 12 * 3600.0).alt_deg > 50.0 and tl.sun(TODAY, 0.0).alt_deg < -60.0


def test_the_sun_sets_in_the_west_behind_the_far_bank():
    """The camera looks west (+y); the November sun sets south of west, so to the left of the frame's centre."""
    r, s = tl.sunrise_sunset(TODAY)
    sun = tl.sun(TODAY, s * 60.0)
    assert sun.west > 0.9 and sun.north < 0.0
    pose = tl.scene(TODAY, s * 60.0 - 300).poses["sun"]
    assert pose.y == tl.SUN_Y and pose.x < 0.0
    assert tl.scene(TODAY, 9 * 3600.0).visible[tl.VIS["sun"]] == 0           # morning: the sun is behind the camera


def test_the_hands_read_the_time():
    sod = 10 * 3600 + 8 * 60 + 22.0
    p = tl.scene(TODAY, sod).poses
    assert p["hand_h"].b == pytest.approx((10 + 8 / 60 + 22 / 3600) / 12)
    assert p["hand_m"].b == pytest.approx((8 + 22 / 60) / 60)
    assert p["hand_s"].b == pytest.approx(22 / 60)
    assert tl.scene(TODAY, 15 * 3600.0).poses["hand_h"].b == pytest.approx(0.25)        # three o'clock: a quarter turn


WRAPPING = ("cloud_", "bird_", "boat_3")


def test_nothing_jumps_between_frames_except_off_screen_wraps():
    """Every fast motion's period divides the hour, and every slow one the day, so the scene runs on across
    the hour and midnight. Clouds, birds and the long-tail wrap round, but only far off the screen's edge."""
    for day, sod in ((TODAY, 3599.99), (TODAY, 86399.99), (TODAY, 45000.0)):
        a = tl.scene(day, sod).poses
        nxt = (day + 1, 0.0) if sod >= 86399 else (day, sod + 1 / 60)
        b = tl.scene(*nxt).poses
        for name in a:
            dx = max(abs(u - v) for u, v in zip(a[name][:3], b[name][:3]))
            if name.startswith(WRAPPING) and dx > 1.0:
                assert min(abs(a[name].x), abs(b[name].x)) > 60.0, (name, a[name], b[name])
                continue
            if name in ("sun", "moon"):
                continue
            assert dx < 0.6, (name, sod, a[name], b[name])


def test_every_actor_stays_inside_the_room():
    x0, y0, z0, x1, y1, z1 = tl.ROOM
    for k in range(0, 24 * 12):
        for day in (TODAY, tl.wall_day(dt.date(2026, 6, 21))):
            for name, p in tl.scene(day, k * 300.0 + 0.5).poses.items():
                assert x0 < p.x < x1 and y0 < p.y < y1 and z0 < p.z < z1, (name, k, p)


def test_by_day_the_look_is_the_authored_colours_so_nothing_is_re_coloured():
    """Above LOOK_TOP the director's colours equal the level's own, so the engine keeps every mesh baked by day."""
    sc = tl.scene(TODAY, 11 * 3600.0)
    assert sc.q == tl.LOOK_TOP
    for (name, slot), rgb in sc.colours.items():
        key = next(k for s, k in enumerate(parts.recolour_keys(name)) if s == slot)
        assert rgb == tuple(tl.byte(v) for v in parts.day_colour(key)), (name, slot)


def test_at_night_windows_and_lanterns_are_lit_and_the_rest_is_dark():
    sc = tl.scene(TODAY, 22 * 3600.0)
    assert sc.q == tl.LOOK_BOTTOM
    window = sc.colours[("houses", 2)]
    wall = sc.colours[("houses", 0)]
    assert min(window[:2]) > 180 and max(wall) < 110, (window, wall)
    assert sc.colours[("lantern_0", 0)][0] > 200
    assert max(sc.colours[("sky_5", 0)]) < 40
    assert sc.visible[tl.VIS["moon"]] == 1 and sc.visible[tl.VIS["birds"]] == 0


def test_the_options_change_only_what_they_name():
    sod = 15 * 3600 + 150.0                        # mid drift swing
    base = tl.scene(TODAY, sod)
    off = tl.scene(TODAY, sod, {"drift": 1})
    assert off.poses["cs_wide"] == tl.Pose(tl.LOOK_AT[0], tl.LOOK_AT[1] - tl.CAMERA_R, tl.CAMERA_Z)
    assert base.poses["cs_wide"] != off.poses["cs_wide"]
    assert {k: v for k, v in off.poses.items() if k != "cs_wide"} == {k: v for k, v in base.poses.items() if k != "cs_wide"}
    roman = tl.scene(TODAY, sod, {"numerals": 1}).visible
    none = tl.scene(TODAY, sod, {"numerals": 2}).visible
    assert (base.visible[705], base.visible[706]) == (1, 0) and (roman[705], roman[706]) == (0, 1) and (none[705], none[706]) == (0, 0)
    assert tl.scene(TODAY, sod, {"gauge": 1}).visible[tl.VIS["gauge"]] == 0 and base.visible[tl.VIS["gauge"]] == 1
    life = tl.scene(TODAY, sod, {"life": 1}).visible
    assert life[tl.VIS["boats"]] == 0 and life[tl.VIS["birds"]] == 0 and base.visible[tl.VIS["boats"]] == 1
    assert base.visible[tl.VIS["birds"]] == 1
