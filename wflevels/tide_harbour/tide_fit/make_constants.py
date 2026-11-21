#!/usr/bin/env python3
"""Fit harmonic constants to the Hydrographic Department's published highs and lows for Bangkok (station HD),
cross-validate them, and write tide_constants.json.

    python3 -I make_constants.py [--cache DIR] [--n 64] [--out ../tide_constants.json]

The table lists only the extrema of the tide, and where the curve has a flat shoulder it lists none, so the fit
does not interpolate. At every listed event the model height equals the listed height and its slope is zero;
both are linear in the harmonic coefficients, so one linear least squares gives them. The basis is the 55
standard constituents (by Doodson number) plus the shallow-water compound tides (sums and differences of the main
ones, up to three terms), 171 in all, from which the N largest are kept and refitted.

Validation is out of sample, both ways: constants fitted to 2026 are scored on 2027, and the reverse. The shipped
constants are fitted to both years.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constituents
from parse_hd import parse, check

EPOCH = dt.datetime(2026, 1, 1)           # local Thai time (UTC+7), as the table prints it
SIGMA_H, SIGMA_S = 0.02, 0.003            # a 2 cm height error and a 3 mm/h slope error (about 10 minutes at a peak) weigh the same


def hours(t):
    return (t - EPOCH).total_seconds() / 3600.0


def fit(events, speeds):
    names = list(speeds)
    w = np.array([math.radians(speeds[n]) for n in names])
    t = np.array([hours(x) for x, _ in events])[:, None]
    h = np.array([y for _, y in events])
    wt = w[None, :] * t
    c, s = np.cos(wt), np.sin(wt)
    ones = np.ones((len(t), 1))
    A = np.vstack([np.hstack([ones, c, s]) / SIGMA_H, np.hstack([0 * ones, -w * s, w * c]) / SIGMA_S])
    y = np.concatenate([h / SIGMA_H, np.zeros(len(t))])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    n = len(names)
    amp = {names[k]: (math.hypot(coef[1 + k], coef[1 + n + k]), math.atan2(coef[1 + n + k], coef[1 + k])) for k in range(n)}
    return coef[0], amp


def top(amp, n):
    return sorted(amp, key=lambda k: -amp[k][0])[:n]


def predict(z0, amp, speeds, t_hours):
    t = np.asarray(t_hours, float)
    out = np.full(t.shape, z0)
    for name, (a, theta) in amp.items():
        out += a * np.cos(math.radians(speeds[name]) * t - theta)
    return out


def score(z0, amp, speeds, events):
    t = [hours(x) for x, _ in events]
    err = np.abs(predict(z0, amp, speeds, t) - np.array([h for _, h in events])) * 100
    return {"events": len(events), "median_cm": float(np.median(err)), "p90_cm": float(np.percentile(err, 90)), "max_cm": float(err.max())}


def time_error(z0, amp, speeds, events):
    """Minutes between each listed high or low and the nearest extremum of the model (within 2.5 hours)."""
    t = np.array([hours(x) for x, _ in events])
    grid = np.arange(t.min() - 6, t.max() + 6, 1 / 60)
    h = predict(z0, amp, speeds, grid)
    d = np.diff(h)
    et = grid[np.where(np.sign(d[:-1]) != np.sign(d[1:]))[0] + 1]
    errs = []
    for x in t:
        j = int(np.argmin(np.abs(et - x)))
        if abs(et[j] - x) <= 2.5:
            errs.append(abs(et[j] - x) * 60)
    return {"matched": len(errs), "of": len(t), "median_min": float(np.median(errs)), "p90_min": float(np.percentile(errs, 90))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=os.path.expanduser("~/tmp/chao-phraya-tide"))
    ap.add_argument("--n", type=int, default=64, help="constituents to keep (default 64)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tide_constants.json"))
    args = ap.parse_args()

    ev = {}
    for year in (2026, 2027):
        path = os.path.join(args.cache, f"HD{year}.pdf")
        if not os.path.exists(path):
            print(f"missing {path}: run fetch_sources.sh first", file=sys.stderr)
            return 2
        ev[year] = parse(path, year)
        problems, days = check(ev[year], year)
        if len({d for d in days}) != 365:
            print(f"{year}: expected 365 days, got {len(days)}", file=sys.stderr)
            return 1
    full = constituents.compound(3, 0.03)
    print(f"events: 2026 {len(ev[2026])}, 2027 {len(ev[2027])}; basis {len(full)} constituents; keeping {args.n}")

    validation = {}
    for a, b in ((2026, 2027), (2027, 2026)):
        _, amp_full = fit(ev[a], full)
        keep = {k: full[k] for k in top(amp_full, args.n)}
        z0, amp = fit(ev[a], keep)
        validation[f"fitted_{a}_scored_on_{b}"] = score(z0, amp, keep, ev[b])
        validation[f"fitted_{a}_scored_on_{a}"] = score(z0, amp, keep, ev[a])
        validation[f"fitted_{a}_time_error_on_{b}"] = time_error(z0, amp, keep, ev[b])
        v = validation[f"fitted_{a}_scored_on_{b}"]
        print(f"fitted on {a}, scored on {b} (unseen): median {v['median_cm']:.1f} cm, 90th {v['p90_cm']:.1f}, max {v['max_cm']:.1f}  ({v['events']} events)")

    # how many waves are enough: fitted to 2026 with the N largest, scored on the unseen 2027
    _, amp26 = fit(ev[2026], full)
    error_vs_n = {}
    for n in (6, 12, 24, 32, 48, 64, 96, len(full)):
        keep_n = {k: full[k] for k in top(amp26, n)}
        z0n, ampn = fit(ev[2026], keep_n)
        error_vs_n[str(n)] = score(z0n, ampn, keep_n, ev[2027])
    print("median error on unseen 2027 by waves kept:", {k: round(v["median_cm"], 1) for k, v in error_vs_n.items()})

    from collections import Counter
    table_stats = {}
    for year in (2026, 2027):
        hs_y = [h for _, h in ev[year]]
        by_day = {}
        for t, h in ev[year]:
            by_day.setdefault(t.date(), []).append(h)
        rng = sorted(max(v) - min(v) for v in by_day.values() if len(v) > 1)
        counts = Counter(len(v) for v in by_day.values())
        table_stats[str(year)] = {"events": len(ev[year]), "days": len(by_day), "min_m": min(hs_y), "max_m": max(hs_y),
                                  "days_by_event_count": {str(k): counts[k] for k in sorted(counts)},
                                  "daily_range_median_m": rng[len(rng) // 2], "daily_range_max_m": rng[-1],
                                  "max_gap_between_events_h": max((b[0] - a[0]).total_seconds() / 3600 for a, b in zip(ev[year], ev[year][1:]))}

    both = ev[2026] + ev[2027]
    _, amp_full = fit(both, full)
    keep = {k: full[k] for k in top(amp_full, args.n)}
    z0, amp = fit(both, keep)
    in_sample = score(z0, amp, keep, both)
    print(f"shipped constants (both years, {len(keep)} constituents), in sample: median {in_sample['median_cm']:.1f} cm, 90th {in_sample['p90_cm']:.1f}, max {in_sample['max_cm']:.1f}")

    heights = [h for _, h in both]
    consts = []
    for name in sorted(keep, key=lambda k: -amp[k][0]):
        a, theta = amp[name]
        consts.append({"name": name, "speed_deg_per_h": keep[name], "cycles_per_hour": keep[name] / 360.0,
                       "amp_m": round(a, 5), "phase_rev": round((-theta / (2 * math.pi)) % 1.0, 6)})
    sources = {}
    for f in ("HD2026.pdf", "HD2027.pdf"):
        with open(os.path.join(args.cache, f), "rb") as fh:
            sources[f] = hashlib.sha256(fh.read()).hexdigest()
    doc = {
        "what": "Harmonic constants for the predicted tide at the Royal Thai Navy Headquarters, Bangkok (Chao Phraya), fitted to the "
                "Hydrographic Department's published predicted highs and lows for 2026 and 2027. A fit to published predictions, not "
                "the department's own constants.",
        "formula": "h(t) = z0_m + sum over constituents of amp_m * cos(2*pi*(cycles_per_hour * t + phase_rev)), t in hours since epoch",
        "epoch_local": "2026-01-01T00:00:00+07:00",
        "time_zone": "Thai local time, UTC+7: measured against UHSLC Ko Lak hourly GMT data (see check_time_zone.py)",
        "datum": "metres above the lowest low water, as the table's footer prints it",
        "z0_m": round(z0, 5),
        "range_of_listed_extrema_m": [min(heights), max(heights)],
        "n_constituents": len(consts),
        "validation_height_error_at_listed_events": validation,
        "error_vs_constituents_fitted_2026_scored_2027": error_vs_n,
        "table_stats": table_stats,
        "shipped_fit_in_sample": in_sample,
        "constituents": consts,
        "sources": {"station": "HD, Royal Thai Navy Headquarters (Bangkok Metropolitan), 13 44' 36\" N 100 29' 25\" E",
                    "retrieved": dt.date.today().isoformat(), "sha256": sources,
                    "urls": ["https://hydro.navy.mi.th/sevicetide", "https://hydro.navy.mi.th/servicetide2570"]},
        "method": "linear least squares on (height = listed height, slope = 0) at every listed event; Doodson-number constituents plus shallow-water compounds; top N by amplitude refitted",
    }
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print("wrote", os.path.relpath(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
