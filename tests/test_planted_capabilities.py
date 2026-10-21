"""Planted Tank coordinator capabilities generated from the settings OAD.

Plan: docs/plans/2026-10-21-planted-tank-screensaver.md (Decision, Will 2026-10-21: the APK's
settings come from the OAD). The test compiles the tracked settings.oas with the same tools
build_planted() uses (oas2oad + prep, built by wflevels/planted_tank_screensaver/build.sh) and
skips without them, then runs scripts/gen-planted-capabilities.py on the result. The JVM side
(PlantedConfigTest with the generated JSON) checks that PlantedConfig accepts every option.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEVEL = ROOT / "wflevels/planted_tank_screensaver"
GENERATOR = ROOT / "scripts/gen-planted-capabilities.py"
OAS2OAD = ROOT / "wftools/oas2oad-rs/target/release/oas2oad"
PREP = ROOT / "wftools/prep/prep"
CATALOG = ROOT / "wftools/wf_attr_edit/target/release/catalog"
TOOLS = (OAS2OAD, PREP, CATALOG)

spec = importlib.util.spec_from_file_location("gen_planted_capabilities", GENERATOR)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

needs_tools = pytest.mark.skipif(not all(t.is_file() for t in TOOLS),
                                 reason="build the OAD tools: bash wflevels/planted_tank_screensaver/build.sh")

# What PlantedSettingsProvider served before it read the asset (hand-written Java), pinned.
EXPECTED = {"schema": 1, "settings": [
    {"id": "water", "type": "choice", "label": "Water", "value": "freshwater", "options": [
        {"id": "random", "label": "Random"}, {"id": "freshwater", "label": "Freshwater"},
        {"id": "saltwater", "label": "Saltwater"}]},
    {"id": "speed", "type": "choice", "label": "Speed", "value": "1", "options": [
        {"id": s, "label": s + "x"} for s in ("0.25", "0.5", "1", "2", "4", "8")]},
    {"id": "hold", "type": "choice", "label": "Hold", "value": "120", "options": [
        {"id": "60", "label": "1 min"}, {"id": "120", "label": "2 min"},
        {"id": "300", "label": "5 min"}, {"id": "600", "label": "10 min"}]},
]}

SKIPPED = ["Seed", "Initial age", "Textures", "Sway", "Random seed on entry"]


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("caps")
    oad = tmp / "settings.oad"
    # oas2oad links the source into the types directory; use a copy so the repo can be read-only.
    types = tmp / "oas"
    shutil.copytree(ROOT / "wfsource/source/oas", types, symlinks=True)
    subprocess.run([str(OAS2OAD), f"--types={types / 'types3ds.s'}",
                    f"--prep={PREP}", "-o", str(oad), str(LEVEL / "settings.oas")],
                   cwd=ROOT, check=True, capture_output=True)
    out = tmp / "planted-settings.json"
    run = subprocess.run([sys.executable, str(GENERATOR), "--oad", str(oad), "--out", str(out)],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return out, run.stderr, oad


@needs_tools
def test_generated_document_matches_the_former_hand_written_one(generated):
    out, _, _ = generated
    assert json.loads(out.read_text()) == EXPECTED
    # Compact, fixed key order: PlantedConfigTest reads it with a pattern.
    assert out.read_text() == json.dumps(EXPECTED, separators=(",", ":")) + "\n"


@needs_tools
def test_paused_is_dropped(generated):
    speed = next(s for s in json.loads(generated[0].read_text())["settings"] if s["id"] == "speed")
    assert [o["label"] for o in speed["options"]][0] == "0.25x"
    assert not [o for o in speed["options"] if o["id"] in ("0", "paused") or o["label"] == "Paused"]


@needs_tools
def test_skipped_fields_are_reported(generated):
    warnings = [line for line in generated[1].splitlines() if "warning: skipped" in line]
    assert [w.split("skipped ", 1)[1].split(" (", 1)[0] for w in warnings] == SKIPPED
    assert "Random seed on entry (Enum, checkbox; no APK key)" in generated[1]


@needs_tools
def test_settings_class_rule_reads_the_oad(generated):
    schema = gen._properties().oad_schema(generated[2])
    assert schema["name"] == "PlantedTankSettings"


@needs_tools
def test_missing_oad_fails(tmp_path):
    run = subprocess.run([sys.executable, str(GENERATOR), "--oad", str(tmp_path / "none.oad"),
                          "--out", str(tmp_path / "x.json")], capture_output=True, text=True)
    assert run.returncode == 1 and "no such OAD" in run.stderr
    assert not (tmp_path / "x.json").exists()


def test_help_exits_zero():
    run = subprocess.run([sys.executable, str(GENERATOR), "-h"], capture_output=True, text=True)
    assert run.returncode == 0 and "--oad" in run.stdout


# --- rules, on synthetic schemas (no tools needed) ------------------------------------------

def _field(key, kind="Enum", show=5, choices="A|B", lo=0, hi=1, default=0):
    return {"key": key, "label": key, "kind": kind, "show": show, "choices": choices,
            "min": lo, "max": hi, "default": default, "scale": 0, "help": "", "group": ""}


def _planted(**replace):
    fields = [_field("Water type", choices="Freshwater|Saltwater"),
              _field("Growth speed", show=2, choices="Paused|0.25x|0.5x|1x|2x|4x|8x", hi=6, default=3),
              _field("Hold seconds", kind="Int", show=1, choices="", hi=86400, default=120)]
    fields += [_field(k, kind="Str", show=1, choices="") for k in ("Seed", "Initial age", "Textures", "Sway")]
    fields = [replace.get(f["key"], f) for f in fields]
    return {"name": "PlantedTankSettings", "fields": fields}


def test_type_must_be_a_settings_class():
    schema = dict(_planted(), name="PlantedTankDirector")
    with pytest.raises(gen.GenerateError, match="not a settings class"):
        gen.capabilities([schema])


def test_renderable_field_without_an_apk_key_fails():
    schema = _planted()
    schema["fields"].append(_field("Colour", choices="Red|Blue"))
    with pytest.raises(gen.GenerateError, match="Colour: renderable field has no APK key"):
        gen.capabilities([schema])


def test_hold_presets_must_fit_the_oad_range():
    schema = _planted(**{"Hold seconds": _field("Hold seconds", kind="Int", show=1, choices="", hi=300)})
    with pytest.raises(gen.GenerateError, match=r"presets \[600\] are outside 0..300"):
        gen.capabilities([schema])


def test_checkbox_and_text_are_skipped_not_invented():
    document, skipped = gen.capabilities([_planted()])
    assert {s["type"] for s in document["settings"]} == {"choice"}
    assert [s.split(" (")[0] for s in skipped] == ["Seed", "Initial age", "Textures", "Sway"]
