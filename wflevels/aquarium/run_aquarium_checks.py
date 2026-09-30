#!/usr/bin/env python3
"""run_aquarium_checks.py — aquarium Phase 2 verification: capture frame A (step 11) and hold
the fish into every wall for 5 s (step 13), over the debug bridge.

Plan: docs/plans/2026-09-30-aquarium-level.md § Verification, Phase 2–3.

Runs the already-built wflevels/aquarium-standalone.iff (build it with `task aquarium-level`)
under -rate20 and drives the Player with frame-exact held buttons, reusing the Phase 1
bridge harness (wflevels/aquarium_swim_spike/run_swim_spike.py `Session`). Prints each
phase's end position and the extremes of the fish's box over the whole run against the
tank's inner faces, the sand and the water line; screenshots land in $OUT
(default ~/tmp/aquarium-phase2).

It also checks the anemone's back/front tentacle split: the fish is parked inside the crown
(X_POS/Z_POS written over the bridge, as the fish's own clamp does) and must not be pushed,
then swims out through the crown at mid-crown height and back again without leaving its line.

Usage: python3 wflevels/aquarium/run_aquarium_checks.py [-h]
Needs: DISPLAY (wf_game opens a GL window), wf_game (WF_GAME= to override; falls back to the
main checkout's engine/wf_game).
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__)
    raise SystemExit(0)
sys.path.insert(0, HERE)                        # first: the spike dir has its own aquarium_constants
sys.path.append(os.path.join(REPO, 'wflevels', 'aquarium_swim_spike'))
import aquarium_constants as C                                     # noqa: E402
import run_swim_spike as rss                                       # noqa: E402

LEVEL_LEV = os.path.join(HERE, 'aquarium.lev')
rss.LEVEL_IFF = os.path.join(REPO, 'wflevels', 'aquarium-standalone.iff')
rss.OUT = os.environ.get('OUT', os.path.expanduser('~/tmp/aquarium-phase2'))

# The crown: tentacles rise from the column top (z 1.665 m) to the bulbs (≤ 2.44 m), at y ±0.36 m.
CROWN_PARK = {3009: C.ANEMONE_X, 3011: 1.95}     # fish box z 1.95–2.31: inside the crown, above the disc

# (name, button / None / {mailbox: value} to place the fish, level seconds, screenshot-after or
# None). Each wall hold lasts long enough to reach the wall and then press on it for ≥ 5 s
# (cruise 2.74 m/s).
PHASES = [
    ('settle', None,     2.0, 'frame-a'),        # step 11: camshot A, fish at spawn
    ('crown',  CROWN_PARK, 2.0, 'in-crown'),     # parked between the tentacle sets: no push
    ('right',  'RIGHT',  7.0, 'right-wall'),     # out through the crown at z 1.95, 3 m to the X clamp
    ('left',   'LEFT',  10.0, 'left-wall'),      # 10.9 m, back through the crown at z 1.95
    ('back',   'C',      6.0, 'back-wall'),
    ('front',  'B',      7.0, 'front-glass'),
    ('up',     'UP',     7.0, 'water-line'),
    ('down',   'DOWN',   7.0, 'sand'),
    ('end',    None,     1.0, None),
]


def lev_box(name):
    lev = open(LEVEL_LEV).read()
    i = lev.index(f"'NAME' \"{name}\"")
    box = re.search(r"Global Bounding Box\" \} \{ 'DATA' ([^/]*)//", lev[i:i + 3000]).group(1)
    return [float(v) for v in re.findall(r'(-?[\d.]+)\(1\.15\.16\)', box)]


def main():
    os.makedirs(rss.OUT, exist_ok=True)
    lev = open(LEVEL_LEV).read()
    names = re.findall(r"\{ 'OBJ'\s*\{ 'NAME' \"([^\"]+)\" \}", lev)
    idx = names.index('Player') + 1
    fb = lev_box('Player')                                   # x0 y0 z0 x1 y1 z1, local
    s = rss.Session('phase2', idx)
    rows, allpos = [], []
    try:
        time.sleep(1.0)
        s.wait_sim(1.5)
        start = s.pos()
        spawn_drift = max(abs(a - b) for a, b in zip(start, C.FISH_SPAWN))
        for name, button, secs, shot in PHASES:
            if isinstance(button, dict):                     # place: teleport, then no input
                for mb, v in button.items():
                    s.c.set_mailbox(mb, v, idx=idx)
                s.wait_sim(0.3)
                start = s.pos()
                button = None
            s.hold(button, secs)
            end = s.pos()
            rows.append((name, button, secs, start, end))
            start = end
            if shot:
                print(f'screenshot {shot}: {s.shot(shot)}')
        allpos = s.series
    finally:
        s.close()
    log = open(os.path.join(rss.OUT, 'phase2.log'), errors='replace').read().splitlines()
    for l in log:
        if l.startswith('jolt: character') or re.search(r'compile error|Assert', l):
            print(l)
    # wf_game's window is on the real desktop (no Xvfb on this host): a key typed while it has
    # focus reaches the fish (seen once: +2.47 m of un-commanded RIGHT before the first hold).
    # The log names only UNMAPPED keys ("unknown key …"), which cannot move the fish, so they
    # only show the window had focus. The witness is motion the harness did not command: drift
    # from spawn before the first hold, any motion in a no-button phase, and motion off the held
    # button's own axis.
    keys = [l for l in log if re.match(r'unknown key \w+ pressed', l)]
    axis = {'RIGHT': 0, 'LEFT': 0, 'C': 1, 'B': 1, 'UP': 2, 'DOWN': 2}
    stray = [(name, k, round(b[k] - a[k], 4)) for name, btn, _, a, b in rows for k in range(3)
             if k != axis.get(btn) and abs(b[k] - a[k]) > 1e-3]
    print(f'desktop (unmapped) key events in the engine log: {len(keys)}; position before the first hold '
          f'{tuple(round(v, 3) for v in rows[0][3])} vs spawn {C.FISH_SPAWN} (drift {spawn_drift:.3f}); '
          f'un-commanded motion: {stray or "none"}')
    clean = spawn_drift < 1e-3 and not stray
    print(f'run isolation: {"CLEAN" if clean else "CONTAMINATED by desktop input — rerun"}')
    print(f"{'phase':7s} {'btn':5s} {'s':>4s}  {'start x,y,z':>23s}  {'end x,y,z':>23s}")
    for name, btn, secs, a, b in rows:
        print(f"{name:7s} {btn or '-':5s} {secs:4.1f}  {''.join(rss.fmt(v) for v in a)}  {''.join(rss.fmt(v) for v in b)}")
    by = {3009: [], 3010: [], 3011: []}
    for _, mb, v in allpos:
        by[mb].append(v)
    ext = {k: (min(v), max(v)) for k, v in by.items() if v}
    ix, iy = C.INNER_X_M, C.INNER_Y_M
    checks = [
        ('fish box right edge vs right wall inner face', ext[3009][1] + fb[3], ix, lambda g, l: g <= l),
        ('fish box left edge vs left wall inner face', ext[3009][0] + fb[0], -ix, lambda g, l: g >= l),
        ('fish box back edge vs back wall inner face', ext[3010][1] + fb[4], iy, lambda g, l: g <= l),
        ('fish box front edge vs front glass plane', ext[3010][0] + fb[1], -iy, lambda g, l: g >= l),
        ('fish feet vs sand top', ext[3011][0] + fb[2], C.SAND_TOP_M, lambda g, l: g >= l - 1e-3),
        ('fish top vs water line', ext[3011][1] + fb[5], C.WATER_LINE_M, lambda g, l: g <= l),
    ]
    print(f'fish box (local, .lev BOX3): x [{fb[0]:.4f}, {fb[3]:.4f}] y [{fb[1]:.4f}, {fb[4]:.4f}] z [{fb[2]:.4f}, {fb[5]:.4f}]')
    print('origin extremes over the whole run: ' + '  '.join(
        f'{a} [{ext[k][0]:.4f}, {ext[k][1]:.4f}]' for a, k in (('x', 3009), ('y', 3010), ('z', 3011)) if k in ext))
    ok_all = True
    for label, got, lim, ok in checks:
        ok_i = ok(got, lim)
        ok_all &= ok_i
        print(f'step 13: {label}: {got:.4f} vs {lim:.4f} (gap {abs(lim - got):.4f}) → {"PASS" if ok_i else "FAIL"}')
    print(f'step 13: {"PASS" if ok_all and clean else "FAIL" if not ok_all else "INVALID (contaminated run)"}')


if __name__ == '__main__':
    main()
