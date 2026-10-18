#!/usr/bin/env python3
"""Seahorse 1 (actor 30, pair 0's male) through its first release, under many frame-delta
schedules: the real Director Forth in the zForth host plus the DFRM reference evaluator
(tests/test_seahorse_behaviour.py's Tank), as the engine runs it.

For every run it records each frame of seahorse 1's release and the first swim frames:
the wrap progress (cell 24), the DFRM wrap centre (cells 33, 34), the body position the
script writes (actor 30's X/Y mailboxes) and the largest one-frame jump. A run "leaves the
room" when the body's bounding box no longer overlaps the level's one room
(wflevels/aquarium_plants/aquarium_plants.lev: x -25..25, y -30..10, z -6..18), which is
the condition under which Room::UpdateRoomContents -> LevelRooms::AddObjectToRoom calls
SetPendingRemove and Level::removePendingObjects deletes the actor.

    scripts/in-linux-container.sh python3 docs/diagnostics/seahorse-actor30-2026-10-18/dt_sweep.py \
        --out docs/diagnostics/seahorse-actor30-2026-10-18/dt-sweep.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests'))
import test_seahorse_behaviour as tsb  # noqa: E402

ROOM = ((-25.0, -30.0, -6.0), (25.0, 10.0, 18.0))
BODY = ((-.045, -.0665, -.9135), (.346, .0665, .637))      # seahorse-1-body's local box (.lev)
S = 1                                                       # seahorse 1: actor 30 in the level


def zf_binary(folder: Path) -> Path:
    src = ROOT / 'docs/reference/swarming-poster/zf_host.c'
    zfs = ROOT / 'engine/vendor/zforth-41db72d1/src/zforth'
    out = folder / 'float'
    subprocess.run(['cc', '-O1', f'-I{ROOT / "engine/stubs"}', f'-I{zfs}', str(src), str(zfs / 'zforth.c'),
                    '-lm', '-o', str(out)], check=True)
    return out


def in_room(x, y, z):
    lo = [p + b for p, b in zip((x, y, z), BODY[0])]
    hi = [p + b for p, b in zip((x, y, z), BODY[1])]
    # ColBox::CheckCollision: separated when max <= omin or min >= omax (NaN compares false: stays "in").
    return not any(hi[k] <= ROOM[0][k] or lo[k] >= ROOM[1][k] for k in range(3))


def run(binary, schedule, label, limit_s=12.0):
    t = tsb.Tank(binary, count=1)
    frames, jump, prev, left, k = [], (0.0, None), None, None, 0
    try:
        while t.now < 1.0 + limit_s:
            dt = schedule(k)
            k += 1
            t.step(1, dt=dt)
            state = int(t.block(S, 41))
            x, y, z, _yaw = t.body(S)
            if prev is not None:
                d = math.hypot(x - prev[0], y - prev[1])
                if not d <= jump[0]:            # NaN counts as a jump
                    jump = (d, round(t.now - 1.0, 4))
            prev = (x, y)
            if state in (tsb.RELEASE, tsb.SWIM) and len(frames) < 400:
                frames.append(dict(t=round(t.now - 1.0, 4), dt=round(dt, 5), state=tsb.NAMES[state],
                                   progress=t.block(S, 24), centre=t.block(S, 33, 2), valid=t.block(S, 59),
                                   x=x, y=y, z=z))
            if not in_room(x, y, z):
                left = dict(t=round(t.now - 1.0, 4), x=x, y=y, z=z, state=tsb.NAMES[state])
                break
            if state == tsb.SWIM and frames and sum(f['state'] == 'swim' for f in frames) > 20:
                break
    finally:
        t.close()
    return dict(label=label, left_room=left, max_jump=jump[0], max_jump_t=jump[1],
                release=[f for f in frames if f['state'] == 'release'][-4:] + [f for f in frames if f['state'] == 'swim'][:2])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', type=Path)
    ap.add_argument('--jitter-runs', type=int, default=200)
    ap.add_argument('--scripts', type=Path,
                    help='directory holding the controller.fth, seahorse_behaviour.fth and urchin_motion.fth to run '
                         '(default: the working tree\'s wflevels/aquarium_tanks)')
    ap.add_argument('--vsync60', type=float, nargs='*',
                    help='only run the 60 Hz vsync model: frame k ends at a whole number of 1/60 s vsyncs (1, or 2 with '
                         'probability .15) plus a timestamp jitter N(0, sigma) (sigmas in ms); dt is the difference of '
                         'consecutive timestamps, so the jitter telescopes as an engine clock does')
    ap.add_argument('--vsync', type=float, nargs='*',
                    help='only run the vsync model: frames of 50 ms + N(0, sigma) (sigmas in ms), clamped by tk-dt@')
    args = ap.parse_args()
    if args.scripts:
        tsb.TANKS = args.scripts.resolve()
    print('scripts:', tsb.TANKS, flush=True)
    results = []
    if args.vsync60:
        with tempfile.TemporaryDirectory() as tmp:
            binary = zf_binary(Path(tmp))
            table = {}
            for sigma in args.vsync60:
                runs = []
                for i in range(args.jitter_runs):
                    rng = random.Random(2000 + i)
                    clock = {'t': 0.0, 'j': 0.0}

                    def dt(_k, rng=rng, clock=clock, sigma=sigma):
                        nominal = (2 if rng.random() < .15 else 1) / 60
                        j = rng.gauss(0, sigma / 1000)
                        d = nominal + j - clock['j']
                        clock['j'] = j
                        return d
                    runs.append(run(binary, dt, f'vsync60-{sigma}ms-{i}'))
                table[sigma] = dict(runs=len(runs), left_room=sum(1 for r in runs if r['left_room']),
                                    jump_over_1=sum(1 for r in runs if not r['max_jump'] <= 1.0))
                print(sigma, json.dumps(table[sigma]), flush=True)
                results += runs
        if args.out:
            args.out.write_text(json.dumps(dict(vsync60=table, runs=results), indent=1))
        return
    if args.vsync:
        with tempfile.TemporaryDirectory() as tmp:
            binary = zf_binary(Path(tmp))
            table = {}
            for sigma in args.vsync:
                runs = [run(binary, lambda k, rng=random.Random(1000 + i), s=sigma: .05 + rng.gauss(0, s / 1000),
                            f'vsync-{sigma}ms-{i}') for i in range(args.jitter_runs)]
                table[sigma] = dict(runs=len(runs), left_room=sum(1 for r in runs if r['left_room']),
                                    jump_over_1=sum(1 for r in runs if not r['max_jump'] <= 1.0))
                print(sigma, json.dumps(table[sigma]), flush=True)
                results += runs
        if args.out:
            args.out.write_text(json.dumps(dict(vsync=table, runs=results), indent=1))
        return
    with tempfile.TemporaryDirectory() as tmp:
        binary = zf_binary(Path(tmp))
        # 1. Fixed deltas: 1/N s for N = 20..60 Hz (the engine's -rateN; tk-dt@ clamps above .05).
        for n in range(20, 61):
            results.append(run(binary, lambda k, n=n: 1.0 / n, f'fixed-{n}Hz'))
        # 2. Device-like jitter: frame deltas uniform in [lo, hi], clamped by tk-dt@ to .05.
        for i in range(args.jitter_runs):
            rng = random.Random(i)
            lo, hi = (.030, .065) if i % 2 == 0 else (.040, .055)
            results.append(run(binary, lambda k, rng=rng, lo=lo, hi=hi: rng.uniform(lo, hi), f'jitter-{i}-{lo}-{hi}'))
    fixed = [r for r in results if r['label'].startswith('fixed')]
    jitter = [r for r in results if r['label'].startswith('jitter')]
    summary = dict(
        fixed_runs=len(fixed), fixed_left_room=[r['label'] for r in fixed if r['left_room']],
        jitter_runs=len(jitter), jitter_left_room=sum(1 for r in jitter if r['left_room']),
        jitter_jump_over_1=sum(1 for r in jitter if not r['max_jump'] <= 1.0),
        fixed_20hz=next(r for r in fixed if r['label'] == 'fixed-20Hz'))
    print(json.dumps(summary, indent=1))
    for r in results:
        if r['left_room']:
            print(r['label'], json.dumps(r['left_room']), 'last release frames:',
                  json.dumps([(f['t'], f['progress'], [round(c, 3) for c in f['centre']], f['valid']) for f in r['release']]))
            break
    if args.out:
        args.out.write_text(json.dumps(dict(summary=summary, runs=results), indent=1))


if __name__ == '__main__':
    main()
