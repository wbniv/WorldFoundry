#!/usr/bin/env python3
"""run_swim_spike.py — aquarium Phase 1 (steps 5–8): build the swim spike and drive it over the bridge.

Plan: docs/plans/2026-09-30-aquarium-level.md § Verification, Phase 1.

For each WORLD_SCALE given (default 10 then 1): build the level (blender_create_swim_spike.py +
build_level_binary.sh), run wf_game, and over the debug bridge (TCP 7777) watch the fish's
X/Y/Z_POS while injecting joystick input:

  step 5  no input for 10 s                      → Z drift vs 1 % of tank height
  step 6  UP 6 s, DOWN 6 s                       → stops under the water-line clamp / on the sand
          RIGHT, LEFT, C (+Y), B (−Y) 5 s each   → never past a wall's inner face
  step 7  RIGHT then LEFT (script writes ROTATION_C 0 / 0.5) → screenshots, tail side flips

Prints a summary per scale and leaves screenshots + logs in $OUT (default ~/tmp/aquarium-swim).
Usage: python3 wflevels/aquarium_swim_spike/run_swim_spike.py [scale ...] [--shell=one] [--fish=box]
"""
import json
import os
import re
import resource
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
MAIN = os.path.expanduser('~/WorldFoundry-wbniv')
sys.path.insert(0, os.path.join(REPO, 'tests'))
from debug_bridge_client import BridgeClient                       # noqa: E402

WF_GAME = os.environ.get('WF_GAME') or next(
    p for p in (os.path.join(REPO, 'engine', 'wf_game'), os.path.join(MAIN, 'engine', 'wf_game'))
    if os.path.exists(p))
LIBS = os.path.join(os.path.dirname(WF_GAME), 'libs')
GAME_CWD = os.path.join(REPO, 'wfsource', 'source', 'game')
LEVEL = 'aquarium_swim_spike'
LEVEL_IFF = os.path.join(REPO, 'wflevels', LEVEL + '-standalone.iff')
OUT = os.environ.get('OUT', os.path.expanduser('~/tmp/aquarium-swim'))
FISH_BOX = '--fish=box' in sys.argv

X_POS, Y_POS, Z_POS = 3009, 3010, 3011
TIME = 1906                                      # level clock (s); -rate20 → 0.05 s per frame
BTN = {'UP': 2048, 'DOWN': 4096, 'RIGHT': 8192, 'LEFT': 16384, 'B': 2, 'C': 4}


