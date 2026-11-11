"""Exercise real seeded meshes and native controls with sanitizers, without a GPU."""
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def test_seeded_growth_and_controls(tmp_path):
    exe=tmp_path/'plants'
    subprocess.run(['python3',str(ROOT/'scripts/embed-planted-oad.py'),str(ROOT/'wfsource/source/oas/plantedtanksettings.oad'),str(tmp_path/'planted_oad.inc')],check=True)
    subprocess.run(['g++','-std=c++17','-O0','-g1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(ROOT/'wfsource/source'),'-I'+str(tmp_path),str(ROOT/'tests/plant_runtime_harness.cc'),str(ROOT/'wfsource/source/game/plant_ui.cc'),str(ROOT/'wfsource/source/game/runtime_property_ui.cc'),str(ROOT/'wfsource/source/game/runtime_settings_ui.cc'),str(ROOT/'wfsource/source/game/runtime_property_touch.cc'),str(ROOT/'wfsource/source/game/ui_font.cc'),str(ROOT/'wfsource/source/game/bitmap_text.cc'),str(ROOT/'engine/runtime_properties.cpp'),str(ROOT/'engine/runtime_oad_adapter.cpp'),str(ROOT/'engine/planted_preview.cpp'),str(ROOT/'engine/runtime_property_form.cpp'),str(ROOT/'engine/runtime_property_host.cpp'),str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(exe)],check=True)
    subprocess.run([str(exe),str(ROOT/'wfsource/source/game/ui-font.wfga')],env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1'),check=True)
