"""CuckooVillageSettings: the type's seven fields and its registration.

docs/plans/2026-11-21-cuckoo-village.md ("Level settings"). The type is modelled on ReefSettings and
SeaStarsSettings (53d7c718): an .oas schema, the generated .oad and .ht, one line appended to each
object registry file, and a trivial Actor subclass. The effect of the fields on the timeline and the
generated Forth is in test_cuckoo_village_settings_effect.py.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
OAS = ROOT / "wfsource/source/oas"
GAME = ROOT / "wfsource/source/game"
CATALOG = ROOT / "wftools/wf_attr_edit/target/release/catalog"
OAS2OAD = ROOT / "wftools/oas2oad-rs/target/release/oas2oad"
# The repo's own prep, passed explicitly as tests/test_level_memory_settings.py does: oas2oad otherwise runs `prep`
# from PATH, which the host has (apt.worldfoundry.org) and the wf-linux-test container does not (triage 2026-11-26:
# "failed to run prep (prep): No such file or directory", exit 1).
PREP = ROOT / "wftools/prep/prep"

# label: (min, max, default). The phone's Dream form and the TV form are built from these labels.
FIELDS = {
    "Bavaria mode": (0, 1, 0),
    "Seasonal events": (0, 1, 1),
    "Candles all year": (0, 1, 0),
    "Window lights": (0, 1, 1),
    "Sound": (0, 1, 1),
    "Camera motion": (0, 1, 0),
    "Detailed flowers": (0, 1, 1),
    "Houses": (0, 24, 13),
    "Trees": (0, 24, 12),
}
TYPE = "CuckooVillageSettings"


def catalog():
    if not CATALOG.exists():
        pytest.skip("build the catalog tool first: cargo build --release --manifest-path "
                    "wftools/wf_attr_edit/Cargo.toml --bin catalog")
    out = subprocess.run([str(CATALOG), str(OAS / "cuckoovillagesettings.oad")],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_the_seven_fields_have_the_plan_ranges_and_defaults_and_are_live():
    fields = {f["key"]: f for f in catalog()["fields"]}
    for label, (low, high, default) in FIELDS.items():
        assert label in fields, label
        f = fields[label]
        assert (f["min"], f["max"], f["default"]) == (low, high, default), label
        assert f["live"], f"{label} must be SHOW_AS_LIVE or the forms cannot edit it"



SHOW_SLIDER = 2   # engine/runtime_property_presentation.hpp ShowSlider: the TV form changes it with Left/Right


def test_houses_and_trees_are_sliders_the_tv_form_can_change():
    # Will, 2026-11-28: "the cuckoo village was supposed to have sliders settings for houses and trees,
    # not just display them". As SHOW_AS_NUMBER the TV form drew them as read-only numbers.
    fields = {f["key"]: f for f in catalog()["fields"]}
    for label in ("Houses", "Trees"):
        assert fields[label]["show"] == SHOW_SLIDER, f"{label} must be SHOW_AS_SLIDER"

GLOBAL_FIELDS = {"Show framerate"}   # oas/global_settings.inc: every settings type carries these


def test_only_the_seven_settings_fields_and_the_global_ones_are_live():
    live = {f["key"] for f in catalog()["fields"] if f["live"]}
    assert live == set(FIELDS) | GLOBAL_FIELDS


def test_the_defaults_are_classic_mode_with_everything_else_on():
    """Bavaria mode off is the shipped Classic village; the seasonal and lighting options default on and
    only take effect with the feature they belong to (events need Bavaria mode)."""
    assert FIELDS["Bavaria mode"][2] == 0
    assert FIELDS["Camera motion"][2] == 0, "0 is Journey, the shipped camera"
    assert all(FIELDS[k][2] == 1 for k in ("Seasonal events", "Window lights", "Sound", "Detailed flowers"))
    assert FIELDS["Candles all year"][2] == 0, "the candles are lit 1 Dec to 6 Jan regardless; the switch adds the rest of the year"


def test_help_text_has_no_commas_the_preprocessor_would_split_on():
    """prep splits macro arguments on commas even inside quotes: the first draft failed in g++ for it."""
    for line in (OAS / "cuckoovillagesettings.oas").read_text().splitlines():
        m = re.search(r',"([^"]*)"\)$', line)
        if m:
            assert "," not in m.group(1), m.group(1)


def test_the_type_is_registered_once_and_appended_after_every_existing_type():
    """objects.mac says new types are appended, never inserted: the position is the type id compiled
    into every level. Every registry file must agree on that position."""
    mac = re.findall(r"^\s*OBJECTENTRY\((\w+),", (OAS / "objects.mac").read_text(), re.M)
    assert mac.count(TYPE) == 1
    assert mac.index(TYPE) == mac.index("TideHarbourSettings") + 1, "appended right after the type that was newest then"
    position = mac.index(TYPE)
    kinds = re.findall(r"^\s*(\w+)_KIND,", (OAS / "objects.h").read_text(), re.M)
    assert kinds.index(TYPE) == position + (len(kinds) - len(mac))
    kinds_e = re.findall(r"^\s*(\w+)_KIND,", (OAS / "objects.e").read_text(), re.M)
    assert kinds_e.index(TYPE) == kinds_e.index("TideHarbourSettings") + 1
    names = re.findall(r'^\s*"(\w+)",', (OAS / "objects.names").read_text(), re.M)
    assert names.index(TYPE) == names.index("TideHarbourSettings") + 1
    lc = (OAS / "objects.lc").read_text().split()
    assert lc.index("cuckoovillagesettings") == lc.index("tideharboursettings") + 1
    assert '#include "cuckoovillagesettings.hp"' in (OAS / "objects.inc").read_text()
    colours = re.findall(r"//\s*(\w+)\s*$", (OAS / "objects.col").read_text(), re.M)
    assert colours.index(TYPE) == colours.index("TideHarbourSettings") + 1
    objects_c = (OAS / "objects.c").read_text()
    assert objects_c.count(f"case Actor::{TYPE}_KIND:") == 2          # the two construction switches
    assert objects_c.count(f"OadCuckooVillageSettings(startData)") == 2


def test_the_actor_class_is_a_trivial_settings_holder_that_never_renders_or_updates():
    header = (GAME / "cuckoovillagesettings.hp").read_text()
    source = (GAME / "cuckoovillagesettings.cc").read_text()
    assert f"class {TYPE}: public Actor" in header
    assert f"Actor* Oad{TYPE}(const SObjectStartupData* startupData);" in header
    assert f"return Actor::{TYPE}_KIND;" in source
    assert "bool CuckooVillageSettings::CanRender() const { return false; }" in source
    assert "bool CuckooVillageSettings::CanUpdate() const { return false; }" in source
    assert f"#include <oas/cuckoovillagesettings.ht>" in source


def test_the_oad_is_what_the_tool_makes_from_the_oas():
    if not OAS2OAD.exists():
        pytest.skip("build oas2oad first: cargo build --release --manifest-path wftools/oas2oad-rs/Cargo.toml")
    if not PREP.exists():
        pytest.skip("build prep first: bash wftools/prep/build.sh")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cuckoovillagesettings.oad"
        subprocess.run([str(OAS2OAD), f"--prep={PREP}", "-o", str(out), str(OAS / "cuckoovillagesettings.oas")],
                       check=True, capture_output=True, cwd=str(OAS))
        assert out.read_bytes() == (OAS / "cuckoovillagesettings.oad").read_bytes(), \
            "cuckoovillagesettings.oad is stale: regenerate it with oas2oad"
