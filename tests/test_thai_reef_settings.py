"""The reef's level settings object, ReefSettings (plan 2026-11-08 W5a).

A Director-owned settings object like the Jellyfish and Planted tanks':
Layout (Fixed|Random), Rocks (1-5, default 3), Colonies (Sparse|Normal|Dense)
and Seed (0 = a new reef on every entry). The Director polls it once a
second into mailboxes 860-863; W5c lays out the reef from those values.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ('aquarium_thai_reef', 'aquarium_thai_reef_anime')
FIELDS = {'Layout': 1, 'Rocks': 2, 'Colonies': 3, 'Seed': 4}


def test_settings_object_declares_the_four_fields():
    oas = (ROOT / 'wflevels/aquarium_thai_reef/settings.oas').read_text()
    assert 'TYPEHEADER(ReefSettings)' in oas
    assert re.search(r'TYPEENTRYINT32\(Layout,,0,1,0,"Fixed\|Random"', oas)
    assert re.search(r'TYPEENTRYINT32\(Rocks,,1,5,3,', oas)               # D6: 1-5, default 3
    assert re.search(r'TYPEENTRYINT32\(Colonies,,0,2,1,"Sparse\|Normal\|Dense"', oas)
    assert re.search(r'TYPEENTRYINT32\(Seed,,0,16777215,0,', oas)         # 24 bits: Forth cells are floats
    bindings = json.loads((ROOT / 'wflevels/aquarium_thai_reef/settings-bindings.json').read_text())
    assert bindings['owner'] == 'Director'
    assert {name: f['id'] for name, f in bindings['fields'].items()} == FIELDS


@pytest.mark.parametrize('level', LEVELS)
def test_each_style_carries_one_reef_settings_catalog(level):
    folder = ROOT / 'wflevels' / level
    for name in ('settings.oas', 'settings-bindings.json'):
        assert (folder / name).read_text() == (ROOT / 'wflevels/aquarium_thai_reef' / name).read_text()
    assert (folder / 'settings.rprp').is_file()
    standalone = (ROOT / 'wflevels' / f'{level}-standalone.iff').read_bytes()
    assert standalone.count(b'RPRP') == 2 and standalone.count(b'ReefSettings') == 1
    for key in FIELDS:
        assert key.encode() in standalone, key
    actor_map = json.loads((folder / 'actor-map.json').read_text())
    assert actor_map['indices'] == actor_map['actors']


@pytest.mark.parametrize('level', LEVELS)
def test_director_polls_the_settings(level):
    folder = ROOT / 'wflevels' / level
    director = json.loads((folder / 'actor-map.json').read_text())['indices']['Director']
    text = (folder / f'{level}.lev').read_text()
    for field, cell in ((1, 860), (2, 861), (3, 862)):
        assert f'{director} {field} property@' in text and f'{cell} tk!' in text
    assert f'{director} 4 property-int-bytes@' in text
