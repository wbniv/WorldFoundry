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
    assert script.rstrip().endswith('fish-rig-tick\naq-camera-tick'), 'rig first (after every actor), then cameras'
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


def test_anemone_body_is_solid_and_tentacles_are_not(objs):
    assert by_name(objs, 'anemone')['class'] == 'statplat'
    t = by_name(objs, 'anemone-tentacles')
    assert t['class'] == 'platform' and t['mass'] == 0.0 and t['visible'] == 1, \
        'tentacles are drawn but have no Jolt body, so the fish can nestle among them from any depth'


def test_infrastructure_actors_never_collide(objs):
    # snowgoons imports every infrastructure actor at Mass 75; a Mass > 0 bbox is solid to the
    # Player (Actor::CanCollide), and LookAt sits at the tank's centre, in the water.
    for n in ('Director', 'LevelObj', 'Matte', 'cs_front', 'cs_anemone', 'LookAt', 'LookB', 'anemone-zone',
              'SunLight', 'AmbientLight'):
        assert by_name(objs, n)['mass'] == 0.0, n
