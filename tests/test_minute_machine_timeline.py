"""Minute Machine timeline: pure-logic tests, no engine.

Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md, Verification 2.
"""
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "minute_machine"))

import timeline as tl  # noqa: E402

HMS = lambda h, m, s=0.0: h * 3600 + m * 60 + s
EPS = 1e-9


def close(p, q, tol=1e-6, screw=False):
    if screw:       # a screw turns whole revolutions: equal modulo 1
        p, q = p._replace(c=p.c % 1.0), q._replace(c=q.c % 1.0)
        if abs(p.c - q.c) > 0.5:
            p, q = p._replace(c=0.0), q._replace(c=0.0)
    return all(abs(a - b) <= tol for a, b in zip(p, q))


def test_every_row_of_the_plan_table_has_pieces():
    names = set(tl.piece_names())
    plan = (ROOT / "docs/plans/2026-11-21-sixty-second-chain-reaction.md").read_text(encoding="utf-8")
    table = plan.split("## Every pose is a function of the clock", 1)[1].split("Four things follow", 1)[0]
    rows = [r for r in table.splitlines() if r.startswith("| ") and "---" not in r and "Piece" not in r]
    assert len(rows) == 10, rows                       # the ten rows of the plan's pose table
    for key, pieces in tl.PIECE_ROWS.items():
        assert pieces and all(p in names for p in pieces), key
    covered = {p for ps in tl.PIECE_ROWS.values() for p in ps}
    assert covered == names, sorted(names ^ covered)


def test_loop_closure_ordinary_minute_and_hour_and_midnight():
    for h, mi in [(10, 8), (12, 59), (23, 59), (0, 0), (3, 29)]:
        end = tl.all_poses(HMS(h, mi, 60.0 - 1e-9))
        nxt_sod = HMS(h, mi + 1) if mi < 59 else HMS(h + 1, 0)
        start = tl.all_poses(nxt_sod % 86400)
        for name in start:
            assert close(end[name], start[name], screw=name.endswith('_screw')), (h, mi, name, end[name], start[name])


def test_a_machine_with_no_display_change_repeats_itself():
    """Pieces other than the display, bell and camera are identical in every minute."""
    a = tl.all_poses(HMS(10, 8, 33.3))
    b = tl.all_poses(HMS(14, 52, 33.3))
    for name in a:
        if name.startswith(("card_", "camera", "bell", "hammer")):
            continue
        assert close(a[name], b[name], screw=name.endswith('_screw')), name


def test_no_pose_jumps_within_a_minute():
    """2 ms steps: a teleport shows as a jump far larger than any real motion."""
    for h, mi in [(10, 8), (12, 59), (23, 59), (13, 0)]:
        prev = tl.all_poses(HMS(h, mi))
        worst = {}
        t = 0.002
        while t < 60.0:
            cur = tl.all_poses(HMS(h, mi, t))
            for name, p in cur.items():
                q = prev[name]
                pos = max(abs(p.x - q.x), abs(p.y - q.y), abs(p.z - q.z))
                ang = max(abs(p.a - q.a), abs(p.b - q.b), abs(p.c - q.c))
                scl = max(abs(p.sx - q.sx), abs(p.sy - q.sy), abs(p.sz - q.sz))
                w = worst.get(name, (0, 0, 0))
                worst[name] = (max(w[0], pos), max(w[1], ang), max(w[2], scl))
            prev = cur
            t += 0.002
        for name, (pos, ang, scl) in worst.items():
            assert pos < 0.02, (h, mi, name, "position", pos)      # < 10 m/s
            assert ang < 0.02 or name.endswith("_screw"), (h, mi, name, "angle", ang)
            assert scl < 0.01 + 1e-9, (h, mi, name, "scale", scl)


