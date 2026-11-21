#!/usr/bin/env python3
"""Real-engine checks for the Sea Stars settings (docs/plans/2026-11-20-sea-stars-settings.md).

Run in the Linux test container under xvfb-run, against an engine built there:

  form          Holding OK opens the settings form (the level stops updating while it is
                open), and the director's read of the settings overlay is valid: the entry seed
                the SeaStarsSettings class writes arrived, Seed 0 resolved to it, and exactly
                the default nine residents are active. Saves screenshots of the running level
                and of the form.
  parking-cost  Frame time of this level against a baseline standalone that has no parked
                residents (the 9-resident level of commit f8d95b37), alternating runs. Parked
                residents are scaled to nothing and skipped; this measures what they still cost.

The form's edits apply when the app's Back key runs, which exists only inside the menu bundle,
so applying an edit is covered by the zForth VM tests (tests/test_sea_stars_settings.py) and on
the device, not here.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'wflevels/aquarium_sea_stars')]
from debug_bridge_client import BridgeClient  # noqa: E402
import controller  # noqa: E402
from config import RESIDENTS, KIND_ORDER, DEFAULT_COUNTS  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('mode', choices=('form', 'parking-cost'))
ap.add_argument('--wf-game', type=Path, default=Path('/build/wf-game/src/engine/wf_game'))
ap.add_argument('--level', type=Path, default=ROOT / 'wflevels/aquarium_sea_stars-standalone.iff')
ap.add_argument('--baseline-level', type=Path, help='parking-cost: a standalone with no parked residents')
ap.add_argument('--out', type=Path, default=ROOT / 'docs/diagnostics/sea-stars-settings-2026-11-20')
ap.add_argument('--port', type=int, default=17996)
ap.add_argument('--frames', type=int, default=40, help='parking-cost: stepped frames per run')
ap.add_argument('--runs', type=int, default=3, help='parking-cost: runs of each level')
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
SECONDS_PER_STEPPED_FRAME = 3276 / 65536


class Engine:
    def __init__(self, level, port, log_path, paused):
        self.log = open(log_path, 'w')
        self.proc = subprocess.Popen(
            [str(a.wf_game), '-L' + str(level), '-rate20', '--debug-port', str(port), '--debug-bind', '127.0.0.1',
             '-width=1280', '-height=720', '--vram-width=4096', '--vram-height=2048', '--vram-slot-width=1024',
             '--vram-slot-height=1024', '--vram-perm-width=1024', '--vram-perm-height=1024'],
            cwd=ROOT, env=dict(os.environ, WF_REST_HOST='127.0.0.1', WF_REST_PORT=str(port + 1000)),
            stdout=self.log, stderr=subprocess.STDOUT,
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
        self.cli = BridgeClient(port=port, timeout=60)
        if paused:
            self.cli.send({'op': 'pause'})

    def watch(self, actor, boxes):
        for box in boxes:
            self.cli.watch(actor, box)

    def value(self, actor, box):
        with self.cli._lock:
            return self.cli.mailbox_values.get((actor, box), 0.)

    def until(self, predicate, what, limit):
        end = time.monotonic() + limit
        while not predicate():
            if self.proc.poll() is not None:
                raise RuntimeError('engine exited while waiting for ' + what)
            if time.monotonic() > end:
                raise RuntimeError('timed out waiting for ' + what)
            time.sleep(.1)

    def shot(self, path):
        self.cli.send({'op': 'screenshot', 'filename': str(path)})
        m = self.cli.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=60)
        assert m and m.get('op') == 'screenshot_done', m

    def step(self, player, frames):
        start = self.value(player, 1906)
        self.cli.send({'op': 'step', 'frames': frames})
        self.until(lambda: self.value(player, 1906) >= start + frames * SECONDS_PER_STEPPED_FRAME - .002,
                   'a step', max(60, frames * 3))

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
            self.log.close()


def indices_of(level_dir):
    return json.loads((ROOT / 'wflevels' / level_dir / 'actor-map.json').read_text())['indices']


def form():
    ix = indices_of('aquarium_sea_stars')
    player, director = ix['Player'], ix['Director']
    serial = {n: i for i, (n, _, _) in enumerate(RESIDENTS)}
    active = [controller.rcell('active', s) for s in range(len(RESIDENTS))]
    counts = [controller.COUNT_CELL[k] for k in KIND_ORDER]
    cells = (controller.SC['valid'], controller.SC['entry'], controller.SC['seed'], controller.SC['speedf'],
             controller.SC['glass'], *active, *counts)
    eng = Engine(a.level, a.port, a.out / 'form-runtime.log', paused=False)
    try:
        eng.watch(player, (1906,))
        eng.watch(director, cells)
        eng.until(lambda: eng.value(player, 1906) > 1.0 and eng.value(director, controller.SC['entry']) > 0,
                  'the level to run with an entry seed', 150)
        eng.shot(a.out / 'form-0-running.png')
        v = lambda box: eng.value(director, box)  # noqa: E731
        # The settings chain on the real engine.
        results = {
            'overlay answered (valid)': v(controller.SC['valid']) == 1,
            'entry seed written by SeaStarsSettings': 1 <= v(controller.SC['entry']) <= 32767,
            'Seed 0 resolved to the entry seed': v(controller.SC['seed']) == v(controller.SC['entry']),
            'counts are the defaults': [int(v(c)) for c in counts] == [DEFAULT_COUNTS[k] for k in KIND_ORDER],
            'speed factor x1 and glass On': v(controller.SC['speedf']) == 1 and v(controller.SC['glass']) == 2,
        }
        shipped = {n for n, k, _ in RESIDENTS[:9]}
        results['exactly the shipped nine are active'] = \
            {n for n, s in serial.items() if v(active[s]) == 1} == shipped
        # Holding OK opens the form; the level stops updating while it is open.
        eng.cli.inject_input('joystick1_raw', 1, duration_frames=-1)
        state = {'t': eng.value(player, 1906), 'since': time.monotonic()}

        def frozen():
            now = eng.value(player, 1906)
            if now != state['t']:
                state['t'], state['since'] = now, time.monotonic()
                return False
            return time.monotonic() - state['since'] > 4
        try:
            eng.until(frozen, 'the form to open (the level to stop updating)', 150)
            results['holding OK opens the settings form'] = True
            eng.cli.inject_input('joystick1_raw', 0, duration_frames=-1)
            eng.shot(a.out / 'form-1-settings-form.png')
        except RuntimeError as e:
            results['holding OK opens the settings form'] = False
            print('form did not open:', e)
        for name, ok in results.items():
            print(('PASS ' if ok else 'FAIL ') + name)
        (a.out / 'form-results.json').write_text(json.dumps(results, indent=2) + '\n')
        return 0 if all(results.values()) else 1
    finally:
        eng.close()


def timed_run(level, label):
    ix = json.loads((level.parent / 'aquarium_sea_stars/actor-map.json').read_text())['indices'] \
        if (level.parent / 'aquarium_sea_stars/actor-map.json').exists() else indices_of('aquarium_sea_stars')
    player = ix['Player']
    eng = Engine(level, a.port, a.out / f'parking-{label}.log', paused=True)
    try:
        eng.watch(player, (1906,))
        eng.step(player, 2)                    # the level is loaded and ticking
        eng.step(player, 10)                   # warm-up
        start = time.monotonic()
        eng.step(player, a.frames)
        return (time.monotonic() - start) / a.frames
    finally:
        eng.close()


def parking_cost():
    if not a.baseline_level or not a.baseline_level.exists():
        sys.exit('parking-cost needs --baseline-level (the 9-resident standalone)')
    samples = {'parked': [], 'baseline': []}
    for run in range(a.runs):
        for label, level in (('baseline', a.baseline_level), ('parked', a.level)):
            samples[label].append(timed_run(level, f'{label}-{run + 1}'))
            print(f'run {run + 1} {label}: {samples[label][-1] * 1000:.1f} ms per stepped frame', flush=True)
    base, parked = statistics.median(samples['baseline']), statistics.median(samples['parked'])
    result = {'frames': a.frames, 'runs': a.runs, 'baseline_ms': [x * 1000 for x in samples['baseline']],
              'parked_ms': [x * 1000 for x in samples['parked']],
              'median_baseline_ms': base * 1000, 'median_parked_ms': parked * 1000,
              'ratio': parked / base}
    (a.out / 'parking-cost.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(form() if a.mode == 'form' else parking_cost())