def limit_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def build(scale, shell_one):
    env = dict(os.environ, WORLD_SCALE=str(scale))
    args = (['shell=one'] if shell_one else []) + (['fish=box'] if FISH_BOX else [])
    r = subprocess.run(['blender', '--background', '--python-exit-code', '1', '--python',
                        os.path.join(HERE, 'blender_create_swim_spike.py'), '--', *args],
                       cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stdout[-3000:] + r.stderr[-3000:])
    info = next(l for l in r.stdout.splitlines() if l.startswith('[swim_spike] WORLD_SCALE'))
    print(info)
    subprocess.run(['bash', os.path.join(REPO, 'wftools', 'wf_blender', 'build_level_binary.sh'), LEVEL],
                   cwd=REPO, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    nums = dict(re.findall(r'(ZMAX|V)=([-\d.]+)', info))
    inner = re.search(r'inner x ±([\d.]+) y ±([\d.]+) sand ([\d.]+) water ([\d.]+)', info).groups()
    lev = open(os.path.join(HERE, LEVEL + '.lev')).read()
    names = re.findall(r"\{ 'OBJ'\s*\{ 'NAME' \"([^\"]+)\" \}", lev)
    i = lev.index("'NAME' \"Player\"")
    box = re.search(r"Global Bounding Box\" \} \{ 'DATA' ([^/]*)//", lev[i:i + 3000]).group(1)
    fish_box = [float(v) for v in re.findall(r'(-?[\d.]+)\(1\.15\.16\)', box)]
    return {'zmax': float(nums['ZMAX']), 'v': float(nums['V']), 'ix': float(inner[0]),
            'iy': float(inner[1]), 'sand': float(inner[2]), 'water': float(inner[3]),
            'player_idx': names.index('Player') + 1, 'fish_box': fish_box}


class Session:
    def __init__(self, tag, idx):
        self.tag, self.idx = tag, idx
        self.log = open(os.path.join(OUT, f'{tag}.log'), 'w')
        self.p = subprocess.Popen([WF_GAME, '--frame-step-smoke=1000000', '-rate20', f'-L{LEVEL_IFF}'],
                                  cwd=GAME_CWD, stdout=self.log, stderr=subprocess.STDOUT,
                                  env=dict(os.environ, LD_LIBRARY_PATH=LIBS), preexec_fn=limit_core)
        try:
            self.c = BridgeClient(timeout=20)
        except RuntimeError:
            self.p.wait(10)
            self.log.flush()
            text = open(os.path.join(OUT, f'{tag}.log'), errors='replace').read().splitlines()
            raise SystemExit(f'ENGINE ABORTED before the bridge came up (exit {self.p.returncode}): ' +
                             ' | '.join(l.strip() for l in text if 'AssertMsg' in l or 'length.Abs' in l))
        self.series = []                      # (t, mailbox, value)
        self.c._listeners = []
        orig = self.c._dispatch

        self.now = 0.0                        # latest level time seen

        def rec(msg):
            if msg.get('op') == 'mailbox' and msg.get('idx') == idx:
                if msg['mailbox'] == TIME:        # std::set order: TIME (1906) precedes 30xx in a batch
                    self.now = float(msg['value'])
                else:
                    self.series.append((self.now, msg['mailbox'], float(msg['value'])))
            orig(msg)
        self.c._dispatch = rec
        for mb in (TIME, X_POS, Y_POS, Z_POS):
            self.c.watch(idx, mb)

    def wait_sim(self, secs):
        """Block until the level clock has advanced `secs` (it runs faster than wall time under
        -rate20, which fixes dt at 0.05 s but does not throttle frames)."""
        t0 = self.now
        deadline = time.time() + 120
        while self.now < t0 + secs:
            if time.time() > deadline:
                raise RuntimeError(f'level clock stuck at {self.now}')
            time.sleep(0.005)
        return t0, self.now

    def pos(self):
        v = self.c.mailbox_values
        return tuple(v.get((self.idx, mb)) for mb in (X_POS, Y_POS, Z_POS))

    def hold(self, button, secs):
        # Frame-exact: the engine counts the override down per frame (-rate20 → 0.05 s/frame), so a
        # hold lasts exactly secs/0.05 frames however far the bridge's view of the clock lags.
        if button:
            self.c.inject_input('joystick1_raw', BTN[button], duration_frames=round(secs / 0.05))
        t0, t1 = self.wait_sim(secs + 0.2)                # + 4 frames so the next hold starts clean
        return self.window(t0, t1)

    def window(self, t0, t1):
        out = {X_POS: [], Y_POS: [], Z_POS: []}
        for t, mb, v in self.series:
            if t0 <= t <= t1:
                out[mb].append(v)
        return out

    def shot(self, name):
        fn = os.path.join(OUT, f'{self.tag}-{name}.png')
        self.c.send({'op': 'screenshot', 'filename': fn})
        r = self.c.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=5)
        return fn if r and r.get('op') == 'screenshot_done' else f'FAILED {r}'

    def close(self):
        self.c.close()
        self.p.terminate()
        self.p.wait(10)


def rng(vals):
    return (min(vals), max(vals)) if vals else (None, None)


# (name, button or None, level seconds, screenshot-after or None)
PHASES = [
    ('idle',        None,    10.0, 'idle'),           # step 5
    ('up',          'UP',     6.0, 'top'),            # step 6: into the water-line clamp
    ('down',        'DOWN',   6.0, None),             #         onto the sand
    ('rest',        None,     1.0, None),
    ('rise',        'UP',     0.6, None),             #         back to mid-water
    ('settle',      None,     2.0, None),
    ('right',       'RIGHT',  5.0, 'facing-right'),   # step 6 walls + step 7 heading
    ('off-wall',    'LEFT',   1.5, None),
    ('glide',       None,     2.0, None),             # release mid-tank: drag-only glide
    ('left',        'LEFT',   6.0, 'facing-left'),
    ('back',        'C',      5.0, None),
    ('front',       'B',      5.0, 'front'),
    ('end',         None,     1.0, None),
]


def run(scale, shell_one):
    geo = build(scale, shell_one)
    tag = f'phase1-x{scale:g}' + ('-shellone' if shell_one else '') + ('-box' if FISH_BOX else '')
    s = Session(tag, geo['player_idx'])
    res = {'scale': scale, 'geo': geo, 'phases': [], 'shots': {}}
    try:
        time.sleep(1.0)
        s.wait_sim(1.5)                                   # load + camera settle (level time)
        res['spawn'] = s.pos()
        start = s.pos()
        for name, button, secs, shot in PHASES:
            w = s.hold(button, secs)
            res['phases'].append((name, button, secs, start, s.pos(),
                                  rng(w[X_POS]), rng(w[Y_POS]), rng(w[Z_POS])))
            start = s.pos()
            if shot:
                res['shots'][name] = s.shot(shot)
    finally:
        s.close()
    log = open(os.path.join(OUT, f'{tag}.log'), errors='replace').read()
    res['jolt'] = [l for l in log.splitlines() if l.startswith('jolt: character')]
    res['errors'] = [l for l in log.splitlines() if re.search(r'compile error|Assert|assert', l)][:5]
    return res


