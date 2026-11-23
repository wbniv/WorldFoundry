"""The Discus tank, the Aquarium's twelfth: roster, species, built level, texture budget, scripts.

Plan: docs/plans/2026-11-22-discus-tank.md. The tank is the Tiger Barbs tank's school framework
(wflevels/aquarium/blender_create_aquarium.py, AQUARIUM_TANK=discus) with the discus asset's mesh
(wflevels/aquarium/discus_school.py, wflevels/discus_asset/discus_geometry.py).
"""
import importlib.util
import json
import math
import os
import re
import struct
import sys
from pathlib import Path

import pytest

from test_aquarium_level import _objects, by_name, _header
from test_species_movement import vm  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / 'wflevels'
HERE = LEVELS / 'aquarium_discus'
sys.path.insert(0, str(LEVELS / 'aquarium'))
sys.path.insert(0, str(ROOT / 'scripts'))
import aquarium_constants as C  # noqa: E402
import discus_school as DS      # noqa: E402
import level_manifest           # noqa: E402

GROUP = DS.SCHOOL_N + 1          # the player and its residents


def test_discus_is_the_last_manifest_entry():
    manifest = level_manifest.read()
    assert manifest.ids[-1] == 'aquarium_discus'
    assert manifest.ids[-2] == 'aquarium_sea_stars', 'append-only: no existing tank index moves'
    assert len(manifest.ids) == len(set(manifest.ids)) == 12
    last = [line for line in (LEVELS / 'aquarium-menu.manifest').read_text().splitlines() if line.startswith('level ')][-1]
    assert [c.strip() for c in last.split('|')] == ['level aquarium_discus-standalone.iff', 'Discus', 'Discus']


def test_species_entry_and_no_species_in_two_tanks():
    species = json.loads((LEVELS / 'aquarium_species.json').read_text())
    assert species['aquarium_discus'] == ['Symphysodon aequifasciatus']
    tanks = {k: v for k, v in species.items() if not k.startswith('_')}
    assert set(tanks) == set(level_manifest.read().ids)
    seen = {}
    for tank, names in tanks.items():
        for name in names:
            assert name.lower() not in seen, f'{name} in {seen[name.lower()]} and {tank}'
            seen[name.lower()] = tank


def test_build_script_exists_and_selects_the_discus_tank():
    script = HERE / 'build.sh'
    assert script.is_file() and os.access(script, os.X_OK)
    text = script.read_text()
    assert 'set -euo pipefail' in text
    assert 'AQUARIUM_TANK=discus' in text and 'AQUARIUM_FOLLOWER_ASSET=discus' in text
    assert f'AQUARIUM_SCHOOL_N={DS.SCHOOL_N}' in text
    assert 'build_level_binary.sh aquarium_discus' in text


def test_model_and_tank_share_one_mesh_source():
    assert 'from discus_geometry import mesh_data' in (LEVELS / 'discus_asset/model.py').read_text()
    verts, faces = DS.geometry()
    assert len(verts) == DS.BODY_VERTEX_COUNT == 1451
    length = max(v[0] for v in verts) - min(v[0] for v in verts)
    assert length == pytest.approx(DS.LENGTH_M)
    assert 1.5 <= DS.LENGTH_M <= 2.0, '15-20 cm at WORLD_SCALE 10'


def test_group_of_ten_single_mesh_discus_and_no_marine_habitat():
    objs = _objects(HERE / 'aquarium_discus.lev')
    fish = [o for o in objs if o['name'].startswith('discus-')]
    assert sorted(o['name'] for o in fish) == sorted(['discus-player'] + [f'discus-{k}' for k in range(1, GROUP)])
    assert all(o['mesh'] == 'discus.iff' and o['class'] == 'platform' and o['mass'] == 0 and not o['script'] for o in fish)
    assert not any(o['name'].startswith(('clownfish', 'anemone', 'tiger-barb')) or o['name'] == 'rock' for o in objs)
    script = by_name(objs, 'Director')['script']
    assert script.rstrip().endswith('discus-player-tick\naq-camera-tick\nsd-tick')
    assert ': fish-off 0 ;' in script and '1037 read-mailbox' not in script
    header = _header(script)
    assert header['sch-n'] == GROUP
    # swim.fth's wave in fish-deform terms (discus_school.py): 0.8 cycles/s, 0.051 of the length.
    assert 'fish-dt 0.8 * startle-gain *' in script and '0.051 startle-gain * sd-actor fish-deform' in script
    assert '0.8 fish-ph-swim fish-advance' in script and 'fish-dt 3 * startle-gain *' not in script
    mapping = json.loads((HERE / 'actor-map.json').read_text())
    assert mapping['title'] == 'Discus' and mapping['fish_count'] == GROUP
    assert mapping['resident_lengths_m'] == [DS.school_length(k) for k in range(1, GROUP)]
    for k in range(1, GROUP):
        actor = mapping['indices'][f'discus-{k}']
        assert f'{actor} {1300 + k - 1} write-mailbox' in script


