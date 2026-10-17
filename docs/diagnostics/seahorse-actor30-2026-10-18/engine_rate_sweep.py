#!/usr/bin/env python3
"""Run the Release wf_game on a pair-1 saltwater level at fixed -rateN clocks and follow
seahorse 1 (actor 30) through its first release, one frame at a time over the debug bridge.

Per run it records, for every frame from 6.5 s to the end: the wrap progress (cell 24 of
block 1300), the reported wrap centre (cells 33, 34), the script's body position (cells
45, 46) and whether the engine process is still alive. A run that dies is a reproduction.

    scripts/in-linux-container.sh python3 docs/diagnostics/seahorse-actor30-2026-10-18/engine_rate_sweep.py \
        --game /src/engine/wf_game --level /build/close-idle-pair1-standalone.iff --rates 20 21 56
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests'))
from debug_bridge_client import BridgeClient  # noqa: E402

VRAM = ['--vram-width=2048', '--vram-height=1024', '--vram-slot-width=512', '--vram-slot-height=512',
        '--vram-perm-width=1024', '--vram-perm-height=1024']
DIRECTOR, PLAYER = 4, 9
BLOCK = 1300                     # seahorse 1
CELLS = {'progress': 24, 'cx': 33, 'cy': 34, 'status': 39, 'state': 41, 'x': 45, 'y': 46, 'z': 47}


def one(args, rate, port, log_dir):
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(ROOT / 'engine/libs') + ':' + env.get('LD_LIBRARY_PATH', '')
    env.update(WF_REST_HOST='127.0.0.1', WF_REST_PORT=str(port + 1000))
    logp = log_dir / f'runtime-{rate}hz.log'
    logf = logp.open('w')
    proc = subprocess.Popen([str(args.game), '-L' + str(args.level), *VRAM, '-width=320', '-height=240',
                             f'-rate{rate}', '--debug-port', str(port), '--debug-bind', '127.0.0.1'],
                            cwd=ROOT / 'wflevels/aquarium_plants', env=env, stdout=logf, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    frames, died, err = [], None, None
    try:
        cli = BridgeClient(port=port, timeout=60)
        cli.send({'op': 'pause'})
        cli.inject_input('joystick1_raw', 0, duration_frames=-1)
        cli.watch(idx=PLAYER, mailbox=1906)
        for k in CELLS.values():
            cli.watch(idx=DIRECTOR, mailbox=BLOCK + k)
        time.sleep(.3)

        def val(m, a=DIRECTOR):
            with cli._lock:
                return cli.mailbox_values.get((a, m), 0.0)

        def step(n):
            t0 = val(1906, PLAYER)
            cli.send({'op': 'step', 'frames': n})
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    return False
                if val(1906, PLAYER) > t0 + n * (1.0 / rate) * .9:
                    time.sleep(.02)
                    return True
                time.sleep(.003)
            raise RuntimeError('step timed out')

        while val(1906, PLAYER) < 6.5:
            if not step(10):
                break
        while proc.poll() is None and val(1906, PLAYER) < args.until:
            alive = step(1)
            frames.append(dict(t=round(val(1906, PLAYER), 4), **{k: val(BLOCK + v) for k, v in CELLS.items()}))
            if not alive:
                break
        time.sleep(.5)
        cli.close()
    except Exception as e:  # noqa: BLE001
        err = repr(e)
    finally:
        rc = proc.poll()
        if rc is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        else:
            died = rc
        logf.close()
    text = logp.read_text(errors='replace')
    crash = [ln for ln in text.splitlines() if any(s in ln for s in ('SIGSEGV', 'Segmentation', 'signal', 'Assert', 'fell out', 'not in any room'))][:8]
    return dict(rate=rate, died_rc=died, error=err, crash_lines=crash,
                release=[f for f in frames if f['state'] in (1, 2)][:40], last=frames[-3:])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--game', type=Path, required=True)
    ap.add_argument('--level', type=Path, required=True)
    ap.add_argument('--rates', type=int, nargs='+', default=list(range(20, 61)))
    ap.add_argument('--until', type=float, default=8.5)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    log_dir = Path(os.environ.get('SWEEP_LOGS', '/build/sweep-logs'))
    log_dir.mkdir(parents=True, exist_ok=True)
    xvfb = None
    if not os.environ.get('DISPLAY'):
        xvfb = subprocess.Popen(['Xvfb', ':79', '-screen', '0', '1280x960x24'], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        os.environ['DISPLAY'] = ':79'
        time.sleep(1.0)
    results = []
    try:
        for i, rate in enumerate(args.rates):
            r = one(args, rate, 7800 + 2 * (i % 50), log_dir)
            results.append(r)
            peak = max((abs(f['cy']) for f in r['release']), default=0)
            print(f"{rate} Hz: died={r['died_rc']} err={r['error']} peak|cy|={peak:.3f} crash={r['crash_lines'][:2]}", flush=True)
            if args.out:
                args.out.write_text(json.dumps(results, indent=1))
    finally:
        if xvfb:
            xvfb.terminate()


if __name__ == '__main__':
    main()
