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

--sway (step 16, Phase 4): 10 s with no input, every tick of each anemone clump's ROTATION_A/B/C
  and position recorded: bounded by its amplitude, periodic (B(t) = B(t + period)), net zero over
  a period, phases offset between clumps, the clumps' pivots never move, and the Player does not
  drift. Two frame-A captures 1 s apart must differ inside the anemone's screen box (the fish,
  which also idles, is outside it); then the Player is set down in the crown (a test teleport;
  step 12 swims there with buttons) and two frame-B captures 1 s apart are taken.

--cost [IFF ...] (step 18): wall time of `wf_game --frame-step-smoke` at 100 and 600 frames, vsync
  off, three runs each, for this level and every IFF given (e.g. a saved Phase 3 build): median
  ms per frame = (t600 − t100) / 500, and the actor count from --debug-print-actors.

Usage: python3 wflevels/aquarium/run_aquarium_checks.py [-h] [--profile keyboard|touch] [--sway]
       [--cost [IFF ...]] [--trace-sand]
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
STEER_MB = ['aq-yaw', 'aq-yaw-w', 'aq-pitch', 'aq-pitch-w', 'aq-roll', 'aq-speed', 'aq-burst', 'aq-pushed',
            'aq-cyc', 'aq-brake']
RIG_MB = ['fish-tail-env', 'fish-ph-swim', 'fish-ph-pec', 'fish-tail', 'fish-pec', 'fish-pec-far', 'fish-heading',
          'fish-pitch']
# every visible part's mesh vertices (its own frame), for the exact per-tick clip check
PART_VERTS = {name: mesh.verts for name, mesh, _ in FISH.parts()}


def part_world_extents(s, parts):
    """World (min, max) over the vertices of every visible part in one recorded frame, posed exactly
    as the engine drew them: pivot position, Euler A/B/C (rev) and the dorsal's Z_SCALE."""
    lo, hi = [1e9] * 3, [-1e9] * 3
    for name, i in parts.items():
        p = [s.get((i, mb)) for mb in (X_POS, Y_POS, Z_POS)]
        r = [s.get((i, mb)) for mb in (ROT_A, ROT_B, ROT_C)]
        if None in p or None in r:
            return None
        rows = CF.rot_matrix(*r)
        zs = s.get((i, Z_SCALE), 1.0) if name == 'clownfish-dorsal' else 1.0
        for v in PART_VERTS[name]:
            w = CF.apply(rows, (v[0], v[1], v[2] * zs))
            for k in range(3):
                c = p[k] + w[k]
                lo[k], hi[k] = min(lo[k], c), max(hi[k], c)
    return lo, hi


def facing(yaw, pitch):
    """The controller's facing unit vector: yaw rev (0 = +x), elevation rev (nose up +)."""
    y, t = math.tau * yaw, math.tau * pitch
    return (math.cos(t) * math.cos(y), math.cos(t) * math.sin(y), math.sin(t))


def wrap(r):
    return ((r + 0.5) % 1.0) - 0.5


def lev_names():
    return re.findall(r"\{ 'OBJ'\s*\{ 'NAME' \"([^\"]+)\" \}", open(LEVEL_LEV).read())


def lev_consts():
    """The aq-* constants the build baked into the Director script."""
    lev = open(LEVEL_LEV).read()
    return {k: float(v) for k, v in re.findall(r": (aq-[a-z-]+) (-?[\d.]+) ;", lev)}


def lev_actor(name):
    """(position, bbox) of one actor, from the .lev (world position; bbox local to it)."""
    num = r"(-?[\d.]+)\(1\.15\.16\)"
    for block in open(LEVEL_LEV).read().split("\t{ 'OBJ' ")[1:]:
        if re.search(r"\{ 'NAME' \"%s\" \}" % re.escape(name), block):
            pos = re.search(r"\"Position\" \} \{ 'DATA' " + r"\s*".join([num] * 3), block)
            box = re.search(r"Global Bounding Box\" \} \{ 'DATA' " + r"\s*".join([num] * 6), block)
            return tuple(float(v) for v in pos.groups()), tuple(float(v) for v in box.groups())
    raise KeyError(name)


def host_point():
    """Where the fish hosts: over the anemone at y 0, its capsule GROUND_CLEARANCE (plus 5 cm) over
    the oral disc's top, so Jolt never treats it as standing on the anemone (Phase 3 verdict)."""
    pos, box = lev_actor('anemone')
    return (C.ANEMONE_X, 0.0, round(pos[2] + box[5] + PLAYER_BOX[5] + C.GROUND_CLEARANCE + 0.05, 3))


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
        self.clock_idx = 1                        # TIME on actor 1 marks a new tick (see step())
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
        """Advance n ticks, ONE engine tick per bridge step. The engine sends one batch per tick,
        but in unordered_map order (debug_server.cc gWatches), not by actor index, so the clock
        key is not first in it. Within a multi-tick step, keys sent before the clock were written
        into the previous tick's frame, and at the step's end that showed as a repeated value then
        a double step (Phase 3's "late tick"; Phase 4 found the cause on the sway trace). Stepped
        one tick at a time, a key that arrives before the clock only updates `state`, which the new
        frame copies, so every frame is exact."""
        out = []
        for _ in range(n):
            out += self._step1()
        return out

    def _step1(self, n=1):
        t0, k0 = self.now(), len(self.frames)
        self.step_k0 = k0
        self.stepping = True
        self.c.send({'op': 'step', 'frames': n})
        deadline = time.time() + 60 + n * 0.1          # a shared host can stall a frame for seconds (Phase 4: load 121)
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
        watches = [(1, TIME), (self.pl, X_POS), (self.pl, Y_POS), (self.pl, Z_POS),
                   (self.pl, ROT_A), (self.pl, ROT_B), (self.pl, ROT_C),
                   (self.pl, CF.MB['fish-w']), (self.dir, JOY_RAW), (self.dir, CAMSHOT),
                   (self.cam, X_POS), (self.cam, Y_POS), (self.cam, Z_POS)]
        watches += [(self.dir, mb) for mb in AQ.values()]
        # Phase 4 steer-and-swim state (global mailboxes, read through the Director) and the rig's
        # inputs and phases, so the motion can be measured from the engine trace
        self.mb = {n: int(self.k[n]) for n in STEER_MB if n in self.k}
        self.mb.update({n: CF.MB[n] for n in RIG_MB})
        watches += [(self.dir, mb) for mb in self.mb.values()]
        for n, i in self.parts.items():
            watches += [(i, X_POS), (i, Y_POS), (i, Z_POS), (i, ROT_A), (i, ROT_B), (i, ROT_C)]
        watches.append((self.parts['clownfish-dorsal'], Z_SCALE))
        self.g.watch(watches)
        self.rows = []

    def m(self, name, f=None):
        """A steering / rig mailbox (by name) in frame f (or now)."""
        s = f[1] if f else self.g.state
        return s.get((self.dir, self.mb[name]))

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
        # The level runs ~1.6 s before the bridge connects and pauses it, and there is no start-
        # paused switch; desktop keys typed into the game window then move the fish before the
        # sticky injection masks the keyboard (Phase 4: a run began at x 1.769, spawn −1.6). So
        # the Player must still be at its spawn on the first recorded tick.
        first = next((f[1] for f in self.g.frames if (self.pl, X_POS) in f[1]), None)
        p0 = tuple(first.get((self.pl, mb)) for mb in (X_POS, Y_POS, Z_POS)) if first else None
        spawn_ok = p0 is not None and None not in p0 and math.dist(p0, C.FISH_SPAWN) < 1e-3
        keys = sum(1 for l in open(self.g.log_path, errors='replace') if l.startswith('unknown key'))
        print(f'Player at the first recorded tick {tuple(round(v, 4) for v in p0) if p0 else None} vs spawn '
              f'{C.FISH_SPAWN} → {"at spawn" if spawn_ok else "MOVED before the harness took input"}; '
              f'unmapped desktop key events in the engine log: {keys}')
        clean = not bad and n > 0 and spawn_ok
        print(f'run isolation: {"CLEAN" if clean else "CONTAMINATED — rerun"}')
        return clean

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


