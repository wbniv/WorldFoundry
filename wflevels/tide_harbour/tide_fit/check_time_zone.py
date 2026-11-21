#!/usr/bin/env python3
"""Which clock does the department's table use? Compare Ko Lak's published highs and lows (KL2026.pdf) with a
prediction made from the observed 2025 hourly record (UHSLC station 328, GMT).

    python3 -I check_time_zone.py [--cache DIR]

Harmonic constants are fitted to the 2025 observations (GMT), 2026 is predicted from them, and the table's event
times are slid against the predicted extrema. The shift with the smallest median mismatch is table time minus GMT.
Ko Lak is strongly diurnal, so a 7 hour shift is 105 degrees of K1 phase and cannot be confused with any other.
"""
import argparse
import datetime as dt
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constituents
from parse_hd import parse


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=os.path.expanduser("~/tmp/chao-phraya-tide"))
    ap.add_argument("--json", help="also write the result to this file")
    args = ap.parse_args()
    kl = parse(os.path.join(args.cache, "KL2026.pdf"), 2026)
    t0 = dt.datetime(2025, 1, 1)
    obs = []
    with open(os.path.join(args.cache, "h328.csv")) as fh:
        for line in fh:
            y, m, d, h, v = line.strip().split(",")
            if y == "2025" and int(v) > -9000:
                obs.append(((dt.datetime(int(y), int(m), int(d), int(h)) - t0).total_seconds() / 3600, int(v) / 1000.0))
    names = ["Sa", "Ssa", "Q1", "O1", "P1", "K1", "J1", "OO1", "N2", "M2", "S2", "K2", "M4", "MS4", "MK3", "Mf", "Mm"]
    w = np.array([math.radians(constituents.SPEEDS[n]) for n in names])
    t = np.array([a for a, _ in obs])
    y = np.array([b for _, b in obs])
    wt = w[None, :] * t[:, None]
    A = np.hstack([np.ones((len(t), 1)), np.cos(wt), np.sin(wt)])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    tp = np.arange((dt.datetime(2025, 12, 28) - t0).total_seconds() / 3600, (dt.datetime(2027, 1, 3) - t0).total_seconds() / 3600, 1 / 30)
    wp = w[None, :] * tp[:, None]
    hp = coef[0] + np.cos(wp) @ coef[1:1 + len(names)] + np.sin(wp) @ coef[1 + len(names):]
    d = np.diff(hp)
    ext = tp[np.where(np.sign(d[:-1]) != np.sign(d[1:]))[0] + 1]
    tab = np.array([(a - t0).total_seconds() / 3600 for a, _ in kl])
    results = []
    for shift in np.arange(-12, 12.01, 0.5):
        g = tab - shift
        results.append((float(np.median([np.min(np.abs(ext - x)) for x in g])) * 60, float(shift)))
    results.sort()
    print(f"Ko Lak: {len(obs)} observed hourly samples in 2025 (GMT), {len(kl)} table events for 2026")
    for m, s in results[:3]:
        print(f"  table minus GMT = {s:+5.1f} h: median mismatch {m:6.1f} min")
    zero = [m for m, s in results if s == 0.0][0]
    print(f"  table minus GMT =  +0.0 h: median mismatch {zero:6.1f} min   (the table is not in GMT)")
    best = results[0][1]
    if args.json:
        import json
        with open(args.json, "w") as fh:
            json.dump({"station": "Ko Lak (UHSLC 328, observed 2025; department table KL2026)", "observed_samples": len(obs), "table_events": len(kl),
                       "median_mismatch_min_by_shift_h": {f"{s:+.1f}": round(m, 1) for m, s in sorted(results, key=lambda r: r[1])},
                       "best_shift_h": best, "mismatch_at_best_min": round(results[0][0], 1), "mismatch_at_zero_min": round(zero, 1)}, fh, indent=1)
            fh.write("\n")
    print("RESULT: the table's times are Thai local time (UTC+7)" if best == 7.0 else f"RESULT: unexpected shift {best:+.1f} h")
    return 0 if best == 7.0 else 1


if __name__ == "__main__":
    sys.exit(main())
