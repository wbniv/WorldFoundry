#!/usr/bin/env python3
"""run_aquarium_checks.py — aquarium verification over the debug bridge (plan steps 11–15).

Plan: docs/plans/2026-09-30-aquarium-level.md § Verification, Phase 2–3.

Runs the already-built level (`task aquarium-level`, or `task aquarium-touch-level` for
--profile touch) PAUSED under -rate20 and steps it one engine tick at a time. Input is a
sticky `inject_input joystick1_raw` for every tick — 0 when nothing is held — so the game
window's desktop keyboard can never reach the fish (the Phase 2 run once took stray keys).
The joystick value the engine saw is watched each tick and compared with what was injected:
that is the `run isolation: CLEAN` line. Every watched mailbox is recorded per tick.

Keyboard profile (default), one run:
  step 11  frame A: camshot A, whole tank, the canonical fish at spawn (screenshot)
  step 15  = Phase 1 steps 5–7 on the canonical fish with the idle running:
           5 hover 10 s: Player drift, idle weight 1, the parts move;
           6 held UP / DOWN / RIGHT / LEFT / C / B stop exactly at the level's clamps,
             cruise speed and release glide; dart (A) burst then glide;
           7 heading: the body part faces +X after RIGHT and −X after LEFT, and the Player's
             own ROTATION_C reads 0 on every tick (nobody writes it);
           and over every tick of the run each part stays at its rigid offset from the body
           part, and the body part sits on the Player (plus the idle bob), through turns and
           wall contact.
  step 12  swim (held buttons only, no teleport) from the far end into the anemone's crown
           at y = 0; camshot B engages, the camera reaches B, the fish is not deflected and
           idles in the crown (screenshot frame B); then out and back in to measure the
           zone hysteresis.
  step 13  hold each direction into every wall ≥ 5 s after contact: the Player's box never
           leaves the tank, and the fish's visible extents stay inside the inner faces.

--profile touch (step 14, logic only; the phone hardware is not exercised):
  A taps cycle Swim → Depth → Swim (mailbox aq-mode), D-pad up/down move Z in Swim mode and Y
  in Depth mode, left/right move X in both, B taps dart, and C (keyboard depth) does nothing.

Usage: python3 wflevels/aquarium/run_aquarium_checks.py [-h] [--profile keyboard|touch]
Needs: DISPLAY (wf_game opens a GL window) and wf_game: engine/wf_game, else the main
checkout's (WF_GAME= overrides). Screenshots and logs go to $OUT (default ~/tmp/aquarium-phase3).
"""
import math
import os
import re
import resource
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__)
    raise SystemExit(0)
PROFILE = 'keyboard'
for i, a in enumerate(sys.argv[1:], 1):
    if a.startswith('--profile='):
        PROFILE = a.split('=', 1)[1]
    elif a == '--profile' and i + 1 < len(sys.argv):
        PROFILE = sys.argv[i + 1]
if PROFILE not in ('keyboard', 'touch'):
    raise SystemExit(f'--profile keyboard|touch, not {PROFILE!r}')

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'tests'))
import aquarium_constants as C                                     # noqa: E402
import clownfish as CF                                             # noqa: E402
from debug_bridge_client import BridgeClient                       # noqa: E402

MAIN = os.path.expanduser('~/WorldFoundry-wbniv')
WF_GAME = os.environ.get('WF_GAME') or next(
    p for p in (os.path.join(REPO, 'engine', 'wf_game'), os.path.join(MAIN, 'engine', 'wf_game'))
    if os.path.exists(p))
LIBS = os.path.join(os.path.dirname(os.path.realpath(WF_GAME)), 'libs')
GAME_CWD = os.path.join(REPO, 'wfsource', 'source', 'game')
LEVEL = 'aquarium' if PROFILE == 'keyboard' else 'aquarium_touch'
LEVEL_LEV = os.path.join(REPO, 'wflevels', LEVEL, LEVEL + '.lev')
LEVEL_IFF = os.path.join(REPO, 'wflevels', LEVEL + '-standalone.iff')
OUT = os.environ.get('OUT', os.path.expanduser('~/tmp/aquarium-phase3'))
PORT = int(os.environ.get('WF_BRIDGE_PORT', '7811'))