def navigate(r, target, speed_now, glide_k, limit=400):
    """Hold the buttons that point at `target` each tick (as a player steers); release when the
    glide would carry the fish there. Returns the recorded frames."""
    g = r.g
    fr = []
    while len(fr) < limit:
        e = [t - p for t, p in zip(target, r.pos())]
        if math.dist(target, r.pos()) < glide_k * speed_now() + 0.1:
            break
        bits = (BTN['RIGHT'] if e[0] > 0.25 else BTN['LEFT'] if e[0] < -0.25 else 0) | \
               (BTN['C'] if e[1] > 0.2 else BTN['B'] if e[1] < -0.2 else 0) | \
               (BTN['UP'] if e[2] > 0.3 else BTN['DOWN'] if e[2] < -0.3 else 0)
        if not bits:                                     # inside every deadband: let it glide
            break
        if bits != g.injected:
            g.inject(bits)
        fr += g.step(1)
    g.inject(0)
    return fr


def keyboard():
    r = Run()
    g, k = r.g, r.k
    ok = {}
    try:
        # ── step 11 + 15/5: settle, frame A, hover 10 s with the idle running ──
        g.step(30)
        shot_a0 = g.v(r.dir, CAMSHOT)
        print(f'screenshot frame-a: {g.shot("phase4-frame-a")}')
        hover = r.phase('hover', None, 10.0)
        print(f'screenshot idle: {g.shot("phase4-idle")}')
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

        # ── step 15/6 + 15/7 (Phase 4: steer and swim; Phase 1's per-axis clamps are gone) ──
        def cruise_stats(fr):
            sp = [math.dist([a[1][(r.pl, mb)] for mb in (X_POS, Y_POS, Z_POS)],
                            [b[1][(r.pl, mb)] for mb in (X_POS, Y_POS, Z_POS)]) / DT for a, b in zip(fr, fr[1:])]
            return sum(sp) / len(sp), max(sp)
        right = r.phase('right', 'RIGHT', 2.0, 'phase4-facing-right')
        mean_u, peak_u = cruise_stats(right[-20:])
        heading_right = wrap(right[-1][1][(r.parts['clownfish-body'], ROT_C)])
        a = r.pos()
        r.phase('glide', None, 2.0)
        glide = math.dist(a, r.pos())
        left = r.phase('to-mid', 'LEFT', 1.2, 'phase4-facing-left')
        heading_left = wrap(left[-1][1][(r.parts['clownfish-body'], ROT_C)])
        r.phase('rest2', None, 3.0)
        a = r.pos()
        fr = r.phase('dart', 'A', 0.05) + r.phase('dart-glide', None, 3.0, 'phase4-dart')
        b = r.pos()
        dmean, dpeak = cruise_stats(fr[:5])
        f0 = facing(r.m('aq-yaw', fr[0]), r.m('aq-pitch', fr[0]))
        d = [q - p for p, q in zip(a, b)]
        dang = math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(d, f0)) / math.dist(a, b)))))
        dart_ok = dpeak > 1.5 * mean_u and math.dist(a, b) > 2.0 and dang < 1.0
        ok['6'] = abs(mean_u - C.SWIM_SPEED) < 0.1 * C.SWIM_SPEED and 0.8 < glide < 2.0 and dart_ok
        print(f'step 15/6: cruise (burst-and-coast, last 1 s of RIGHT): mean {mean_u:.3f} m/s (V = {C.SWIM_SPEED}), peak '
              f'{peak_u:.3f}; glide after release {glide:.3f} m; dart (A tap, facing −x): peak {dpeak:.3f} m/s, travelled '
              f'{math.dist(a, b):.3f} m, {dang:.3f}° off the facing it darted from → {verdict(ok["6"])}')
        rot_all = [abs(wrap(f[1].get((r.pl, mb), 0.0))) for f in g.frames for mb in (ROT_A, ROT_B, ROT_C)]
        ok['7'] = abs(heading_right) < 0.03 and abs(abs(heading_left) - 0.5) < 0.03 and max(rot_all) == 0.0
        print(f'step 15/7: body part heading after RIGHT {heading_right:+.4f} rev, after LEFT {heading_left:+.4f} rev (the '
              f'tail-beat recoil swings it ±0.014); Player ROTATION_A/B/C over {len(rot_all) // 3} ticks: max {max(rot_all):g} '
              f'→ {verdict(ok["7"])}')

        # ── step 12: swim into the anemone's crown (held buttons only) and rest there ──
        zone_c = (k['aq-zone-x'], k['aq-zone-y'], k['aq-zone-z'])
        crown = host_point()
        apos, abox = lev_actor('anemone')
        print(f'step 12: host point {crown} (oral disc top z {apos[2] + abox[5]:.3f})')
        start12 = len(r.rows)
        r.phase('to-left', 'LEFT', 3.0)
        glide_k = C.TAU_GLIDE                                     # released at speed U, it glides ≈ U × τ_glide

        def speed_now():
            return g.v(r.dir, r.mb['aq-speed']) or 0.0
        # Steer like a player: every tick hold the buttons that point at the host point (x, y, z with
        # deadbands, so the fish heads there along one of the 8 yaws, climbing or diving on the way),
        # and let go when the glide (speed × τ_glide) would carry it the rest of the way.
        fr = navigate(r, crown, speed_now, glide_k)
        a = fr[0][1] if fr else None
        entered = next(((tuple(s.get((r.pl, mb)) for mb in (X_POS, Y_POS, Z_POS)),
                         math.dist([s.get((r.pl, mb)) for mb in (X_POS, Y_POS, Z_POS)], zone_c))
                        for t, s in fr if s.get((r.dir, AQ['aq-in-b'])) == 1), None)
        r.rows.append(('into-crown', 'nav', len(fr) * DT, tuple(a.get((r.pl, mb)) for mb in (X_POS, Y_POS, Z_POS)),
                       r.pos(), fr))
        rest = strip_phase(r, 'approach-and-rest', None, 4.0)
        rows_in, st_in = motion_stats(r, fr + rest)
        pushes = [tuple(round(v, 2) for v in q['p']) for q in rows_in if q['pushed']]
        pushes_in_zone = [q for q in pushes if math.dist(q, zone_c) < k['aq-zone-out']]
        idle_crown = r.phase('host', None, 3.0, 'phase4-frame-b')
        p = r.pos()
        cam = tuple(g.v(r.cam, mb) for mb in (X_POS, Y_POS, Z_POS))
        cs = g.v(r.dir, CAMSHOT)
        w = g.v(r.pl, CF.MB['fish-w'])
        pitch = max(abs(f[1][(r.dir, r.mb['aq-pitch'])]) for f in idle_crown) * 360
        hd = [max(f[1].get((r.pl, mb)) for f in idle_crown) - min(f[1].get((r.pl, mb)) for f in idle_crown)
              for mb in (X_POS, Y_POS, Z_POS)]
        r.print_rows(r.rows[start12:])
        print(f'step 12: entered the zone at {tuple(round(v, 3) for v in entered[0]) if entered else None}, '
              f'{entered[1] if entered else float("nan"):.3f} m from the zone centre (radius {k["aq-zone-in"]:g})')
        defl = st_in['worst_angle']
        print(f'step 12: resting at {tuple(round(v, 3) for v in p)} (host point {crown}); on the way in the fish moved '
              f'along its facing to {defl:.3f}° (pushed back inside the tank at {pushes}, none of it in the zone: {not pushes_in_zone}), so nothing deflected it; '
              f'Player drift while hosting x/y/z {hd[0]:.5f}/{hd[1]:.5f}/{hd[2]:.5f} m; '
              f'idle weight {w:.3f}; |pitch| while resting ≤ {pitch:.2f}°')
        print(f'step 12: CAMSHOT {cs:g} (cs_anemone = {r.idx["cs_anemone"]}); camera at '
              f'{tuple(round(v, 3) for v in cam)} vs camshot B {C.CAM_B_POS}')
        ok12 = (cs == r.idx['cs_anemone'] and abs(p[0] - crown[0]) < 0.45 and abs(p[1]) < 0.3
                and crown[2] - 0.2 < p[2] < crown[2] + 0.6 and defl < 1.0 and not pushes_in_zone and max(hd) < 1e-3 and w > 0.999
                and pitch < 1.0 and math.dist(cam, C.CAM_B_POS) < 0.05)
        # hysteresis: swim out left until the shot returns to A, glide on, then back right until B again
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
        print(f'screenshot b-reentry: {g.shot("phase4-b-reentry")}  fish at {tuple(round(v, 3) for v in r.pos())}')
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

        # ── step 13: hold each direction into every wall; the fish eases to a stop facing it ──
        start13 = len(r.rows)
        walls = (('right', 'RIGHT', 9.0, 1), ('left', 'LEFT', 12.0, 0), ('back', 'C', 7.5, 3), ('front', 'B', 7.5, 2),
                 ('up', 'UP', 9.0, 5), ('down', 'DOWN', 9.0, 4))
        reach = []
        for name, btn, secs, face in walls:
            fr = r.phase(name + '13', btn, secs, f'phase4-wall-{name}')
            sp = [math.dist([a[1][(r.pl, mb)] for mb in (X_POS, Y_POS, Z_POS)],
                            [b[1][(r.pl, mb)] for mb in (X_POS, Y_POS, Z_POS)]) / DT for a, b in zip(fr, fr[1:])]
            still = next((len(sp) - i for i in range(len(sp) - 1, -1, -1) if sp[i] > 0.05), len(sp)) * DT
            lo, hi = part_world_extents(fr[-1][1], r.parts)
            gaps = [lo[0] + C.INNER_X_M, C.INNER_X_M - hi[0], lo[1] + C.INNER_Y_M, C.INNER_Y_M - hi[1],
                    lo[2] - C.SAND_TOP_M, C.WATER_LINE_M - hi[2]]
            reach.append((btn, gaps[face], still))
        r.print_rows(r.rows[start13:])
        print('step 13: at the end of each hold: gap from the visible fish to the face it swam at, and time held there '
              'without moving: ' + ', '.join(f'{b} {gp:.3f} m {st:.2f} s' for b, gp, st in reach))
        worst = [1e9] * 6
        for t, s in g.frames:
            e = part_world_extents(s, r.parts)
            if e:
                lo, hi = e
                worst = [min(q, v) for q, v in zip(worst, [lo[0] + C.INNER_X_M, C.INNER_X_M - hi[0], lo[1] + C.INNER_Y_M,
                                                           C.INNER_Y_M - hi[1], lo[2] - C.SAND_TOP_M, C.WATER_LINE_M - hi[2]])]
        print('step 13: every visible part over the whole run, smallest gap to the left wall / right wall / front glass / '
              'back wall / sand / water line: ' + ' '.join(f'{v:.4f}' for v in worst) + ' m')
        ok['13'] = (min(worst) > 0 and all(0 < gp < (0.5 if f < 4 else 1.0) for (_, gp, _), (_, _, _, f) in zip(reach, walls))
                    and all(st >= 5.0 for _, _, st in reach))
        print(f'step 13: {verdict(ok["13"])}')

        # ── step 15: every part attached, every tick of the run ──
        bob = FISH.T['fish-bob-amp']
        n, worst, wxy, wbob = r.attachment(g.frames)
        att_ok = n > 1000 and max(worst.values()) < 0.005 and wxy < 1e-3 and wbob < bob + 1e-3
        print(f'step 15: part attachment over {n} ticks (turns at any yaw and pitch, banks, darts, walls, hosting): worst '
              '|part − body| − |offset| ' + ', '.join(f'{a.split("-", 1)[1]} {b * 1000:.2f} mm' for a, b in worst.items())
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


def clump_indices(r):
    return {C.clump_name(row, side): r.idx[C.clump_name(row, side)] for row, side, *_ in C.ANEMONE_CLUMPS}


def differing_pixels(a, b, box=None):
    """Pixels whose max channel differs by > 8, optionally inside box = (x0, y0, x1, y1)."""
    from PIL import Image
    ia, ib = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    if box:
        ia, ib = ia.crop(box), ib.crop(box)
    pa, pb = ia.load(), ib.load()
    return sum(1 for x in range(ia.size[0]) for y in range(ia.size[1])
               if max(abs(p - q) for p, q in zip(pa[x, y], pb[x, y])) > 8)


def screen_x(x, y, cam=C.CAM_A_POS, w=640):
    """Screen column of world (x, y) seen by camshot A (level aim, fixed 60° vertical FOV, 4:3)."""
    f = (480 / 2) / math.tan(math.radians(30))
    return w / 2 + f * (x - cam[0]) / (y - cam[1])


def clump_stats(fr, i, amp_b, amp_a, period):
    """One clump's sway over recorded frames (angles in rev): bounded by its amplitudes and reaching
    them, net zero over its first period, periodic (B(t) = B(t + period) on every pair of ticks; the
    recording is exact since step() advances one tick at a time), its pivot never moves, C stays 0,
    and its period measured from the upward zero crossings. Used by --sway and the pytest guard."""
    bs = [wrap(f[1][(i, ROT_B)]) for f in fr]
    as_ = [wrap(f[1][(i, ROT_A)]) for f in fr]
    cs = [wrap(f[1][(i, ROT_C)]) for f in fr]
    n = round(period / DT)
    mean_b = sum(bs[:n]) / n
    gaps = [abs(bs[k] - bs[k + n]) for k in range(len(bs) - n)]
    around = lambda j: [round(bs[q] * 360, 3) for q in range(max(0, j - 2), min(len(bs), j + 3))]
    outliers = [(round(fr[k][0], 2), round(fr[k + n][0], 2), around(k), around(k + n))
                for k, gp in enumerate(gaps) if gp >= 0.05 * amp_b]
    pivot = max(max(f[1][(i, mb)] for f in fr) - min(f[1][(i, mb)] for f in fr) for mb in (X_POS, Y_POS, Z_POS))
    ups = [fr[k][0] + DT * (-bs[k]) / (bs[k + 1] - bs[k]) for k in range(len(bs) - 1) if bs[k] < 0 <= bs[k + 1]]
    bounded = max(abs(v) for v in bs) <= amp_b * 1.01 + 1e-5 and max(abs(v) for v in as_) <= amp_a * 1.01 + 1e-5
    full = max(bs) - min(bs) >= 1.9 * amp_b and max(as_) - min(as_) >= 1.9 * amp_a
    c_max = max(abs(v) for v in cs)
    return dict(b=(min(bs), max(bs)), a=(min(as_), max(as_)), mean_b=mean_b, pairs=len(gaps), outliers=outliers,
                gap_median=sorted(gaps)[len(gaps) // 2], pivot=pivot, c_max=c_max,
                period=(ups[-1] - ups[0]) / (len(ups) - 1) if len(ups) > 1 else float('nan'),
                ok=bounded and full and abs(mean_b) < 0.05 * amp_b and not outliers and pivot < 1e-4 and c_max < 1e-4)


def sway():
    """Step 16: the anemone sway, 10 s traced per tick, with no input."""
    r = Run()
    g = r.g
    clumps = clump_indices(r)
    g.watch([(i, mb) for i in clumps.values() for mb in (ROT_A, ROT_B, ROT_C, X_POS, Y_POS, Z_POS)])
    phase_mb = {C.clump_name(row, side): C.SWAY_MB_BASE + k for k, (row, side, *_) in enumerate(C.ANEMONE_CLUMPS)}
    g.watch([(r.dir, mb) for mb in phase_mb.values()])            # the phase accumulators (global 720..)
    table = {C.clump_name(row, side): (amp_b / 360, amp_a / 360, period, phase)
             for row, side, amp_b, amp_a, period, phase in C.ANEMONE_CLUMPS}
    ok = {}
    try:
        g.step(30)
        print(f'screenshot sway-a0: {g.shot("phase4-sway-a0")}')
        fr = g.step(20)
        print(f'screenshot sway-a1 (1 s later): {g.shot("phase4-sway-a1")}')
        fr += r.phase('sway', None, 9.0)
        t0 = fr[0][0]
        print(f'step 16: {len(fr)} ticks traced, t {t0:.2f} → {fr[-1][0]:.2f} s')
        print(f"{'clump':22s} {'B min..max (deg)':>18s} {'amp':>5s} {'A min..max (deg)':>18s} {'mean B/period':>13s} "
              f"{'|B(t)-B(t+T)| median (odd)':>26s} {'phase t0':>13s} {'pivot':>9s} {'C':>4s}")
        good = True
        starts, outliers, measured = {}, [], {}
        for name, i in clumps.items():
            amp_b, amp_a, period, phase = table[name]
            s = clump_stats(fr, i, amp_b, amp_a, period)
            outliers += [(name,) + o for o in s['outliers']]
            measured[name] = s['period']
            # the clump's own phase at t0: its accumulator plus its offset (a fraction of a turn)
            starts[name] = (fr[0][1][(r.dir, phase_mb[name])] + phase) % 1.0
            good &= s['ok']
            print(f'{name:22s} {s["b"][0] * 360:+8.3f}..{s["b"][1] * 360:+7.3f} {amp_b * 360:5.1f} '
                  f'{s["a"][0] * 360:+8.3f}..{s["a"][1] * 360:+7.3f} {s["mean_b"] * 360:+13.4f} '
                  f'{s["gap_median"] * 360:7.4f} ({len(s["outliers"])}/{s["pairs"]}) {starts[name]:9.3f} rev '
                  f'{s["pivot"] * 1000:7.3f}mm {s["c_max"]:4.2g} → {verdict(s["ok"])}')
        for o in outliers:
            print(f'step 16: periodicity outlier {o[0]}: B(t {o[1]}) vs B(t {o[2]}); B (deg) ±2 ticks around each: {o[3]} | {o[4]}')
        # Not mechanical: each clump runs at its own period (measured from its upward zero
        # crossings, interpolated) and they are all at least 0.15 s apart, so no two ever lock.
        # A correlation over one 10 s window is only informative: close periods beat, and over
        # some windows any two sines line up (checked offline for every period set in 3–5 s).
        spread = sorted(starts.values())
        traces = {n: [wrap(f[1][(i, ROT_B)]) for f in fr] for n, i in clumps.items()}
        per_ok = all(abs(measured[n] - table[n][2]) < 0.02 * table[n][2] for n in measured)
        ms = sorted(measured.values())
        apart = min(b - a for a, b in zip(ms, ms[1:]))

        def corr(a, b):
            ma, mb_ = sum(a) / len(a), sum(b) / len(b)
            num = sum((x - ma) * (y - mb_) for x, y in zip(a, b))
            return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb_) ** 2 for y in b))
        names = list(traces)
        worst = max(((corr(traces[a], traces[b]), a, b) for k, a in enumerate(names) for b in names[k + 1:]),
                    key=lambda p: abs(p[0]))
        offset_ok = per_ok and apart >= 0.15
        print('step 16: measured periods (s): ' + ', '.join(f'{n.split("tent-")[1]} {measured[n]:.3f} '
                                                          f'(authored {table[n][2]:.2f})' for n in names)
              + f'; closest pair {apart:.3f} s apart → {verdict(offset_ok)}')
        print(f'step 16: most correlated pair over this window (information): {worst[1]} / {worst[2]} r = {worst[0]:+.3f}')
        drift = [max(f[1][(r.pl, mb)] for f in fr) - min(f[1][(r.pl, mb)] for f in fr) for mb in (X_POS, Y_POS, Z_POS)]
        print(f'step 16: phases at t0 (rev, sorted): {[round(v, 3) for v in spread]}; periods '
              f'{sorted({round(p[2], 2) for p in table.values()})} s')
        print(f'step 16: Player drift while swaying x/y/z {drift[0]:.5f}/{drift[1]:.5f}/{drift[2]:.5f} m → '
              f'{verdict(max(drift) < 1e-4)}')
        # The anemone's screen box in frame A: the crown ±1.6 m about x 2.5 at the rows' depth. The
        # idling fish (spawn x −1.6) is outside it, so a difference in there is the sway.
        x0, x1 = int(screen_x(C.ANEMONE_X - 1.6, -0.4)), int(screen_x(C.ANEMONE_X + 1.6, -0.4)) + 1
        fish_x1 = screen_x(C.FISH_SPAWN[0] + 0.53, 0.0)
        diff_a = differing_pixels(os.path.join(OUT, 'phase4-sway-a0.png'), os.path.join(OUT, 'phase4-sway-a1.png'), (x0, 0, x1, 480))
        print(f'step 16: frame A 1 s apart, pixels differing inside the anemone box x {x0}..{x1} '
              f'(fish ends at x {fish_x1:.0f}): {diff_a} → {verdict(diff_a > 50 and fish_x1 < x0)}')
        ok['16'] = good and offset_ok and max(drift) < 1e-4 and diff_a > 50 and fish_x1 < x0
        # Frame B: set the Player down in the crown (test teleport), let camshot B settle.
        host = host_point()
        for mb, v in zip((X_POS, Y_POS, Z_POS), host):
            g.c.set_mailbox(mb, v, idx=r.pl)
        time.sleep(0.2)
        g.step(80)
        print(f'step 16: Player set down at {host}; CAMSHOT {g.v(r.dir, CAMSHOT):g} (cs_anemone = {r.idx["cs_anemone"]}); '
              f'Player at {tuple(round(v, 3) for v in r.pos())}')
        print(f'screenshot sway-b0: {g.shot("phase4-sway-b0")}')
        g.step(20)
        print(f'screenshot sway-b1 (1 s later): {g.shot("phase4-sway-b1")}')
        diff_b = differing_pixels(os.path.join(OUT, 'phase4-sway-b0.png'), os.path.join(OUT, 'phase4-sway-b1.png'))
        print(f'step 16: frame B 1 s apart, pixels differing (whole frame; the idling fish moves too): {diff_b}')
        print(f'step 16: {verdict(ok["16"])}')
    finally:
        clean = r.isolation()
        g.close()
    for l in open(g.log_path, errors='replace').read().splitlines():
        if re.search(r'zforth compile error|Assert|abort', l, re.I):
            print(l)
    print('SUMMARY ' + ' '.join(f'step {s}: {verdict(v) if clean else "INVALID (contaminated)"}' for s, v in ok.items()))


