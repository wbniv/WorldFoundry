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
    subprocess.run(['c++','-std=c++17','-I'+str(ROOT/'engine'),str(ROOT/'tests/object_property_core_test.cpp'),str(ROOT/'engine/runtime_properties.cpp'),str(ROOT/'engine/runtime_property_form.cpp'),str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(binary)],check=True)
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
