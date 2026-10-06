"""Exercise real seeded meshes and native controls with sanitizers, without a GPU."""
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def test_seeded_growth_and_controls(tmp_path):
    exe=tmp_path/'plants'
    subprocess.run(['g++','-std=c++17','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(ROOT/'wfsource/source'),str(ROOT/'tests/plant_runtime_harness.cc'),str(ROOT/'wfsource/source/game/plant_ui.cc'),str(ROOT/'wfsource/source/game/runtime_property_ui.cc'),str(ROOT/'engine/runtime_properties.cpp'),str(ROOT/'engine/runtime_property_form.cpp'),str(ROOT/'wftools/wf_attr_edit/target/release/libwf_attr_edit.a'),'-ldl','-lpthread','-lm','-o',str(exe)],check=True)
    subprocess.run([str(exe)],env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:abort_on_error=1'),check=True)
