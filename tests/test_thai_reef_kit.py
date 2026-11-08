"""The reef's rock-module kit (plan 2026-11-08 W5b).

Regression guard for the kit's contract with W5c and with the Fixed reef:
* the Fixed layout is the kit's hero modules at their pivots, and the exported pieces put
  every dressing face exactly where today's merged groups put it;
* colliders are boxes centred on their module pivot (Jolt never rotates a static body), and
  the heroes keep today's RockColliderLeft/Right boxes;
* every hideable piece has its own visibility cell in the free global range, and the
  Director shows the Fixed arrangement at entry;
* site tables are module-local points on each module's own surface;
* the cooked levels fit the Room #0 slot (R0 report section 9) and the visible budgets.
"""
import json
import math
import re
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REEF = ROOT / 'wflevels' / 'aquarium_thai_reef'
sys.path.insert(0, str(REEF))
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))

from mesh import Mesh  # noqa: E402
from reef import kit, uvmap  # noqa: E402
from reef.geometry import build_groups  # noqa: E402
from reef.surface import SAND_Z  # noqa: E402

LEVELS = ('aquarium_thai_reef', 'aquarium_thai_reef_anime')


def _actor_map(level):
    return json.loads((ROOT / 'wflevels' / level / 'actor-map.json').read_text())


def _lev_blocks(level):
    text = (ROOT / 'wflevels' / level / f'{level}.lev').read_text()
    out = {}
    for block in text.split("\t{ 'OBJ'")[1:]:
        out[re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)] = block
    return out


def _position(block):
    m = re.search(r'"Position" \} \{ \'DATA\' (\S+)\(1\.15\.16\) (\S+)\(1\.15\.16\) (\S+)\(1\.15\.16\)', block)
    return tuple(float(m.group(i)) for i in (1, 2, 3))


def _visibility(block):
    return int(re.search(r'"Visibility Mailbox" \} \{ \'DATA\' (\d+)l', block).group(1))


def _mesh_vertices(path):
    data = path.read_bytes()
    pos = 8
    while pos + 8 <= len(data):
        tag, size = struct.unpack_from('<4sI', data, pos)
        if tag == b'VRTX':
            return [tuple(v / 65536 for v in struct.unpack_from('<iii', data, pos + 8 + i + 12))
                    for i in range(0, size, 24)]
        pos += 8 + ((size + 3) & ~3)
    raise AssertionError(f'{path}: no VRTX chunk')


@pytest.fixture(scope='module')
def pieces():
    return kit.dressing_pieces(build_groups(Mesh), Mesh, uvmap.face_uvs)


def test_dressing_split_keeps_every_face_of_todays_groups(pieces):
    groups = build_groups(Mesh)
    sources = [n for n in groups if n.startswith(('reef_hard', 'reef_soft', 'reef_sponges', 'reef_life'))]
    before = Counter(tuple(tuple(round(c, 6) for c in groups[n].vertices[v]) for v in face)
                     for n in sources for face in groups[n].faces)
    after = Counter(tuple(tuple(round(c, 6) for c in m.vertices[v]) for v in face)
                    for _, _, m in pieces.values() for face in m.faces)
    assert before == after
    assert all(len(m.vertices) <= kit.MAX_PIECE_VERTICES for _, _, m in pieces.values())


def test_dressing_faces_keep_the_uvs_of_their_original_group(pieces):
    groups = build_groups(Mesh)
    expected = {}
    for name in groups:
        if name.startswith(('reef_hard', 'reef_soft', 'reef_sponges', 'reef_life')):
            for face, uv in zip(groups[name].faces, uvmap.face_uvs(groups[name])):
                expected[tuple(tuple(round(c, 6) for c in groups[name].vertices[v]) for v in face)] = \
                    tuple(tuple(round(c, 6) for c in p) for p in uv)
    for _, _, m in pieces.values():
        for face, uv in zip(m.faces, uvmap.face_uvs(m)):
            key = tuple(tuple(round(c, 6) for c in m.vertices[v]) for v in face)
            assert tuple(tuple(round(c, 6) for c in p) for p in uv) == expected[key]


@pytest.mark.parametrize('level', LEVELS)
def test_exported_hero_dressing_sits_where_the_fixed_reef_had_it(level, pieces):
    blocks = _lev_blocks(level)
    for name, (hero, _, mesh) in pieces.items():
        pivot = kit.hero_pivot(hero)
        assert _position(blocks[name]) == pytest.approx(pivot, abs=1e-4)
        tolerance = .0045 if level.endswith('anime') and name.startswith('reef_hard') else 1e-3
        grid = {}
        for p in mesh.vertices:
            grid.setdefault(tuple(int(math.floor(c / .01)) for c in p), []).append(p)
        exported = _mesh_vertices(ROOT / 'wflevels' / level / f'{name}.iff')
        assert len(exported) >= .5 * len(set(mesh.vertices))
        for v in exported:
            w = tuple(v[i] + pivot[i] for i in range(3))
            cell = tuple(int(math.floor(c / .01)) for c in w)
            near = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                    for q in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ())]
            # Anime pieces also carry their outline hull: the same surface pushed out by its width.
            assert any(math.dist(w, q) < tolerance for q in near), (name, w)


