#!/usr/bin/env python3
"""Phase-bin soak PSS samples by seconds since the latest tank start.

Usage: phase.py [-h] [SOAK_DIR]   (default ./soak)
"""
import json, re, sys, statistics, datetime
from pathlib import Path
if '-h' in sys.argv or '--help' in sys.argv: print(__doc__); sys.exit(0)
D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'soak'
TZ = datetime.timezone(datetime.timedelta(hours=7))
def devtime(line):
    m = re.match(r'(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d+)', line)
    mo, d, h, mi, s = m.groups()
    return datetime.datetime(2026, int(mo), int(d), int(h), int(mi), 0, tzinfo=TZ).timestamp() + float(s)
starts = sorted(devtime(l) for l in json.loads((D / 'markers.json').read_text()))
iv = [b - a for a, b in zip(starts, starts[1:])]
print(f'starts {len(starts)}  interval min/median/max {min(iv):.2f}/{statistics.median(iv):.2f}/{max(iv):.2f} s')
samples = json.loads((D / 'sample-values.json').read_text())
# clock offset bound: last logcat line (device clock) must precede capture end (host clock)
off = []
for s in samples:
    p = D / 'evidence' / s['logcat']
    if p.exists():
        ts = [devtime(l) for l in p.read_text(errors='replace').splitlines() if re.match(r'\d\d-\d\d ', l)]
        if ts: off.append(max(ts) - s['captured'])
print(f'(host captured vs device clock) lower bound: max(last logcat line - captured) = {max(off):+.2f} s (median {statistics.median(off):+.2f})')
def cat(fn, key):
    for l in open(D / 'evidence' / fn):
        m = re.match(r'\s+' + re.escape(key) + r'\s+(\d+)', l)
        if m: return int(m.group(1))
GROW = 195 / 8
rows = []
for s in samples:
    # sample time on the device clock: dumpsys meminfo forces one 'Explicit ... GC' line in the app,
    # exactly one new one per sample, so it timestamps the meminfo on the same clock as the markers
    gcs = [devtime(l) for l in (D / 'evidence' / s['logcat']).read_text(errors='replace').splitlines() if 'Explicit' in l and ' GC ' in l]
    t = gcs[-1]; prev = [x for x in starts if x <= t]
    if not prev: continue
    ph = t - prev[-1]
    rows.append(dict(t=t, phase=ph, part='grow' if ph < GROW else 'hold', pss=s['total_pss_kb'],
                     gl=cat(s['meminfo'], 'GL mtrack'), nat=cat(s['meminfo'], 'Native Heap')))
end = rows[-1]['t']; fin = [r for r in rows if r['t'] >= end - 600]
def sp(v): return max(v) - min(v) if v else None
print(f'final-10-min samples {len(fin)}')
bins = [(0, 6), (6, 12), (12, 18), (18, GROW), (GROW, 40)]
print('phase bin (s)     n   PSS min..max  spread | GL mean spread | Native mean spread')
for a, b in bins:
    r = [x for x in fin if a <= x['phase'] < b]
    if not r: print(f'{a:5.1f}-{b:5.1f}     0'); continue
    P = [x['pss'] for x in r]; G = [x['gl'] for x in r]; N = [x['nat'] for x in r]
    print(f'{a:5.1f}-{b:5.1f}  {len(r):4d}  {min(P)}..{max(P)} {sp(P):6d} | {statistics.mean(G):8.0f} {sp(G):6d} | {statistics.mean(N):8.0f} {sp(N):6d}')
for part in ('grow', 'hold'):
    r = [x for x in fin if x['part'] == part]
    if r: print(part, len(r), 'PSS spread', sp([x['pss'] for x in r]))
def corr(x, y):
    mx, my = statistics.mean(x), statistics.mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / ((sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** .5)
for k in ('pss', 'gl', 'nat'):
    print(f'corr(phase, {k}) final10 {corr([x["phase"] for x in fin], [x[k] for x in fin]):+.2f}  all {corr([x["phase"] for x in rows], [x[k] for x in rows]):+.2f}')
print('final-10 rows (phase s, PSS, GL, Native):')
for x in sorted(fin, key=lambda r: r['phase']): print(f'  {x["phase"]:5.1f} {x["part"]} {x["pss"]} {x["gl"]} {x["nat"]}')