def test_contacts_start_the_next_act():
    # the falling flap lifts the gate at 0 s, and the marble sets off from the gate
    assert tl.gate_lift(0.0) == 0.0 and tl.gate_lift(0.3) > 0.99
    x0, _ = tl.marble_px(0.0)
    assert abs(x0 - tl.GATE_X) < 1e-9
    # the marble touches domino 1 at 12 s
    mx, _ = tl.marble_px(12.0)
    assert abs((mx + tl.MR) - tl.DOMINO_X0) < 1e-9
    assert tl.domino_deg(0, 11.999) == 0.0 and tl.domino_deg(0, 12.5) > 0.0
    # dominoes fall three a second; each starts when the one before has a third of a second to go
    for i in range(1, tl.DOMINO_COUNT):
        assert abs((tl.domino_start(i) - tl.domino_start(i - 1)) - 1 / 3) < 1e-9
    # the last domino lands on the seesaw at 20 s, and the seesaw then tips
    assert abs(tl.domino_end(tl.DOMINO_COUNT - 1) - 20.0) < 1e-9
    assert tl.seesaw_u(20.0) == 0.0 and tl.seesaw_u(20.9) > 0.99
    # the hopper gate is fully open at 22 s, when the sand starts to run
    assert tl.gate_open(21.0) == 0.0 and tl.gate_open(22.0) > 0.999
    assert tl.bucket_fill(22.0) == 0.0 and tl.bucket_fill(37.0) > 0.45
    # the hopper is empty and the bucket full at 52 s, then everything holds to 55 s
    assert tl.hopper_fill(52.0) < 1e-9 and tl.bucket_fill(52.0) > 0.999
    assert tl.pin_travel_px(54.9) == 0.0
    # five teeth, one a second, the fifth finishing at 59.15 s
    for k in range(5):
        before, after = tl.pin_travel_px(55.0 + k - 1e-6), tl.pin_travel_px(55.0 + k + tl.TOOTH_TIME + 1e-6)
        assert abs((after - before) - tl.TOOTH_TRAVEL_PX) < 1e-3, k
    assert tl.pin_travel_px(59.2) == tl.TEETH * tl.TOOTH_TRAVEL_PX
    # the comb finishes standing the dominoes just before the seesaw and gate swing back
    last_up = tl.TL["comb"][0] + tl.comb_step() * (tl.DOMINO_COUNT - 1) + tl.COMB_REARM_EASE
    assert abs(last_up - tl.TL["comb"][1]) < 1e-9 and last_up <= 52.1 + 1e-9
    assert tl.domino_deg(tl.DOMINO_COUNT - 1, 52.1) == 0.0


def test_each_piece_ends_the_minute_where_it_starts():
    a, b = tl.all_poses(HMS(10, 8, 0.0)), tl.all_poses(HMS(10, 8, 60.0 - 1e-9))
    for name in ("marble", "seesaw", "hopper_sand", "bucket", "bucket_sand", "spring", "pin", "trough_sand"):
        assert close(a[name], b[name]), name


def flips_at(sod_start, sod_end, k, step=0.002):
    """Seconds, relative to sod_start, at which drum k's position crosses its flip."""
    t0 = sod_start
    seen = {"start": None, "end": None}
    prev = tl.drum_pos(k, t0)
    t = t0
    while t < sod_end:
        t += step
        p = tl.drum_pos(k, t)
        if seen["start"] is None and abs(p - prev) > 1e-12:
            seen["start"] = t - sod_start
        prev = p
    return seen["start"]


def test_hour_cascade_flips_right_to_left_120_ms_apart():
    base = HMS(13, 0)
    # 12:59 -> 13:00: minutes 9 -> 0, tens of minutes 5 -> 0, hours 2 -> 3; the tens of hours stays 1
    starts = [flips_at(base, base + 2.0, k) for k in (3, 2, 1)]          # minutes ones first
    assert all(s is not None for s in starts), starts
    assert flips_at(base, base + 2.0, 0) is None
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(abs(g - tl.CASCADE) < 0.004 for g in gaps), gaps
    assert abs(starts[0] - 0.0) < 0.004
    # each flip takes 0.4 s: every drum is settled by then
    for k in range(4):
        assert abs(tl.drum_pos(k, base + 3 * tl.CASCADE + 0.5) - tl.digits_at(base)[k]) < 1e-9


