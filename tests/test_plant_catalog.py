"""Real cooked plant entry, retained assets, CLI rejection and profiling fixtures."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from plant_settings_catalog import configure_level,configure_cd,catalog_payload,records,validate

@pytest.fixture(scope='module')
def consumer(tmp_path_factory):
    exe=tmp_path_factory.mktemp('plant-consumer')/'check'
    subprocess.run(['c++','-std=c++17','-O1','-I'+str(ROOT/'wfsource/source'),
        str(ROOT/'tests/plant_catalog_test.cpp'),*[str(ROOT/'engine'/n) for n in
        ['runtime_properties.cpp','runtime_property_form.cpp','runtime_property_host.cpp']],
        str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(exe)],check=True)
    return exe

@pytest.mark.parametrize('seed,water,age,flags',[(0,'freshwater',0,False),(4294967295,'saltwater',240,True),(713,'saltwater',150,False)])
def test_real_cooked_consumer_and_geometry(consumer,tmp_path,seed,water,age,flags):
    before=(ROOT/'wflevels/baseline-standalone.iff').read_bytes()
    original=records(catalog_payload(before))
    after,receipt=configure_level(before,dict(seed=seed,water=water,age=age,speed=0,textures=flags,sway=flags))
    assert not receipt['settings']['random_entry']
    assert records(catalog_payload(after))[:-1]==original
    locator=2056+struct.unpack_from('<I',before,2052)[0]-12;offset=2048+struct.unpack_from('<I',before,locator+4)[0]
    assert before[8:locator]==after[8:locator] and before[locator+12:offset]==after[locator+12:offset]
    assert configure_level(after,receipt['settings'])[0]==after
    payload=tmp_path/'catalog.rprp';payload.write_bytes(catalog_payload(after));subprocess.run([consumer,payload],check=True)

@pytest.mark.parametrize('options',[{'seed':-1},{'seed':4294967296},{'seed':True},{'age':float('nan')},{'age':-1},{'age':241},{'speed':7},{'speed':False},{'water':'brackish'},{'sway':0},{'textures':'0'},{'unknown':0}])
def test_invalid_authored_configuration(options):
    with pytest.raises(ValueError):validate(options)

def test_default_random_policy_and_bundle_preservation(tmp_path,consumer):
    assert validate({})['random_entry'] and not validate({'seed':0})['random_entry']
    default,_=configure_level((ROOT/'wflevels/baseline-standalone.iff').read_bytes(),{})
    default_payload=tmp_path/'random.rprp';default_payload.write_bytes(catalog_payload(default));subprocess.run([consumer,default_payload],check=True)
    before=(ROOT/'wflevels/aquarium-menu-cd.iff').read_bytes()
    after,receipt=configure_cd(before,dict(seed=713,water='saltwater',age=150,speed=0,sway=False))
    count=struct.unpack_from('<I',before,12)[0]//12;changed=[]
    for i in range(count):
        tag,offset,size=struct.unpack_from('<4sII',before,16+12*i)
        new_tag,new_offset,new_size=struct.unpack_from('<4sII',after,16+12*i)
        assert tag==new_tag
        if before[offset:offset+size]!=after[new_offset:new_offset+new_size]:changed.append(i)
    assert changed==[6]  # SHEL plus menu index 5, preserving all other tanks/menu.
    _,offset,size=struct.unpack_from('<4sII',after,16+12*changed[0]);payload=tmp_path/'bundle.rprp';payload.write_bytes(catalog_payload(after[offset:offset+size]));subprocess.run([consumer,payload],check=True)
    assert receipt['settings']['seed']==713

def test_removed_engine_switches_fail_explicitly():
    exe=ROOT/'engine/wf_game'
    for key in ['seed','age','speed','texture','sway','water']:
        result=subprocess.run([str(exe),'--plant-'+key+'=0'],capture_output=True,text=True)
        assert result.returncode==2 and 'removed plant CLI override' in result.stderr
    source=(ROOT/'wfsource/source/game/main.cc').read_text()
    assert not any('--plant-'+key+'=' in source for key in ['seed','age','speed','texture','sway','water'])
