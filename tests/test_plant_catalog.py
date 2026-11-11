"""Actor-backed plant fixtures preserve the compiled level and menu assets."""
from pathlib import Path
import struct
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from plant_settings_actor import NoPlantActor,actor_layout,configure_level,configure_cd,validate

@pytest.mark.parametrize('seed,water,age,flags',[(0,'freshwater',0,False),(2147483647,'saltwater',240,True),(713,'saltwater',150,False)])
def test_actor_fixture_changes_only_settings_fields(seed,water,age,flags):
    before=(ROOT/'wflevels/aquarium_plants-standalone.iff').read_bytes()
    after,receipt=configure_level(before,dict(seed=seed,water=water,age=age,speed=0,textures=flags,sway=flags))
    assert receipt['source']=='OAD' and not receipt['settings']['random_entry']
    assert len(after)==len(before) and b'RPRP' not in after
    restored=bytearray(after)
    for offset in receipt['field_offsets']:restored[offset:offset+4]=before[offset:offset+4]
    assert bytes(restored)==before
    actor,base,positions=actor_layout(after)
    assert actor==receipt['actor']
    assert struct.unpack_from('<i',after,base+positions['Seed'])[0]==seed
    assert struct.unpack_from('<i',after,base+positions['Water type'])[0]==int(water=='saltwater')
    assert struct.unpack_from('<i',after,base+positions['Initial age'])[0]==round(age*65536)
    assert configure_level(after,receipt['settings'])[0]==after

@pytest.mark.parametrize('options',[{'seed':-1},{'seed':2147483648},{'seed':True},{'age':float('nan')},{'age':-1},{'age':241},{'speed':7},{'speed':False},{'water':'brackish'},{'sway':0},{'textures':'0'},{'unknown':0}])
def test_invalid_authored_configuration(options):
    with pytest.raises(ValueError):validate(options)

def test_default_random_policy_and_bundle_preservation():
    assert validate({})['random_entry'] and not validate({'seed':0})['random_entry']
    with pytest.raises(NoPlantActor):configure_level((ROOT/'wflevels/baseline-standalone.iff').read_bytes(),{})
    before=(ROOT/'wflevels/aquarium-menu-cd.iff').read_bytes()
    after,receipt=configure_cd(before,dict(seed=713,water='saltwater',age=150,speed=0,sway=False))
    count=struct.unpack_from('<I',before,12)[0]//12;changed=[]
    for i in range(count):
        tag,offset,size=struct.unpack_from('<4sII',before,16+12*i)
        assert (tag,offset,size)==struct.unpack_from('<4sII',after,16+12*i)
        if before[offset:offset+size]!=after[offset:offset+size]:changed.append(i)
    assert changed==[6] and receipt['settings']['seed']==713