DT = 0.05                                        # -rate20
X_POS, Y_POS, Z_POS, ROT_A, ROT_B, ROT_C, Z_SCALE = 3009, 3010, 3011, 3012, 3013, 3014, 3042
TIME, JOY_RAW, CAMSHOT = 1906, 1909, 1921
BTN = {'UP': 2048, 'DOWN': 4096, 'RIGHT': 8192, 'LEFT': 16384, 'A': 1, 'B': 2, 'C': 4}
AXIS = {'RIGHT': (0, 1), 'LEFT': (0, -1), 'C': (1, 1), 'B': (1, -1), 'UP': (2, 1), 'DOWN': (2, -1)}
AQ = {n: 700 + i for i, n in enumerate(['aq-prev', 'aq-mode', 'aq-dart-t', 'aq-dart-req', 'aq-in-b',
                                           'aq-dx', 'aq-dy', 'aq-dz'])}
FISH = CF.Clownfish()
OFFSETS = {name: off for name, _, off in FISH.parts()}
PLAYER_BOX = FISH.collision_box()


def wrap(r):
    return ((r + 0.5) % 1.0) - 0.5


def lev_names():
    return re.findall(r"\{ 'OBJ'\s*\{ 'NAME' \"([^\"]+)\" \}", open(LEVEL_LEV).read())


def lev_consts():
    """The aq-* constants the build baked into the Director script."""
    lev = open(LEVEL_LEV).read()
    return {k: float(v) for k, v in re.findall(r": (aq-[a-z-]+) (-?[\d.]+) ;", lev)}


class Game:
    """wf_game paused under the bridge, stepped per tick, every watched mailbox recorded per tick."""

    def __init__(self, tag):
        os.makedirs(OUT, exist_ok=True)
        self.log_path = os.path.join(OUT, f'{tag}.log')
        self.log = open(self.log_path, 'w')
        self.p = subprocess.Popen(
            [WF_GAME, f'-L{LEVEL_IFF}', '-rate20', '--debug-port', str(PORT), '--debug-bind', '127.0.0.1',
             '--debug-print-actors'],
            cwd=GAME_CWD, stdout=self.log, stderr=subprocess.STDOUT,
            env=dict(os.environ, LD_LIBRARY_PATH=LIBS),
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
        self.c = BridgeClient('127.0.0.1', PORT, timeout=20.0)
        self.c.send({'op': 'pause'})
        self.frames = []                          # [(t, {(idx, mb): value})], one per tick
        self.state = {}
        self.clock_idx = 1                        # TIME watched on the lowest index → first in each batch
        self.injected = 0
        self.inj_log = {}                         # t → value injected for that tick
        # The bridge also broadcasts while paused (a new injected joystick value shows up at
        # once). Such a message belongs to the NEXT tick, not the last recorded one, so only
        # messages that arrive while a step is in flight are written into the current frame;
        # the rest update `state`, which the next tick's frame starts from.
        self.stepping = False
        self.step_k0 = 0
        orig = self.c._dispatch

        def rec(msg):
            if msg.get('op') == 'mailbox':
                key = (msg['idx'], msg['mailbox'])
                v = float(msg['value'])
                if key == (self.clock_idx, TIME):
                    self.frames.append((v, dict(self.state)))
                self.state[key] = v
                if self.stepping and len(self.frames) > self.step_k0:   # a tick of THIS step
                    self.frames[-1][1][key] = v
            orig(msg)
        self.c._dispatch = rec
        self.inject(0)

    def watch(self, pairs):
        for idx, mb in pairs:
            self.c.watch(idx=idx, mailbox=mb)
        time.sleep(0.2)

    def inject(self, bits):
        self.injected = bits
        self.c.inject_input('joystick1_raw', bits, duration_frames=-1)       # sticky: masks the keyboard
        time.sleep(0.08)

    def now(self):
        return self.frames[-1][0] if self.frames else 0.0

    def step(self, n=1):
        t0, k0 = self.now(), len(self.frames)
        self.step_k0 = k0
        self.stepping = True
        self.c.send({'op': 'step', 'frames': n})
        deadline = time.time() + 10 + n * 0.1
        while time.time() < deadline:
            if len(self.frames) >= k0 + n and self.now() >= t0 + n * DT - 1e-4:
                time.sleep(0.03)                  # the rest of the last batch
                self.stepping = False
                for t, _ in self.frames[k0:]:
                    self.inj_log[round(t, 3)] = self.injected
                if TRACE:
                    for t, s in self.frames[k0:]:
                        print(f'  t {t:7.2f} ' + ' '.join(f'{lbl} {s.get(key, float("nan")):+.4f}' for lbl, key in TRACE))
                return self.frames[k0:]
            time.sleep(0.003)
        self.stepping = False
        raise RuntimeError(f'step {n} stalled at t={self.now()} ({len(self.frames) - k0} frames); see {self.log_path}')

    def hold(self, button, ticks):
        self.inject(BTN[button] if button else 0)
        out = []
        while ticks > 0:
            k = min(ticks, 20)
            out += self.step(k)
            ticks -= k
        self.inject(0)
        return out

    def tap(self, button):
        return self.hold(button, 1)

    def v(self, idx, mb):
        return self.state.get((idx, mb))

    def shot(self, name):
        fn = os.path.join(OUT, f'{name}.png')
        if os.path.exists(fn):
            os.unlink(fn)
        self.c.send({'op': 'screenshot', 'filename': fn})
        r = self.c.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=10)
        return fn if r and r.get('op') == 'screenshot_done' else f'FAILED {r}'

    def close(self):
        try:
            self.c.close()
        finally:
            self.p.terminate()
            try:
                self.p.wait(10)
            except subprocess.TimeoutExpired:
                self.p.kill()
            self.log.close()


