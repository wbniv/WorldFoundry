import importlib.util
from pathlib import Path
import struct
import pytest
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'wflevels/baseline'))
from memory_settings_fixture import load, sheet, project_legacy, validate
ENGINE = Path('/home/will/WorldFoundry-wbniv')

def test_projection_keeps_level_and_catalog_offsets():
    original = (ENGINE/'wflevels/baseline-standalone.iff').read_bytes()
    old_size = struct.unpack_from('<I',original,2052)[0]
    old_locator = original[2056+old_size-12:2056+old_size]
    config = dict(load(), object_heap_bytes=524288, permanent_asset_bytes=2097152, room_asset_bytes=4194304, active_room_slots=1)
    changed = project_legacy(original,config)
    size = struct.unpack_from('<I',changed,2052)[0]
    assert size == old_size+8
    assert changed[:2048] == original[:2048] and changed[4096:] == original[4096:]
    assert changed[2056+size-12:2056+size] == old_locator
    assert struct.unpack_from('<I',changed,2060)[0] == 524288
    assert changed[2092:2096] == b'SLOT'
    assert struct.unpack_from('<I',changed,2096)[0] == 1
    assert project_legacy(changed,config) == changed

@pytest.mark.parametrize('key,value',[('active_room_slots',0),('active_room_slots',10),('object_heap_bytes',0),('doom_stick',2),('room_asset_bytes',True),('permanent_asset_bytes',2147483647)])
def test_invalid_config_rejected(key,value):
    with pytest.raises(ValueError):validate(dict(load(),**{key:value}))

def test_sheet_stable_readonly_controls():
    lines, bindings = sheet()
    assert len(bindings) == 6 and {v['id'] for v in bindings.values()} == set(range(2000,2006))
    assert all(v['readonly'] for v in bindings.values())
    assert lines.count('PROPERTY_SHEET_HEADER(Level Memory,0)') == 1

@pytest.mark.parametrize('offset,value',[(2048,b'BAD!'),(2052,struct.pack('<I',4096)),(2056,b'BAD!')])
def test_invalid_level_rejected(offset,value):
    original=bytearray((ENGINE/'wflevels/baseline-standalone.iff').read_bytes())
    original[offset:offset+4]=value
    with pytest.raises(ValueError):project_legacy(original)


def test_compiled_oad_and_cooked_catalog():
    import json, subprocess
    spec=importlib.util.spec_from_file_location('cooker',ENGINE/'scripts/build-object-properties.py')
    cooker=importlib.util.module_from_spec(spec);spec.loader.exec_module(cooker)
    for name in ['settings','settings-gallery']:
        schema=json.loads(subprocess.check_output([ENGINE/'wftools/wf_attr_edit/target/release/catalog',ROOT/'wflevels/baseline'/f'{name}.oad'],text=True))
        fields={f['key']:f for f in schema['fields']}
        bindings=json.loads((ROOT/'wflevels/baseline'/f'{name}-bindings.json').read_text())
        for key,initial in load().items():
            if key=='version':continue
            field=fields['memory_'+key]
            assert field['default']==initial
            assert bindings['fields']['memory_'+key]['initial']==str(initial)
            assert bindings['fields']['memory_'+key]['readonly']
        catalog=cooker.catalog(ROOT/'wflevels/baseline'/f'{name}.oad',bindings,19)
        assert catalog.startswith(b'RP01')
        assert b'memory_active_room_slots' in catalog