def test_midnight_hours_drum_flutters_through_seven_cards():
    base = HMS(0, 0)
    assert tl.digits_at(base - 60) == (2, 3, 5, 9) and tl.digits_at(base) == (0, 0, 0, 0)
    steps = (0 - 3) % 10
    assert steps == 7
    start = tl.drum_pos(1, base)
    assert abs(start - 3.0) < 1e-9
    mid = tl.drum_pos(1, base + 2 * tl.CASCADE + 0.5)        # part-way through the flutter
    assert 3.0 < mid < 10.0
    end = tl.drum_pos(1, base + 2 * tl.CASCADE + 6 * tl.FLIP_STEP + tl.FLIP + 0.01)
    assert abs(end - 0.0) < 1e-9 or abs(end - 10.0) < 1e-9
    # tens of hours goes 2 -> 0 in one flip (a three-card drum)
    assert abs(tl.drum_pos(0, base + 3 * tl.CASCADE + 0.45) - 0.0) < 1e-9


def test_a_card_stands_upright_in_front_and_the_one_before_hangs():
    sod = HMS(10, 8, 30.0)
    for k in range(4):
        digit = tl.digits_at(sod)[k]
        n = tl.DRUM_SIZES[k]
        assert tl.card_angle_deg(k, digit, sod) == 0.0
        assert tl.card_angle_deg(k, (digit - 1) % n, sod) == 180.0


def test_bell_strikes_only_on_the_hour():
    on = [tl.all_poses(HMS(13, 0, s))["bell"].b for s in (1.0, 2.0, 3.5)]
    off = [tl.all_poses(HMS(13, 1, s))["bell"].b for s in (1.0, 2.0, 3.5)]
    assert any(abs(b) > 1e-4 for b in on) and all(b == 0.0 for b in off)
    assert tl.all_poses(HMS(13, 0, 30.0))["bell"].b == 0.0


def test_poses_depend_only_on_the_time():
    when = HMS(10, 8, 41.5)
    first = tl.all_poses(when)
    for other in (HMS(3, 3, 3.3), HMS(23, 59, 59.9), HMS(0, 0, 0.0), when):
        tl.all_poses(other)
    second = tl.all_poses(when)
    assert first == second
    assert all(all(math.isfinite(v) for v in p) for p in first.values())
    # at :47 the comb is half-way along the dominoes and the marble two thirds up the lift
    up = [i for i in range(tl.DOMINO_COUNT) if tl.domino_deg(i, 47.0) < 1e-9]
    assert abs(len(up) - tl.DOMINO_COUNT / 2) <= 1, up
    lo, hi = tl.TL["marble_lift"]
    assert abs((47.0 - lo) / (hi - lo) - 2 / 3) < 0.05
    assert 0.0 < tl.domino_deg(0, 41.3) < tl.DOMINO_LEAN_DEG


def test_camera_pushes_in_late_and_drifts_slowly():
    wide = tl.all_poses(HMS(10, 8, 30.0))["camera_proxy"]
    near = tl.all_poses(HMS(10, 8, 58.0))["camera_proxy"]
    assert abs(near.y) < abs(wide.y)
    assert abs(tl.push(30.0)) < 1e-12 and abs(tl.push(58.0) - 1.0) < 1e-12 and abs(tl.push(0.0) - 1.0) < 1e-12
    x0 = tl.all_poses(HMS(10, 0, 30.0))["camera_proxy"].x
    x1 = tl.all_poses(HMS(10, 5, 30.0))["camera_proxy"].x
    assert x0 != x1


def test_forth_constants_name_every_act():
    text = tl.forth_constants()
    for key in tl.TL:
        name = key.replace("_", "-")
        assert re.search(rf"^[\d.]+ constant mm-{name}-start$", text, re.M), key
        assert re.search(rf"^[\d.]+ constant mm-{name}-end$", text, re.M), key
    assert "24 constant mm-dominoes" in text
