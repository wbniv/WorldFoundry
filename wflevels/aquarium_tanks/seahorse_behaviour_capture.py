#!/usr/bin/env python3
"""Desktop evidence for the seahorse behaviour (Phase 3): the saltwater planted tank
under the Release wf_game, stepped at a fixed 20 Hz through the debug bridge.

1. Behaviour: a close view of the whip while seahorse 1 runs hold -> release -> swim ->
   probe -> grasp -> hold, then a wide view while it swims, then the greeting (forced
   due by writing the shared greeting timer, 1603), close on the whip.
2. Settings: one wide shot per Seahorses setting (None, 1 pair, 2 pairs) and freshwater,
   each a fresh run of the level cooked with that setting (plant_settings_catalog).

Every shot records each seahorse's state, spot, wrap progress, DFRM status and the
contact error (the engine-reported wrap centre against its post's axis) in capture.json.
Starts Xvfb when no DISPLAY is set (the Linux test image).

    scripts/in-linux-container.sh python3 wflevels/aquarium_tanks/seahorse_behaviour_capture.py \\
        --out docs/plans/2026-10-16-saltwater-seahorses/evidence/phase3
"""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'scripts'))
from debug_bridge_client import BridgeClient  # noqa: E402
from plant_settings_catalog import configure_level  # noqa: E402

VRAM = ['--vram-width=2048', '--vram-height=1024', '--vram-slot-width=512', '--vram-slot-height=512',
        '--vram-perm-width=1024', '--vram-perm-height=1024']   # android/app/src/aquarium/assets/wf_args.txt
STATES = ('hold', 'release', 'swim', 'probe', 'grasp', 'strike', 'greet')
CELLS = {'state': 41, 'spot': 43, 'x': 45, 'y': 46, 'z': 47, 'yaw': 48, 'progress': 24, 'status': 39,
         'cx': 33, 'cy': 34, 'ax': 65, 'ay': 66, 'init': 40}


