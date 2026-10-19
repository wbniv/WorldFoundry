#!/usr/bin/env python3
"""Desktop screenshots of Pick in 3D on the baseline level (verification step 10 of
docs/plans/2026-10-16-runtime-object-editing.md).

Runs Release wf_game on wflevels/baseline-standalone.iff, drives it with injected
joystick input over the debug bridge and saves PNGs to OUT:
  a-chooser        the chooser, Pick in 3D first
  b-pick           pick mode with the first highlight
  c-after-right    the highlight after the Right arrow
  d1-same-spot     the "2 objects here" bracket
  d2-short-list    OK on it: the short list of just those
  e-nothing        a second session with the camera turned away
Needs a display (Xvfb in the container): see -h.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from debug_bridge_client import BridgeClient  # noqa: E402

OK, RIGHT, LEFT = 1, 1 << 13, 1 << 14


class Session:
    def __init__(self, out, port, log_name):
        self.out = out
        self.log = (out / log_name).open('w')
        args = [str(ROOT / 'engine/wf_game'), '-L' + str(ROOT / 'wflevels/baseline-standalone.iff'),
                '--debug-port', str(port), '--debug-bind', '127.0.0.1', '-width=1280', '-height=720',
                '--vram-width=5120', '--vram-height=2048', '--vram-slot-width=1024', '--vram-slot-height=1024',
                '--vram-perm-width=1024', '--vram-perm-height=1024']
        self.proc = subprocess.Popen(args, cwd=out, stdout=self.log, stderr=subprocess.STDOUT)
        self.bridge = BridgeClient(port=port, timeout=20)
        self.settle(2)

    def settle(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError('wf_game exited; see ' + self.log.name)
            time.sleep(.05)

    def hold(self, bits, seconds):
        self.bridge.inject_input('joystick1_raw', bits, -1)
        self.settle(seconds)
        self.bridge.inject_input('joystick1_raw', 0, -1)
        self.settle(.4)

    def tap(self, bits):
        self.hold(bits, .25)

    def shot(self, name):
        path = self.out / (name + '.png')
        if path.exists():
            path.unlink()
        self.bridge.send(dict(op='screenshot', filename=str(path)))
        done = self.bridge.wait_for(lambda m: m.get('op') == 'screenshot_done', timeout=10)
        if not done or not path.exists():
            raise RuntimeError('no screenshot ' + str(path))
        print('captured', path, flush=True)

    def close(self):
        try:
            self.bridge.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.log.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, default=ROOT / 'docs/plans/2026-10-16-runtime-object-editing/evidence/picker')
    ap.add_argument('--port', type=int, default=7786)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('DISPLAY', ':0')

    s = Session(args.out, args.port, 'desktop-session1.log')
    try:
        s.hold(OK, 1.4)            # Hold OK: the chooser (three owners)
        s.shot('a-chooser')
        s.tap(OK)                  # row 0: Pick in 3D
        s.shot('b-pick')
        s.tap(RIGHT)
        s.shot('c-after-right')
        s.shot('d1-same-spot')     # the highlight now sits on the shared bracket
        s.tap(OK)
        s.shot('d2-short-list')
    finally:
        s.close()

    s = Session(args.out, args.port + 1, 'desktop-session2.log')
    try:
        # Debug-assisted setup: the player (and its follow camera) far from the owners, facing away.
        ids = __import__('json').loads((ROOT / 'wflevels/baseline/actor-map.json').read_text())['indices']
        s.bridge.send(dict(op='scene:set_transform', idx=ids['Player'], pos=[40, 40, 1.1]))
        s.settle(1.5)
        s.hold(OK, 1.4)
        s.tap(OK)
        s.shot('e-nothing-in-view')
    finally:
        s.close()


if __name__ == '__main__':
    main()
