"""Keep the proposed touch control inventory, table, and visual gallery in sync."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/plans/2026-10-29-touch-settings"
CASES = json.loads(BASE.with_name(BASE.name + "-examples.json").read_text())
PLAN = BASE.with_name(BASE.name + "-phone-tablet.md")
SVG = BASE.with_name(BASE.name + "-examples.svg")
SPEC = importlib.util.spec_from_file_location(
    "touch_examples", ROOT / "scripts/render-touch-settings-examples.py")
RENDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDER)


def test_sensible_type_showas_pairs_and_modifiers_are_covered():
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    pairs = {(case["type"], case["showAs"]) for case in CASES}
    assert {
        ("Int", "N_A (0)"), ("Int", "NUMBER (1)"),
        ("Int", "SLIDER (2)"), ("Int", "COLOR (7)"),
        ("Int", "MAILBOX (9)"),
        ("Float", "NUMBER (1)"), ("Float", "SLIDER (2)"),
        ("Enum", "N_A (0)"), ("Enum", "NUMBER (1)"),
        ("Enum", "SLIDER (2)"), ("Enum", "TOGGLE (3)"),
        ("Enum", "DROPMENU (4)"), ("Enum", "RADIOBUTTONS (5)"),
        ("Enum", "COMBOBOX (10)"),
        ("Bool", "TOGGLE (3)"), ("Bool", "CHECKBOX (8)"),
        ("Str", "N_A (0)"), ("Str + uint32 rule", "NUMBER (1)"),
        ("Str / Annotation", "TEXTEDITOR (11)"),
        ("Str", "FILENAME (12)"),
        ("FileRef / ObjRef", "N_A (0) / VECTOR (128)"),
        ("Action", "N_A (0)"), ("Spacer", "N_A (0)"),
    } <= pairs
    assert {"int-readonly", "enum-many", "enum-long", "int-help"} <= set(ids)
    assert all(case["status"] in ("existing", "proposed") for case in CASES)


def test_plan_table_and_mockup_cover_each_example():
    text = PLAN.read_text()
    table = text.split(RENDER.START, 1)[1].split(RENDER.END, 1)[0].strip()
    assert table == RENDER.table()
    svg = SVG.read_text()
    assert svg == RENDER.gallery()
    for case in CASES:
        assert svg.count(f'data-example="{case["id"]}"') == 1
        assert table.count(f'`{case["id"]}`') == 1
    assert "showAs=6" in text  # hidden fields have no control
    assert "nonzero enum minimum" in text


def test_showas_numbers_match_oad_definitions():
    oad = (ROOT / "wfsource/source/oas/oad.h").read_text()
    definitions = {name: int(raw, 0) for name, raw in re.findall(
        r"#define\s+SHOW_AS_([A-Z_]+)\s+(0x[0-9A-Fa-f]+|\d+)", oad)}
    for case in CASES:
        for name, raw in re.findall(r"([A-Z_]+) \((\d+)\)", case["showAs"]):
            assert definitions[name] == int(raw), case["id"]


@pytest.fixture(scope="module")
def touch_harness(tmp_path_factory):
    out = tmp_path_factory.mktemp("touch-settings") / "touch"
    source = ROOT / "wfsource/source/game"
    subprocess.run([
        "c++", "-std=c++17", "-O1", "-I" + str(ROOT / "wfsource/source"),
        str(ROOT / "tests/runtime_property_touch_test.cpp"),
        *[str(source / file) for file in (
            "runtime_property_ui.cc", "runtime_settings_ui.cc", "runtime_property_touch.cc",
            "ui_font.cc", "bitmap_text.cc")],
        *[str(ROOT / "engine" / file) for file in (
            "runtime_properties.cpp", "runtime_property_form.cpp", "runtime_property_host.cpp")],
        str(ROOT / "wftools/wf_attr_edit/target/release/libwf_attr_edit.a"),
        "-ldl", "-lpthread", "-lm", "-o", str(out)], check=True)
    return out


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_each_example_accepts_the_intended_touch_action(touch_harness, case):
    show = re.search(r"\((\d+)\)", case["showAs"])
    assert show
    subprocess.run([
        str(touch_harness), str(ROOT / "wflevels/planted_tank_screensaver/settings.rprp"),
        case["id"], case["type"], show.group(1)], check=True)
