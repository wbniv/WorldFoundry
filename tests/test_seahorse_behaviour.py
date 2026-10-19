"""The seahorse Director (Phase 3) run as real Forth, with the engine's half played by
the DFRM reference evaluator: each frame the Forth tick writes the control blocks and
the actor positions, then dfrm_ref.evaluate poses every visible seahorse and writes the
wrap centre, tail tip and status back (cells 33..39), one frame late as in the engine.

docs/plans/2026-10-16-saltwater-seahorses.md, Phase 3 (state diagram, mailbox map,
Settings, Visibility) and Phase 1 E3 (the block layout).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

from test_urchin_motion import binaries, zf  # noqa: F401  (the session fixture builds the zForth hosts)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))
import dfrm_ref  # noqa: E402
import seahorse as sh  # noqa: E402

TANKS = ROOT / 'wflevels' / 'aquarium_tanks'
DT = .05                                    # the desktop captures' -rate20
HOLD, RELEASE, SWIM, PROBE, GRASP, STRIKE, GREET = range(7)
NAMES = ('hold', 'release', 'swim', 'probe', 'grasp', 'strike', 'greet')
DIRECTOR = 4
ACTORS = {s: (20 + 2 * s, 21 + 2 * s) for s in range(len(sh.SEXES_BY_SEAHORSE))}     # body, fins (test indices)
MM = .01                                    # 1 mm (real) in world units
GREET_MM = 1.5                              # the error bound outside steady holds, at 20 Hz


def actor_cell(actor, mailbox):
    return 4000 + 16 * actor + (mailbox - 3009)


class Tank:
    """The Director's seahorse words in a zForth host plus the reference evaluator."""

    def __init__(self, binary, water=1, count=2, greeting=1):
        zf.BIN = binary
        self.h = zf.Host()
        self.rig = sh.rig()
        indices = {f'seahorse-{s}-body': ACTORS[s][0] for s in ACTORS}
        indices.update({f'seahorse-{s}-fins': ACTORS[s][1] for s in ACTORS})
        before, inside = sh.director_tick(indices)
        words = [
            ': INDEXOF_TIME 1906 ; : INDEXOF_DELTA_TIME 1907 ;',
            ': INDEXOF_X_POS 3009 ; : INDEXOF_Y_POS 3010 ; : INDEXOF_Z_POS 3011 ; : INDEXOF_ROTATION_C 3014 ;',
            ': tk@ read-mailbox ; : tk! write-mailbox ;',
            ': tk-dt@ INDEXOF_DELTA_TIME tk@ dup .2 > if drop 0 else 0 max .05 min then ;',
            ': write-actor-mailbox 16 * 4000 + + 3009 - write-mailbox ;',
            ': property@ swap drop 7000 + read-mailbox 1 ;',          # field f of the Director at 7000 + f
            f': pg-salt {DIRECTOR} 2 property@ if else drop 0 then ;',
            ': dfrm-pose 2drop 0 ;', ': fin-deform 2drop 2drop drop ;',
        ]
        for w in words:
            assert self.h.eval(w) == 'ok', w
        motion = (TANKS / 'urchin_motion.fth').read_text()
        source = (sh.forth_definitions(motion, ['uf-hypot']) + sh.posts_forth() + sh.clips_forth()
                  + sh.behaviour_source(DIRECTOR, TANKS)
                  + ': tick\n' + before + ' pg-salt if\n' + inside + ' then ;\n')
        path = ROOT / 'build-docker' / 'tmp'
        path.mkdir(parents=True, exist_ok=True)
        self.path = path / f'seahorse-director-{id(self)}.fth'
        self.path.write_text(source)
        loaded = self.h.load(self.path)
        assert loaded == 'ok', (loaded, source.splitlines()[int(loaded.split()[-1]) - 1] if 'line' in loaded else '')
        self.now = 1.0
        self.settings(water=water, count=count, greeting=greeting)
        self.log = {s: [] for s in ACTORS}
        self.contact = []                       # (s, state, error in world units) while held

    def settings(self, water=None, count=None, greeting=None):
        for field, v in ((2, water), (8, count), (9, greeting)):
            if v is not None:
                self.h.write(7000 + field, v)

    def block(self, s, k, n=1):
        return self.h.read(sh.cell_address(s, k)) if n == 1 else [self.h.read(sh.cell_address(s, k + i)) for i in range(n)]

    def set(self, s, k, v):
        self.h.write(sh.cell_address(s, k), v)

    def body(self, s):
        a = ACTORS[s][0]
        return [self.h.read(actor_cell(a, m)) for m in (3009, 3010, 3011, 3014)]

    def visible(self, s):
        return self.h.read(sh.PAIR_VISIBILITY[s // 2]) != 0

    def step(self, n=1, dt=DT):
        for _ in range(n):
            self.now += dt
            self.h.write(1906, self.now)
            self.h.write(1907, dt)
            assert self.h.eval('tick') == 'ok'
            for s in ACTORS:
                if not self.visible(s) or self.block(s, 40) == 0:
                    continue
                blk = self.block(s, 0, 40)
                x, y, z, yaw = self.body(s)
                c, si = math.cos(2 * math.pi * yaw), math.sin(2 * math.pi * yaw)
                world = [c, si, 0, -si, c, 0, 0, 0, 1]
                r = dfrm_ref.evaluate(self.rig, blk, self.now, world, chain_only=True)
                out = r['outputs']
                for k in range(6):
                    self.h.write(sh.block_base(s) + 33 + k, out[k])
                self.h.write(sh.block_base(s) + 39, r['status'])
                state = int(self.block(s, 41))
                if not self.log[s] or self.log[s][-1][1] != state:
                    self.log[s].append((round(self.now, 2), state))
                if state in (HOLD, GREET, STRIKE) and blk[24] >= 1:
                    # This frame's coil centre, in world, against the post axis it holds.
                    ax, ay = self.block(s, 65, 2)
                    wx = x + c * out[0] - si * out[1]
                    wy = y + si * out[0] + c * out[1]
                    self.contact.append((s, state, math.hypot(wx - ax, wy - ay), r['status']))

    def states(self, s):
        return [NAMES[k] for _t, k in self.log[s]]

    def close(self):
        self.h.close()
        self.path.unlink(missing_ok=True)


@pytest.fixture
def tank(binaries):
    t = Tank(binaries['float'])
    yield t
    t.close()


def run_until(t, pred, limit):
    for _ in range(int(limit / DT)):
        t.step()
        if pred():
            return True
    return False


def test_spots_are_grippable_and_clear_of_the_surface():
    tops = []
    for n in range(len(sh.SPOTS)):
        sp = sh.spot(n)
        assert sp['start'] >= 16                                  # hold_idle leaves rings 0..10 free
        r = dfrm_ref.evaluate(sh.rig(), sh.wrap_block('hold_idle', 2, sp['start'], sp['radius'], 1.0), 0.0,
                              chain_only=True)
        assert r['status'] == 0, n                                # no joint at its limit when held
        pos, _yaw = sh.body_at(n)
        tops.append(pos[2] + .62)
    assert max(tops) < 4.826 - .05                                # the head stays under the water surface
    assert sh.GREET_SPOTS == (0, 1) and sh.SPOTS[0][0] == sh.SPOTS[1][0]   # greeting: one post,
    assert sh.SPOTS[0][2] != sh.SPOTS[1][2] and sh.SPOTS[0][1] != sh.SPOTS[1][1]  # opposite sides, offset heights


def test_rig_chunk_matches_the_exported_rig():
    import struct
    import dfrm_chunk as dc
    data = (ROOT / 'wflevels/aquarium_plants/seahorse_f_body.iff').read_bytes()
    o, chunks = 8, {}
    while o < len(data):
        size = struct.unpack_from('<I', data, o + 4)[0]
        chunks[data[o:o + 4].decode()] = data[o + 8:o + 8 + size]
        o += 8 + size + (-size % 4)
    exported = dc.decode(chunks['DFRM'])
    mine = sh.rig_chunk()
    assert [(c['first'], c['frames'], c['loop']) for c in exported['clips']] == \
        [(c['first'], c['frames'], c['loop']) for c in mine['clips']]
    assert len(exported['frames']) == len(mine['frames'])
    assert max(abs(a - b) for r, q in zip(exported['frames'], mine['frames']) for a, b in zip(r, q)) < .011


def test_the_director_compiles_within_the_dictionary(tank):
    assert tank.h.size() < 65536


def test_hold_release_swim_probe_grasp_hold(tank):
    """Seahorse 1 (restless first, at 6 s) runs the whole cycle onto another spot."""
    t = tank
    t.step(2)
    assert all(t.block(s, 41) == HOLD for s in range(4))
    start = t.block(1, 43)
    assert run_until(t, lambda: t.block(1, 41) == SWIM, 15)
    assert t.block(1, 24) == 0 and t.block(1, 43) != start
    assert run_until(t, lambda: t.block(1, 41) == HOLD, 120), t.states(1)
    seq = t.states(1)
    i = seq.index('release')
    # Longer trips can include a prey strike, then resume swimming.
    cycle = []
    for state in seq[i:]:
        if state != 'strike' and (not cycle or state != cycle[-1]):
            cycle.append(state)
    assert cycle[:5] == ['release', 'swim', 'probe', 'grasp', 'hold'], seq
    assert t.block(1, 24) == 1 and t.block(1, 21) == 2
    assert t.block(1, 22) >= 16
    # Arrived at the spot it reserved: the coil is on that post.
    t.step(10)
    held = [e for s, st, e, _ in t.contact[-40:] if s == 1]
    assert held and max(held) <= .5 * MM


def test_hold_keeps_the_wrap_centre_on_the_post(tank):
    """Over 20 s of hold (body sway, hold_idle, saccades, strikes) the coil centre stays
    within 0.5 mm (real) of the post axis: the solve is one frame late."""
    t = tank
    t.step(1)
    for s in range(4):
        t.set(s, 44, 999)                  # nobody leaves
    t.step(400)
    errs = [e for _s, _st, e, _ in t.contact]
    assert len(errs) > 1500
    assert max(errs) <= .5 * MM, max(errs) / MM
    assert {st for _s, st, _e, _ in t.contact} >= {HOLD, STRIKE}
    assert all(status in (0, 3) for *_x, status in t.contact)


def test_strike_snaps_the_head_in_one_frame_then_recovers_slowly(tank):
    t = tank
    t.step(2)
    t.set(0, 44, 999)
    t.set(0, 52, .01)                       # an ambient particle comes into range
    t.step(1)
    assert t.block(0, 41) == STRIKE
    snap = t.block(0, 30)
    assert snap > 18                        # within one frame
    t.step(4)
    later = t.block(0, 30)
    assert 3 < later < snap                 # and recovers over several frames, not at once
    assert run_until(t, lambda: t.block(0, 41) == HOLD, 3)
    assert t.block(0, 30) < later


def test_clips_crossfade_rather_than_snap(tank):
    t = tank
    t.step(2)
    assert t.block(1, 25) == sh.CLIP_IDS['hold_idle']
    assert run_until(t, lambda: t.block(1, 41) == RELEASE, 15)
    assert t.block(1, 27) == sh.CLIP_IDS['release'] and t.block(1, 29) > 0
    assert t.block(1, 25) == sh.CLIP_IDS['hold_idle']       # A stays while B fades in
    assert run_until(t, lambda: t.block(1, 41) == SWIM, 5)
    assert t.block(1, 25) == sh.CLIP_IDS['release'] and t.block(1, 27) == sh.CLIP_IDS['swim']


def test_swim_is_slow_upright_and_ruddered(tank):
    t = tank
    assert run_until(t, lambda: t.block(1, 41) == SWIM, 15)
    # Start a quarter-turn off the route to exercise steering independently of which free post is picked.
    t.set(1, 48, t.block(1, 48) + .25)
    speeds, rudder = [], []
    for _ in range(200):
        t.step()
        if t.block(1, 41) != SWIM:
            break
        speeds.append(math.hypot(t.block(1, 49), t.block(1, 50)))
        rudder.append(abs(t.block(1, 13)))
    assert max(speeds) <= sh.SWIM_SPEED + 1e-3                    # 1.5 cm/s real
    assert max(speeds) > .1
    assert max(rudder) > .5                                      # the tail steers through the knot layer


def test_greeting_brings_a_pair_to_one_post_for_two_minutes(tank):
    t = tank
    t.step(2)
    t.h.write(sh.GREET_BASE + 3, .01)                                         # greeting due now
    assert run_until(t, lambda: t.h.read(sh.GREET_BASE + 0) == 2, 240), (t.states(0), t.states(1), t.states(2), t.states(3))
    pair = int(t.h.read(sh.GREET_BASE + 1))
    f, m = 2 * pair, 2 * pair + 1
    assert t.block(f, 41) == GREET and t.block(m, 41) == GREET
    assert t.block(f, 43) == 0 and t.block(m, 43) == 1          # one post, opposite sides, offset heights
    assert t.block(f, 25) in (sh.CLIP_IDS['greet_f'],) or t.block(f, 27) == sh.CLIP_IDS['greet_f']
    assert t.block(m, 27) == sh.CLIP_IDS['greet_m']
    began = t.now
    assert run_until(t, lambda: t.h.read(sh.GREET_BASE + 0) == 0, sh.GREET_SECONDS + 5)
    assert t.now - began == pytest.approx(sh.GREET_SECONDS, abs=1)
    assert t.block(f, 41) in (HOLD, STRIKE) and t.block(m, 41) in (HOLD, STRIKE) and t.block(f, 60) == 0
    held = [e for s, st, e, _ in t.contact if s in (f, m) and st == GREET]
    assert held and max(held) <= GREET_MM * MM, max(held) / MM


def test_greeting_off_never_starts_one(binaries):
    t = Tank(binaries['float'], greeting=0)
    try:
        t.step(2)
        t.h.write(sh.GREET_BASE + 3, .01)
        t.step(200)
        assert t.h.read(sh.GREET_BASE + 0) == 0 and all(GREET not in [k for _t, k in t.log[s]] for s in range(4))
    finally:
        t.close()


@pytest.mark.parametrize('count', range(sh.PAIR_COUNT + 1))
def test_settings_choose_the_pairs(binaries, count):
    shown = tuple(int(p < count) for p in range(sh.PAIR_COUNT))
    t = Tank(binaries['float'], count=count)
    try:
        t.step(3)
        assert tuple(t.h.read(mb) for mb in sh.PAIR_VISIBILITY) == shown
        for s in ACTORS:
            assert (t.block(s, 40) != 0) == bool(shown[s // 2])         # hidden pairs are skipped
    finally:
        t.close()


def test_freshwater_hides_and_skips_then_saltwater_restores(tank):
    t = tank
    t.step(5)
    t.settings(water=0)
    t.step(3)
    assert (t.h.read(1162), t.h.read(1163)) == (0, 0)
    assert all(t.block(s, 40) == 0 for s in range(4))
    frozen = t.block(0, 0, 40)
    t.step(5)
    assert t.block(0, 0, 40) == frozen                                 # no behaviour runs in freshwater
    t.settings(water=1, count=1)
    t.step(3)
    assert (t.h.read(1162), t.h.read(1163)) == (1, 0)
    assert t.block(0, 41) == HOLD and t.block(0, 24) == 1
    t.settings(count=2)
    t.step(3)
    assert t.h.read(1163) == 1 and t.block(3, 40) == 1


def test_no_two_seahorses_share_a_spot_over_ten_minutes(tank):
    t = tank
    worst = 0.0
    for _ in range(int(600 / DT)):
        t.step()
        spots = [int(t.block(s, 43)) for s in range(4)]
        assert len(set(spots)) == 4, (t.now, spots)
    for s in range(4):
        seq = t.states(s)
        assert seq.count('grasp') >= 1, seq
    hold = [e for _s, st, e, _ in t.contact if st in (HOLD, STRIKE)]
    every = [e for _s, _st, e, _ in t.contact]
    assert len(hold) > 10000
    # Steady holds stay within 0.5 mm; the greet clip and clip crossfades bend the free
    # rings faster, so their one-frame-late error is larger (still under a ring's width).
    assert sorted(hold)[int(.999 * len(hold))] <= .5 * MM
    assert max(every) <= GREET_MM * MM, max(every) / MM


def test_mailbox_map_matches_the_actor_map():
    m = json.loads((ROOT / 'wflevels/aquarium_plants/actor-map.json').read_text())['seahorses']
    assert m['pair_visibility'] == list(sh.PAIR_VISIBILITY) and m['post_visibility'] == 1162
    assert m['greeting_state'] == [sh.GREET_BASE, sh.GREET_BASE + 9]
    blocks = [[sh.cell_address(a['seahorse'], i) for i in range(98)] for a in m['actors']]
    cells = [c for b in blocks for c in b] + list(range(sh.GREET_BASE, sh.GREET_BASE + 10)) + list(sh.PAIR_VISIBILITY)
    assert len(cells) == len(set(cells)) and max(cells) < 1900
    other = set(range(600, 640)) | {747, 748, 1160, 1161} | set(range(800, 968)) | set(range(1000, 1112)) \
        | set(range(1140, 1160)) | {70, 71, 72} | set(range(1800, 1900))
    assert not other & set(cells)


def test_six_pairs_have_distinct_homes_and_run_independently(binaries):
    t = Tank(binaries['float'], count=sh.PAIR_COUNT, greeting=0)
    try:
        t.step(2)
        assert len(ACTORS) == 12
        assert all(t.visible(s) and t.block(s, 40) == 1 for s in ACTORS)
        assert [int(t.block(s, 43)) for s in ACTORS] == list(sh.HOME)
        for _ in range(int(90 / DT)):
            t.step()
            spots = [int(t.block(s, 43)) for s in ACTORS]
            assert len(set(spots)) == 12, (t.now, spots)
        assert all('swim' in t.states(s) for s in ACTORS)
        t.settings(water=0)
        t.step(2)
        assert all(not t.visible(s) and t.block(s, 40) == 0 for s in ACTORS)
        t.settings(water=1, count=6)
        t.step(2)
        assert all(t.visible(s) and t.block(s, 40) == 1 for s in ACTORS)
    finally:
        t.close()


@pytest.mark.parametrize('pair', [2, 5])
def test_greeting_finds_both_partners_across_mailbox_ranges(binaries, pair):
    t = Tank(binaries['float'], count=6)
    try:
        t.step(2)
        # Clear the two reserved greeting spots without changing the actors' state.
        for s in ACTORS:
            t.set(s, 43, s + 2)
        t.h.write(sh.GREET_BASE + 1, pair - 1)
        assert t.h.eval('shg-start') == 'ok'
        assert t.h.read(sh.GREET_BASE) == 1
        assert int(t.h.read(sh.GREET_BASE + 1)) == pair
        assert t.block(2 * pair, 60) == t.block(2 * pair + 1, 60) == 1
        assert all(t.block(s, 60) == 0 for s in ACTORS if s // 2 != pair)
    finally:
        t.close()
