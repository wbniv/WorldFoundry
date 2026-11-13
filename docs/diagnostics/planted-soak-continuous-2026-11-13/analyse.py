#!/usr/bin/env python3
"""Judge the step-9 soak strictly: same PID, no crash, final-10-minute PSS spread < 4096 KiB.

Usage: analyse.py [-h]   (reads ./soak/, writes ./soak/verdict.json)
"""
import json, re, statistics, sys
from pathlib import Path

if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__); sys.exit(0)
D = Path(__file__).resolve().parent / 'soak'
samples = json.loads((D / 'sample-values.json').read_text())
markers = json.loads((D / 'markers.json').read_text())
status = json.loads((D / 'run-status.json').read_text())
LIMIT = 4096
wall = [s['host_wall'] for s in samples]
gaps = [b - a for a, b in zip(wall, wall[1:])]
end = wall[-1]
final = [s for s in samples if s['host_wall'] >= end - 600]
fp = [s['total_pss_kb'] for s in final]
fw = [s['host_wall'] for s in final]
fgaps = [b - a for a, b in zip(fw, fw[1:])]
# rolling 10-minute windows across the run, for the trend
rolling = []
for i, s in enumerate(samples):
    w = [x['total_pss_kb'] for x in samples if s['host_wall'] <= x['host_wall'] <= s['host_wall'] + 600]
    if samples[-1]['host_wall'] - s['host_wall'] >= 600: rolling.append(max(w) - min(w))
fatal = []
for f in (D / 'evidence').glob('*logcat.txt'):
    fatal += [l for l in f.read_text(errors='replace').splitlines()
              if re.search(r'FATAL EXCEPTION|Fatal signal|ASSERTION FAILED|ANR in|tombstone', l)]
pids = sorted({s['pid_before'] for s in samples} | {s['pid_after'] for s in samples})
spread = max(fp) - min(fp)
v = dict(
    job=(D / 'job.txt').read_text().strip(), invalid=status['invalid'],
    samples=len(samples), all_stable=all(s['stable'] for s in samples), pids=pids,
    tank_starts_observed=len(markers), reloads_lower_bound=len(markers) - 1,
    run_span_s=round(end - wall[0], 1), max_gap_s=round(max(gaps), 1), median_gap_s=round(statistics.median(gaps), 1),
    pss_min_kib=min(s['total_pss_kb'] for s in samples), pss_max_kib=max(s['total_pss_kb'] for s in samples),
    final10_samples=len(final), final10_span_s=round(fw[-1] - fw[0], 1), final10_max_gap_s=round(max(fgaps), 1),
    final10_min_kib=min(fp), final10_max_kib=max(fp), final10_median_kib=statistics.median(fp),
    final10_spread_kib=spread, limit_kib_exclusive=LIMIT,
    rolling10_spread_min_kib=min(rolling) if rolling else None, rolling10_spread_max_kib=max(rolling) if rolling else None,
    fatal_markers=fatal[:20],
)
v['pass'] = (not v['invalid'] and v['all_stable'] and len(pids) == 1 and v['reloads_lower_bound'] >= 50
             and not fatal and v['final10_max_gap_s'] <= 60 and spread < LIMIT)
(D / 'verdict.json').write_text(json.dumps(v, indent=2) + '\n')
print(json.dumps(v, indent=2))
