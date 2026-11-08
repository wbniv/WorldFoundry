"""Summarize 120 seconds of presented frames after the selector touch settles.

Usage: python3 profile-idle-window.py EVIDENCE_DIRECTORY
The final touch release is followed by a two-second settling interval.
"""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
touch = json.loads((root / 'touch-evidence.json').read_text())
edges = touch['observed_edges'].values()
release_ms = max(edge['device_uptime_ms'] for edge in edges
                 if edge['action'] == 2 and edge['accepted'])
start = (release_ms + 2000) * 1_000_000
presents = sorted(set(json.loads((root / 'run-1/presents-ns.json').read_text())))
window = [value for value in presents if start <= value <= start + 120_000_000_000]
if len(window) < 2 or window[-1] - window[0] < 119_900_000_000:
    raise SystemExit('Incomplete 120-second idle window')
intervals = sorted((b - a) / 1_000_000 for a, b in zip(window, window[1:]))
summary = json.loads((root / 'summary.json').read_text())['runs'][0]
if summary['sampling_holes'] or summary['latency_statistics_may_include_unobserved_bridges']:
    raise SystemExit('SurfaceFlinger sampling has gaps')
print(json.dumps({'fps': (len(window)-1)*1_000_000_000/(window[-1]-window[0]),
                  'frames': len(window), 'span_seconds': (window[-1]-window[0])/1e9,
                  'p95_ms': intervals[int(.95*(len(intervals)-1))],
                  'p99_ms': intervals[int(.99*(len(intervals)-1))],
                  'worst_ms': max(intervals)}, indent=2))
