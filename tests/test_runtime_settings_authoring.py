"""OAD is the source of labels/defaults; bindings cannot bypass its enum."""
import importlib.util
from pathlib import Path
import json
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('settings_authoring',ROOT/'scripts/build-runtime-settings.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
OAD=ROOT/'docs/plans/2026-10-05-sea-anemone-realism/assets/anemone_settings.oad'
BINDINGS=ROOT/'wflevels/aquarium/anemone_settings_bindings.json'

def test_authored_enum_survives_oad_compilation():
    s=M.settings_from_oad(OAD,json.loads(BINDINGS.read_text()))
    assert s['fields']==[dict(name='Control Focus',type='enum',min=0,max=1,default=0,choices=['Clownfish','Anemone'],mailbox=729)]

@pytest.mark.parametrize('field,mailbox',[('Not declared',729),('Control Focus',1),('Control Focus',4000),('Control Focus',True)])
def test_binding_cannot_expose_missing_field_or_invalid_mailbox(field,mailbox):
    with pytest.raises(ValueError):
        M.settings_from_oad(OAD,dict(version=1,title='Controls',fields=[dict(field=field,mailbox=mailbox)]))

def test_truncated_oad_is_rejected(tmp_path):
    p=tmp_path/'bad.oad';p.write_bytes(OAD.read_bytes()[:-1])
    with pytest.raises(ValueError):M.settings_from_oad(p,json.loads(BINDINGS.read_text()))
