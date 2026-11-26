"""LevelRenderSettings "Maximum surface height": the engine reads it as the level asks, the field is in the type, the
Android TV host applies it and gives the size back, and the lava lamp asks for 1080.

docs/plans/2026-11-26-lava-lamp.md, build record (the 4K TV held 30 FPS at 2160 rows, 59.98 at 1080).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


ATTR = ROOT / "wftools/wf_attr_edit/target/release/libwf_attr_edit.a"


@pytest.mark.skipif(shutil.which("c++") is None, reason="needs a C++ compiler")
@pytest.mark.skipif(not ATTR.exists(), reason="task build-rust-test-tools builds libwf_attr_edit")
def test_the_engine_reads_the_field(tmp_path):
    exe = tmp_path / "surface_cap_test"
    subprocess.run(["c++", "-std=c++17", "-O1", "-pthread", "-I" + str(ROOT / "engine"), str(ROOT / "tests/surface_cap_test.cpp"),
                    str(ROOT / "engine/runtime_properties.cpp"), str(ATTR), "-ldl", "-lpthread", "-lm", "-o", str(exe)], check=True)
    r = subprocess.run([str(exe)], capture_output=True, text=True)
    assert r.returncode == 0 and "surface cap: PASS" in r.stdout, r.stdout + r.stderr


def test_the_type_the_host_and_the_lava_lamp_carry_it():
    oas = (ROOT / "wfsource/source/oas/levelrendersettings.oas").read_text()
    assert "TYPEENTRYINT32(Maximum surface height,,0,4320,0," in oas
    assert oas.index("Maximum surface height") < oas.index("global_settings.inc")
    host = (ROOT / "android/screensaver/src/main/cpp/dream_host.cc").read_text()
    assert "WFMaximumSurfaceHeight()" in host and host.count("ANativeWindow_setBuffersGeometry") >= 2   # cap and release
    assert "appliedCap = 0;" in host                                                                     # a new window
    level = (ROOT / "wfsource/source/game/level.cc").read_text()
    assert 'extern "C" int WFMaximumSurfaceHeight()' in level and "maximumSurfaceHeight(_runtimeProperties" in level
    lev = (ROOT / "wflevels/lava_lamp/lava_lamp.lev").read_text()
    assert "{ 'I32' { 'NAME' \"Maximum surface height\" } { 'DATA' 1080l }" in lev
