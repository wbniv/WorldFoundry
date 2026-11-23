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
    line = text.split("TYPEENTRYINT32(Show framerate", 1)[1].splitlines()[0]
    # An on/off setting is a real checkbox: a 0..1 integer with the checkbox display and an EMPTY choice string.
    # TYPEENTRYBOOLEAN adds a hidden "False|True" choice list, which makes the catalog call it an Enum and the touch
    # form draw a drop-down (Will, 2026-11-22: "i wish they were all checkboxes and actually had a checkbox").
    assert ',0,1,0,"",SHOW_AS_CHECKBOX|SHOW_AS_LIVE,' in line, "a live checkbox, default off"
    assert "TYPEENTRYBOOLEAN(" not in text.replace("Do not use TYPEENTRYBOOLEAN", "")


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


def test_level_settings_and_later_types_keep_consistent_registry_order():
    """Later types are appended after LevelSettings in every generated registry."""
    mac = re.findall(r"^\s*OBJECTENTRY\((\w+),", (OAS / "objects.mac").read_text(), re.M)
    assert mac.count("LevelSettings") == 1
    suffix = mac[mac.index("LevelSettings"):]
    assert suffix[:5] == ["LevelSettings", "DiscusSettings", "AnamorphicShardsSettings", "GlobeSunRingSettings", "TrainLoopsSettings"]
    for name,pattern in (("objects.e",r"^\s*(\w+)_KIND,"), ("objects.h",r"^\s*(\w+)_KIND,"),
                         ("objects.names",r'^\s*"(\w+)",'), ("objects.col",r"//\s*(\w+)\s*$")):
        assert re.findall(pattern,(OAS/name).read_text(),re.M)[-len(suffix):] == suffix
    lower=[name.lower() for name in suffix]
    assert [l.strip() for l in (OAS / "objects.lc").read_text().splitlines() if l.strip().isidentifier()][-len(suffix):] == lower
    assert re.findall(r'#include "(\w+)\.hp"', (OAS / "objects.inc").read_text())[-len(suffix):] == lower
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
    assert stored[-1]["kind"] == "Bool", f"{name}.oad: Show framerate must be a real checkbox (Bool), not an Enum"
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


def test_the_levels_roster_is_what_a_player_can_reach():
    audit = _audit()
    reachable = audit.shipped_levels()
    # every manifest's levels, plus an app's own level
    for manifest in (ROOT / "wflevels").glob("*.manifest"):
        for line in manifest.read_text().splitlines():
            m = re.match(r"\s*level\s+(\S+?)(?:-standalone)?\.iff\b", line)
            if m:
                assert m.group(1) in reachable, m.group(1)
    assert "condo_639_640" in reachable
    # not the style, practice or regression levels
    for hidden in ("style_flat_anime", "mm_practice", "teleport_regression", "unloaded_actor_regression"):
        assert hidden not in reachable
    # an exemption always names its reason, and only reachable levels are exempt
    assert audit.EXEMPT and all(reason.strip() and level in reachable for level, reason in audit.EXEMPT.items())


def test_the_audit_prints_every_row_and_strict_fails_exactly_when_a_reachable_level_is_missing():
    import subprocess, sys
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / "scripts/audit-level-settings.py"), *a],
                                    capture_output=True, text=True)
    plain = run("--roster", "levels")
    assert plain.returncode == 0 and "levels audited" in plain.stdout        # prints even without --strict
    strict = run("--roster", "levels", "--strict")
    assert strict.returncode == (1 if "MISSING" in strict.stdout else 0)
    built = run("--roster", "built")
    assert built.returncode == 0 and "every wflevels/<id>-standalone.iff" in built.stdout


def test_no_settings_holder_declares_an_on_off_setting_as_off_on_radio_buttons():
    """Every on/off setting is a checkbox. A 0..1 choice labelled Off|On draws as Off/On segments and looks
    different from the rest of the form."""
    for oas in holders():
        assert '"Off|On"' not in oas.read_text(), f"{oas.name}: declare it as a checkbox (see global_settings.inc)"
