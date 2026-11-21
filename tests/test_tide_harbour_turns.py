"""The next high and low water (wflevels/tide_harbour/turns.py), for the river panel.

The search samples the fitted tide every 10 minutes, so it must agree with a dense one-minute search of the same
curve, and with the Navy's table to about the fit's own accuracy. The numbers asserted here were measured when the
module was written (plan docs/plans/2026-11-21-tide-harbour-clock.md, the river panel).
"""
import datetime as dt
import os
import random
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour" / "tide_fit"))
import timeline as tl  # noqa: E402
import turns as tn  # noqa: E402

CACHE = Path(os.environ.get("CHAO_PHRAYA_TIDE_CACHE", Path.home() / "tmp" / "chao-phraya-tide"))


def test_highs_and_lows_alternate_and_the_next_of_each_is_ahead():
    day = tl.wall_day(dt.date(2026, 11, 21))
    hi, lo = tn.next_high_low(day, 16.5 * 3600)
    assert hi.high and not lo.high and hi.t > 0 and lo.t > 0
    assert hi.h > lo.h
    ts = tn.next_turns(day, 16.5 * 3600)
    assert all(a.high != b.high for a, b in zip(ts, ts[1:])), "a high is followed by a low"


def test_the_sample_step_costs_no_accuracy_against_a_one_minute_search():
    random.seed(7)
    for _ in range(60):
        day = tl.wall_day(dt.date(2026, 1, 1)) + random.randrange(365)
        sod = random.uniform(0, 86400)
        hi, lo = tn.next_high_low(day, sod)
        dense = [t for t in tn.filtered(tn.raw_turns(day, sod, step_s=60.0)) if t.t > 0]
        for got, want in ((hi, next(t for t in dense if t.high)), (lo, next(t for t in dense if not t.high))):
            assert abs(got.t - want.t) < 120.0, (day, sod, got, want)       # within two minutes
            assert abs(got.h - want.h) < 0.005                               # within half a centimetre


def test_a_turn_less_than_4_cm_from_the_last_is_dropped():
    wiggle = [tn.Turn(True, 100.0, 2.00), tn.Turn(False, 700.0, 1.97), tn.Turn(True, 1300.0, 2.01), tn.Turn(False, 9000.0, 1.00)]
    kept = tn.filtered(wiggle)
    assert [(t.high, t.h) for t in kept] == [(True, 2.01), (False, 1.00)]


@pytest.mark.skipif(not (CACHE / "HD2026.pdf").exists(), reason="the Navy's table is not fetched (tide_fit/fetch_sources.sh)")
def test_the_search_finds_the_navy_tables_highs_and_lows():
    from parse_hd import parse
    events = parse(str(CACHE / "HD2026.pdf"), 2026)
    found = total = 0
    time_err, height_err = [], []
    for i, (when, height) in enumerate(events):
        around = [events[j][1] for j in (i - 1, i + 1) if 0 <= j < len(events)]
        if all(height > x for x in around):
            high = True
        elif all(height < x for x in around):
            high = False
        else:
            continue
        total += 1
        day, sod = tl.wall_day(when.date()), when.hour * 3600 + when.minute * 60 - 3 * 3600
        if sod < 0:
            day, sod = day - 1, sod + 86400
        ours = [t for t in tn.next_turns(day, sod, 12.0) if t.high == high]
        if not ours:
            continue
        near = min(ours, key=lambda t: abs(t.t - 3 * 3600))
        if abs(near.t - 3 * 3600) <= 3 * 3600:
            found += 1
            time_err.append(abs(near.t - 3 * 3600) / 60)
            height_err.append(abs(near.h - height) * 100)
    assert total > 1200
    assert found / total > 0.97, (found, total)                              # measured 98.3 %
    assert statistics.median(time_err) < 12                                  # measured 8 minutes
    assert statistics.median(height_err) < 7                                 # measured 4.9 cm: the fit's own accuracy


def test_the_panel_reading_is_a_function_of_the_time_and_moves_on_when_a_turn_passes():
    day = tl.wall_day(dt.date(2026, 11, 21))
    a = tn.panel_reading(day, 16.5 * 3600 + 11)
    assert a.mark == 16.5 * 3600 and a.now == 11
    b = tn.panel_reading(day, 16.5 * 3600 + 500)              # the same ten-minute mark: the same scan, the same turns
    assert (b.mark, b.high, b.low, b.rise) == (a.mark, a.high, a.low, a.rise)
    # just after the next low water the reading's low is a later one, with no new scan needed within the mark
    lo = a.low
    t_after = a.mark + lo.t + 30.0
    c = tn.panel_reading(day, t_after)
    assert c.low.t > lo.t + 3 * 3600                          # a low is about 12 hours apart, never within three hours
    assert c.mark == (t_after // 600) * 600
    for sod in (0.0, 86399.0, 12 * 3600.0):                    # the ends of the day: the horizon reaches into the next day
        r = tn.panel_reading(day, sod)
        assert r.high.t > r.now and r.low.t > r.now
