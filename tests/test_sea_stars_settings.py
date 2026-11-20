"""SeaStarsSettings: the type's nine fields and its registration (plan phase 0).

docs/plans/2026-11-20-sea-stars-settings.md. The director tests (edit-and-check per field,
parking) are added in the later phases; this file holds the type-shape checks.
"""
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
OAS = ROOT / "wfsource/source/oas"
CATALOG = ROOT / "wftools/wf_attr_edit/target/release/catalog"

# label: (min, max, default). The phone's Dream form is built from these labels.
FIELDS = {
    "Chocolate-chip stars": (0, 4, 2),
    "Red Fromia": (0, 5, 3),
    "Sand-sifting stars": (0, 4, 2),
    "Brittle stars": (0, 2, 1),
    "Cushion stars": (0, 2, 1),
    "Speed": (0, 2, 1),
    "Glass climbing": (0, 1, 1),
    "Caustics": (0, 1, 1),
    "Seed": (0, 2147483647, 0),
}
# The level holds the maximum population; the director parks the extras (D10).
MAXIMUM_RESIDENTS = 4 + 5 + 4 + 2 + 2
DEFAULT_RESIDENTS = 2 + 3 + 2 + 1 + 1


def catalog():
    if not CATALOG.exists():
        pytest.skip("build the catalog tool first: cargo build --release --manifest-path "
                    "wftools/wf_attr_edit/Cargo.toml --bin catalog")
    out = subprocess.run([str(CATALOG), str(OAS / "seastarssettings.oad")],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_the_nine_fields_have_the_d9_ranges_and_defaults_and_are_live():
    fields = {f["key"]: f for f in catalog()["fields"]}
    for label, (low, high, default) in FIELDS.items():
        assert label in fields, label
        f = fields[label]
        assert (f["min"], f["max"], f["default"]) == (low, high, default), label
        assert f["live"], f"{label} must be SHOW_AS_LIVE or a runtime edit has no effect"


def test_only_the_nine_settings_fields_are_live():
    live = {f["key"] for f in catalog()["fields"] if f["live"]}
    assert live == set(FIELDS)


def test_default_and_maximum_population_match_the_plan():
    defaults = sum(FIELDS[k][2] for k in list(FIELDS)[:5])
    maximum = sum(FIELDS[k][1] for k in list(FIELDS)[:5])
    assert (defaults, maximum) == (DEFAULT_RESIDENTS, MAXIMUM_RESIDENTS) == (9, 17)


def test_the_type_is_registered_once_and_after_every_existing_type():
    """objects.mac says new types are appended, never inserted: the position is the type id
    compiled into every level. Every registry file must agree on that position."""
    mac = [m for m in re.findall(r"^\s*OBJECTENTRY\((\w+),", (OAS / "objects.mac").read_text(), re.M)]
    assert mac.count("SeaStarsSettings") == 1
    position = mac.index("SeaStarsSettings")
    assert mac[position - 1] == "LevelRenderSettings"
    kinds = re.findall(r"^\s*(\w+)_KIND,", (OAS / "objects.h").read_text(), re.M)
    assert kinds.index("SeaStarsSettings") == position + (len(kinds) - len(mac))
    names = re.findall(r'^\s*"(\w+)",', (OAS / "objects.names").read_text(), re.M)
    assert names.index("SeaStarsSettings") == names.index("LevelRenderSettings") + 1
    assert (OAS / "objects.lc").read_text().split().index("seastarssettings") == \
        (OAS / "objects.lc").read_text().split().index("levelrendersettings") + 1
    assert '#include "seastarssettings.hp"' in (OAS / "objects.inc").read_text()
    assert "OadSeaStarsSettings" in (OAS / "objects.c").read_text()
