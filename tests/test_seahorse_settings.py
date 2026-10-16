"""The Seahorses settings sheet: catalog fields 8 and 9, and their round trip through Apply
(the plan's Phase 3 open question). Compiles the real plant_settings.h host with the cooked
catalog, as test_plant_phone.py does."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'wflevels/aquarium_plants'


def test_sheet_and_bindings():
    oas = (HERE / 'settings.oas').read_text()
    assert 'PROPERTY_SHEET_HEADER(Seahorses,0)' in oas
    assert re.search(r'TYPEENTRYINT32\(Seahorses,,0,2,2,"None\|1 pair\|2 pairs",SHOW_AS_RADIOBUTTONS', oas)
    assert re.search(r'TYPEENTRYBOOLEAN\(Greeting,,1,SHOW_AS_CHECKBOX', oas)
    fields = json.loads((HERE / 'settings-bindings.json').read_text())['fields']
    assert fields['Seahorses'] == {'id': 8} and fields['Greeting'] == {'id': 9}


def test_fields_8_and_9_round_trip_through_apply(tmp_path):
    exe = tmp_path / 'roundtrip'
    subprocess.run(['g++', '-std=c++17', '-O1', '-pthread', '-I' + str(ROOT / 'wfsource/source'),
                    str(ROOT / 'tests/seahorse_settings_roundtrip.cc'),
                    *(str(ROOT / 'engine' / n) for n in ('runtime_properties.cpp', 'runtime_property_form.cpp',
                                                         'runtime_property_host.cpp')),
                    str(ROOT / 'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'), '-ldl', '-lpthread', '-lm',
                    '-o', str(exe)], check=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert 'round-trip ok' in out.stdout