def test_every_fish_stays_inside_the_water_at_the_school_bounds():
    """The largest resident at the school's corner (sd-hx/hy/hz, in player lengths) clears every wall."""
    script = by_name(_objects(HERE / 'aquarium_discus.lev'), 'Director')['script']
    # Several `: name value ;` share a line here (sd-cx .. sd-bl), so not test_aquarium_level._header.
    h = {k: float(v) for k, v in re.findall(r": (sd-[a-z]+) (-?[\d.]+) ;", script)}
    verts = DS.geometry()[0]
    big = max(DS.SCHOOL_LENGTHS_M) / DS.LENGTH_M
    reach_xy = max(math.hypot(v[0], v[1]) for v in verts) * big     # any heading in the horizontal plane
    up, down = max(v[2] for v in verts) * big, -min(v[2] for v in verts) * big
    bl = h['sd-bl']
    assert h['sd-hx'] * bl + reach_xy < C.INNER_X_M
    assert h['sd-hy'] * bl + reach_xy < C.INNER_Y_M
    assert h['sd-cz'] + h['sd-hz'] * bl + up < C.WATER_LINE_M
    assert h['sd-cz'] - h['sd-hz'] * bl - down > C.SAND_TOP_M


def test_built_level_carries_the_default_settings_holder():
    data = (LEVELS / 'aquarium_discus-standalone.iff').read_bytes()
    assert b'Show framerate' in data


def test_room_budget_is_carried_by_playable_and_screensaver_levels():
    # Ten deformable fish exhausted the old 3 MB room heap during level load.
    for name in ('aquarium_discus', 'aquarium_discus_screensaver'):
        data = (LEVELS / f'{name}-standalone.iff').read_bytes()
        assert data[2048:2052] == b'RAM\0'
        assert data[2072:2076] == b'ROOM'
        assert struct.unpack_from('<I', data, 2076)[0] == 8_000_000
        assert data[2092:2096] == b'SLOT'
        assert struct.unpack_from('<I', data, 2096)[0] == 1


def page(level_dir, key):
    flags = dict(re.findall(r'^(\w+)=(\d+)$', (level_dir / 'textile.flags').read_text(), re.M))
    return int(flags[key])


def test_texture_fits_the_page_and_the_app_slot():
    from PIL import Image
    slot = dict(re.findall(r'--vram-(slot-width|slot-height)=(\d+)', (LEVELS / 'aquarium-wf_args.txt').read_text()))
    assert page(HERE, 'PAGEX') <= int(slot['slot-width']) and page(HERE, 'PAGEY') <= int(slot['slot-height'])
    assert Image.open(HERE / 'discus-index-rgb555.png').size == (DS.TEXTURE_SIZE, DS.TEXTURE_SIZE)
    for name, keys in (('Room0.tga', ('PAGEX', 'PAGEY')), ('Perm.tga', ('PERMPAGEX', 'PERMPAGEY'))):
        w, h = Image.open(HERE / name).size
        assert w <= page(HERE, keys[0]) and h <= page(HERE, keys[1]), name


def test_dream_variant_drives_the_player():
    spec = importlib.util.spec_from_file_location('ss_builder', ROOT / 'scripts/build-aquarium-screensaver-levels.py')
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    assert builder.TANKS[-1] == 'aquarium_discus'
    name = builder.SCRIPT_NAMES['aquarium_discus']
    driver = (HERE / name).read_text()
    text = builder.player_script((HERE / 'aquarium_discus.lev').read_text(), 'aquarium_discus', driver)
    blocks = [b for b in text.split("\t{ 'OBJ'") if re.search(r"\{ 'NAME' \"Player\" \}", b)]
    assert len(blocks) == 1 and 'aq-screensaver-tick' in blocks[0] and ': aq-screen-x' in blocks[0]


def test_discus_scripts_execute_and_player_rig_follows(vm):  # noqa: F811
    rows = vm('discus', 'reset -1.6 0 2.4\nset 650 10\nstep 50 8192 .025\nstep 30 1 .025\nstep 60 16384 .025\nstep 20 0 .025\n')
    assert rows[49]['x'] > rows[0]['x'] + .5
    assert all(math.isfinite(v) for r in rows for v in r.values())
    assert all(abs(r['part-x'] - r['x']) < 1e-5 and abs(r['part-z'] - r['z']) < 1e-5 for r in rows)
    assert all(abs(r['x']) < C.INNER_X_M and abs(r['y']) < C.INNER_Y_M and C.SAND_TOP_M < r['z'] < C.WATER_LINE_M for r in rows)
