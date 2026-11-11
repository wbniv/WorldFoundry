import importlib.util
from pathlib import Path
import struct
import pytest
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'wflevels/baseline'))
from memory_settings_fixture import FIELDS, load, sheet, project_legacy, validate
ENGINE = ROOT

@pytest.mark.parametrize('slot_present', [False, True])
def test_projection_keeps_level_offsets(slot_present):
    original = project_legacy((ENGINE/'wflevels/baseline-standalone.iff').read_bytes(), load())
    assert original[2092:2096] == b'SLOT'
    if not slot_present:
        data = bytearray(original)
        size = struct.unpack_from('<I', data, 2052)[0]
        end = 2056 + size
        pad = struct.unpack_from('<I', data, end + 4)[0]
        payload = data[2056:2092] + data[2100:end]
        data[2048:4096] = (b'RAM\0' + struct.pack('<I', size-8) + payload +
                           b'ALGN' + struct.pack('<I', pad+8) + bytes(pad+8))
        original = bytes(data)
    old_size = struct.unpack_from('<I',original,2052)[0]
    config = dict(load(), object_heap_bytes=524288, permanent_asset_bytes=2097152, room_asset_bytes=4194304, active_room_slots=1)
    changed = project_legacy(original,config)
    size = struct.unpack_from('<I',changed,2052)[0]
    assert size == old_size+(0 if slot_present else 8)
    assert changed[:2048] == original[:2048] and changed[4096:] == original[4096:]
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
    assert lines.count('PROPERTY_SHEET_HEADER(Level Behavior,0)') == 1


def test_built_level_ram_matches_the_runtime_settings_catalog():
    data = (ENGINE/'wflevels/baseline-standalone.iff').read_bytes()
    assert b'RPRP' not in data
    config = load()
    ram = [struct.unpack_from('<I', data, offset)[0] for offset in (2060, 2068, 2076, 2096, 2084, 2088)]
    assert data[2092:2096] == b'SLOT'
    assert ram == [config[key] for _, key, _, _, _ in FIELDS]


def test_nondefault_configuration_cooks_same_values_into_oad_and_ram(tmp_path):
    import json, subprocess
    config = dict(load(), object_heap_bytes=524288, permanent_asset_bytes=2097152,
                  room_asset_bytes=1048576, active_room_slots=1,
                  doom_stick=0, bungee_camera=0)
    lines, bindings = sheet(config)
    source = tmp_path/'memory.oas'
    compiled = tmp_path/'memory.oad'
    source.write_text('\n'.join(['TYPEHEADER(MemoryFixture)', *lines, 'TYPEFOOTER'])+'\n')
    subprocess.run([str(ROOT/'wftools/oas2oad-rs/target/release/oas2oad'),
                    '--types='+str(ROOT/'wfsource/source/oas/types3ds.s'),
                    '--prep='+str(ROOT/'wftools/prep/prep'), '-o', str(compiled), str(source)], check=True)
    schema = json.loads(subprocess.check_output([ROOT/'wftools/wf_attr_edit/target/release/catalog', compiled], text=True))
    fields = {f['key']: f for f in schema['fields']}
    for _, key, _, _, _ in FIELDS:
        assert fields['memory_'+key]['default'] == config[key]
        assert bindings['memory_'+key]['initial'] == str(config[key])
        assert bindings['memory_'+key]['readonly']
    data = project_legacy((ROOT/'wflevels/baseline-standalone.iff').read_bytes(), config)
    actual = [struct.unpack_from('<I', data, offset)[0] for offset in (2060, 2068, 2076, 2096, 2084, 2088)]
    assert actual == [config[key] for _, key, _, _, _ in FIELDS]

@pytest.mark.parametrize('offset,value',[(2048,b'BAD!'),(2052,struct.pack('<I',4096)),(2056,b'BAD!')])
def test_invalid_level_rejected(offset,value):
    original=bytearray((ENGINE/'wflevels/baseline-standalone.iff').read_bytes())
    original[offset:offset+4]=value
    with pytest.raises(ValueError):project_legacy(original)


def test_compiled_oad_and_cooked_catalog():
    import json, subprocess
    spec=importlib.util.spec_from_file_location('cooker',ENGINE/'tests/fixtures/build_property_fixture.py')
    cooker=importlib.util.module_from_spec(spec);spec.loader.exec_module(cooker)
    for name in ['runtime-settings','settings-gallery']:
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
