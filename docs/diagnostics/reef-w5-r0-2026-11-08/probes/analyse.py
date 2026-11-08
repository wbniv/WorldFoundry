#!/usr/bin/env python3
"""R0: fetch evidence for every job in jobs.tsv, compute each run's window, aggregate medians per probe.

Usage: python3 build-docker/r0/analyse.py [--no-fetch]
cast1 runs: the 120 s window starting 2 s after the selector release (profile-idle-window.py, the
baseline protocol). Pixel runs: the coordinator's summary.json window (scene launch, no selector).
"""
import json
import statistics as S
import subprocess
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
    print(__doc__); raise SystemExit(0)
ROOT = Path(__file__).resolve().parents[2]
R0 = Path(__file__).resolve().parent
EV = R0 / 'evidence'
IDLE = ROOT / 'docs/diagnostics/reef-gameplay-verification-2026-11-05/profile-idle-window.py'
fetch = '--no-fetch' not in sys.argv
rows = []
for line in (R0 / 'jobs.tsv').read_text().splitlines():
    device, style, probe, rnd, job = line.split('\t')
    out = EV / f'{device}-{style}-{probe}-r{rnd}-{job}'
    if fetch and not (out / 'summary.json').exists():
        subprocess.run(['task', 'chromecast:evidence', f'JOB={job}', f'OUT={out}'], cwd=ROOT,
                       capture_output=True, text=True)
    if not (out / 'summary.json').exists():
        rows.append(dict(device=device, style=style, probe=probe, round=int(rnd), job=job, status='pending'))
        continue
    summary = json.loads((out / 'summary.json').read_text())['runs'][0]
    if device == 'cast1':
        r = subprocess.run([sys.executable, str(IDLE), str(out)], capture_output=True, text=True)
        if r.returncode:
            rows.append(dict(device=device, style=style, probe=probe, round=int(rnd), job=job, status='invalid: ' + (r.stderr or r.stdout).strip()))
            continue
        w = json.loads(r.stdout)
    else:
        w = {k: summary[k] for k in ('fps', 'p95_ms', 'p99_ms', 'worst_ms')}
        if summary['sampling_holes']:
            w['note'] = 'sampling holes'
    rows.append(dict(device=device, style=style, probe=probe, round=int(rnd), job=job, status='ok',
                     fps=w['fps'], p95=w['p95_ms'], p99=w['p99_ms'], worst=w['worst_ms'],
                     missed=summary.get('missed_refresh_percent'), note=w.get('note', '')))
(R0 / 'results.json').write_text(json.dumps(rows, indent=1))
for r in sorted(rows, key=lambda r: (r['device'], r['style'], r['probe'], r['round'])):
    if r['status'] == 'ok':
        print(f"{r['device']:6} {r['style']:9} {r['probe']} r{r['round']} {r['job']}  {r['fps']:6.2f} FPS  "
              f"{1000 / r['fps']:6.2f} ms  p95 {r['p95']:.1f}  p99 {r['p99']:.1f}  worst {r['worst']:.1f} {r['note']}")
    else:
        print(f"{r['device']:6} {r['style']:9} {r['probe']} r{r['round']} {r['job']}  {r['status']}")
print()
for device in sorted({r['device'] for r in rows}):
    for style in ('realistic', 'anime'):
        med = {}
        for probe in ('P0', 'P1', 'P2', 'P3'):
            v = [r['fps'] for r in rows if r['device'] == device and r['style'] == style and r['probe'] == probe and r['status'] == 'ok']
            if v:
                med[probe] = S.median(v)
                print(f"{device:6} {style:9} {probe}: n={len(v)} median {S.median(v):.2f} FPS ({1000 / S.median(v):.2f} ms)  "
                      f"runs {', '.join(f'{x:.2f}' for x in v)}")
        if 'P0' in med:
            for probe in ('P1', 'P2', 'P3'):
                if probe in med:
                    print(f"         {probe}-P0: {med[probe] - med['P0']:+.2f} FPS, {1000 / med[probe] - 1000 / med['P0']:+.2f} ms")