class Run:
    def __init__(self, args, out, options, tag):
        here = ROOT / 'wflevels/aquarium_plants'
        self.map = json.loads((here / 'actor-map.json').read_text())
        self.idx, self.sea = self.map['indices'], self.map['seahorses']
        self.player, self.director = self.idx['Player'], self.idx['Director']
        self.out, self.tag, self.shots = out, tag, []
        self.level = out / f'configured-{tag}.iff'
        data, self.receipt = configure_level((ROOT / 'wflevels/aquarium_plants-standalone.iff').read_bytes(),
                                             dict(seed=args.seed, age=args.age, speed=0, **options))
        self.level.write_bytes(data)
        env = os.environ.copy()
        env['LD_LIBRARY_PATH'] = str(ROOT / 'engine/libs') + ':' + env.get('LD_LIBRARY_PATH', '')
        env.update(WF_REST_HOST='127.0.0.1', WF_REST_PORT=str(args.port + 1000))
        self.xvfb = None
        if not env.get('DISPLAY'):
            self.xvfb = subprocess.Popen(['Xvfb', ':79', '-screen', '0', '1280x960x24'], stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
            env['DISPLAY'] = ':79'
            time.sleep(1.0)
        self.logf = (out / f'runtime-{tag}.log').open('w')
        self.proc = subprocess.Popen([str(args.game), '-L' + str(self.level), *VRAM, '-width=1280', '-height=720',
                                      '-rate20', '--debug-port', str(args.port), '--debug-bind', '127.0.0.1'],
                                     cwd=here, env=env, stdout=self.logf, stderr=subprocess.STDOUT,
                                     preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
        self.cli = BridgeClient(port=args.port, timeout=30)
        self.cli.send({'op': 'pause'})
        self.cli.inject_input('joystick1_raw', 0, duration_frames=-1)
        self.cli.watch(idx=self.player, mailbox=1906)
        for m in (1162, 1163, 1600, 1601, 1602):
            self.cli.watch(idx=self.director, mailbox=m)
        for a in self.sea['actors']:
            for k in CELLS.values():
                self.cli.watch(idx=self.director, mailbox=a['block'] + k)
        time.sleep(.3)

    def value(self, m, actor=None):
        with self.cli._lock:
            return self.cli.mailbox_values.get((self.director if actor is None else actor, m), 0.0)

    def cell(self, s, name):
        return self.value(1200 + 100 * s + CELLS[name])

    def step(self, n):
        start = self.value(1906, self.player)
        self.cli.send({'op': 'step', 'frames': n})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.value(1906, self.player) >= start + n * (3276 / 65536) - .0002:
                time.sleep(.05)
                return
            if self.proc.poll() is not None:
                raise RuntimeError('engine exited; see the runtime log')
            time.sleep(.005)
        raise RuntimeError('step timed out')

    def until(self, pred, limit_s, chunk=4):
        for _ in range(int(limit_s * 20 / chunk)):
            if pred():
                return True
            self.step(chunk)
        return pred()

    def seahorses(self):
        rows = []
        for s in range(4):
            if self.cell(s, 'init') == 0:
                rows.append({'seahorse': s, 'shown': False})
                continue
            yaw = 2 * math.pi * self.cell(s, 'yaw')
            cx, cy = self.cell(s, 'cx'), self.cell(s, 'cy')
            wx = self.cell(s, 'x') + math.cos(yaw) * cx - math.sin(yaw) * cy
            wy = self.cell(s, 'y') + math.sin(yaw) * cx + math.cos(yaw) * cy
            held = self.cell(s, 'progress') >= 1
            rows.append({'seahorse': s, 'shown': True, 'state': STATES[int(self.cell(s, 'state'))],
                         'spot': int(self.cell(s, 'spot')), 'progress': round(self.cell(s, 'progress'), 3),
                         'status': int(self.cell(s, 'status')),
                         'position': [round(self.cell(s, k), 4) for k in ('x', 'y', 'z')],
                         'contact_error_mm': round(math.hypot(wx - self.cell(s, 'ax'), wy - self.cell(s, 'ay')) / .01, 3)
                         if held else None})
        return rows

    def shot(self, name, note=''):
        path = self.out / (name + '.png')
        self.cli.send({'op': 'screenshot', 'filename': str(path)})
        msg = self.cli.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=20)
        assert msg and msg.get('op') == 'screenshot_done', msg
        self.shots.append({'shot': name, 'note': note, 'time': round(self.value(1906, self.player), 2),
                           'visible': [self.value(1162), self.value(1163)],
                           'greeting': {'phase': self.value(1600), 'pair': self.value(1601), 'time': round(self.value(1602), 1)},
                           'seahorses': self.seahorses()})

    def view(self, x, y, z, side=1, dist=3.2):
        """Point the wide camshot at (x, y, z) from in front (the Phase 2 close-view technique)."""
        for actor, pos in ((self.idx['LookAt'], (x, y, z)), (self.idx['cs_wide'], (x - .5 * side, y - dist, z + .3))):
            for m, v in zip((3009, 3010, 3011), pos):
                self.cli.set_mailbox(m, v, idx=actor)

    def close(self):
        try:
            self.cli.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.logf.close()
            if self.xvfb:
                self.xvfb.terminate()
            self.level.unlink(missing_ok=True)
        text = (self.out / f'runtime-{self.tag}.log').read_text(errors='replace')
        return {'tag': self.tag, 'settings': self.receipt['settings'], 'shots': self.shots,
                'forth_errors': sum(text.count(s) for s in ('zforth compile error', 'zforth eval error', 'Unknown')),
                'fatal': sum(text.count(s) for s in ('Assertion', 'FATAL', 'abort', 'Segmentation'))}


def behaviour(args, out):
    r = Run(args, out, dict(water='saltwater', seahorses=2, greeting=True), 'behaviour')
    try:
        r.step(20)
        whip = (-3.1, -.75, 3.35)
        r.view(*whip)
        r.step(60)
        r.shot('hold', 'pair 1 holding the whip')
        for state, name in (('release', 'release'), ('swim', 'swim-close'), ('probe', 'probe'), ('grasp', 'grasp')):
            assert r.until(lambda: STATES[int(r.cell(1, 'state'))] == state, 60, chunk=2), state
            if state == 'grasp':
                r.step(14)                      # mid-grasp: the coil spreading from the tip
            elif state == 'swim':
                r.step(30)
            r.shot(name, f'seahorse 1: {state}')
        assert r.until(lambda: STATES[int(r.cell(1, 'state'))] == 'hold', 20, chunk=2)
        r.step(10)
        r.shot('hold-after', 'seahorse 1 holds its new spot')
        # Wide: whoever swims next, followed from further back.
        assert r.until(lambda: any(STATES[int(r.cell(s, 'state'))] == 'swim' for s in range(4)), 120)
        r.step(40)
        s = next(s for s in range(4) if STATES[int(r.cell(s, 'state'))] == 'swim')
        r.view(r.cell(s, 'x'), -.8, 3.2, dist=5.5)
        r.step(30)
        r.shot('swim-wide', 'a seahorse crossing between posts')
        # Greeting, forced due now.
        r.cli.set_mailbox(1603, .01, idx=r.director)
        assert r.until(lambda: r.value(1600) == 2, 240, chunk=8), 'greeting never reached the dance'
        r.view(-3.1, -.7, 3.25)
        r.step(80)
        r.shot('greet-0', 'a pair on the whip, opposite sides, offset heights')
        r.step(60)
        r.shot('greet-1', 'still greeting')
    finally:
        result = r.close()
    return result


def settings(args, out):
    results = []
    for tag, options in (('none', dict(water='saltwater', seahorses=0)), ('pair1', dict(water='saltwater', seahorses=1)),
                         ('pair2', dict(water='saltwater', seahorses=2)), ('freshwater', dict(water='freshwater'))):
        r = Run(args, out, options, tag)
        try:
            r.step(40)
            r.shot(f'wide-{tag}', tag)
        finally:
            results.append(r.close())
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--game', type=Path, default=ROOT / 'engine/wf_game')
    ap.add_argument('--port', type=int, default=17946)
    ap.add_argument('--seed', type=int, default=713)
    ap.add_argument('--age', type=float, default=150)
    ap.add_argument('--only', choices=('behaviour', 'settings'))
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    if args.only != 'settings':
        runs.append(behaviour(args, out))
    if args.only != 'behaviour':
        runs += settings(args, out)
    (out / 'capture.json').write_text(json.dumps({'level': 'aquarium_plants', 'vram': VRAM, 'runs': runs}, indent=2) + '\n')
    print(json.dumps({r['tag']: {'shots': len(r['shots']), 'forth_errors': r['forth_errors'], 'fatal': r['fatal']}
                      for r in runs}))


if __name__ == '__main__':
    main()
