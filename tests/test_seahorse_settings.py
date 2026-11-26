"""The Seahorses settings sheet: catalog fields 8 and 9, and their round trip through Apply
(the plan's Phase 3 open question). Compiles the real plant_settings.h host with the cooked
catalog, as test_plant_phone.py does."""
import json
import re
import subprocess
from pathlib import Path
from plant_preview_build import preview_sources

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'wflevels/aquarium_plants'


def test_sheet_and_bindings():
    # cd6b9e9e0 moved the tank's settings.oas and settings-bindings.json into the PlantedTankSettings actor type:
    # the sheet is wfsource/source/oas/plantedtanksettings.oas and a field's id is its catalog index.
    oas = (ROOT / 'wfsource/source/oas/plantedtanksettings.oas').read_text()
    assert 'PROPERTY_SHEET_HEADER(Seahorses,0)' in oas
    assert re.search(r'TYPEENTRYINT32\(Seahorses,,0,6,6,"None\|1 pair\|2 pairs\|3 pairs\|4 pairs\|5 pairs\|6 pairs",SHOW_AS_RADIOBUTTONS', oas)
    assert re.search(r'TYPEENTRYBOOLEAN\(Greeting,,1,SHOW_AS_CHECKBOX', oas)
    schema = json.loads(subprocess.check_output([str(ROOT / 'wftools/wf_attr_edit/target/release/catalog'),
                                                 str(ROOT / 'wfsource/source/oas/plantedtanksettings.oad')], text=True))
    fields = {f['key']: f['index'] for f in schema['fields'] if f.get('width')}
    assert fields['Greeting'] == fields['Seahorses'] + 1


def test_fields_8_and_9_round_trip_through_apply(tmp_path):
    exe = tmp_path / 'roundtrip'
    subprocess.run(['g++', '-std=c++17', '-O1', '-pthread', '-I' + str(ROOT / 'wfsource/source'),
                    *preview_sources(tmp_path),
                    str(ROOT / 'tests/seahorse_settings_roundtrip.cc'),
                    *(str(ROOT / 'engine' / n) for n in ('runtime_properties.cpp', 'runtime_property_form.cpp',
                                                         'runtime_property_host.cpp')),
                    str(ROOT / 'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'), '-ldl', '-lpthread', '-lm',
                    '-o', str(exe)], check=True)
    out = subprocess.run([str(exe)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert 'round-trip ok' in out.stdout
