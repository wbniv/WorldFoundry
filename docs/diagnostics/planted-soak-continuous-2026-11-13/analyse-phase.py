#!/usr/bin/env python3
"""Judge the phase-locked step-9 soak: one sample per tank at a fixed phase; final-10-minute spread < 4096 KiB.

Usage: analyse-phase.py [-h]   (reads ./soak-phase/, writes ./soak-phase/verdict.json)
Times are on the device clock (tank-start markers and each sample's meminfo-forced GC line).
"""
import datetime, json, re, statistics, sys
from pathlib import Path

if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__); sys.exit(0)
D = Path(__file__).resolve().parent / 'soak-phase'
LIMIT, PHASE, TOL, GROW = 4096, 20.0, 3.0, 195 / 8
TZ = datetime.timezone(datetime.timedelta(hours=7))
def devtime(line):
    mo, d, h, mi, s = re.match(r'(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d+)', line).groups()
    return datetime.datetime(2026, int(mo), int(d), int(h), int(mi), tzinfo=TZ).timestamp() + float(s)
def cat(fn, key):
    for l in open(D / 'evidence' / fn):
        m = re.match(r'\s+' + re.escape(key) + r'\s+(\d+)', l)
        if m: return int(m.group(1))
samples = json.loads((D / 'sample-values.json').read_text())
starts = sorted(devtime(l) for l in json.loads((D / 'markers.json').read_text()))
status = json.loads((D / 'run-status.json').read_text())
rows = []
for s in samples:
    g = [devtime(l) for l in (D / 'evidence' / s['logcat']).read_text(errors='replace').splitlines() if 'Explicit' in l and ' GC ' in l]
    t = g[-1]; prev = [x for x in starts if x <= t]
    rows.append(dict(t=t, tank=len(prev), phase=t - prev[-1], pss=s['total_pss_kb'], gl=cat(s['meminfo'], 'GL mtrack'),
                     nat=cat(s['meminfo'], 'Native Heap'), stable=s['stable'], pid=s['pid_before']))
locked = [r for r in rows if abs(r['phase'] - PHASE) <= TOL]
# one sample per tank: the one closest to the target phase
per_tank = {}
for r in locked:
    if r['tank'] not in per_tank or abs(r['phase'] - PHASE) < abs(per_tank[r['tank']]['phase'] - PHASE): per_tank[r['tank']] = r
locked = sorted(per_tank.values(), key=lambda r: r['t'])
end = locked[-1]['t']; fin = [r for r in locked if r['t'] >= end - 600]
def sp(k, rs): v = [r[k] for r in rs]; return max(v) - min(v)
ph = [r['phase'] for r in fin]
iv = [b - a for a, b in zip(starts, starts[1:])]
wall = [s['host_wall'] for s in samples]
fatal = []
for f in (D / 'evidence').glob('*logcat.txt'):
    fatal += [l for l in f.read_text(errors='replace').splitlines()
              if re.search(r'FATAL EXCEPTION|Fatal signal|ASSERTION FAILED|ANR in|tombstone', l)]
v = dict(
    job=(D / 'job.txt').read_text().strip(), invalid=status['invalid'], target_phase_s=PHASE, tolerance_s=TOL,
    samples=len(samples), all_stable=all(r['stable'] for r in rows), pids=sorted({r['pid'] for r in rows}),
    tank_starts_observed=len(starts), reloads_lower_bound=len(starts) - 1,
    start_interval_s=[round(min(iv), 2), round(statistics.median(iv), 2), round(max(iv), 2)],
    max_host_gap_s=round(max(b - a for a, b in zip(wall, wall[1:])), 1),
    phase_locked_samples=len(locked), off_phase_samples=len(rows) - len(locked),
    final10_locked_samples=len(fin), final10_span_s=round(fin[-1]['t'] - fin[0]['t'], 1),
    final10_tanks=[fin[0]['tank'], fin[-1]['tank']],
    final10_phase_s=dict(min=round(min(ph), 2), median=round(statistics.median(ph), 2), max=round(max(ph), 2),
                         stdev=round(statistics.pstdev(ph), 2)),
    final10_pss_kib=dict(min=min(r['pss'] for r in fin), median=statistics.median(r['pss'] for r in fin), max=max(r['pss'] for r in fin)),
    final10_spread_kib=sp('pss', fin), final10_gl_spread_kib=sp('gl', fin), final10_native_spread_kib=sp('nat', fin),
    limit_kib_exclusive=LIMIT, fatal_markers=fatal[:20],
    final10_rows=[[round(r['phase'], 2), r['pss'], r['gl'], r['nat']] for r in fin],
)
v['pass'] = (not v['invalid'] and v['all_stable'] and len(v['pids']) == 1 and v['reloads_lower_bound'] >= 50 and not fatal
             and v['final10_span_s'] >= 540 and v['final10_spread_kib'] < LIMIT)
(D / 'verdict.json').write_text(json.dumps(v, indent=2) + '\n')
print(json.dumps({k: x for k, x in v.items() if k != 'final10_rows'}, indent=2))
print('final10 rows [phase, PSS, GL mtrack, Native]:', v['final10_rows'])
