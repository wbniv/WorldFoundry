"""The touch settings form on a short landscape phone, and its sliders (Will, 2026-11-22: "settings is too big and
unusable", "range sliders don't have any sort of ticks"). Builds tests/runtime_property_touch_layout_test.cpp the way
tests/test_touch_settings_plan_examples.py builds the example harness."""
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def layout_harness(tmp_path_factory):
    lib = ROOT / "wftools/wf_attr_edit/target/release/libwf_attr_edit.a"
    if not lib.exists():
        pytest.skip("build the attribute library first: task build-test-tools")
    out = tmp_path_factory.mktemp("touch-layout") / "touch_layout"
    source = ROOT / "wfsource/source/game"
    subprocess.run([
        "c++", "-std=c++17", "-O1", "-I" + str(ROOT / "wfsource/source"),
        str(ROOT / "tests/runtime_property_touch_layout_test.cpp"),
        *[str(source / file) for file in (
            "runtime_property_ui.cc", "runtime_settings_ui.cc", "runtime_property_touch.cc",
            "ui_font.cc", "bitmap_text.cc")],
        *[str(ROOT / "engine" / file) for file in (
            "runtime_properties.cpp", "runtime_property_form.cpp", "runtime_property_host.cpp")],
        str(lib), "-ldl", "-lpthread", "-lm", "-o", str(out)], check=True)
    return out


def test_a_short_landscape_phone_shows_several_fields_with_ticks_and_bar_relative_taps(layout_harness):
    result = subprocess.run(
        [str(layout_harness), str(ROOT / "tests/fixtures/touch_settings.rprp"),
         str(ROOT / "wfsource/source/game/ui-font.wfga")], check=True, capture_output=True, text=True)
    print(result.stdout)
    assert "touch_layout: ok" in result.stdout
