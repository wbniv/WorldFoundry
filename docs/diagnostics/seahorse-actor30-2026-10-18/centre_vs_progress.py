#!/usr/bin/env python3
"""The DFRM wrap centre (cells 33, 34) that seahorse 1 reports as its release ends, as a
function of the wrap progress (cell 24), from the reference evaluator.

Runs the Director Forth (Tank) at 20 Hz to the last release frame, then re-evaluates that
frame's block with cell 24 swept over (0, 0.1]: the release decrements progress by dt/1.2 a
frame, so the last pose before 0 has a progress anywhere in (0, dt/1.2) set by the frame
deltas. Prints the centre and the one-frame body jump the next frame's sh-solve would make.

    scripts/in-linux-container.sh python3 docs/diagnostics/seahorse-actor30-2026-10-18/centre_vs_progress.py
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dt_sweep  # noqa: E402

tsb = dt_sweep.tsb


def main():
    with tempfile.TemporaryDirectory() as tmp:
        binary = dt_sweep.zf_binary(Path(tmp))
        t = tsb.Tank(binary, count=1)
        try:
            while not (t.block(1, 41) == tsb.RELEASE and t.block(1, 24) < .09):
                t.step(1)
            blk = t.block(1, 0, 40)
            x, y, z, yaw = t.body(1)
            c, s = math.cos(2 * math.pi * yaw), math.sin(2 * math.pi * yaw)
            world = [c, s, 0, -s, c, 0, 0, 0, 1]
            now = t.now
            cprev = t.block(1, 33, 2)
        finally:
            t.close()
    print(f'release end at t={now - 1:.3f} s, mode={blk[21]} start={blk[22]} radius={blk[23]:.4f}, '
          f'clip A={blk[25]} B={blk[27]}, yaw={yaw:.3f}')
    rig = tsb.dfrm_ref and tsb.sh.rig()
    rows = []
    ps = sorted(set([10 ** (-e / 8) for e in range(8, 57)] + [k / 1000 for k in range(1, 100)]))
    for p in ps:
        b = list(blk)
        b[24] = p
        r = tsb.dfrm_ref.evaluate(rig, b, now, world, chain_only=True)
        cx, cy = r['outputs'][0], r['outputs'][1]
        F, L, _ = r['angles']
        # next frame: sh-solve with gain min(1, 6 dt) at dt .05 and k = 1 extrapolation
        px, py = cx + (cx - cprev[0]), cy + (cy - cprev[1])
        jump = .3 * math.hypot(px, py)
        rows.append((p, cx, cy, L[34], jump))
    print(f'{"progress":>10} {"cx":>9} {"cy":>9} {"L[34] deg":>10} {"jump@20Hz":>10}')
    for p, cx, cy, l34, jump in rows:
        print(f'{p:10.3g} {cx:9.4f} {cy:9.3f} {l34:10.5f} {jump:10.3f}{"  LEAVES ROOM" if jump > 10.5 else ""}')
    deadly = [p for p, *_r, j in rows if j > 10.5]
    print('progress band whose next-frame jump exceeds 10.5 (room y edge):',
          (min(deadly), max(deadly)) if deadly else None)


if __name__ == '__main__':
    main()