@pytest.mark.parametrize('level', LEVELS)
def test_colliders_are_pivot_centred_and_heroes_keep_todays_boxes(level):
    blocks = _lev_blocks(level)
    modules = {m['name']: m for m in _actor_map(level)['kit']['modules']}
    assert list(modules) == list(kit.MODULES)
    for name, module in modules.items():
        lo, hi = module['collider_box']['lo'], module['collider_box']['hi']
        assert lo[0] == pytest.approx(-hi[0]) and lo[1] == pytest.approx(-hi[1])
        assert 'statplat' in blocks[module['collider']]
        location = _position(blocks[module['collider']])
        if module['role'] == 'hero':
            assert location == pytest.approx(module['pivot'], abs=1e-4)
        else:
            assert location == pytest.approx(module['park'], abs=1e-4)
            assert -6 < location[2] < 0              # parked inside the room box, under the sand
    for name, world_lo, world_hi in (('left', (-5.0, -.25, .72), (-1.65, 1.25, 2.5)),
                                     ('right', (1.65, -.25, .72), (5.0, 1.25, 2.5))):
        m = modules[name]
        got_lo = [m['pivot'][i] + m['collider_box']['lo'][i] for i in range(3)]
        got_hi = [m['pivot'][i] + m['collider_box']['hi'][i] for i in range(3)]
        assert got_lo == pytest.approx(world_lo, abs=1e-3) and got_hi == pytest.approx(world_hi, abs=1e-3)


@pytest.mark.parametrize('level', LEVELS)
def test_every_hideable_piece_has_its_own_free_cell_and_fixed_shows_the_heroes(level):
    blocks = _lev_blocks(level)
    data = _actor_map(level)
    cells = []
    for module in data['kit']['modules']:
        cells.append(module['cell'])
        for piece in module['pieces'] + module['attached']:
            assert _visibility(blocks[piece]) == module['cell'], piece
    for clump in data['kit']['clumps']:
        cells.append(clump['cell'])
        assert _visibility(blocks[clump['actor']]) == clump['cell']
    assert len(cells) == len(set(cells)) and all(2 <= c <= 599 for c in cells)
    script = re.search(r'"Script" \} \{ \'STR\' "(.*?)" \}', blocks['Director']).group(1)
    init = re.search(r': reef-kit-init (.*?) ;', script).group(1)
    for hero in kit.HEROES:
        assert f' 1 {kit.module_cell(hero["name"])} tk!' in init
    for module in data['kit']['modules'][len(kit.HEROES):]:
        assert f' {module["cell"]} tk!' not in init
    assert 'reef-kit-init reef-shoal' in script


def test_site_tables_are_module_local_points_on_each_module():
    for name in kit.MODULES:
        sites = kit.site_table(name)
        assert len(sites) == 16
        hero = name in (h['name'] for h in kit.HEROES)
        origin = kit.hero_pivot(name) if hero else (0.0, 0.0, 0.0)
        sand = SAND_Z if hero else 0.0
        for site in sites:
            p = tuple(site['p'][i] + origin[i] for i in range(2)) + (site['p'][2] + sand,)
            assert abs(kit.module_field(name, p)) < .03, (name, site)
            assert math.isclose(math.sqrt(sum(c * c for c in site['n'])), 1.0, abs_tol=1e-3)
            assert site['p'][2] >= .12
        assert all(math.dist(a['p'], b['p']) >= .28 for i, a in enumerate(sites) for b in sites[i + 1:])


@pytest.mark.parametrize('level', LEVELS)
def test_actor_map_carries_site_tables_and_actor_indices_for_w5c(level):
    data = _actor_map(level)
    for module in data['kit']['modules']:
        assert module['sites'] == [{'p': list(s['p']), 'n': list(s['n'])} for s in kit.site_table(module['name'])]
        assert module['collider_actor'] == data['indices'][module['collider']]
        assert module['piece_actors'] == [data['indices'][p] for p in module['pieces']]
    for clump in data['kit']['clumps']:
        assert clump['actor_index'] == data['indices'][clump['actor']]
    for name, attached in data['kit']['attached'].items():
        pivot = kit.hero_pivot(attached['module'])
        position = _position(_lev_blocks(level)[name])
        assert [position[i] - pivot[i] for i in range(3)] == pytest.approx(attached['offset'], abs=1e-3)


def test_cooked_levels_fit_the_room_slot_and_visible_budgets():
    result = subprocess.run([sys.executable, str(REEF / 'report_budget.py'), '--cooked'],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    reports = json.loads(result.stdout)
    for row in reports.values():
        assert row['room_slot_bytes'] <= row['room_slot_limit'] == 32_000_000
        assert row['fixed_groups'] == 11
