"""The settings every level offers: declared once (oas/global_settings.inc), carried by every settings holder.

docs/plans/2026-11-22-global-level-settings.md. Will, 2026-11-22: "Show framerate: hook that up and make sure
all wf levels include this level setting"; "i recommend having a global declaration (right now consisting
only of Show FPS) so you only have to change in 1 place in future".
"""
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
OAS = ROOT / "wfsource/source/oas"
GAME = ROOT / "wfsource/source/game"
CATALOG = ROOT / "wftools/wf_attr_edit/target/release/catalog"


def declared_globals():
    """The keys global_settings.inc declares, in order: the one place a global is declared."""
    text = (OAS / "global_settings.inc").read_text()
    return re.findall(r"^\s*TYPEENTRY\w+\(([^,]+),", text, re.M)


def holders():
    """Every .oas that includes settings.inc: a settings holder."""
    return sorted(p for p in OAS.glob("*.oas") if "@include settings.inc" in p.read_text())


def test_one_declaration_holds_exactly_show_framerate_today():
    assert declared_globals() == ["Show framerate"]
    text = (OAS / "global_settings.inc").read_text()
    assert "SHOW_AS_CHECKBOX|SHOW_AS_LIVE" in text, "a live checkbox: the form edits it and Apply takes effect"
    assert ",0," in text.split("TYPEENTRYBOOLEAN(Show framerate", 1)[1].splitlines()[0], "default off"


def test_every_holder_ends_with_the_global_sheet_so_no_field_id_moves():
    assert len(holders()) >= 10
    for oas in holders():
        lines = [l.strip() for l in oas.read_text().splitlines() if l.strip() and not l.lstrip().startswith("@*")]
        assert lines[-1] == "TYPEFOOTER", oas.name
        assert lines[-2] == "@include global_settings.inc", f"{oas.name} must end with @include global_settings.inc"
    assert "@include global_settings.inc" not in (OAS / "settings.inc").read_text().replace("@*", "#"), \
        "settings.inc must not include it: the sheet goes last in each holder, never first"


def test_the_engine_table_has_one_row_for_each_declared_global():
    source = (GAME / "global_settings.cc").read_text()
    rows = re.findall(r'^\s*\{"([^"]+)",\s*\w+\},', source, re.M)
    assert rows == declared_globals(), "global_settings.inc and the engine table in global_settings.cc must list the same keys"


def test_the_level_applies_the_globals_on_change_and_at_load():
    level = (GAME / "level.cc").read_text()
    assert '#include "global_settings.hp"' in level
    assert "wfglobals::applyChanged(*object);" in level
    assert "wfglobals::applyAtLoad(_runtimeProperties);" in level


def test_level_settings_is_registered_last_in_every_registry():
    """A new type is appended, never inserted: the position is the type id compiled into every level."""
    mac = re.findall(r"^\s*OBJECTENTRY\((\w+),", (OAS / "objects.mac").read_text(), re.M)
    assert mac.count("LevelSettings") == 1 and mac[-1] == "LevelSettings"
    kinds = re.findall(r"^\s*(\w+)_KIND,", (OAS / "objects.e").read_text(), re.M)
    assert kinds[-1] == "LevelSettings"
    assert re.findall(r"^\s*(\w+)_KIND,", (OAS / "objects.h").read_text(), re.M)[-1] == "LevelSettings"
    assert re.findall(r'^\s*"(\w+)",', (OAS / "objects.names").read_text(), re.M)[-1] == "LevelSettings"
    assert [l.strip() for l in (OAS / "objects.lc").read_text().splitlines() if l.strip().isidentifier()][-1] == "levelsettings"
    assert re.findall(r"//\s*(\w+)\s*$", (OAS / "objects.col").read_text(), re.M)[-1] == "LevelSettings"
    assert re.findall(r'#include "(\w+)\.hp"', (OAS / "objects.inc").read_text())[-1] == "levelsettings"
    c = (OAS / "objects.c").read_text()
    assert c.count("case Actor::LevelSettings_KIND:") == 2 and c.count("OadLevelSettings(startData)") == 2
    header = (GAME / "levelsettings.hp").read_text()
    source = (GAME / "levelsettings.cc").read_text()
    assert "class LevelSettings: public Actor" in header and "Actor* OadLevelSettings(" in header
    assert "bool LevelSettings::CanRender() const { return false; }" in source
    assert "bool LevelSettings::CanUpdate() const { return false; }" in source


def test_the_minimal_holder_has_no_sheet_of_its_own():
    text = (OAS / "levelsettings.oas").read_text()
    assert "PROPERTY_SHEET_HEADER" not in text and "@include settings.inc" in text


@pytest.mark.parametrize("name", [p.stem for p in holders()])
def test_each_compiled_holder_lists_the_global_field_last(name):
    if not CATALOG.exists():
        pytest.skip("build the catalog tool first: task build-test-tools")
    oad = OAS / f"{name}.oad"
    fields = json.loads(subprocess.check_output([str(CATALOG), str(oad)], text=True))["fields"]
    stored = [f for f in fields if f["width"]]
    assert stored[-1]["key"] == "Show framerate", f"{name}.oad: regenerate it with oas2oad"
    assert stored[-1]["live"] and stored[-1]["default"] in (0, "0"), name
    assert [f["key"] for f in stored].count("Show framerate") == 1


def _audit():
    import importlib.util
    spec = importlib.util.spec_from_file_location("audit_level_settings", ROOT / "scripts/audit-level-settings.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_audit_reads_its_keys_from_the_one_declaration():
    assert _audit().global_keys() == declared_globals() == ["Show framerate"]


def test_the_audit_finds_the_field_in_a_built_level_and_reports_its_absence(tmp_path, monkeypatch):
    audit = _audit()
    levels = tmp_path / "wflevels"
    levels.mkdir()
    (levels / "has-standalone.iff").write_bytes(b"\x00junk\x00Show framerate\x00more")
    (levels / "lacks-standalone.iff").write_bytes(b"\x00junk\x00Seed\x00")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert audit.built_levels() == ["has", "lacks"]
    assert audit.missing_globals("has") == []
    assert audit.missing_globals("lacks") == ["Show framerate"]


def test_the_levels_roster_prints_every_row_and_strict_fails_on_a_gap():
    import subprocess, sys
    plain = subprocess.run([sys.executable, str(ROOT / "scripts/audit-level-settings.py"), "--roster", "levels"],
                           capture_output=True, text=True)
    assert plain.returncode == 0 and "levels audited" in plain.stdout        # prints even without --strict
    strict = subprocess.run([sys.executable, str(ROOT / "scripts/audit-level-settings.py"), "--roster", "levels", "--strict"],
                            capture_output=True, text=True)
    assert strict.returncode == (1 if " without the global settings" in strict.stdout
                                 and not strict.stdout.rstrip().endswith("0 without the global settings") else 0)