def fmt(v):
    return '   None' if v is None else f'{v:7.3f}'


def report(r):
    g = r['geo']
    col = g['water'] - g['sand']
    print(f"\n## WORLD_SCALE = {r['scale']:g}   (player idx {g['player_idx']}; walls x ±{g['ix']:.4f}, "
          f"y ±{g['iy']:.4f}; sand {g['sand']:.4f}; water {g['water']:.4f}; clamp ZMAX {g['zmax']:.4f}; "
          f"V {g['v']:.4f})")
    for l in r['jolt'] + r['errors']:
        print(l)
    print(f"{'phase':9s} {'btn':5s} {'s':>4s}  {'start x,y,z':>23s}  {'end x,y,z':>23s}  "
          f"{'x range':>17s} {'y range':>17s} {'z range':>17s}")
    by = {}
    for name, btn, secs, a, b, xr, yr, zr in r['phases']:
        by[name] = (a, b, xr, yr, zr)
        print(f"{name:9s} {btn or '-':5s} {secs:4.1f}  {''.join(fmt(v) for v in a):>23s}  "
              f"{''.join(fmt(v) for v in b):>23s}  {fmt(xr[0])}{fmt(xr[1])}   {fmt(yr[0])}{fmt(yr[1])}   "
              f"{fmt(zr[0])}{fmt(zr[1])}")
    a, b, xr, yr, zr = by['idle']
    drift = max(abs(v - a[2]) for v in (zr if zr[0] is not None else (a[2],)) + (b[2],))
    print(f"step 5: idle Z drift {drift:.5f} vs 1 % of the water column {col / 100:.5f} → "
          f"{'PASS' if drift < col / 100 else 'FAIL'}")
    checks = [
        ('UP stops at the clamp', by['up'][1][2], g['zmax'], lambda got, lim: got <= lim + 1e-3),
        ('DOWN stops on the sand', by['down'][1][2], g['sand'], lambda got, lim: got >= lim - 1e-3),
        ('RIGHT: capsule stays inside the right wall', by['right'][2][1], g['ix'], lambda got, lim: got < lim),
        ('LEFT: capsule stays inside the left wall', by['left'][2][0], -g['ix'], lambda got, lim: got > lim),
        ('C: inside the back wall', by['back'][3][1], g['iy'], lambda got, lim: got < lim),
        ('B: inside the front collider', by['front'][3][0], -g['iy'], lambda got, lim: got > lim),
    ]
    for label, got, lim, ok in checks:
        print(f"step 6: {label}: {got if got is None else round(got, 4)} vs {lim:.4f} → "
              f"{'PASS' if got is not None and ok(got, lim) else 'FAIL'}")
    fb = g['fish_box']                                  # mesh extents (local): x0 y0 z0 x1 y1 z1
    print(f"fish mesh extents (local, from the .lev BOX3): x [{fb[0]:.4f}, {fb[3]:.4f}] y [{fb[1]:.4f}, "
          f"{fb[4]:.4f}] z [{fb[2]:.4f}, {fb[5]:.4f}]; levcomp raises any span < 0.25 m to 0.25 (min side)")
    vis = [('right wall', g['ix'] - (by['right'][2][1] + fb[3])),
           ('left wall', (by['left'][2][0] - fb[3]) - (-g['ix'])),      # facing -X (C = 0.5): nose at X - x1
           ('back wall', g['iy'] - (by['back'][3][1] + fb[4])),
           ('front glass', (by['front'][3][0] + fb[1]) - (-g['iy'])),
           ('sand', by['down'][1][2] - g['sand']),
           ('water line', g['water'] - (by['up'][1][2] + fb[5]))]
    print('visual gap mesh→surface at the limit (negative = the mesh pokes through):  ' +
          '  '.join(f'{n} {v:+.4f}' for n, v in vis))
    ga, gb = by['glide'][0], by['glide'][1]
    print(f"glide: released at x {ga[0]:.4f}, 2 s later x {gb[0]:.4f} → {abs(gb[0] - ga[0]):.4f}")
    print(f"step 7 screenshots: {r['shots'].get('right')}  {r['shots'].get('left')}")


def main():
    os.makedirs(OUT, exist_ok=True)
    shell_one = '--shell=one' in sys.argv
    scales = [float(a) for a in sys.argv[1:] if not a.startswith('--')] or [10.0, 1.0]
    for sc in scales:
        try:
            report(run(sc, shell_one))
        except SystemExit as e:
            print(f'\n## WORLD_SCALE = {sc:g}\n{e}')


if __name__ == '__main__':
    main()
