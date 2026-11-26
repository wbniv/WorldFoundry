#!/usr/bin/env python3
"""Run the standalone lava lamp headless (inside the Linux container, under xvfb-run) and capture engine frames.

docs/plans/2026-11-26-lava-lamp.md, Phase 0 and Verification 6. Set the wall clock with WF_WALL_CLOCK as usual
(WF_CONTAINER_ENV="WF_WALL_CLOCK=2026-11-26T23:59:50"). Modes:

  --at HH:MM:SS (repeatable)   wait until the level's wall clock reaches each time, capture it and check the base
                               shows that time (the digit visibility cells), and that the colon is lit
  --expect-dashes              check the base shows the dashes (the clock was never set) and no digit
  --phase0                     the E1 spike: replace the director's script with one that tints the wax red and
                               green on alternate frames, pause the engine and step it one frame at a time, and
                               check that the captures alternate (vertex colours written by the Morph deformer
                               reach the screen every frame), and that the liquid, posed once at start, keeps its
                               violet (a pose persists when it is not repeated)
  --still SECONDS              run that long and capture one frame (for reviews)
  --property 'LavaLampSettings.Lava color=0'   passed to the engine (repeatable)

Captures go to build-docker/lava-lamp/captures/ (or --out DIR). Exit status 0 only when every check passes.

    scripts/in-linux-container.sh bash -c 'timeout 600 xvfb-run -a -s "-screen 0 1920x1080x24" python3 wflevels/lava_lamp/capture_pc.py --phase0'

(timeout keeps xvfb-run from being the container's PID 1, where it waits forever for Xvfb's ready signal.)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tests'), str(Path(__file__).resolve().parent)]
from debug_bridge_client import BridgeClient  # noqa: E402
import lamp as L  # noqa: E402

# The container-built engine: WF_GAME, else the Release build (fast to start), else the Debug one.
ENGINE = os.environ.get('WF_GAME') or next((p for p in ('/build/lava-rel/src/engine/wf_game', '/build/lava-dev/src/engine/wf_game')
                                            if os.path.exists(p)), '/build/wf-game/src/engine/wf_game')
PORT = 17811
MAILBOX = {'WALL_HOUR': 1922, 'WALL_MINUTE': 1923, 'WALL_SECOND': 1924, 'WALL_DAY': 1925}


def parse():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--at', action='append', default=[], metavar='HH:MM:SS')
    ap.add_argument('--expect-dashes', action='store_true')
    ap.add_argument('--phase0', action='store_true')
    ap.add_argument('--still', type=float, default=None, metavar='SECONDS')
    ap.add_argument('--property', action='append', default=[])
    ap.add_argument('--out', default='/build/lava-lamp/captures' if Path('/build').is_dir()
                    else str(ROOT / 'build-docker/lava-lamp/captures'))
    ap.add_argument('--size', default='1920x1080')
    ap.add_argument('--name', default='lava')
    return ap.parse_args()


class Run:
    def __init__(self, args):
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.ids = json.loads((ROOT / 'wflevels/lava_lamp/actor-map.json').read_text())['indices']
        w, h = args.size.split('x')
        self.log = (self.out / f'{args.name}.log').open('w')
        env = dict(os.environ, WF_REST_PORT='0')
        cmd = [ENGINE, '-L' + str(ROOT / 'wflevels/lava_lamp-standalone.iff'), '--debug-port', str(PORT),
               '--debug-bind', '127.0.0.1', f'-width={w}', f'-height={h}', '--no-fps']
        cmd += ['--property=' + p for p in args.property]
        self.proc = subprocess.Popen(cmd, env=env, stdout=self.log, stderr=subprocess.STDOUT, cwd=str(ROOT / 'wfsource/source/game'))
        self.c = BridgeClient(port=PORT, timeout=90)
        self.director = self.ids['Director']
        self.watched = set()

    def watch(self, mailbox):
        if mailbox not in self.watched:
            self.c.watch(self.director, mailbox)
            self.watched.add(mailbox)

    def value(self, mailbox, timeout=60.0):
        self.watch(mailbox)
        deadline = time.time() + timeout
        while (self.director, mailbox) not in self.c.mailbox_values:
            if self.proc.poll() is not None:
                raise SystemExit(f'the engine exited ({self.proc.returncode}); see {self.log.name}')
            if time.time() > deadline:
                raise SystemExit(f'no value for mailbox {mailbox}')
            self.c.wait_for(lambda m: m.get('op') == 'mailbox', timeout=1.0)
        return self.c.mailbox_values[(self.director, mailbox)]

    def shot(self, name):
        path = self.out / name
        self.c.send({'op': 'screenshot', 'filename': str(path)})
        msg = self.c.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error') and
                              (m.get('filename') == str(path) or m.get('what') == 'screenshot'), timeout=60)
        if not msg or msg.get('op') != 'screenshot_done':
            raise SystemExit(f'screenshot failed: {msg}')
        return path

    def close(self):
        self.c.close()
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def colours(path, box):
    """Counts of strongly red, strongly green and violet-ish pixels inside box = (x0, y0, x1, y1) as fractions."""
    from PIL import Image
    im = Image.open(path).convert('RGB')
    w, h = im.size
    x0, y0, x1, y1 = (int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))
    red = green = violet = n = 0
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            r, g, b = im.getpixel((x, y))
            n += 1
            red += r > 120 and g < 0.45 * r and b < 0.6 * r
            green += g > 120 and r < 0.45 * g and b < 0.8 * g
            violet += b > 60 and b > 1.3 * g and r > 0.8 * g
    return red / n, green / n, violet / n


GLOBE_BOX = (0.40, 0.18, 0.60, 0.70)       # the globe in a 16:9 frame (the lamp is centred, 88 % of the height)


def phase0(run: Run) -> list:
    bad = []
    source = (": p0-flip 199 read-mailbox 1 + dup 199 write-mailbox 2 mod ;\n"
              f"p0-flip if 1 0 0 else 0 1 0 then {L.WAX_RGB + 2} write-mailbox {L.WAX_RGB + 1} write-mailbox "
              f"{L.WAX_RGB} write-mailbox ll-tick")
    run.value(MAILBOX['WALL_SECOND'])              # the level is running: the director's cells answer
    run.c.send({'op': 'reload_script', 'idx': run.director, 'source': source})
    run.watch(199)
    run.c.wait_for(lambda m: m.get('op') == 'mailbox' and m.get('mailbox') == 199, timeout=30)
    run.c.send({'op': 'pause'})
    run.c.wait_for(lambda m: m.get('op') == 'paused', timeout=30)
    rows = []
    for k in range(8):
        before = run.c.mailbox_values.get((run.director, 199))
        run.c.send({'op': 'step', 'frames': 1})
        run.c.wait_for(lambda m: m.get('op') == 'mailbox' and m.get('mailbox') == 199 and m.get('value') != before, timeout=30)
        n = run.c.mailbox_values[(run.director, 199)]
        p = run.shot(f'phase0-{k}.png')
        red, green, violet = colours(p, GLOBE_BOX)
        rows.append((int(n), red, green, violet))
        print(f'frame counter {int(n)}: red {red:.3f} green {green:.3f} violet {violet:.3f}  {p.name}', flush=True)
    kinds = ['red' if r > g else 'green' for _n, r, g, _v in rows]
    alternate = all(kinds[k] != kinds[k + 1] for k in range(len(kinds) - 1))
    strong = all(max(r, g) > 0.01 for _n, r, g, _v in rows)
    if not (alternate and strong):
        bad.append(f'phase0: the wax colour did not alternate frame by frame: {kinds}')
    if not all(v > 0.05 for *_x, v in rows):
        bad.append('phase0: the liquid (posed once, at start) lost its violet')
    run.c.send({'op': 'resume'})
    return bad


def digits_at(run: Run):
    return [[v for v in range(10) if run.value(L.VIS_DIGIT0 + 10 * p + v) == 1] for p in range(4)]


def next_frame(run: Run):
    """Wait for the next broadcast of WALL_SECOND (it changes every frame while the clock runs)."""
    before = run.value(MAILBOX['WALL_SECOND'])
    msg = run.c.wait_for(lambda m: m.get('op') == 'mailbox' and m.get('mailbox') == MAILBOX['WALL_SECOND']
                         and m.get('value') != before, timeout=30)
    if not msg:
        raise SystemExit('no frame after the clock moved')


def wait_until(run: Run, hms: str):
    h, m, s = (int(x) for x in hms.split(':'))
    target = h * 3600 + m * 60 + s
    deadline = time.time() + 120
    while time.time() < deadline:
        now = run.value(MAILBOX['WALL_HOUR']) * 3600 + run.value(MAILBOX['WALL_MINUTE']) * 60 + run.value(MAILBOX['WALL_SECOND'])
        late = (now - target) % 86400
        if late < 1.5:
            return
        if late < 600:
            raise SystemExit(f'the wall clock was already past {hms} when the level started; start WF_WALL_CLOCK earlier')
        run.c.wait_for(lambda msg: msg.get('op') == 'mailbox', timeout=1.0)
    raise SystemExit(f'the wall clock did not reach {hms}')


def main() -> int:
    args = parse()
    run = Run(args)
    bad = []
    try:
        # Watch every cell read below before anything is read, so a reading taken at one moment is current for all of
        # them (watching one at a time spreads the reads over many frames, across a minute change).
        cells = list(MAILBOX.values()) + [L.VIS_COLON, L.VIS_DASH] + [L.VIS_DIGIT0 + k for k in range(40)]
        for c in cells:
            run.watch(c)
        for c in cells:
            run.value(c)
        if args.phase0:
            bad += phase0(run)
        for hms in args.at:
            wait_until(run, hms)
            next_frame(run)                     # the director switches the holes in the frame after the clock moves
            want = [[int(c)] for c in hms.replace(':', '')[:4]]
            got = digits_at(run)
            p = run.shot(f'{args.name}-{hms.replace(":", "")}.png')
            colon, dash = run.value(L.VIS_COLON), run.value(L.VIS_DASH)
            print(f'{hms}: digits {got}, colon {colon}, dashes {dash}  {p}', flush=True)
            if got != want or colon != 1 or dash != 0:
                bad.append(f'{hms}: the base shows {got} (colon {colon}, dashes {dash}), want {want}')
        if args.expect_dashes:
            run.value(MAILBOX['WALL_DAY'])
            next_frame(run)
            got = digits_at(run)
            dash, colon = run.value(L.VIS_DASH), run.value(L.VIS_COLON)
            p = run.shot(f'{args.name}-dashes.png')
            print(f'clock not set (day {run.value(MAILBOX["WALL_DAY"])}): digits {got}, colon {colon}, dashes {dash}  {p}')
            if dash != 1 or colon != 0 or any(got):
                bad.append(f'expected dashes: digits {got}, colon {colon}, dashes {dash}')
        if args.still is not None:
            run.value(MAILBOX['WALL_SECOND'])
            time.sleep(args.still)
            print('captured', run.shot(f'{args.name}-still.png'))
    finally:
        run.close()
    for b in bad:
        print('FAIL', b)
    print('PASS' if not bad else f'FAIL: {len(bad)}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