def verdict(ok):
    return 'PASS' if ok else 'FAIL'


class Run:
    def __init__(self):
        names = lev_names()
        self.idx = {n: names.index(n) + 1 for n in names}
        self.k = lev_consts()
        self.g = Game(f'phase3-{PROFILE}')
        self.pl = self.idx['Player']
        self.dir = self.idx['Director']
        self.parts = {n: self.idx[n] for n in CF.PART_NAMES}
        self.cam = self.idx['Camera']
        watches = [(1, TIME), (self.pl, X_POS), (self.pl, Y_POS), (self.pl, Z_POS), (self.pl, ROT_C),
                   (self.pl, CF.MB['fish-w']), (self.dir, JOY_RAW), (self.dir, CAMSHOT),
                   (self.cam, X_POS), (self.cam, Y_POS), (self.cam, Z_POS)]
        watches += [(self.dir, mb) for mb in AQ.values()]
        for n, i in self.parts.items():
            watches += [(i, X_POS), (i, Y_POS), (i, Z_POS), (i, ROT_C)]
        self.g.watch(watches)
        self.rows = []

    def pos(self, f=None):
        s = f[1] if f else self.g.state
        return tuple(s.get((self.pl, mb)) for mb in (X_POS, Y_POS, Z_POS))

    def phase(self, name, button, secs, shot=None):
        a = self.pos()
        fr = self.g.hold(button, round(secs / DT))
        b = self.pos()
        self.rows.append((name, button, secs, a, b, fr))
        if shot:
            print(f'screenshot {shot}: {self.g.shot(shot)}')
        return fr

    def print_rows(self, rows):
        print(f"{'phase':9s} {'btn':5s} {'s':>5s}  {'start x,y,z':>24s}  {'end x,y,z':>24s}")
        for name, btn, secs, a, b, _ in rows:
            f = lambda p: ''.join(f'{v:8.3f}' for v in p)
            print(f"{name:9s} {btn or '-':5s} {secs:5.2f}  {f(a)}  {f(b)}")

    # ── per-tick invariants over every recorded frame ──
    def isolation(self):
        bad = [(t, s.get((self.dir, JOY_RAW)), self.g.inj_log.get(round(t, 3)))
               for t, s in self.g.frames if round(t, 3) in self.g.inj_log
               and s.get((self.dir, JOY_RAW)) is not None
               and int(s.get((self.dir, JOY_RAW))) != self.g.inj_log[round(t, 3)]]
        n = sum(1 for t, _ in self.g.frames if round(t, 3) in self.g.inj_log)
        print(f'joystick1_raw seen by the engine vs injected, {n} ticks: {len(bad)} mismatches {bad[:5]}')
        print(f'run isolation: {"CLEAN" if not bad and n > 0 else "CONTAMINATED — rerun"}')
        return not bad and n > 0

    def attachment(self, frames):
        """Rigid offsets: |part − body| == |offset| every tick; body on the Player (+ bob)."""
        worst_off, worst_xy, worst_bob, n = {}, 0.0, 0.0, 0
        for t, s in frames:
            p = [s.get((self.pl, mb)) for mb in (X_POS, Y_POS, Z_POS)]
            b = [s.get((self.parts['clownfish-body'], mb)) for mb in (X_POS, Y_POS, Z_POS)]
            if None in p or None in b:
                continue
            n += 1
            worst_xy = max(worst_xy, math.hypot(b[0] - p[0], b[1] - p[1]))
            worst_bob = max(worst_bob, abs(b[2] - p[2]))
            for name, i in self.parts.items():
                if name == 'clownfish-body':
                    continue
                q = [s.get((i, mb)) for mb in (X_POS, Y_POS, Z_POS)]
                if None in q:
                    continue
                d = math.dist(q, b)
                worst_off[name] = max(worst_off.get(name, 0.0), abs(d - math.hypot(*OFFSETS[name])))
        return n, worst_off, worst_xy, worst_bob


