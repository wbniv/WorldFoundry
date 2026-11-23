#!/usr/bin/env python3
"""Count the turning points of the fitted tide and compare them with the highs and lows the Navy's table lists.

    python3 -I wflevels/tide_harbour/tide_fit/count_turns.py --json wflevels/tide_harbour/turning_points.json

The fitted curve wiggles near slack water: where the table shows one flat top, the sum of 64 waves can turn two or
three times within a few centimetres. Anything that reads "the next high water" from the model (a tide board in the
harbour, the poster) has to ignore those. This script measures how many there are, per year, and how many remain when
a pair of neighbouring turns less than a threshold apart is dropped (smallest pair first, repeated), for several
thresholds. The table itself lists small secondary highs and lows, so too large a threshold drops real events:
10 cm leaves 63 fewer than the table in both years; 4 cm leaves within 3 of it.

Reads tide_constants.json beside this directory. One-minute steps, Thai local time, the whole calendar year.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CONSTANTS = HERE.parent / 'tide_constants.json'
MIN_SWING_M = 0.04           # the threshold that brings the count closest to the table's in both years (see TRIED_CM)
TRIED_CM = (1, 2, 3, 4, 5, 7, 10)
STEP_H = 1.0 / 60.0


def heights(const, hours):
    """The fitted tide, metres above the lowest low water, at each of HOURS since the epoch (2026-01-01 00:00 +07)."""
    h = np.full(hours.shape, const['z0_m'])
    for c in const['constituents']:
        h += c['amp_m'] * np.cos(2 * np.pi * (c['cycles_per_hour'] * hours + c['phase_rev']))
    return h


def turns(h):
    """Indices where the curve changes direction."""
    d = np.sign(np.diff(h))
    return np.nonzero(d[:-1] * d[1:] < 0)[0] + 1


def drop_wiggles(values, min_swing):
    """Remove neighbouring pairs of turns less than MIN_SWING apart, the smallest pair first. Returns what is left."""
    kept = list(values)
    while len(kept) > 1:
        swings = np.abs(np.diff(kept))
        k = int(np.argmin(swings))
        if swings[k] >= min_swing:
            break
        del kept[k:k + 2]
    return kept


def count_year(const, year):
    start = (year - 2026) * 365 * 24.0            # 2026 and 2027 are not leap years
    hours = start + np.arange(0, 365 * 24 * 60 + 1) * STEP_H
    h = heights(const, hours)
    at = turns(h)
    swings = np.abs(np.diff(h[at]))
    listed = const['table_stats'][str(year)]['events']
    kept = len(drop_wiggles(h[at], MIN_SWING_M))
    return {
        'model_turns': int(len(at)),
        'table_events': int(listed),
        'extra': int(len(at) - listed),
        'swings_under_5_cm': int((swings < 0.05).sum()),
        'turns_kept': int(kept),
        'kept_minus_table': int(kept - listed),
        'kept_minus_table_by_min_swing_cm': {str(cm): int(len(drop_wiggles(h[at], cm / 100.0)) - listed) for cm in TRIED_CM},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--json', type=Path, help='write the result here')
    args = ap.parse_args(argv)
    const = json.loads(CONSTANTS.read_text())
    out = {'what': 'Turning points of the fitted tide against the highs and lows the table lists, per calendar year.',
           'step_minutes': 1, 'min_swing_m': MIN_SWING_M,
           'years': {str(y): count_year(const, y) for y in (2026, 2027)}}
    text = json.dumps(out, indent=1) + '\n'
    if args.json:
        args.json.write_text(text)
    sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
