"""Authored catalogs and real host transactions for process-global settings."""
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/baseline'))
from runtime_options_fixture import inventory

def test_inventory_and_stable_pair():
    fields=inventory()
    assert len({f['id'] for f in fields})==len(fields)
    for name in ['settings','settings-gallery']:
        source=(ROOT/'wflevels/baseline'/f'{name}.oas').read_text()
        assert source.count('PROPERTY_SHEET_HEADER(Runtime Options,0)')==1
        b=json.loads((ROOT/'wflevels/baseline'/f'{name}-bindings.json').read_text())['fields']
        assert len({f['id'] for f in b.values()})==len(b)
        assert all(b[f['key']]['id']==f['id'] and b[f['key']]['readonly'] for f in fields)

def test_active_long_parser_switches_accounted_for():
    source=(ROOT/'wfsource/source/game/main.cc').read_text().split('ParseCommandLine(int argc, char** argv)',1)[1].split('void\nPIGSMain',1)[0]
    source=re.sub(r"//[^\n]*", "", source)
    found=set()
    for literal in re.findall(r'"(-[a-z][a-z-]*(?:=)?)',source):
        # Patterns matched against argv+1 retain the second dash.
        found.add(literal if literal.startswith('--') else '-'+literal)
    cli={c for f in inventory() for c in f['cli']}
    cli.update(json.loads((ROOT/'wflevels/baseline/runtime-options.json').read_text())['exclusions'])
    assert found<=cli, found-cli

def test_real_catalog_process_transactions(tmp_path):
    spec=importlib.util.spec_from_file_location('cooker',ROOT/'scripts/build-object-properties.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    b=json.loads((ROOT/'wflevels/baseline/settings-bindings.json').read_text())
    catalogs=[m.catalog(ROOT/'wflevels/baseline/settings.oad',b,a) for a in [11,22]]
    payload=tmp_path/'settings.rprp';payload.write_bytes(b'RP01'+struct.pack('<I',2)+b''.join(c[8:] for c in catalogs))
    exe=tmp_path/'runtime-options'
    subprocess.run(['c++','-std=c++17','-O1','-I'+str(ROOT/'engine'),str(ROOT/'tests/runtime_options_test.cpp'),*[str(ROOT/'engine'/n) for n in ['runtime_properties.cpp','runtime_property_form.cpp','runtime_property_host.cpp']],str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(exe)],check=True)
    subprocess.run([exe,payload],check=True)