def keyboard():
    r = Run()
    g, k = r.g, r.k
    ok = {}
    try:
        # ── step 11 + 15/5: settle, frame A, hover 10 s with the idle running ──
        g.step(30)
        shot_a0 = g.v(r.dir, CAMSHOT)
        print(f'screenshot frame-a: {g.shot("phase3-frame-a")}')
        hover = r.phase('hover', None, 10.0)
        print(f'screenshot idle: {g.shot("phase3-idle")}')
        zs = [f[1].get((r.pl, Z_POS)) for f in hover]
        drift = [max(f[1].get((r.pl, mb)) for f in hover) - min(f[1].get((r.pl, mb)) for f in hover)
                 for mb in (X_POS, Y_POS, Z_POS)]
        w_end = hover[-1][1].get((r.pl, CF.MB['fish-w']))
        tail_rel = [wrap(f[1].get((r.parts['clownfish-tail'], ROT_C)) - f[1].get((r.parts['clownfish-body'], ROT_C)))
                    for f in hover]
        bz = [f[1].get((r.parts['clownfish-body'], Z_POS)) - f[1].get((r.pl, Z_POS)) for f in hover]
        col = C.WATER_LINE_M - C.SAND_TOP_M
        print(f'step 11: CAMSHOT {shot_a0:g} (cs_front = {r.idx["cs_front"]}) → {verdict(shot_a0 == r.idx["cs_front"])}')
        print(f'step 15/5: hover 10 s: Player drift x/y/z {drift[0]:.5f}/{drift[1]:.5f}/{drift[2]:.5f} m '
              f'(limit 1 % of the water column = {0.01 * col:.5f}); idle weight at end {w_end:.3f}; '
              f'tail yaw rel. body {min(tail_rel):+.4f}..{max(tail_rel):+.4f} rev; body bob {min(bz) * 1000:+.1f}..{max(bz) * 1000:+.1f} mm')
        ok['5'] = max(drift) < 0.01 * col and w_end > 0.999 and max(tail_rel) - min(tail_rel) > 0.05
        print(f'step 15/5: {verdict(ok["5"])}')

        # ── step 15/6 + 15/7: the Phase 1 sequence on the canonical fish ──
        seq = [('up', 'UP', 6.0, None), ('down', 'DOWN', 6.0, None), ('rest', None, 1.0, None),
               ('rise', 'UP', 0.6, None), ('settle', None, 2.0, None),
               ('right', 'RIGHT', 5.0, 'phase3-facing-right'), ('off-wall', 'LEFT', 1.5, None),
               ('glide', None, 2.0, None), ('left', 'LEFT', 6.0, 'phase3-facing-left'),
               ('back', 'C', 5.0, None), ('front', 'B', 5.0, None), ('end', None, 1.0, None)]
        start = len(r.rows)
        heading = {}
        for name, btn, secs, shot in seq:
            fr = r.phase(name, btn, secs, shot)
            heading[name] = wrap(fr[-1][1].get((r.parts['clownfish-body'], ROT_C)))
        r.print_rows(r.rows[start:])
        end = {n: b for n, _, _, _, b, _ in r.rows[start:]}
        checks = [
            ('UP stops at the clamp aq-zmax', end['up'][2], k['aq-zmax']),
            ('DOWN stops at the clamp aq-zmin', end['down'][2], k['aq-zmin']),
            ('RIGHT stops at the clamp aq-xmax', end['right'][0], k['aq-xmax']),
            ('LEFT stops at the clamp −aq-xmax', end['left'][0], -k['aq-xmax']),
            ('C stops at the clamp aq-ymax', end['back'][1], k['aq-ymax']),
            ('B stops at the clamp −aq-ymax', end['front'][1], -k['aq-ymax']),
        ]
        ok6 = True
        for label, got, want in checks:
            good = abs(got - want) < 1e-3
            ok6 &= good
            print(f'step 15/6: {label}: {got:.4f} vs {want:.4f} → {verdict(good)}')
        # cruise: the per-tick step in the middle of the RIGHT crossing
        fr = next(x[5] for x in r.rows[start:] if x[0] == 'right')
        # About one tick in 40 the bridge delivers a position a tick late (a 0 step, then a
        # double one), so the per-tick speed is the MEDIAN of the moving ticks, not the max.
        xs = [f[1].get((r.pl, X_POS)) for f in fr]
        steps = sorted(b - a for a, b in zip(xs, xs[1:]) if b - a > 1e-6)
        cruise = steps[len(steps) // 2] / DT if steps else 0.0
        gl = next(x for x in r.rows[start:] if x[0] == 'glide')
        glide = abs(gl[4][0] - gl[3][0])
        print(f'step 15/6: cruise {cruise:.3f} m/s (Phase 1: 2.74); glide over 2 s after release {glide:.3f} m '
              f'(Phase 1: 0.892 over 2 s)')
        ok6 &= abs(cruise - 2.743) < 0.02
        ok['6'] = ok6

        # dart: from rest in mid-tank, facing +X, one A tap
        r.phase('to-mid', 'RIGHT', 1.2, None)
        r.phase('rest2', None, 3.0, None)
        a = r.pos()
        fr = r.phase('dart', 'A', 0.05, None) + r.phase('dart-glide', None, 3.0, 'phase3-dart')
        b = r.pos()
        xs = [a[0]] + [f[1].get((r.pl, X_POS)) for f in fr]
        burst_n = round(k['aq-dart-time'] / DT)
        # speed on the burst ticks (median: robust to the bridge's late-delivered tick)
        bsteps = sorted(bb - aa for aa, bb in zip(xs[1:burst_n + 2], xs[2:burst_n + 2]))
        peak = bsteps[len(bsteps) // 2] / DT
        dart_ok = peak > 1.5 * cruise and b[0] - a[0] > 1.0 and abs(b[1] - a[1]) < 1e-3 and abs(b[2] - a[2]) < 1e-3
        print(f'step 15/6: dart (one A tap, facing +X): {peak:.3f} m/s over the burst, travelled {b[0] - a[0]:.3f} m in 3.05 s '
              f'(burst {k["aq-dart-v"]:g} m/s × {k["aq-dart-time"]:g} s, then the glide); y/z unchanged → {verdict(dart_ok)}')
        ok['6'] &= dart_ok
        print(f'step 15/6: {verdict(ok["6"])}')

        rot_c = [f[1].get((r.pl, ROT_C)) for f in g.frames if f[1].get((r.pl, ROT_C)) is not None]
        ok7 = abs(heading['right']) < 0.02 and abs(abs(heading['left']) - 0.5) < 0.02 and \
            rot_c and max(abs(v) for v in rot_c) == 0.0
        print(f'step 15/7: body part heading after RIGHT {heading["right"]:+.4f} rev, after LEFT {heading["left"]:+.4f} rev; '
              f'Player ROTATION_C over {len(rot_c)} ticks: {min(rot_c):g}..{max(rot_c):g} → {verdict(ok7)}')
        ok['7'] = ok7

        # ── step 12: swim into the anemone's crown (held buttons only) ──
        zone_c = (k['aq-zone-x'], k['aq-zone-y'], k['aq-zone-z'])
        # Host height: the capsule (half-height 0.195) 0.15 m over the oral disc (top z 1.705), so
        # Jolt never treats the fish as standing on the anemone; the tentacles rise to z 2.44.
        crown = (C.ANEMONE_X, 0.0, 2.1)
        start12 = len(r.rows)
        r.phase('to-left', 'LEFT', 4.0, None)                   # far end, well outside the zone
        glide_k = 0.5                                            # a release glides 0.45 × the written 3.048 m/s ≈ 1.37 m

        def approach(axis, target, plus, minus, name, limit=8.0):
            """Hold toward `target` until the release glide (0.45 × speed) would carry it there.
            One tick of input already glides ≈ 1.4 m, so 0.25 m is as close as a tap can aim."""
            for _ in range(2):
                p0 = r.pos()
                if abs(p0[axis] - target) < 0.25:
                    return
                btn = plus if target > p0[axis] else minus
                g.inject(BTN[btn])
                fr, last = [], p0[axis]
                while len(fr) * DT < limit:
                    fr += g.step(1)
                    p = r.pos()[axis]
                    spd, last = abs(p - last) / DT, p
                    if abs(target - p) <= glide_k * spd + 0.02 or (target - p) * (1 if btn == plus else -1) <= 0:
                        break
                g.inject(0)
                fr += g.step(40)
                r.rows.append((name, btn, len(fr) * DT, p0, r.pos(), fr))
        approach(1, 0.0, 'C', 'B', 'to-y0')
        approach(2, crown[2], 'UP', 'DOWN', 'to-z')
        a = r.pos()
        entered = None
        g.inject(BTN['RIGHT'])
        fr = []
        while r.pos()[0] < crown[0] - glide_k * 2.743:          # release so the glide ends at the crown
            fr += g.step(1)
            if entered is None and g.v(r.dir, AQ['aq-in-b']) == 1:
                entered = (r.pos(), math.dist(r.pos(), zone_c))
                print(f'screenshot b-edge: {g.shot("phase3-b-edge")}')
        g.inject(0)
        fr += g.step(60)                                        # glide into the crown, camera settles
        for _ in range(40):
            fr += g.step(1)
            if entered is None and g.v(r.dir, AQ['aq-in-b']) == 1:
                entered = (r.pos(), math.dist(r.pos(), zone_c))
        r.rows.append(('into-crown', 'RIGHT', len(fr) * DT, a, r.pos(), fr))
        ys = [f[1].get((r.pl, Y_POS)) for f in fr]
        idle_crown = r.phase('host', None, 4.0, 'phase3-frame-b')
        p = r.pos()
        cam = tuple(g.v(r.cam, mb) for mb in (X_POS, Y_POS, Z_POS))
        cs = g.v(r.dir, CAMSHOT)
        w = g.v(r.pl, CF.MB['fish-w'])
        hd = [max(f[1].get((r.pl, mb)) for f in idle_crown) - min(f[1].get((r.pl, mb)) for f in idle_crown)
              for mb in (X_POS, Y_POS, Z_POS)]
        r.print_rows(r.rows[start12:])
        print(f'step 12: entered the zone at {tuple(round(v, 3) for v in entered[0]) if entered else None}, '
              f'{entered[1] if entered else float("nan"):.3f} m from the zone centre (radius {k["aq-zone-in"]:g})')
        defl = max(abs(y - a[1]) for y in ys)
        print(f'step 12: in the crown at {tuple(round(v, 3) for v in p)} (target {crown}); sideways deflection on the way '
              f'in {defl:.4f} m; Player drift while hosting x/y/z {hd[0]:.5f}/{hd[1]:.5f}/{hd[2]:.5f} m; idle weight {w:.3f}')
        print(f'step 12: CAMSHOT {cs:g} (cs_anemone = {r.idx["cs_anemone"]}); camera at '
              f'{tuple(round(v, 3) for v in cam)} vs camshot B {C.CAM_B_POS}')
        ok12 = (cs == r.idx['cs_anemone'] and abs(p[0] - crown[0]) < 0.35 and abs(p[1]) < 0.3
                and defl < 0.02 and max(hd) < 1e-3 and w > 0.999
                and math.dist(cam, C.CAM_B_POS) < 0.05)
        # hysteresis: swim out left until the shot returns to A, glide on, then back right until
        # it is B again; record the distance at every flip (both crossings through the band)
        flips, hyst_fr = [], []
        for btn, want in (('LEFT', 0), (None, None), ('RIGHT', 1), (None, None)):
            g.inject(BTN[btn] if btn else 0)
            fr = []
            while len(fr) < 200:
                fr += g.step(1)
                if btn and g.v(r.dir, AQ['aq-in-b']) == want:
                    break
                if not btn and len(fr) >= 60:
                    break
            g.inject(0)
            hyst_fr += fr
        print(f'screenshot b-reentry (camshot B after re-entering at the zone edge and gliding 3 s): '
              f'{g.shot("phase3-b-reentry")}  fish at {tuple(round(v, 3) for v in r.pos())}')
        prev = None
        for t, s in hyst_fr:
            v = s.get((r.dir, AQ['aq-in-b']))
            if prev is not None and v != prev:
                pp = tuple(s.get((r.pl, mb)) for mb in (X_POS, Y_POS, Z_POS))
                flips.append((round(t, 2), int(v), round(math.dist(pp, zone_c), 3)))
            prev = v
        outs = [d for _, v, d in flips if v == 0]
        ins = [d for _, v, d in flips if v == 1]
        hyst_ok = outs and ins and all(d >= k['aq-zone-out'] - 0.01 for d in outs) and \
            all(d <= k['aq-zone-in'] + 0.01 for d in ins) and len(flips) == 2
        print(f'step 12: zone flips (t, in-b, distance m): {flips} — leave at ≥ {k["aq-zone-out"]:g}, enter at ≤ '
              f'{k["aq-zone-in"]:g}, one flip each way → {verdict(bool(hyst_ok))}')
        ok['12'] = ok12 and bool(hyst_ok)
        print(f'step 12: {verdict(ok["12"])}')

        # ── step 13: every wall held ≥ 5 s after contact ──
        start13 = len(r.rows)
        for name, btn, secs, shot in (('right', 'RIGHT', 7.0, 'phase3-right-wall'), ('left', 'LEFT', 10.0, 'phase3-left-wall'),
                                      ('back', 'C', 6.0, 'phase3-back-wall'), ('front', 'B', 7.0, 'phase3-front-glass'),
                                      ('up', 'UP', 7.0, 'phase3-water-line'), ('down', 'DOWN', 7.0, 'phase3-sand'),
                                      ('end', None, 1.0, None)):
            r.phase(name + '13', btn, secs, shot)
        r.print_rows(r.rows[start13:])
        held = []
        for name, btn, secs, a, b, fr in r.rows[start13:]:
            if not btn:
                continue
            ax, _ = AXIS[btn]
            vals = [f[1].get((r.pl, (X_POS, Y_POS, Z_POS)[ax])) for f in fr]
            first = next(i for i, v in enumerate(vals) if abs(v - vals[-1]) < 1e-4)
            held.append(f'{btn} {(len(vals) - first) * DT:.2f} s')
        print('step 13: time pressed against the limit: ' + ', '.join(held))
        frames = g.frames
        ext = {mb: (min(f[1][(r.pl, mb)] for f in frames if (r.pl, mb) in f[1]),
                    max(f[1][(r.pl, mb)] for f in frames if (r.pl, mb) in f[1])) for mb in (X_POS, Y_POS, Z_POS)}
        x0, y0, z0, x1, y1, z1 = PLAYER_BOX
        e = FISH.extents()
        bob = FISH.T['fish-bob-amp']
        ix, iy = C.INNER_X_M, C.INNER_Y_M
        checks = [
            ('Player box right edge vs right wall inner face', ext[X_POS][1] + x1, ix, 1),
            ('Player box left edge vs left wall inner face', ext[X_POS][0] + x0, -ix, -1),
            ('Player box back edge vs back wall inner face', ext[Y_POS][1] + y1, iy, 1),
            ('Player box front edge vs front glass plane', ext[Y_POS][0] + y0, -iy, -1),
            ('Player box bottom vs sand top', ext[Z_POS][0] + z0, C.SAND_TOP_M, -1),
            ('Player box top vs water line', ext[Z_POS][1] + z1, C.WATER_LINE_M, 1),
            ('visible fish, tail tip or nose, vs right wall', ext[X_POS][1] + max(e['nose_x'], -e['tail_x']), ix, 1),
            ('visible fish, tail tip or nose, vs left wall', ext[X_POS][0] - max(e['nose_x'], -e['tail_x']), -ix, -1),
            ('visible fish pectoral vs back wall', ext[Y_POS][1] + e['half_width'], iy, 1),
            ('visible fish pectoral vs front glass plane', ext[Y_POS][0] - e['half_width'], -iy, -1),
            ('visible fish belly (bob low) vs sand', ext[Z_POS][0] + e['bottom_z'] - bob, C.SAND_TOP_M, -1),
            ('visible fish dorsal (bob high) vs water line', ext[Z_POS][1] + e['top_z'] + bob, C.WATER_LINE_M, 1),
        ]
        ok13 = True
        print(f'Player box (authored, local): x ±{x1:.4f} y ±{y1:.4f} z ±{z1:.4f}; fish extents {({a: round(b, 3) for a, b in e.items()})}')
        print('origin extremes over the whole run: ' + '  '.join(
            f'{a} [{ext[mb][0]:.4f}, {ext[mb][1]:.4f}]' for a, mb in (('x', X_POS), ('y', Y_POS), ('z', Z_POS))))
        for label, got, lim, sign in checks:
            good = (got <= lim) if sign > 0 else (got >= lim)
            ok13 &= good
            print(f'step 13: {label}: {got:.4f} vs {lim:.4f} (gap {abs(lim - got):.4f}) → {verdict(good)}')
        ok['13'] = ok13

        # ── step 15: every part attached, every tick of the run ──
        n, worst, wxy, wbob = r.attachment(g.frames)
        att_ok = n > 1000 and max(worst.values()) < 0.005 and wxy < 1e-3 and wbob < bob + 1e-3
        print(f'step 15: part attachment over {n} ticks (turns, darts, wall contact, hosting): worst |part − body| − |offset| '
              + ', '.join(f'{a.split("-", 1)[1]} {b * 1000:.2f} mm' for a, b in worst.items())
              + f'; body vs Player horizontal {wxy * 1000:.3f} mm, vertical {wbob * 1000:.2f} mm (bob amplitude {bob * 1000:.0f} mm) '
              f'→ {verdict(att_ok)}')
        ok['15'] = ok['5'] and ok['6'] and ok['7'] and att_ok
    finally:
        clean = r.isolation()
        g.close()
    for l in open(g.log_path, errors='replace').read().splitlines():
        if l.startswith('jolt: character') or re.search(r'zforth compile error|Assert|abort', l, re.I):
            print(l)
    print('SUMMARY ' + ' '.join(f'step {s}: {verdict(v) if clean else "INVALID (contaminated)"}' for s, v in ok.items()))


def touch():
    r = Run()
    g = r.g
    try:
        g.step(30)
        seq = [('swim-up', 'UP', 1.0), ('tap-A', 'A', 0.05), ('settle1', None, 1.5), ('depth-up', 'UP', 1.0),
               ('settle2', None, 1.5), ('depth-down', 'DOWN', 1.0), ('settle3', None, 3.0),
               ('depth-right', 'RIGHT', 0.5), ('settle4', None, 4.0), ('tap-A2', 'A', 0.05), ('settle5', None, 0.5),
               ('swim-down', 'DOWN', 1.0), ('settle6', None, 3.0), ('key-C', 'C', 1.0), ('settle7', None, 1.0),
               ('tap-B', 'B', 0.05), ('dart-glide', None, 3.0)]
        modes = {}
        for name, btn, secs in seq:
            r.phase(name, btn, secs)
            modes[name] = g.v(r.dir, AQ['aq-mode'])
        r.print_rows(r.rows)
        row = {n: (a, b) for n, _, _, a, b, _ in r.rows}

        def moved(name):
            a, b = row[name]
            return tuple(round(bb - aa, 3) for aa, bb in zip(a, b))
        OFF = 0.01                      # off-axis tolerance: residual glide (× 0.9 per tick) and 1 mm contact nudges
        tests = [
            ('Swim mode: UP swims +Z only', moved('swim-up'), lambda d: d[2] > 0.5 and abs(d[0]) < OFF and abs(d[1]) < OFF),
            ('A tap → Depth mode (aq-mode 1)', modes['tap-A'], lambda m: m == 1),
            ('Depth mode: UP swims +Y (away from the glass) only', moved('depth-up'), lambda d: d[1] > 0.3 and abs(d[0]) < OFF and abs(d[2]) < OFF),
            ('Depth mode: DOWN swims −Y only', moved('depth-down'), lambda d: d[1] < -0.3 and abs(d[0]) < OFF and abs(d[2]) < OFF),
            ('Depth mode: RIGHT still swims +X', moved('depth-right'), lambda d: d[0] > 0.5 and abs(d[1]) < OFF and abs(d[2]) < OFF),
            ('second A tap → Swim mode (aq-mode 0)', modes['tap-A2'], lambda m: m == 0),
            ('Swim mode: DOWN swims −Z only', moved('swim-down'), lambda d: d[2] < -0.5 and abs(d[0]) < OFF and abs(d[1]) < OFF),
            ('C (keyboard depth) does nothing in the touch profile', moved('key-C'), lambda d: max(abs(v) for v in d) < OFF),
        ]
        a = row['tap-B'][0]
        b = row['dart-glide'][1]
        tests.append(('B tap darts along the facing (+X)', tuple(round(bb - aa, 3) for aa, bb in zip(a, b)),
                      lambda d: d[0] > 1.0 and abs(d[1]) < OFF and abs(d[2]) < OFF))
        ok = True
        for label, got, pred in tests:
            good = bool(pred(got))
            ok &= good
            print(f'step 14: {label}: {got} → {verdict(good)}')
        print(f'screenshot touch: {g.shot("phase3-touch")}')
    finally:
        clean = r.isolation()
        g.close()
    for l in open(g.log_path, errors='replace').read().splitlines():
        if l.startswith('jolt: character') or re.search(r'zforth compile error|Assert|abort', l, re.I):
            print(l)
    print(f'SUMMARY step 14 (logic, injected buttons): {verdict(ok) if clean else "INVALID (contaminated)"}; '
          'phone hardware: not run')


def trace(seq):
    """--trace: print every tick of a short held-button sequence (Player position and speeds)."""
    global TRACE
    r = Run()
    pl = r.pl
    r.g.watch([(pl, 3018), (pl, 3019), (pl, 3020)])
    TRACE = [('x', (pl, X_POS)), ('y', (pl, Y_POS)), ('z', (pl, Z_POS)), ('vx', (pl, 3018)),
             ('vy', (pl, 3019)), ('vz', (pl, 3020)), ('joy', (r.dir, JOY_RAW))]
    try:
        for name, btn, secs in seq:
            print(f'-- {name} {btn or "-"} {secs} s')
            r.phase(name, btn, secs)
    finally:
        r.isolation()
        r.g.close()


TRACE = []
if __name__ == '__main__':
    if '--trace-sand' in sys.argv:
        trace([('settle', None, 1.5), ('down', 'DOWN', 3.0), ('rest', None, 1.0), ('rise', 'UP', 0.2),
               ('settle', None, 1.0), ('down', 'DOWN', 1.0), ('right', 'RIGHT', 3.0), ('glide', None, 1.5)])
    else:
        touch() if PROFILE == 'touch' else keyboard()
