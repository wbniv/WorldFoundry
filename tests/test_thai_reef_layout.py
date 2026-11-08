"""The reef's Forth layout (plan 2026-11-08 W5c), run in the real zForth VM on the exported scripts.

Regression guard for the layout contract: Fixed is the reviewed reef exactly; Random is seeded
(same seed, same reef; Seed 0 draws a seed), shows Rocks modules with heroes first while
Rocks >= 3, keeps heroes at heading 0, never overlaps footprints, keeps everything in the
room box and the boxfish's patrol lane and spawn clear, grows the chosen number of colony
clumps on site-table points, and moves every reaction anchor with its module.
"""
import ast
import json
import math
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# REEF_TEST_LEVEL_DIR picks another export (the anime style, or a scratch build).
HERE = Path(os.environ.get('REEF_TEST_LEVEL_DIR', ROOT / 'wflevels' / 'aquarium_thai_reef'))
LEVEL = HERE.name
ROOM = ((-25, -30, -6), (25, 10, 18))
X_POS, ROT_A = 3009, 3012


@pytest.fixture(scope='module')
def run(tmp_path_factory):
    """run(props, steps=2, extra='') -> (actors {index: (x, y, z, a, b, c)}, globals {cell: v})."""
    tmp = tmp_path_factory.mktemp('reef-layout-vm')
    src = (ROOT / 'engine/stubs/scripting_zforth.cc').read_text()
    core = src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')]
    core = re.sub(r'//[^\n]*', '', core)
    definitions = ''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"', core))
    mailbox = (ROOT / 'wfsource/source/mailbox/mailbox.inc').read_text()
    constants = {f'INDEXOF_{k}': int(v) for k, v in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)', mailbox)}
    constants.update({f'JOYSTICK_BUTTON_{k}': 1 << i for i, k in enumerate('ABCDEFGHIJK')})
    constants.update({f'JOYSTICK_BUTTON_{k}': 1 << i for i, k in enumerate(('UP', 'DOWN', 'RIGHT', 'LEFT'), 11)})
    definitions += '\n' + ''.join(f': {k} {v} ;\n' for k, v in constants.items())
    definitions += (": read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ;"
                    " : read-actor-mailbox 152 sys ; : random 153 sys ; : seed-random 154 sys ;"
                    " : r@ ' lit , 0 , ' pickr , ; immediate\n")
    definitions += re.search(r'zf_eval\(&g_ctx, "(: profile-begin [^"]*)"\)', src).group(1) + '\n'
    vendor = ROOT / 'engine/vendor/zforth-41db72d1/src/zforth'
    binary = tmp / 'vm'
    subprocess.run(['cc', '-O1', '-I' + str(ROOT / 'engine/stubs'), '-I' + str(vendor), str(ROOT / 'tests/species_vm.c'),
                    str(vendor / 'zforth.c'), '-lm', '-o', str(binary)], check=True)
    mapping = json.loads((HERE / 'actor-map.json').read_text())
    text = (HERE / f'{LEVEL}.lev').read_text()
    paths = []
    for name, entry in (('Player', 'tk-player-tick'), ('Director', 'reef-tick')):
        block = text[text.index('{ \'NAME\' "' + name + '" }'):].split("{ 'OBJ'", 1)[0]
        encoded = re.search(r'\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' ("(?:\\.|[^"\\])*")', block).group(1)
        path = tmp / f'{name}.fth'
        path.write_text(definitions + json.loads(encoded).removesuffix('\n' + entry + '\n'))
        paths.append(path)
    director = mapping['indices']['Director']

    def go(props, steps=2, extra='', player=(4, -1.2, 2.5)):
        trace = f'reset {player[0]} {player[1]} {player[2]}\n'
        trace += ''.join(f'prop {director} {field} {value}\n' for field, value in props.items())
        trace += f'step {steps} 0 .0166667\n{extra}dumpa 1 {len(mapping["indices"]) + 1}\ndumpg 0 1100\n'
        result = subprocess.run([str(binary), *map(str, paths), str(mapping['indices']['Player']), str(director),
                                 'tk-player-tick', 'reef-tick'], input=trace, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        actors, cells = {}, {}
        for line in result.stdout.splitlines():
            if line.startswith('A '):
                f = line.split()
                actors[int(f[1])] = tuple(map(float, f[2:8]))
            elif line.startswith('G '):
                f = line.split()
                cells = {int(f[1]) + i: float(v) for i, v in enumerate(f[2:])}
        return actors, cells
    go.mapping = mapping
    return go


def _modules(run):
    return run.mapping['kit']['modules']


def _layout(run, layout=1, rocks=3, colonies=1, seed=7):
    return run({1: layout, 2: rocks, 3: colonies, 4: seed})


def _shown(cells, run):
    return [m['name'] for i, m in enumerate(_modules(run)) if cells[880 + i] == 1]


def _pivots(cells, run):
    return {m['name']: (cells[886 + i], cells[892 + i], cells[898 + i]) for i, m in enumerate(_modules(run))
            if cells[880 + i] == 1}


def test_fixed_is_the_reviewed_reef(run):
    actors, cells = _layout(run, layout=0)
    mods = _modules(run)
    assert _shown(cells, run) == [m['name'] for m in mods if m['role'] == 'hero']
    for i, m in enumerate(mods):
        assert cells[m['cell']] == (1 if m['role'] == 'hero' else 0)
        if m['role'] == 'hero':
            for actor in m['piece_actors'] + [m['collider_actor']]:
                assert actors[actor][:3] == pytest.approx(tuple(m['pivot']), abs=1e-4)
            for actor, off in m['attached_offsets']:
                assert actors[actor][1] == pytest.approx(m['pivot'][1] + off[1], abs=1e-4)
            assert cells[904 + i] == 0 and cells[907 + i] == 0
    for clump in run.mapping['kit']['clumps']:
        assert cells[clump['cell']] == 0


@pytest.mark.parametrize('rocks', [1, 2, 3, 4, 5])
def test_rocks_pick_heroes_first_without_overlap_inside_the_room(run, rocks):
    mods = {m['name']: m for m in _modules(run)}
    heroes = [m for m in mods if mods[m]['role'] == 'hero']
    for seed in (1, 2, 3, 99, 4242):
        actors, cells = _layout(run, rocks=rocks, seed=seed)
        shown = _shown(cells, run)
        assert len(shown) == rocks
        if rocks >= 3:
            assert set(heroes) <= set(shown)
        else:
            assert set(shown) <= set(heroes)
        pivots = _pivots(cells, run)
        boxes = []
        for name, (x, y, h) in pivots.items():
            m = mods[name]
            if m['role'] == 'hero':
                assert h == 0                                   # heroes keep heading 0
            else:
                assert h in (0, .5)
            half = m['footprint_half']
            depth = m['collider_box']['hi'][1]
            boxes.append((x - half, x + half, y - depth, y + depth))
            assert ROOM[0][0] < x - half and x + half < ROOM[1][0]
            assert -6 < x - half and x + half < 6               # on the sand
            assert -3 < y - depth and y + depth < 3
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                overlap = min(a[1], b[1]) - max(a[0], b[0]) > 1e-6 and min(a[3], b[3]) - max(a[2], b[2]) > 1e-6
                assert not overlap, (seed, rocks, a, b)
        for name in mods:
            if name not in shown:
                assert cells[mods[name]['cell']] == 0
                c = actors[mods[name]['collider_actor']]
                assert c[2] < 0 and ROOM[0][2] < c[2]           # parked under the sand, inside the room


def test_same_seed_same_reef_other_seed_other_reef(run):
    a = _layout(run, rocks=5, seed=31)[1]
    b = _layout(run, rocks=5, seed=31)[1]
    c = _layout(run, rocks=5, seed=32)[1]
    key = lambda cells: [round(cells[k], 5) for k in range(880, 904)] + [cells[k] for k in range(210, 219)]
    assert key(a) == key(b)
    assert key(a) != key(c)


def test_seed_zero_draws_a_seed_and_keeps_it_across_other_changes(run):
    director = run.mapping['indices']['Director']
    _, first = _layout(run, rocks=4, seed=0)
    assert first[875] >= 1
    # Colonies changes a second later: the reef re-lays out with the same drawn seed.
    _, later = run({1: 1, 2: 4, 3: 1, 4: 0}, steps=2, extra=f'prop {director} 3 2\nstep 70 0 .0166667\n')
    assert later[872] == 2 and later[875] == first[875]
    assert [later[k] for k in range(880, 904)] == [first[k] for k in range(880, 904)]


@pytest.mark.parametrize('colonies, shown', [(0, 3), (1, 6), (2, 9)])
def test_colonies_show_their_clumps_on_site_points(run, colonies, shown):
    mods = _modules(run)
    actors, cells = _layout(run, rocks=5, colonies=colonies, seed=5)
    clumps = run.mapping['kit']['clumps']
    on = [c for c in clumps if cells[c['cell']] == 1]
    assert len(on) == shown
    sites = []
    for i, m in enumerate(mods):
        if cells[880 + i] != 1 or m['role'] != 'filler':
            continue
        x, y, h = cells[886 + i], cells[892 + i], cells[898 + i]
        s = -1 if h else 1
        sites += [(x + s * p['p'][0], y + s * p['p'][1], .72 + p['p'][2], m['name']) for p in m['sites']]
    for c in on:
        pos = actors[c['actor_index']][:3]
        assert min(math.dist(pos, q[:3]) for q in sites) < 1e-3, c['actor']
        a, b = actors[c['actor_index']][3:5]
        z = (math.sin(b * math.tau) * math.cos(a * math.tau), -math.sin(a * math.tau),
             math.cos(b * math.tau) * math.cos(a * math.tau))
        assert z[2] > -.5                                       # turned out of the rock, not into the sand
    for c in clumps:
        if c not in on:
            assert actors[c['actor_index']][2] < 0


def test_anchors_follow_their_modules(run):
    mods = {m['name']: m for m in _modules(run)}
    actors, cells = _layout(run, rocks=3, seed=11)
    for i, name in enumerate(('left', 'arch', 'right')):
        dx, dy = cells[904 + i], cells[907 + i]
        pivot = mods[name]['pivot']
        assert cells[886 + i] - pivot[0] == pytest.approx(dx, abs=1e-4)
        for actor, off in mods[name]['attached_offsets']:
            assert actors[actor][1] == pytest.approx(pivot[1] + dy + off[1], abs=1e-3)
    # The cleaner station (arch) and the guard crab (left) follow their hosts.
    station = run.mapping['anchors']['cleaner_station']
    # (the shrimp ease toward a gently wobbling target, amplitude 0.06)
    assert cells[645] == pytest.approx(station[0] + cells[905], abs=.1)
    assert cells[747] == pytest.approx(station[1] + cells[908], abs=.1)
    assert abs(cells[905]) > .1 or abs(cells[908]) > .05      # the arch really moved in this layout


def test_patrol_lane_and_spawn_stay_clear_of_colliders(run):
    spawn = run.mapping['anchors']['boxfish_spawn']
    mods = _modules(run)
    for rocks in (3, 4, 5):
        for seed in (1, 8, 64):
            actors, cells = _layout(run, rocks=rocks, seed=seed)
            for i, m in enumerate(mods):
                c = actors[m['collider_actor']]
                lo = [c[k] + m['collider_box']['lo'][k] for k in range(3)]
                hi = [c[k] + m['collider_box']['hi'][k] for k in range(3)]
                # lane: x in [-3.3, 3.3], z 2.2-2.8, y near the spawn's -0.5 (hull 0.05)
                lane = not (hi[0] < -3.3 or lo[0] > 3.3 or hi[2] < 2.2 or lo[2] > 2.8 or hi[1] < -.6 or lo[1] > -.4)
                assert not lane, (rocks, seed, m['name'], lo, hi)
                inside = all(lo[k] - .1 <= spawn[k] <= hi[k] + .1 for k in range(3))
                assert not inside


def test_neighbouring_seeds_choose_different_rocks(run):
    """xorshift's first outputs barely differ for small neighbouring seeds; the layout warms the
    generator up, so Rocks 1 across seeds 1-8 shows more than one hero."""
    picks = {tuple(_shown(_layout(run, rocks=1, seed=seed)[1], run)) for seed in range(1, 9)}
    assert len(picks) >= 2, picks
