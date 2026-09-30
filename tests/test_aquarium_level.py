"""Regression guard for the aquarium level (docs/plans/2026-09-30-aquarium-level.md § Regression guard).

Reads the exported wflevels/aquarium/aquarium.lev (rebuilt by `task aquarium-level`) and
wflevels/aquarium/aquarium_constants.py, so the plan's tank table, the level and this test
cannot drift. Plan B: there is no front pane, so the plan's pane-texture check is dropped and
replaced by "no translucent actor exists, the front collider is invisible".
"""
import importlib.util
import os
import re

import pytest

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
LEVEL_DIR = os.path.join(REPO, 'wflevels', 'aquarium')
LEV = os.path.join(LEVEL_DIR, 'aquarium.lev')

_spec = importlib.util.spec_from_file_location('aquarium_constants',
                                               os.path.join(LEVEL_DIR, 'aquarium_constants.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

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
        objs.append({
            'name': name,
            'class': cls.group(1) if cls else '',
            'box': [float(v) for v in re.findall(r'(-?[\d.]+)\(1\.15\.16\)', box.group(1))] if box else None,
            'mesh': mesh.group(1) if mesh else '',
            'visible': int(vis.group(1)) if vis else None,
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
