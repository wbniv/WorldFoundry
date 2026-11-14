#!/usr/bin/env python3
"""Summarise the patch_trace.py lines of the last wf_game session in a device wf.log:
per seahorse, the raw frame deltas, the largest one-frame body move and where it happened,
the peak reported centre, and whether the log shows a fatal, an assertion or an actor that
fell out of its room. Prints every seahorse-1 frame as a table.

    python3 trace_report.py WF.LOG
"""
import math
import re
import sys


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0 if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help') else 2
    text = open(sys.argv[1], errors='replace').read()
    last = text.rsplit('=== wf_game android_main', 1)[-1]
    rows = []
    for line in last.splitlines():
        parts = line.split()
        if len(parts) == 8 and parts[0] == '777':
            rows.append([float(p) for p in parts[1:]])     # id t dt progress cy x y
    print(f'trace rows: {len(rows)}')
    for sid in sorted({int(r[0]) for r in rows}):
        s = [r for r in rows if int(r[0]) == sid]
        dts = [r[2] for r in s]
        moves = [(b[1], math.hypot(b[5] - a[5], b[6] - a[6])) for a, b in zip(s, s[1:])]
        worst = max(moves, key=lambda m: m[1]) if moves else (0, 0)
        print(f'seahorse {sid}: frames {len(s)} t {s[0][1]:.3f}..{s[-1][1]:.3f}  raw dt {min(dts)*1e3:.2f}..{max(dts)*1e3:.2f} ms'
              f' (frames under 50 ms: {sum(d < .05 for d in dts)})  max move {worst[1]:.4f} at t={worst[0]:.3f}'
              f'  peak |cy| {max(abs(r[4]) for r in s):.4f}  min progress>0 {min((r[3] for r in s if r[3] > 0), default=0):.3g}')
    if rows:
        print('\nseahorse 1, every frame:\n     t      dt(ms)  progress      cy        x        y     move')
        s = [r for r in rows if int(r[0]) == 1]
        prev = None
        for r in s:
            mv = math.hypot(r[5] - prev[5], r[6] - prev[6]) if prev else 0
            print(f'{r[1]:7.3f}  {r[2]*1e3:6.2f}  {r[3]:8.5f}  {r[4]:8.4f}  {r[5]:7.3f}  {r[6]:7.3f}  {mv:.4f}')
            prev = r
    bad = re.findall(r'(?m)^.*(?:FatalError|ASSERTION|SIGSEGV|fell out of room|not in any room|LookupMailboxes).*$', last)
    print('\nfatal/assert/room lines in the last session:', len(bad))
    for b in bad[:10]:
        print('  ', b[:200])
    times = [float(m) for m in re.findall(r'(?m)^777 \d+ ([0-9.]+) ', last)]
    print('last session log lines:', len(last.splitlines()), ' last trace t:', max(times) if times else None)
    return 0


if __name__ == '__main__':
    sys.exit(main())
