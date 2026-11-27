#!/usr/bin/env python3
"""Candle flicker A/B on cast1: presentation and CPU frame-profile figures per variant run.

    python3 analyse.py PAIR_DIR [PAIR_DIR ...]

Per run (PAIR_DIR/<label>/run-1): FPS, p50/p95/p99, missed refreshes from summary.json, and the engine's --frame-profile windows
from wf.log, scoped to the latest `=== wf_game android_main` start and to windows lying wholly inside the measured presentation span
(presents-ns.json, the device's CLOCK_MONOTONIC, the clock the profile's steady_clock start-ns/end-ns use on Android). Each window's
section means are weighted by its frame count. Also prints the installed APK hashes from apk-installations.json.
"""
import gzip, json, re, statistics, sys
from pathlib import Path

WIN = re.compile(r'frame-window: start-ns=(\d+) end-ns=(\d+)')
PROF = re.compile(r'frame-profile: (\w[\w-]*) frames=(\d+) mean=([\d.]+) p50=([\d.]+) p95=([\d.]+) max=([\d.]+)')
COUNT = re.compile(r'frame-count: ([\w-]+) frames=(\d+) mean=([\d.]+) max=(\d+)')


def windows(log: str):
    text = log.rsplit('=== wf_game android_main', 1)[-1]
    out, cur = [], None
    for line in text.splitlines():
        m = WIN.search(line)
        if m:
            cur = {'start': int(m[1]), 'end': int(m[2]), 'sec': {}, 'count': {}}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = PROF.search(line)
        if m:
            cur['sec'][m[1]] = dict(frames=int(m[2]), mean=float(m[3]), p50=float(m[4]), p95=float(m[5]), max=float(m[6]))
        m = COUNT.search(line)
        if m:
            cur['count'][m[1]] = float(m[3])
    return out


def read(path: Path) -> str:
    """A file of the evidence, plain or as the .gz the large ones are kept as (compressed-evidence.json holds their hashes)."""
    if path.is_file():
        return path.read_text(errors='replace')
    return gzip.decompress(Path(str(path) + '.gz').read_bytes()).decode(errors='replace')


def run(folder: Path):
    s = json.loads(read(folder / 'summary.json'))
    pres = json.loads(read(folder / 'presents-ns.json'))
    lo, hi = min(pres), max(pres)
    ws = [w for w in windows(read(folder / 'wf.log')) if w['start'] >= lo and w['end'] <= hi and 'total' in w['sec']]
    agg = {}
    for k in ('update', 'actors', 'director', 'render', 'animation', 'total'):
        n = sum(w['sec'][k]['frames'] for w in ws)
        agg[k] = sum(w['sec'][k]['mean'] * w['sec'][k]['frames'] for w in ws) / n if n else float('nan')
    p95 = statistics.median(w['sec']['total']['p95'] for w in ws) if ws else float('nan')
    cnt = {k: statistics.mean(w['count'].get(k, 0) for w in ws) for k in ('draws', 'triangles', 'actor-mailbox-writes', 'fish-deformations', 'uploads', 'upload-bytes')} if ws else {}
    return s, ws, agg, p95, cnt


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return 0
    for pair in map(Path, argv):
        print(f'== {pair.name}')
        inst = json.loads(read(pair / 'apk-installations.json'))
        for i in inst:
            print(f"  install {i.get('variant') or '-':9s} {i['action']:8s} {i['status']:9s} before {str(i.get('before_sha256'))[:12]} installed {str(i.get('installed_sha256'))[:12]}")
        for folder in sorted(pair.glob('*/run-1')):
            s, ws, agg, p95, cnt = run(folder)
            print(f"  {folder.parent.name:9s} fps {s['fps']:.2f}  p50 {s['p50_ms']:.2f}  p95 {s['p95_ms']:.2f}  p99 {s['p99_ms']:.2f}  worst {s['worst_ms']:.1f}  missed {s['missed_refresh_percent']:.2f} %  span {s['observed_span_seconds']:.1f} s")
            print(f"            cpu-ms mean over {len(ws)} windows ({sum(w['sec']['total']['frames'] for w in ws)} frames): " + '  '.join(f'{k} {v:.3f}' for k, v in agg.items()) + f"  | total p95 (median window) {p95:.3f}")
            print('            counts/frame: ' + '  '.join(f'{k} {v:.1f}' for k, v in cnt.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
