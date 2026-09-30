"""Regression guard for the aquarium level (docs/plans/2026-09-30-aquarium-level.md § Regression guard).

Reads the exported wflevels/aquarium/aquarium.lev (rebuilt by `task aquarium-level`) and
wflevels/aquarium/aquarium_constants.py, so the plan's tank table, the level and this test
cannot drift. Plan B: there is no front pane, so the plan's pane-texture check is dropped and
replaced by "no translucent actor exists, the front collider is invisible".

Phase 3 adds: the canonical clownfish (an invisible Physics hull created first, then five Mass-0
anchored platform parts, never statplats), no placeholder mesh, the Director running the rig
then the camera zones with the right actor indices, camshots A and B outside the tank, the
anemone zone and its hysteresis, the level's clamps from the fish's extents, and one source for
the scale and the fish's length. The runtime behaviour is wflevels/aquarium/run_aquarium_checks.py.
"""
import importlib.util
import math
import os
import re
import sys

import pytest

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
LEVEL_DIR = os.path.join(REPO, 'wflevels', 'aquarium')
LEV = os.path.join(LEVEL_DIR, 'aquarium.lev')

_spec = importlib.util.spec_from_file_location('aquarium_constants',
                                               os.path.join(LEVEL_DIR, 'aquarium_constants.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
sys.path.insert(0, LEVEL_DIR)
import clownfish as CF                                             # noqa: E402

FISH = CF.Clownfish()
NUM = r"(-?[\d.]+)\(1\.15\.16\)"

# Names the snowgoons scaffold uses (`player_33`, `target_14`, …): class + '_' + number.
SNOWGOONS_NAME = re.compile(r'^(room|light|camera|director|levelobj|matte|camshot|target|player|'
                            r'statplat|platform|enemy|snowgoon|actbox)_\d+$', re.I)


def _objects():
    if not os.path.exists(LEV):
        pytest.fail(f'{LEV} missing — run `task aquarium-level`')
    text = open(LEV).read()
    objs = []
    for block in text.split("\t{ 'OBJ' ")[1:]:
        name = re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)
        box = re.search(r"Global Bounding Box\" \} \{ 'DATA' ([^/]*)//", block)
        cls = re.search(r"\"Class Name\" \} \{ 'DATA' \"([^\"]+)\"", block)
        mesh = re.search(r"\"Mesh Name\" \} \{ 'STR' \"([^\"]*)\"", block)
        vis = re.search(r"\"Visibility Mailbox\" \} \{ 'DATA' (-?\d+)l", block)
        mass = re.search(r"\"Mass\" \} \{ 'DATA' " + NUM, block)
        mob = re.search(r"\"Mobility\" \} \{ 'STR' \"([^\"]*)\"", block)
        pos = re.search(r"\"Position\" \} \{ 'DATA' " + r"\s*".join([NUM] * 3), block)
        script = re.search(r"\"Script\" \} \{ 'STR' \"(.*?)\" \}", block, re.S)
        objs.append({
            'name': name,
            'class': cls.group(1) if cls else '',
            'box': [float(v) for v in re.findall(NUM, box.group(1))] if box else None,
            'mesh': mesh.group(1) if mesh else '',
            'visible': int(vis.group(1)) if vis else None,
            'mass': float(mass.group(1)) if mass else None,
            'mobility': mob.group(1) if mob else '',
            'pos': tuple(float(v) for v in pos.groups()) if pos else None,
            'script': script.group(1).replace('\\n', '\n').replace('\\\\', '\\') if script else '',
            'block': block,
        })
    return objs


@pytest.fixture(scope='module')
def objs():
    return _objects()


def by_name(objs, name):
    hits = [o for o in objs if o['name'] == name]
    assert len(hits) == 1, f'{name}: {len(hits)} actors'
    return hits[0]


def test_shell_bbox_is_48_by_13_by_21_inches(objs):
    box = by_name(objs, 'tank-shell')['box']
    size = [box[3] - box[0], box[4] - box[1], box[5] - box[2]]
    want = [48 * C.IN * C.WORLD_SCALE, 13 * C.IN * C.WORLD_SCALE, 21 * C.IN * C.WORLD_SCALE]
    assert size == pytest.approx(want, abs=1e-3), f'shell {size} m, want {want} m at ×{C.WORLD_SCALE:g}'
    assert box[2] == pytest.approx(0.0, abs=1e-4), 'shell base must sit at z = 0'


def test_water_line_volume_is_45_2_gallons():
    # Recomputed from the raw dimensions, not read from C.FILL_GAL, so a stray edit to either shows.
    inner = (C.EXT_X - 2 * C.WALL) * (C.EXT_Y - 2 * C.WALL) * (C.WATER_Z - C.WALL)
    gal = inner / 231.0
    assert gal == pytest.approx(45.2, rel=0.01)
    assert C.FILL_GAL == pytest.approx(gal)


def test_exactly_one_player_anemone_and_zone(objs):
    names = [o['name'] for o in objs]
    for n in ('Player', 'anemone', 'anemone-zone'):
        assert names.count(n) == 1, f'{n} appears {names.count(n)} times'
    assert by_name(objs, 'anemone-zone')['class'] == 'target'


def test_no_snowgoons_derived_names_remain(objs):
    leaks = [o['name'] for o in objs if SNOWGOONS_NAME.match(o['name'])]
    leaks += [o['mesh'] for o in objs if o['mesh'] and SNOWGOONS_NAME.match(os.path.splitext(o['mesh'])[0])]
    leaks += [o['mesh'] for o in objs if o['mesh'] == 'player.iff']        # snowgoons' player mesh
    assert not leaks, f'snowgoons names leaked: {leaks}'
    assert all(len(o['mesh']) <= 30 for o in objs), 'asset map holds 31 bytes per name'


def test_player_is_created_before_the_tank(objs):
    # Phase 1: JoltCharacterCreate ignores a static body whose AABB already encloses the
    # character, and the one-piece tank-shell encloses the fish.
    names = [o['name'] for o in objs]
    assert names.index('Player') < names.index('tank-shell')


def test_player_bbox_is_authored_symmetric_and_not_thin(objs):
    # Phase 1: levcomp inflates any span < 0.25 m by moving its min face, shifting the capsule.
    x0, y0, z0, x1, y1, z1 = by_name(objs, 'Player')['box']
    assert min(x1 - x0, y1 - y0, z1 - z0) >= 0.25
    assert x0 == pytest.approx(-x1) and y0 == pytest.approx(-y1)


def test_plan_b_nothing_translucent_front_collider_invisible(objs):
    names = {o['name'] for o in objs}
    assert not names & {'tank-front-pane', 'water-surface'}, 'Plan B: the engine drops texture alpha'
    assert by_name(objs, 'tank-front-collider')['visible'] == 0


def test_fog_is_the_water(objs):
    cam = by_name(objs, 'Camera')['block']
    colour = int(re.search(r"\"FoggingColor\" \} \{ 'DATA' (\d+)l", cam).group(1))
    complete = float(re.search(r"\"FoggingCompleteDistance\" \} \{ 'DATA' ([\d.]+)", cam).group(1))
    assert colour == C.FOG_COLOR != 0x888888, 'snowgoons fog must be overridden'
    assert complete == pytest.approx(C.FOG_COMPLETE) and complete < 1000.0


# ── Phase 3: the canonical clownfish, the controls, camshot B ────────────────────────────
def _header(script):
    """The `: name value ;` constants a script carries (the fish's and the level's headers)."""
    return {k: float(v) for k, v in re.findall(r"^: ([a-z][\w-]*) (-?[\d.]+) ;", script, re.M)}


def test_constants_have_one_source():
    # aquarium_constants.py is the single source; clownfish.py takes the scale and the length from it.
    assert CF.DEFAULT_WORLD_SCALE == C.WORLD_SCALE
    assert CF.FISH_REAL_LENGTH_M == pytest.approx(C.FISH_LEN * C.IN)
    assert FISH.length_m == pytest.approx(C.m(C.FISH_LEN))
    assert FISH.T['fish-swim-speed'] == pytest.approx(C.SWIM_SPEED)     # Phase 1's 12 in/s × scale
    assert CF.PHYSICS['wf_Max Air Speed'] == pytest.approx(C.DART_SPEED)  # the dart is capped there anyway


def test_player_first_then_the_five_parts_then_the_tank(objs):
    names = [o['name'] for o in objs]
    order = [names.index('Player')] + [names.index(n) for n in CF.PART_NAMES] + [names.index('tank-shell')]
    assert order == sorted(order), f'actor order {order}: Player, then the parts, then tank-shell'


def test_player_is_the_invisible_physics_hull_running_the_swim_controller(objs):
    p = by_name(objs, 'Player')
    assert p['class'] == 'player' and p['mobility'] == 'Physics'
    assert p['visible'] == 0, 'the Player is the invisible hull; the parts are the fish'
    assert p['mesh'] == CF.mesh_file(CF.PLAYER_MESH)
    assert tuple(p['box']) == pytest.approx(FISH.collision_box(), abs=1e-3)
    assert p['script'].rstrip().endswith('aq-player-tick'), 'the level swim controller is the entry'
    assert 'fish-idle-sense' in p['script'] and 'aq-no-kicks' in p['script']
    # Nobody writes the Player's own ROTATION_C: the rig owns the visual heading.
    assert not re.search(r'INDEXOF_ROTATION_C\s+write-mailbox', p['script'])


def test_five_parts_are_mass0_anchored_platforms_not_statplats(objs):
    for n in CF.PART_NAMES:
        o = by_name(objs, n)
        # Every statplat gets a Jolt body whatever its Mass, and a statplat part pins the Player.
        assert o['class'] == 'platform', f'{n} is a {o["class"]}, must be an anchored platform'
        assert o['mobility'] == 'Anchored' and o['mass'] == 0.0 and o['visible'] == 1, n
        assert o['mesh'] == CF.mesh_file(n), n
        assert not o['script'], f'{n}: the Director poses the parts; they carry no script'


def test_no_placeholder_fish_remains(objs):
    assert not any('placeholder' in o['mesh'] or 'placeholder' in o['name'] for o in objs)
    assert not os.path.exists(os.path.join(LEVEL_DIR, 'fish_placeholder.iff'))
    assert 'fish_placeholder' not in open(os.path.join(LEVEL_DIR, 'blender_create_aquarium.py')).read()


def test_director_runs_the_rig_then_the_camera_with_the_right_indices(objs):
    names = [o['name'] for o in objs]
    script = by_name(objs, 'Director')['script']
    assert script.rstrip().endswith('fish-rig-tick\naq-camera-tick\naq-sway-tick'), \
        'rig first (after every actor), then cameras, then the anemone sway'
    h = _header(script)
    for n in CF.PART_NAMES:
        assert h[f'fish-actor-{CF.ROLES[n]}'] == names.index(n) + 1, f'{n}: header index != export position + 1'
    assert h['fish-actor-player'] == names.index('Player') + 1
    assert h['aq-shot-a'] == names.index('cs_front') + 1
    assert h['aq-shot-b'] == names.index('cs_anemone') + 1
    assert h['aq-look-b'] == names.index('LookB') + 1
    mailboxes = ('aq-prev', 'aq-mode', 'aq-dart-t', 'aq-dart-req', 'aq-in-b', 'aq-dx', 'aq-dy', 'aq-dz',
                 'aq-vx', 'aq-vy', 'aq-vz')
    assert all(700 <= h[k] < 720 for k in mailboxes), 'the level mailboxes live in 700..719 (the fish owns 600..639)'
    assert h['aq-touch'] == 0, 'the committed level is the keyboard/gamepad profile'


def test_camshots_a_and_b_sit_outside_the_tank_clear_of_the_fish(objs):
    names = [o['name'] for o in objs]
    for n in ('cs_front', 'cs_anemone'):
        assert names.count(n) == 1 and by_name(objs, n)['class'] == 'camshot'
    a, b = by_name(objs, 'cs_front'), by_name(objs, 'cs_anemone')
    assert a['pos'] == pytest.approx(C.CAM_A_POS, abs=1e-3) and b['pos'] == pytest.approx(C.CAM_B_POS, abs=1e-3)
    # A bungee camera climbs while its bbox overlaps a Mass > 0 actor (the Player is Mass 1):
    # camera B's box must stay in front of the furthest the fish's box can come toward the glass.
    cam = by_name(objs, 'Camera')
    h = _header(by_name(objs, 'Director')['script'])
    fish_front = -(h['aq-ymax'] + FISH.collision_box()[4])
    assert b['pos'][1] + cam['box'][4] < fish_front, 'camera B box overlaps the fish swimming at the glass'
    assert b['pos'][1] < -C.EXT_Y_M / 2, 'camera B must be outside the tank'
    for n in ('Follow', 'Target', 'Track Object'):     # bungee aim = Target − Follow + Track Object
        assert re.search(r"\"%s\" \} \{ 'STR' \"LookB\"" % n, b['block']), f'cs_anemone {n} must be LookB'
    assert by_name(objs, 'LookB')['class'] == 'platform' and by_name(objs, 'LookB')['mass'] == 0.0


def test_anemone_zone_and_hysteresis(objs):
    z = by_name(objs, 'anemone-zone')
    R = C.ANEMONE_ZONE_RADIUS
    assert z['box'] == pytest.approx([-R, -R, -R, R, R, R], abs=1e-3)
    h = _header(by_name(objs, 'Director')['script'])
    assert (h['aq-zone-x'], h['aq-zone-y'], h['aq-zone-z']) == pytest.approx(z['pos'], abs=1e-3)
    assert h['aq-zone-in'] == pytest.approx(R) and h['aq-zone-out'] > h['aq-zone-in'], 'no hysteresis band'


def test_clamps_come_from_the_fish_extents(objs):
    h = _header(by_name(objs, 'Player')['script'])
    e = FISH.extents()
    reach = max(e['nose_x'], -e['tail_x'])
    assert h['aq-xmax'] + reach == pytest.approx(C.INNER_X_M - C.CLAMP_MARGIN, abs=1e-4), 'tail tip / nose off the end wall'
    assert h['aq-ymax'] + e['half_width'] == pytest.approx(C.INNER_Y_M - C.CLAMP_MARGIN, abs=1e-4)
    assert h['aq-zmax'] + e['top_z'] + FISH.T['fish-bob-amp'] == pytest.approx(C.WATER_LINE_M - C.CLAMP_MARGIN, abs=1e-4)
    # the capsule stays clear of Jolt's floor contact over the sand (never standing on it)
    assert h['aq-zmin'] - FISH.collision_box()[5] - C.SAND_TOP_M == pytest.approx(C.GROUND_CLEARANCE, abs=1e-4)


CLUMPS = [C.clump_name(row, side) for row, side, *_ in C.ANEMONE_CLUMPS]


def _world_box(o):
    """World-space bbox: the .lev box is local to the actor's position."""
    return [p + b for p, b in zip(o['pos'] * 2, o['box'])]


def test_anemone_body_is_solid_and_tentacles_are_six_non_colliding_clumps(objs):
    assert by_name(objs, 'anemone')['class'] == 'statplat'
    assert not any(o['name'] == 'anemone-tentacles' for o in objs), 'Phase 4 split the tentacles into clumps'
    assert len(CLUMPS) == 6 and len(set(CLUMPS)) == 6
    for n in CLUMPS:
        t = by_name(objs, n)
        # Drawn, but no Jolt body (never a statplat) and out of WF actor collision (Mass 0), so the
        # fish nestles among them from any depth and the sway can never push it.
        assert t['class'] == 'platform', f'{n} is a {t["class"]}: every statplat gets a Jolt body'
        assert t['mobility'] == 'Anchored' and t['mass'] == 0.0 and t['visible'] == 1, n
        assert not t['script'], f'{n}: the Director sways the clumps; they carry no script'


def test_clump_pivots_are_their_bases_on_the_oral_disc(objs):
    # The sway rotates each clump about its origin, so the origin must be where its tentacles
    # root: inside the oral disc's rim, with the mesh rising from local z ≈ 0.
    a = by_name(objs, 'anemone')
    disc_top = _world_box(a)[5]
    for n in CLUMPS:
        t = by_name(objs, n)
        assert disc_top - 0.04 <= t['pos'][2] <= disc_top, f'{n}: pivot z {t["pos"][2]:.3f}, disc top {disc_top:.3f}'
        assert abs(t['pos'][0] - C.ANEMONE_X) < 0.25 and abs(abs(t['pos'][1]) - 0.4) < 1e-3, n
        # The roots are at local z 0; the outermost tentacles droop back to that height, so their
        # bulbs (radius ≤ 0.10 m) hang just below it, and nothing lower.
        assert -0.11 <= t['box'][2] <= 0.0, f'{n}: mesh bottom {t["box"][2]:.3f} m below its pivot'


def test_anemone_crown_is_about_the_spec_width(objs):
    lo = min(_world_box(by_name(objs, n))[0] for n in CLUMPS)
    hi = max(_world_box(by_name(objs, n))[3] for n in CLUMPS)
    span = C.m(C.ANEMONE_SPAN)
    # at rest, bulbs included; ±5 % (the build asserts the same about its own tips)
    assert hi - lo == pytest.approx(span, rel=0.05), f'crown {hi - lo:.3f} m, spec {C.ANEMONE_SPAN:g} in = {span:.3f} m'


def test_no_statplat_inside_the_swim_volume_but_the_tank_itself(objs):
    # Every statplat is a Jolt collision body. Inside the water only the tank and what the fish
    # is meant to bump into may be one: nothing added for looks (tentacles, water gradient, shafts).
    allowed = {'tank-shell', 'tank-front-collider', 'sand', 'rock', 'anemone'}
    vol = (-C.INNER_X_M, -C.INNER_Y_M, C.SAND_TOP_M, C.INNER_X_M, C.INNER_Y_M, C.WATER_LINE_M)
    inside = []
    for o in objs:
        if o['class'] != 'statplat' or o['box'] is None:
            continue
        b = _world_box(o)
        if all(b[k] < vol[k + 3] and b[k + 3] > vol[k] for k in range(3)):
            inside.append(o['name'])
    assert set(inside) <= allowed, f'statplats inside the tank that should not be: {sorted(set(inside) - allowed)}'
    assert {'tank-shell', 'rock', 'anemone'} <= set(inside)          # (the sand's top is the volume's floor)


def test_sway_is_generated_for_every_clump_in_its_own_mailboxes(objs):
    names = [o['name'] for o in objs]
    script = by_name(objs, 'Director')['script']
    calls = re.findall(r"^\s+(-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (\d+) (\d+) aq-sway-clump\s+\\ (\S+)$",
                       script, re.M)
    assert [c[6] for c in calls] == CLUMPS, 'one aq-sway-clump call per clump, in table order'
    for (amp_a, amp_b, phase, hz, mb, actor, name), (row, side, deg_b, deg_a, period, ph) in zip(calls, C.ANEMONE_CLUMPS):
        assert int(actor) == names.index(name) + 1, f'{name}: sway actor index != export position + 1'
        assert 720 <= int(mb) < 740, f'{name}: sway mailbox {mb} outside 720..739'
        assert float(amp_b) == pytest.approx(deg_b / 360, abs=1e-6) and 0 < deg_b <= 6.0
        assert float(amp_a) == pytest.approx(deg_a / 360, abs=1e-6) and 0 < deg_a <= 2.0
        assert float(hz) == pytest.approx(1 / period, abs=1e-6) and 3.0 <= period <= 5.0
        assert float(phase) == pytest.approx(ph, abs=1e-6)
    assert len({int(c[4]) for c in calls}) == len(calls), 'each clump has its own phase mailbox'
    periods = sorted(p for *_, p, _ in C.ANEMONE_CLUMPS)
    assert min(b - a for a, b in zip(periods, periods[1:])) >= 0.25, 'periods apart, so no two clumps lock together'
    assert _header(script)['aq-sway-b'] == 720 + len(CLUMPS)
    # The sway writes only the clumps' rotations: never a position, a speed or the Player.
    body = script[script.index(': aq-sway-pose'):script.index(': aq-sway-clump')]
    assert re.findall(r'INDEXOF_\w+', body) == ['INDEXOF_ROTATION_A', 'INDEXOF_ROTATION_B', 'INDEXOF_ROTATION_C']


def test_player_is_created_before_every_clump(objs):
    names = [o['name'] for o in objs]
    assert all(names.index('Player') < names.index(n) for n in CLUMPS)


def test_camera_a_is_level_and_frames_the_tank(objs):
    # Straight-on: the aim point is at the eye's height (bungee aim = Target − Follow + Track Object,
    # all three LookAt), so the camera has no pitch.
    a, look = by_name(objs, 'cs_front'), by_name(objs, 'LookAt')
    assert a['pos'][2] == pytest.approx(look['pos'][2], abs=1e-3) and a['pos'][0] == pytest.approx(look['pos'][0])
    for n in ('Follow', 'Target', 'Track Object'):
        assert re.search(r"\"%s\" \} \{ 'STR' \"LookAt\"" % n, a['block']), f'cs_front {n} must be LookAt'
    # The whole tank width at the front glass fits the 4:3 frame with a margin (60° vertical FOV).
    half_w = (4 / 3) * math.tan(math.radians(30)) * (-C.EXT_Y_M / 2 - a['pos'][1])
    assert 0.80 <= C.EXT_X_M / (2 * half_w) <= 0.90, 'the tank should span ~85 % of the frame width'


def test_infrastructure_actors_never_collide(objs):
    # snowgoons imports every infrastructure actor at Mass 75; a Mass > 0 bbox is solid to the
    # Player (Actor::CanCollide), and LookAt sits at the tank's centre, in the water.
    for n in ('Director', 'LevelObj', 'Matte', 'cs_front', 'cs_anemone', 'LookAt', 'LookB', 'anemone-zone',
              'SunLight', 'AmbientLight'):
        assert by_name(objs, n)['mass'] == 0.0, n


# ── Phase 4 runtime: the sway, in the running level (needs a display and engine/wf_game) ──────
requires_runtime = pytest.mark.skipif(
    not os.environ.get('DISPLAY') or not os.path.exists(os.path.join(REPO, 'engine', 'wf_game')),
    reason='needs a display (wf_game opens a GL window) and engine/wf_game')


@requires_runtime
def test_sway_is_bounded_periodic_net_zero_and_never_moves_the_player():
    """The harness (run_aquarium_checks.py, step 16's machinery): paused, one tick per step, a sticky
    injected joystick 0. Over one longest period plus 10 ticks, every clump's B/A stay within their
    amplitudes and reach them, B is net zero over a period and B(t) = B(t + period), its pivot and C
    never move, its measured period is the authored one; and the Player does not move at all."""
    os.environ.setdefault('WF_BRIDGE_PORT', '7813')              # not the harness's default 7811
    os.environ.setdefault('OUT', os.path.expanduser('~/tmp/aquarium-test'))
    import run_aquarium_checks as R                            # noqa: E402  (LEVEL_DIR is on sys.path)
    r = R.Run()
    g = r.g
    clumps = R.clump_indices(r)
    g.watch([(i, mb) for i in clumps.values() for mb in (R.ROT_A, R.ROT_B, R.ROT_C, R.X_POS, R.Y_POS, R.Z_POS)])
    try:
        g.step(20)
        fr = g.step(round(max(p for *_, p, _ in C.ANEMONE_CLUMPS) / R.DT) * 2 + 10)
        report = []
        for (row, side, deg_b, deg_a, period, _), (name, i) in zip(C.ANEMONE_CLUMPS, clumps.items()):
            s = R.clump_stats(fr, i, deg_b / 360, deg_a / 360, period)
            report.append((name, s['ok'], round(s['b'][0] * 360, 3), round(s['b'][1] * 360, 3),
                           round(s['mean_b'] * 360, 4), s['outliers'][:2], round(s['period'], 3)))
            assert s['ok'] and abs(s['period'] - period) < 0.02 * period, report[-1]
        drift = [max(f[1][(r.pl, mb)] for f in fr) - min(f[1][(r.pl, mb)] for f in fr) for mb in (R.X_POS, R.Y_POS, R.Z_POS)]
        print('\nSWAY', report, 'Player drift', drift)
        assert max(drift) < 1e-4, f'the sway moved the Player: drift {drift}'
    finally:
        clean = r.isolation()
        g.close()
    assert clean, 'run contaminated by desktop input: rerun'
