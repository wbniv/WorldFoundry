#!/usr/bin/env python3
"""Tide Harbour: the next high water and the next low water, from the fitted tide.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (the river panel, Will 2026-11-21). The panel shows each
turn's time to ten minutes and its height to 0.1 m, so the search needs no more than that, and it must be
cheap enough for the director's zForth VM, which evaluates the 64-wave sum (timeline.tide_m) in one go.

The search steps through the tide at STEP_S seconds, finds each place the curve changes direction, places the
turn by a parabola through the three samples around it, and keeps it only if it is at least MIN_SWING_M from
the turn kept before it (the fitted curve wiggles at flat tops: tide_fit/count_turns.py). A wiggle is two turns
close together, so a streaming rule is enough: a turn of the same kind as the last kept one replaces it if more
extreme; a turn of the other kind is kept only if it is far enough from it.

    python3 turns.py --at 2026-11-21T16:30:00      the next turns after that Thai time
"""
from __future__ import annotations

import argparse
import math
import sys
from typing import List, NamedTuple, Tuple

import timeline as tl

STEP_S = 600.0               # sample spacing: a turn is placed to the second by the parabola, but never found closer than this
MIN_SWING_M = 0.04           # tide_fit/count_turns.py: 4 cm leaves within 3 of the table's highs and lows in both years
HORIZON_H = 30.0             # how far ahead to look: more than a full cycle of any two turns (the table's longest gap is 17.5 h)
N_SAMPLES = int(HORIZON_H * 3600.0 / STEP_S) + 2     # the director's scan runs to this many samples (forth.py scan_words)
KEPT_MAX = 8                 # turns the director keeps while scanning: a 30 hour horizon holds six at most


class Turn(NamedTuple):
    high: bool
    t: float                 # seconds from the start of the search
    h: float                 # metres above the datum


def _tide(day: int, sod: float) -> float:
    d, s = divmod(sod, 86400.0)
    return tl.tide_split_m(day + int(d), s)


def _parabola(y0: float, y1: float, y2: float) -> Tuple[float, float]:
    """The vertex of the parabola through samples at -1, 0, +1: (offset in steps, height)."""
    den = y0 - 2.0 * y1 + y2
    if den == 0.0:
        return 0.0, y1
    off = 0.5 * (y0 - y2) / den
    return off, y1 - 0.25 * (y0 - y2) * off


def raw_turns(day: int, sod: float, horizon_h: float = HORIZON_H, step_s: float = STEP_S) -> List[Turn]:
    """Every direction change within the horizon, as sampled (no filtering). t counts from (day, sod)."""
    n = int(horizon_h * 3600.0 / step_s) + 2
    y = [_tide(day, sod + k * step_s) for k in range(-1, n + 1)]         # y[k + 1] is the tide at sample k
    out: List[Turn] = []
    for k in range(1, n):
        a, b, c = y[k - 1], y[k], y[k + 1]
        if (b - a) * (c - b) < 0.0:
            off, h = _parabola(a, b, c)
            out.append(Turn(b > a, (k - 1 + off) * step_s, h))
    return out


def filtered(turns: List[Turn], min_swing: float = MIN_SWING_M) -> List[Turn]:
    """Streaming wiggle removal: see the module docstring."""
    kept: List[Turn] = []
    for t in turns:
        if not kept:
            kept.append(t)
        elif kept[-1].high == t.high:
            if (t.h > kept[-1].h) == t.high:
                kept[-1] = t
        elif abs(t.h - kept[-1].h) >= min_swing:
            kept.append(t)
        else:
            continue          # a wiggle: the turn is too close in height to the one before it
    return kept


MARK_S = 600.0               # the panel's scan starts on every ten-minute mark of the clock, so its reading is a function of the time


class Reading(NamedTuple):
    mark: float              # the scan's start, second of the day
    high: Turn               # the next high water: t counts from the mark
    low: Turn
    rise: bool               # the next turn is a high
    now: float               # seconds from the mark to the second asked about


def panel_reading(day: int, sod: float) -> Reading:
    """What the river panel shows at second of day sod (whole seconds, as the director's clock): the scan that started
    on the latest ten-minute mark, with the first high and first low water still ahead of sod. Times are from the mark."""
    s = math.floor(sod)
    mark = math.floor(s / MARK_S) * MARK_S
    ts = filtered(raw_turns(day, mark))
    now = s - mark
    ahead = [t for t in ts if t.t > now]
    return Reading(mark, next(t for t in ahead if t.high), next(t for t in ahead if not t.high), ahead[0].high, now)


def next_turns(day: int, sod: float, horizon_h: float = HORIZON_H) -> List[Turn]:
    """The turns still to come, nearest first, with the wiggles removed. The first is dropped if it is behind us."""
    ts = [t for t in filtered(raw_turns(day, sod, horizon_h)) if t.t > 0.0]
    return ts


def next_high_low(day: int, sod: float) -> Tuple[Turn, Turn]:
    """(next high water, next low water). Raises if the horizon holds neither (it never does: the longest gap is 17.5 h)."""
    ts = next_turns(day, sod)
    high = next(t for t in ts if t.high)
    low = next(t for t in ts if not t.high)
    return high, low


def rising(day: int, sod: float) -> bool:
    """True when the next turn is a high water."""
    return next_turns(day, sod)[0].high


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--at", metavar="YYYY-MM-DDTHH:MM:SS", required=True)
    args = ap.parse_args(argv)
    day, sod = tl.parse_when(args.at)
    hi, lo = next_high_low(day, sod)
    print(f"tide {_tide(day, sod):.2f} m, {'rising' if rising(day, sod) else 'falling'}")
    for name, t in (("high", hi), ("low", lo)):
        when = (sod + t.t) % 86400.0
        print(f"next {name}: {int(when // 3600):02d}:{int(when % 3600 // 60):02d} (+{t.t / 3600:.2f} h), {t.h:.2f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