def cost(extra_iffs):
    """Step 18: frame cost from --frame-step-smoke wall time (100 vs 600 frames, vsync off)."""
    env = dict(os.environ, LD_LIBRARY_PATH=LIBS, vblank_mode='0', __GL_SYNC_TO_VBLANK='0')

    def run(iff, n):
        t = time.monotonic()
        p = subprocess.run([WF_GAME, f'--frame-step-smoke={n}', '--cycles=1', '--debug-print-actors', f'-L{iff}'],
                           cwd=GAME_CWD, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600,
                           preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
        out = p.stdout.decode(errors='replace')
        return time.monotonic() - t, p.returncode, len(set(re.findall(r'actor idx=(\d+)', out)))
    for iff in extra_iffs + [LEVEL_IFF]:
        per, actors = [], None
        for _ in range(3):
            (t1, e1, a1), (t2, e2, a2) = run(iff, 100), run(iff, 600)
            assert e1 == 0 and e2 == 0, f'{iff}: exit {e1}/{e2}'
            per.append((t2 - t1) / 500 * 1000)
            actors = a2
        per.sort()
        print(f'step 18: {os.path.relpath(iff, REPO) if iff.startswith(REPO) else iff}: {actors} actors; '
              f'ms/frame over 3 runs {[round(v, 2) for v in per]} → median {per[1]:.2f} ms')


def motion_stats(r, fr):
    """Per-tick motion measured from the engine trace (step 20 and the pytest guard).

    Between ticks k and k+1 the Player moves by the velocity the script wrote at tick k:
    speed(k) × facing(yaw(k), pitch(k)). So v = ΔP / dt is compared with that facing. A tick where
    the script moved the body back inside the tank (aq-pushed, a turn that swung the nose or tail
    past a limit) also moves it, so those ticks are counted apart, not hidden."""
    rows = []
    for (t0, a), (t1, b) in zip(fr, fr[1:]):
        p0 = [a.get((r.pl, mb)) for mb in (X_POS, Y_POS, Z_POS)]
        p1 = [b.get((r.pl, mb)) for mb in (X_POS, Y_POS, Z_POS)]
        v = [(q - p) / DT for p, q in zip(p0, p1)]
        sp = math.sqrt(sum(c * c for c in v))
        f = facing(r.m('aq-yaw', (t0, a)), r.m('aq-pitch', (t0, a)))
        cosang = sum(x * y for x, y in zip(v, f)) / sp if sp > 1e-9 else 1.0
        rows.append(dict(t=t0, v=v, speed=sp, cmd=r.m('aq-speed', (t0, a)), f=f,
                         ang=math.degrees(math.acos(max(-1.0, min(1.0, cosang)))),
                         pushed=b.get((r.dir, r.mb['aq-pushed']), 0) > 0.5,
                         yaw=r.m('aq-yaw', (t0, a)), pitch=r.m('aq-pitch', (t0, a)),
                         yaw_w=r.m('aq-yaw-w', (t0, a)), burst=r.m('aq-burst', (t0, a)),
                         env=r.m('fish-tail-env', (t0, a)), ph_swim=r.m('fish-ph-swim', (t0, a)),
                         ph_pec=r.m('fish-ph-pec', (t0, a)), p=p0))
    moving = [q for q in rows if q['speed'] > 0.05]
    free = [q for q in moving if not q['pushed']]
    return rows, dict(
        moving=len(moving), pushed=sum(1 for q in moving if q['pushed']),
        worst_angle=max((q['ang'] for q in free), default=0.0),
        worst_speed_err=max((abs(q['speed'] - q['cmd']) for q in free), default=0.0),
        max_pitch=max((abs(q['pitch']) for q in rows), default=0.0),
        max_dyaw=max((abs(((b['yaw'] - a['yaw'] + 0.5) % 1.0) - 0.5) for a, b in zip(rows, rows[1:])), default=0.0),
        max_dv=max((math.dist(a['v'], b['v']) for a, b in zip(free, free[1:]) if b['t'] - a['t'] < DT * 1.5), default=0.0))


def rates(rows, key):
    """A phase accumulator's frequency per tick (Hz), from its wrapped increments."""
    return [(((b[key] - a[key]) % 1.0) / DT) for a, b in zip(rows, rows[1:])]


def segments(flags):
    """Runs of equal values: [(value, start, length)]."""
    out, k = [], 0
    while k < len(flags):
        j = k
        while j < len(flags) and flags[j] == flags[k]:
            j += 1
        out.append((flags[k], k, j - k))
        k = j
    return out


def strip_phase(r, name, button, secs, n=10):
    """Hold `button` for `secs`, taking n frames at fixed intervals, and compose them into
    OUT/phase4-motion-<name>.png (two rows, left to right = time)."""
    from PIL import Image, ImageDraw
    g = r.g
    ticks = round(secs / DT)
    per = max(1, ticks // n)
    a = r.pos()
    g.inject(BTN[button] if button else 0)
    fr, shots = [], []
    while len(fr) < ticks:
        fr += g.step(min(per, ticks - len(fr)))
        if len(shots) < n:
            on_a = g.v(r.dir, CAMSHOT) == r.idx['cs_front'] and \
                math.dist([g.v(r.cam, mb) for mb in (X_POS, Y_POS, Z_POS)], C.CAM_A_POS) < 0.05
            shots.append((fr[-1][0], g.shot(f'strip-{name}-{len(shots):02d}'), r.pos() if on_a else None))
    g.inject(0)
    r.rows.append((name, button, secs, a, r.pos(), fr))
    w, h, cols = 256, 192, 5
    img = Image.new('RGB', (w * cols, h * ((len(shots) + cols - 1) // cols)), (0, 0, 0))
    f_px = 240 / math.tan(math.radians(30))
    for k, (t, fn, p) in enumerate(shots):
        tile = Image.open(fn).convert('RGB')
        if p:          # camshot A, parked: crop 200 × 150 px around the fish (a 4.7 m × 3.5 m window)
            cx = screen_x(p[0], p[1])
            cy = 240 - f_px * (p[2] - C.CAM_A_POS[2]) / (p[1] - C.CAM_A_POS[1])
            x0 = int(min(max(cx - 100, 0), 440))
            y0 = int(min(max(cy - 75, 0), 330))
            tile = tile.crop((x0, y0, x0 + 200, y0 + 150))
        tile = tile.resize((w, h))
        ImageDraw.Draw(tile).text((6, 4), f'{name}  t {t:.2f} s', fill=(255, 255, 255))
        img.paste(tile, ((k % cols) * w, (k // cols) * h))
    out = os.path.join(OUT, f'phase4-motion-{name}.png')
    img.save(out)
    print(f'strip {name}: {out} ({len(shots)} frames, every {per * DT:.2f} s)')
    return fr


def plot_trajectory(rows, seg, base, out):
    """Top (x–y) and side (x–z) views of the Player's path, coloured by segment."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))
    for name, (a, b) in seg.items():
        pts = [q['p'] for q in rows[a - base:b - base]]
        if pts:
            ax1.plot([p[0] for p in pts], [p[2] for p in pts], '.-', ms=2, label=name, color=plt.cm.tab20(list(seg).index(name)))
            ax2.plot([p[0] for p in pts], [p[1] for p in pts], '.-', ms=2, color=plt.cm.tab20(list(seg).index(name)))
    for ax, lo, hi, lbl in ((ax1, C.SAND_TOP_M, C.WATER_LINE_M, 'z (m)'), (ax2, -C.INNER_Y_M, C.INNER_Y_M, 'y (m), glass at bottom')):
        ax.axhline(lo, color='k', lw=0.5)
        ax.axhline(hi, color='k', lw=0.5)
        for x in (-C.INNER_X_M, C.INNER_X_M):
            ax.axvline(x, color='k', lw=0.5)
        ax.set_ylabel(lbl)
        ax.set_aspect('equal')
    ax1.set_title('Player path (body centre), side view (x–z) and top view (x–y); one dot per tick')
    ax1.legend(fontsize=7, ncol=4)
    ax2.set_xlabel('x (m)')
    fig.tight_layout()
    fig.savefig(out, dpi=90)
    plt.close(fig)
    print(f'trajectory plot: {out}')


def steer():
    """Step 20: steer-and-swim, from the engine trace. Held buttons only, one tick per step."""
    r = Run()
    g = r.g
    k = r.k
    ok = {}
    # (name, button, seconds, strip?) — every move starts in open water
    seq = [('settle', None, 1.5, False), ('cruise-right', 'RIGHT', 1.0, False),
           ('climb-right', 'UP', 1.2, True), ('level', None, 1.5, False),
           ('u-turn', 'LEFT', 1.5, True), ('dive-left', 'DOWN', 1.2, True), ('level2', None, 1.5, False),
           ('toward-glass', 'B', 1.5, True), ('stop', None, 1.5, False), ('away', 'C', 1.5, False),
           ('cruise', 'RIGHT', 2.5, False), ('wall-approach', 'RIGHT', 2.0, True), ('rest', None, 2.0, False)]
    seg = {}
    try:
        g.step(30)
        for name, btn, secs, strip in seq:
            a = len(g.frames)
            strip_phase(r, name, btn, secs) if strip else r.phase(name, btn, secs)
            seg[name] = (a, len(g.frames))
        r.print_rows(r.rows)
        fr = g.frames[seg['settle'][0]:]
        rows, st = motion_stats(r, fr)
        base = seg['settle'][0]
        sl = lambda n: rows[seg[n][0] - base:seg[n][1] - base - 1]
        print(f"step 20: {st['moving']} moving ticks; velocity vs the facing: worst angle {st['worst_angle']:.3f}° "
              f"(pushed back inside the tank on {st['pushed']} ticks, excluded); |v| vs the written speed: worst "
              f"{st['worst_speed_err']:.4f} m/s")
        ok['parallel'] = st['worst_angle'] < 1.0 and st['worst_speed_err'] < 0.02
        # climb: Up alone climbs along the pitched facing, so it also moves forward
        cl = [q for q in sl('climb-right') if q['speed'] > 0.5] or [dict(v=(0, 0, 0), pitch=0.0)]
        vz = sum(q['v'][2] for q in cl) / len(cl)
        vh = sum(math.hypot(q['v'][0], q['v'][1]) for q in cl) / len(cl)
        pmax = max(q['pitch'] for q in cl) * 360
        ok['climb'] = vz > 0.3 and vh > 0.3 and pmax <= C.PITCH_MAX * 360 + 0.5
        print(f'step 20: climb (Up alone, facing +x): mean vz {vz:.3f} m/s, horizontal {vh:.3f} m/s, pitch up to '
              f'{pmax:.1f}° (limit {C.PITCH_MAX * 360:.0f}°) → {verdict(ok["climb"])}')
        dv = [q for q in sl('dive-left') if q['speed'] > 0.5] or [dict(v=(0, 0, 0), pitch=0.0)]
        ok['dive'] = sum(q['v'][2] for q in dv) < 0 and sum(q['v'][0] for q in dv) < 0
        print(f'step 20: dive (Down alone, facing −x): mean vz {sum(q["v"][2] for q in dv) / len(dv):.3f}, vx '
              f'{sum(q["v"][0] for q in dv) / len(dv):.3f} m/s, pitch down to {min(q["pitch"] for q in dv) * 360:.1f}° '
              f'→ {verdict(ok["dive"])}')
        # U-turn: the yaw passes through the side (|sin yaw| ≈ 1) and the fish moves in y: an arc
        ut = sl('u-turn')
        side = max(abs(math.sin(math.tau * q['yaw'])) for q in ut)
        ys = [q['p'][1] for q in ut]
        ok['arc'] = side > 0.95 and max(ys) - min(ys) > 0.2 and st['max_dyaw'] <= C.YAW_WMAX * DT + 1e-3
        print(f'step 20: U-turn: |sin yaw| peaks at {side:.3f}, y swept {max(ys) - min(ys):.3f} m (an arc, not a flip); '
              f'largest yaw step {st["max_dyaw"] * 360:.1f}°/tick (limit {C.YAW_WMAX * DT * 360:.1f}) → {verdict(ok["arc"])}')
        # pitch levels after release
        lv = sl('level')
        after = next((q['t'] - lv[0]['t'] for q in lv if abs(q['pitch']) * 360 < 1.0), None)
        ok['level'] = after is not None and after < 1.5 and st['max_pitch'] <= C.PITCH_MAX + 1e-4
        print(f'step 20: pitch back under 1° {after} s after release; |pitch| never over {st["max_pitch"] * 360:.2f}° '
              f'→ {verdict(ok["level"])}')
        # burst and coast while held (the cruise): durations, the coast decays, the tail is still
        cr = sl('cruise')[12:]                  # after the turn toward +x, before the wall
        runs = segments([q['burst'] for q in cr])[1:-1]
        bursts = [n * DT for v, _, n in runs if v]
        coasts = [n * DT for v, _, n in runs if not v]
        mono = all(b['cmd'] <= a['cmd'] + 1e-4 for v, s0, n in runs if not v for a, b in zip(cr[s0:s0 + n], cr[s0 + 1:s0 + n]))
        mean_u = sum(q['speed'] for q in cr) / len(cr)
        env_coast = max((cr[s0 + n - 1]['env'] for v, s0, n in runs if not v), default=1.0)
        ok['gait'] = (bursts and coasts and all(0.15 <= d <= 0.6 for d in bursts + coasts) and mono and env_coast < 0.1
                      and abs(mean_u - C.SWIM_SPEED) < 0.1 * C.SWIM_SPEED)
        print(f'step 20: cruise: mean speed {mean_u:.3f} m/s ({mean_u / C.L_M:.2f} BL/s), peak {max(q["speed"] for q in cr):.3f}, '
              f'low {min(q["speed"] for q in cr):.3f}; bursts {sorted(set(round(d, 2) for d in bursts))} s, coasts '
              f'{sorted(set(round(d, 2) for d in coasts))} s; coast speed decays monotonically: {mono}; tail envelope at '
              f'the end of a coast ≤ {env_coast:.3f} → {verdict(ok["gait"])}')
        # Strouhal: f from the engine's phase accumulator, U the measured speed, A the tail-tip excursion
        # The Director advances the phase between ticks k and k+1 with the speed the Player
        # published at tick k+1, so pair each rate with that speed. Ticks at the Nyquist cap
        # (fish-tail-hz-max) are reported but kept out of the f ∝ U check.
        fs = rates(cr, 'ph_swim')
        us = [q['cmd'] for q in cr[1:]]
        fmax = FISH.T['fish-tail-hz-max']
        st_n = [f * FISH.T['fish-tail-app'] / u for f, u in zip(fs, us) if u > 0.5]
        capped = sum(1 for f in fs if f >= fmax - 1e-3)
        bands = {}
        for f, u in zip(fs, us):
            if u > 0.5 and f < fmax - 1e-3:
                bands.setdefault(min(2, int((u - 1.5) // 1.0)) if u > 1.5 else 0, []).append(f / u)
        ratio = {b: sum(v) / len(v) for b, v in bands.items()}
        prop = max(ratio.values()) / min(ratio.values()) - 1 if ratio else 1.0
        ok['strouhal'] = min(st_n) >= 0.2 - 1e-3 and max(st_n) <= 0.4 and prop < 0.15
        print(f'step 20: tail beat: St = f·A/U over the cruise {min(st_n):.3f}..{max(st_n):.3f} (A = 0.2 L = '
              f'{FISH.T["fish-tail-app"]:.3f} m), f/U by speed band {({b: round(v, 3) for b, v in sorted(ratio.items())})} '
              f'(spread {prop * 100:.1f} %), f {min(fs):.2f}..{max(fs):.2f} Hz, {capped} ticks at the {fmax:g} Hz cap → {verdict(ok["strouhal"])}')
        pf = rates(rows, 'ph_pec')
        pu = [q['cmd'] for q in rows[1:]]
        pairs = sorted(zip(pu, pf))
        mono_p = all(b[1] >= a[1] - 1e-3 for a, b in zip(pairs, pairs[1:]) if b[0] - a[0] > 0.05)
        ok['pectoral'] = min(pf) >= 2.4 - 0.01 and max(pf) <= 4.6 + 0.01 and mono_p
        print(f'step 20: pectoral beat {min(pf):.2f}..{max(pf):.2f} Hz, rising with speed: {mono_p} → {verdict(ok["pectoral"])}')
        ok['smooth'] = st['max_dv'] < C.BURST_SPEED * DT / C.TAU_ACCEL + 0.2
        print(f'step 20: largest change of velocity between ticks {st["max_dv"]:.3f} m/s (bound '
              f'{C.BURST_SPEED * DT / C.TAU_ACCEL + 0.2:.2f}) → {verdict(ok["smooth"])}')
        # every visible part inside the tank on every tick
        lo_ok = True
        worst = [1e9] * 6
        for t, s in fr:
            e = part_world_extents(s, r.parts)
            if e is None:
                continue
            lo, hi = e
            gaps = [lo[0] + C.INNER_X_M, C.INNER_X_M - hi[0], lo[1] + C.INNER_Y_M, C.INNER_Y_M - hi[1],
                    lo[2] - C.SAND_TOP_M, C.WATER_LINE_M - hi[2]]
            worst = [min(a, b) for a, b in zip(worst, gaps)]
        ok['inside'] = min(worst) > 0
        print('step 20: every visible part, every tick: smallest gap to left/right/front glass/back/sand/water line '
              + ' '.join(f'{v:.4f}' for v in worst) + f' m → {verdict(ok["inside"])}')
        rot = [abs(wrap(s.get((r.pl, mb), 0.0))) for t, s in fr for mb in (ROT_A, ROT_B, ROT_C)]
        ok['player-rot'] = max(rot) == 0.0
        n, worst_off, wxy, wbob = r.attachment(fr)
        ok['attached'] = max(worst_off.values()) < 0.005 and wxy < 1e-3
        print(f'step 20: Player ROTATION_A/B/C over {len(fr)} ticks: max {max(rot):g} → {verdict(ok["player-rot"])}; '
              f'parts vs body offsets worst ' + ', '.join(f'{a.split("-", 1)[1]} {b * 1000:.2f} mm' for a, b in worst_off.items())
              + f' → {verdict(ok["attached"])}')
        with open(os.path.join(OUT, 'phase4-steer-trace.tsv'), 'w') as fh:
            fh.write('t\tx\ty\tz\tspeed\tcmd\tyaw\tpitch\tburst\tenv\tangle\tpushed\n')
            for q in rows:
                fh.write('\t'.join(f'{v:.4f}' for v in (q['t'], *q['p'], q['speed'], q['cmd'], q['yaw'], q['pitch'],
                                                       q['burst'], q['env'], q['ang'], q['pushed'])) + '\n')
        print(f'step 20: per-tick trace {os.path.join(OUT, "phase4-steer-trace.tsv")}')
        plot_trajectory(rows, seg, base, os.path.join(OUT, 'phase4-motion-trajectory.png'))
    finally:
        clean = r.isolation()
        g.close()
    for l in open(g.log_path, errors='replace').read().splitlines():
        if re.search(r'zforth compile error|Assert|abort', l, re.I):
            print(l)
    print('SUMMARY step 20: ' + ' '.join(f'{s} {verdict(v) if clean else "INVALID"}' for s, v in ok.items()))


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
    elif '--sway' in sys.argv:
        sway()
    elif '--steer' in sys.argv:
        steer()
    elif '--cost' in sys.argv:
        cost([os.path.abspath(a) for a in sys.argv[sys.argv.index('--cost') + 1:] if not a.startswith('-')])
    else:
        touch() if PROFILE == 'touch' else keyboard()
