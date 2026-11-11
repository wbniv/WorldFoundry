"""The reef's level settings object, ReefSettings (plan 2026-11-08 W5a).

A Director-owned settings object like the Jellyfish and Planted tanks':
Layout (Fixed|Random, default Random), Rocks (1-5, default 3), Colonies (Sparse|Normal|Dense)
and Seed (0 = a new reef on every entry). The Director polls it once a
second into mailboxes 860-863; W5c lays out the reef from those values.
"""
import json
import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ('aquarium_thai_reef', 'aquarium_thai_reef_anime')
FIELDS = {'Layout': 1, 'Rocks': 2, 'Colonies': 3, 'Seed': 4}


def test_settings_object_declares_the_four_fields():
    oas = (ROOT / 'wfsource/source/oas/reefsettings.oas').read_text()
    assert 'TYPEHEADER(Reef Settings,ReefSettings)' in oas
    # Default Random (Will, 2026-11-09: "Approve, default Random"); Fixed stays selectable.
    assert re.search(r'TYPEENTRYINT32\(Layout,,0,1,1,"Fixed\|Random"', oas)
    assert re.search(r'TYPEENTRYINT32\(Rocks,,1,5,3,', oas)               # D6: 1-5, default 3
    assert re.search(r'TYPEENTRYINT32\(Colonies,,0,2,1,"Sparse\|Normal\|Dense"', oas)
    assert re.search(r'TYPEENTRYINT32\(Seed,,0,16777215,0,', oas)         # 24 bits: Forth cells are floats
    assert oas.count('SHOW_AS_LIVE') == 4


@pytest.mark.parametrize('level', LEVELS)
def test_each_style_carries_one_reef_settings_actor(level):
    folder = ROOT / 'wflevels' / level
    standalone = (ROOT / 'wflevels' / f'{level}-standalone.iff').read_bytes()
    assert b'RPRP' not in standalone
    for key in FIELDS:
        assert key.encode() in standalone, key
    actor_map = json.loads((folder / 'actor-map.json').read_text())
    assert actor_map['indices'] == actor_map['actors']
    assert 'ReefSettings' in actor_map['indices']


@pytest.mark.parametrize('level', LEVELS)
def test_director_polls_the_settings(level):
    folder = ROOT / 'wflevels' / level
    owner = json.loads((folder / 'actor-map.json').read_text())['indices']['ReefSettings']
    text = (folder / f'{level}.lev').read_text()
    raw = (ROOT/'wfsource/source/oas/reefsettings.oad').read_bytes()
    fields = {}
    for index in range((len(raw)-80)//1491):
        entry = raw[80+1491*index:80+1491*(index+1)]
        name = entry[1:65].split(b'\0',1)[0].decode()
        if name in FIELDS: fields[name] = index
    for key, cell in (('Layout', 860), ('Rocks', 861), ('Colonies', 862)):
        assert f'{owner} {fields[key]} property@' in text and f'{cell} tk!' in text
    assert f'{owner} {fields["Seed"]} property-int-bytes@' in text


def test_live_reef_settings_reach_the_running_poll(tmp_path):
    text = (ROOT/'wflevels/aquarium_thai_reef/aquarium_thai_reef.lev').read_text()
    block = next(b for b in text.split("\t{ 'OBJ'") if "{ 'NAME' \"Director\" }" in b)
    encoded = re.search(r'\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' ("(?:\\.|[^"\\])*") \}', block).group(1)
    script = json.loads(encoded)
    poll = re.search(r': reef-poll .*? ;', script).group()
    raw = (ROOT/'wfsource/source/oas/reefsettings.oad').read_bytes()
    fields = {}
    for index in range((len(raw)-80)//1491):
        entry = raw[80+1491*index:80+1491*(index+1)]
        name = entry[1:65].split(b'\0',1)[0].decode()
        if name in FIELDS: fields[name] = index
    spec=importlib.util.spec_from_file_location('reef_zf',ROOT/'docs/reference/swarming-poster/zfhost.py')
    zf=importlib.util.module_from_spec(spec);spec.loader.exec_module(zf)
    src=ROOT/'engine/vendor/zforth-41db72d1/src/zforth';zf.BIN=tmp_path/'zf_host'
    subprocess.run(['cc','-O1',f'-I{ROOT}/engine/stubs',f'-I{src}',
                    str(ROOT/'docs/reference/swarming-poster/zf_host.c'),str(src/'zforth.c'),'-lm','-o',str(zf.BIN)],check=True)
    definitions=(': tk@ read-mailbox ; : tk! write-mailbox ; : tk-dt@ 2 ;\n'
                 ': property@ swap drop dup 7000 + read-mailbox swap 7050 + read-mailbox ;\n'
                 ': property-int-bytes@ drop drop 3 2 1 0 1 ;\n')
    path=tmp_path/'reef.fth';path.write_text(definitions+poll+'\n')
    host=zf.Host()
    try:
        assert host.load(path)=='ok'
        for key,value in [('Layout',1),('Rocks',4),('Colonies',2)]:
            host.write(7000+fields[key],value);host.write(7050+fields[key],1)
        assert host.eval('reef-poll')=='ok'
        assert host.read(860,4)==[1,4,2,66051]
        host.write(7000+fields['Rocks'],2)
        assert host.eval('reef-poll')=='ok' and host.read(861)==2
    finally:
        host.close()
