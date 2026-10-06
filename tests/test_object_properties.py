"""Exercise the actual shared Rust validator and C++ instance editor."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('property_build',ROOT/'scripts/build-object-properties.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

@pytest.fixture(scope='session')
def catalog():
    subprocess.run(['cargo','build','--release','--offline','--manifest-path',str(ROOT/'wftools/wf_attr_edit/Cargo.toml')],check=True)
    bindings=json.loads((ROOT/'wflevels/aquarium_plants/settings-bindings.json').read_text())
    return M.catalog(ROOT/'wflevels/aquarium_plants/settings.oad',bindings,1)

def test_real_core_edit_isolation_and_readback(catalog,tmp_path):
    second=M.catalog(ROOT/'wflevels/aquarium_plants/settings.oad',json.loads((ROOT/'wflevels/aquarium_plants/settings-bindings.json').read_text()),2)
    payload=catalog[:4]+struct.pack('<I',2)+catalog[8:]+second[8:]
    file=tmp_path/'properties';file.write_bytes(payload);binary=tmp_path/'check'
    subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'engine'),str(ROOT/'tests/object_property_core_test.cpp'),str(ROOT/'engine/runtime_properties.cpp'),str(ROOT/'engine/runtime_property_form.cpp'),str(ROOT/'engine/runtime_property_host.cpp'),str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(binary)],check=True)
    subprocess.run([binary,file],check=True)

def test_catalog_attachment_preserves_asset_bytes_and_is_idempotent(catalog):
    original=(ROOT/'wflevels/aquarium_plants-standalone.iff').read_bytes()
    result=M.attach(original,catalog)
    asset_end=4096+8+struct.unpack_from('<I',original,4100)[0]
    assert result[4096:asset_end]==original[4096:asset_end]
    assert len(result)%2048==0
    assert M.attach(result,catalog)==result
    ram_len=struct.unpack_from('<I',result,2052)[0]
    offset,size=struct.unpack_from('<II',result,2056+ram_len-8)
    assert result[2048+offset:2048+offset+4]==b'RPRP' and size%2048==0

def test_missing_oad_field_rejected():
    with pytest.raises(ValueError):
        M.catalog(ROOT/'wflevels/aquarium_plants/settings.oad',{'fields':{'Invented':{'id':1}}},1)

def test_colour_text_and_notes_ui(catalog,tmp_path):
    path=tmp_path/'properties';path.write_bytes(catalog);exe=tmp_path/'controls'
    subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'wfsource/source'),str(ROOT/'tests/runtime_property_controls_test.cpp'),str(ROOT/'wfsource/source/game/runtime_property_ui.cc'),str(ROOT/'wfsource/source/game/runtime_settings_ui.cc'),str(ROOT/'engine/runtime_properties.cpp'),str(ROOT/'engine/runtime_property_form.cpp'),str(ROOT/'engine/runtime_property_host.cpp'),str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(exe)],check=True)
    subprocess.run([exe,path,tmp_path],check=True)

def test_explicit_notes_binding_uses_multiline_string(tmp_path):
    key='Cave Logic Studios Notes|'
    payload=M.catalog(ROOT/'wfsource/source/oas/actor.oad',{'fields':{key:{'id':205,'initial':'One\nTwo'}}},1)
    # Verify the actual cooker's projection of a shipped ignored-XData Notes field.
    path=tmp_path/'notes.rprp';path.write_bytes(payload)
    cursor=8
    cursor+=4 # actor ID
    def skip_string():
        nonlocal cursor
        size=struct.unpack_from('<I',payload,cursor)[0];cursor+=4+size
    skip_string();skip_string();count=struct.unpack_from('<I',payload,cursor)[0];cursor+=4
    found=None
    for _ in range(count):
        values=struct.unpack_from('<IBBBBiiIII',payload,cursor);cursor+=28
        if values[0]==205:found=values
        for _ in range(6):skip_string()
    assert found and found[1]==3 and found[3]==0 and found[4]==2 and found[-1]==4096


def test_catalog_replacement_on_flag_only_baseline_ram(catalog):
    original=(ROOT/'wflevels/baseline-standalone.iff').read_bytes()
    assert struct.unpack_from('<I',original,2052)[0]==48
    result=M.attach(original,catalog)
    assert struct.unpack_from('<I',result,2052)[0]==48
    assert M.attach(result,catalog)==result
    asset_end=4096+8+struct.unpack_from('<I',original,4100)[0]
    assert result[4096:asset_end]==original[4096:asset_end]
