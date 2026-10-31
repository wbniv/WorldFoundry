#!/usr/bin/env python3
"""Desktop screenshots of every UI-font text user (verification step 7 of
docs/plans/2026-10-17-settings-editor-font.md).

Runs the Release engine/wf_game at 1920x1080 (the UI font's own canvas, so the atlas
lands 1:1) under a display (Xvfb in the container) and saves PNGs to OUT:

  menu-fishtank      the aquarium app's level menu, cursor on Planted Tank (--capture-frame)
  planted-hud        the Planted Tank running: the HUD strip and the FPS counter
  chooser            baseline: hold OK, the object chooser (Pick in 3D first)
  pick-tags          Pick in 3D: the highlight tag
  form               the chooser's next row opened: the settings form
  form-error         A on a text field with no browser connected: the error line
  hud-banner         Q*bert's HUD with the moon launch banner and position block forced on
  hud-game-over      Q*bert's GAME OVER banner and the high-score table

    scripts/in-linux-container.sh <Xvfb wrapper> python3 tests/ui_font_screenshots.py --out DIR

The phone pairing overlay is drawn only by the Android TV app, so it is not here: the
level-menu and phone-overlay host tests composite it from the same glyph quads.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from debug_bridge_client import BridgeClient  # noqa: E402

OK, DOWN, RIGHT, LEFT = 1, 1 << 12, 1 << 13, 1 << 14
SIZE = ['-width=1920', '-height=1080']
AQUARIUM_VRAM = (ROOT / 'android/app/src/aquarium/assets/wf_args.txt').read_text().split()
BASELINE_VRAM = ['--vram-width=5120', '--vram-height=2048', '--vram-slot-width=1024', '--vram-slot-height=1024',
                 '--vram-perm-width=1024', '--vram-perm-height=1024']


def menu_capture(out, cwd):
    """The fishtank menu from the aquarium app's own bundle. The debug bridge is not served while the
    menu runs, so this grabs the X screen (the window fills the 1920x1080 Xvfb screen)."""
    from PIL import ImageGrab
    shutil.copy(ROOT / 'wflevels/aquarium-menu-cd.iff', cwd / 'cd.iff')
    path = out / 'menu-fishtank.png'
    path.unlink(missing_ok=True)
    log = (out / 'menu-fishtank.log').open('w')
    # The first press only primes the menu; five more reach Planted Tank. Then hold still and quit.
    proc = subprocess.Popen([str(ROOT / 'engine/wf_game'), *AQUARIUM_VRAM, *SIZE,
                             '--menu-input=down,down,down,down,down,down,wait:900,quit'], cwd=cwd, stdout=log,
                            stderr=subprocess.STDOUT)
    time.sleep(6)
    if proc.poll() is not None:
        raise RuntimeError('wf_game exited; see ' + log.name)
    ImageGrab.grab(xdisplay=os.environ['DISPLAY']).crop((0, 0, 1920, 1080)).save(path)
    proc.wait(timeout=120)
    print('captured', path, flush=True)


class Session:
    def __init__(self, out, port, log_name, args, cwd):
        self.out = out
        self.log = (out / log_name).open('w')
        self.proc = subprocess.Popen([str(ROOT / 'engine/wf_game'), *args, '--debug-port', str(port),
                                      '--debug-bind', '127.0.0.1', *SIZE], cwd=cwd, stdout=self.log,
                                     stderr=subprocess.STDOUT)
        self.bridge = BridgeClient(port=port, timeout=60)
        self.settle(3)

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
        path.unlink(missing_ok=True)
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
    ap.add_argument('--out', type=Path, default=ROOT / 'docs/diagnostics/ui-font/desktop')
    ap.add_argument('--port', type=int, default=7796)
    ap.add_argument('--only', nargs='+', choices=('menu', 'planted', 'baseline', 'hud'),
                    default=['menu', 'planted', 'baseline', 'hud'],
                    help='hud needs an engine built with -DDESIGNER_CHEATS=1 (display.cc draws the HUD only then)')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('DISPLAY', ':0')
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        if 'menu' in args.only:
            menu_capture(args.out, cwd)
        if 'planted' in args.only:
            planted(args, cwd)
        if 'baseline' in args.only:
            baseline(args, cwd)
        if 'hud' in args.only:
            hud(args, cwd)


def planted(args, cwd):
    if True:

        # The Planted Tank: its HUD strip shows while the tank runs (planted::state().active).
        s = Session(args.out, args.port, 'planted.log',
                    [*AQUARIUM_VRAM, '-L' + str(ROOT / 'wflevels/aquarium_plants-standalone.iff')], cwd)
        try:
            s.settle(4)
            s.shot('planted-hud')
        finally:
            s.close()



def baseline(args, cwd):
    if True:
        # Baseline: the chooser, Pick in 3D's tags, the form, and an error line.
        s = Session(args.out, args.port + 1, 'baseline.log',
                    [*BASELINE_VRAM, '-L' + str(ROOT / 'wflevels/baseline-standalone.iff')], cwd)
        try:
            s.hold(OK, 1.4)
            s.shot('chooser')
            s.tap(OK)                 # row 0: Pick in 3D
            s.shot('pick-tags')
        finally:
            s.close()
        s = Session(args.out, args.port + 2, 'baseline-form.log',
                    [*BASELINE_VRAM, '-L' + str(ROOT / 'wflevels/baseline-standalone.iff')], cwd)
        try:
            s.hold(OK, 1.4)
            s.tap(DOWN)               # Field types (row 0 is Pick in 3D)
            s.tap(OK)
            s.shot('form')
            s.tap(LEFT)               # the section rail
            for _ in range(3):
                s.tap(DOWN)           # Numbers, Choices, Switches, Text
            s.tap(RIGHT)              # into the values: Caption, a text field
            s.tap(OK)                 # no browser on the desktop: the form says so
            s.shot('form-error')
        finally:
            s.close()



def hud(args, cwd):
    if True:
        # display.cc's HUD on Q*bert, which turns it on (LIVES); the banners forced through the mailboxes.
        s = Session(args.out, args.port + 3, 'qbert.log',
                    ['-L' + str(ROOT / 'wflevels/qbert_practice-standalone.iff')], cwd)
        try:
            s.settle(2)
            for mailbox, value in ((1875, 1), (1881, 1), (1882, 5)):
                s.bridge.set_mailbox(mailbox, value)
            s.settle(1)
            s.shot('hud-banner')
            for mailbox in (1875, 1881):
                s.bridge.set_mailbox(mailbox, 0)
            s.bridge.set_mailbox(420, 1)
            s.settle(1)
            s.shot('hud-game-over')
        finally:
            s.close()


if __name__ == '__main__':
    main()
