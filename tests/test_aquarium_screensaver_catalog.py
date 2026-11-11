"""Aquarium Dream variants use settings actors and preserve their authored defaults."""
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
LEVELS=ROOT/'wflevels'
sys.path.insert(0,str(ROOT/'scripts'))
from plant_settings_actor import actor_layout

spec=importlib.util.spec_from_file_location('aquarium_screensaver_builder',ROOT/'scripts/build-aquarium-screensaver-levels.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

def water_value(level):
    _,base,positions=actor_layout(level)
    return struct.unpack_from('<i',level,base+positions['Water type'])[0]

def test_canonical_planted_tank_keeps_freshwater_default():
    assert water_value((LEVELS/'aquarium_plants-standalone.iff').read_bytes())==0

def test_variant_authors_saltwater_without_touching_other_actors():
    source=(LEVELS/'aquarium_plants/aquarium_plants.lev').read_text()
    changed=builder.planted_saltwater_variant(source)
    blocks=changed.split("\t{ 'OBJ'")
    actor=next(b for b in blocks if "{ 'NAME' \"PlantedTankSettings\" }" in b)
    assert actor.count('"Water type"')==1
    assert re.search(r'"Water type" \} \{ \'DATA\' 1l \}',actor)
    assert builder.planted_saltwater_variant(changed)==changed

def test_canonical_actor_map_matches_level():
    blocks=(LEVELS/'aquarium_plants/aquarium_plants.lev').read_text().split("\t{ 'OBJ'")
    indices=json.loads((LEVELS/'aquarium_plants/actor-map.json').read_text())['indices']
    for name,index in indices.items():
        assert re.search(r"\{ 'NAME' \""+re.escape(name)+r"\" \}",blocks[index]),(name,index)

@pytest.mark.parametrize('tank,field', [('aquarium_plants',b'Hold seconds'),('aquarium_jellyfish',b'Pulse tempo'),
                                       ('aquarium_thai_reef',b'Colonies'),('aquarium_thai_reef_anime',b'Colonies')])
def test_actor_descriptor_check(tank,field):
    builder.check_actor_settings(field,tank)
    with pytest.raises(ValueError):builder.check_actor_settings(b'RPRP '+field,tank)
    with pytest.raises(ValueError):builder.check_actor_settings(b'missing',tank)

@pytest.mark.skipif(not (LEVELS/'aquarium_plants_screensaver-standalone.iff').is_file(),reason='build the Dream variants first')
def test_built_planted_dream_is_saltwater():
    data=(LEVELS/'aquarium_plants_screensaver-standalone.iff').read_bytes()
    builder.check_actor_settings(data,'aquarium_plants')
    assert water_value(data)==1
