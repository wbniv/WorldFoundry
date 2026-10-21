"""The Aquarium screensaver's Planted variant carries the PlantedTankSettings catalog.

Without it the level runs `legacy-defaults` (always freshwater). The variant builder
(scripts/build-aquarium-screensaver-levels.py attach_catalog) attaches the canonical
aquarium_plants catalog to aquarium_plants_screensaver-standalone.iff before cdpack packs
aquarium-screensaver-cd.iff. The artifact checks need `python3 scripts/build-aquarium-screensaver-levels.py`
and skip without its output; the source checks always run.
"""
import importlib.util
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / "wflevels"
VARIANT = LEVELS / "aquarium_plants_screensaver-standalone.iff"
BUNDLE = LEVELS / "aquarium-screensaver-cd.iff"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load("aquarium_screensaver_builder", ROOT / "scripts/build-aquarium-screensaver-levels.py")


def test_only_the_planted_tank_has_a_catalog_source():
    sources = [tank for tank in builder.TANKS if (LEVELS / tank / "settings-bindings.json").is_file()]
    assert sources == ["aquarium_plants"]


def test_canonical_actor_map_matches_the_canonical_level():
    # attach_catalog() makes the same check against the variant's own .lev.
    blocks = (LEVELS / "aquarium_plants/aquarium_plants.lev").read_text().split("\t{ 'OBJ'")
    indices = json.loads((LEVELS / "aquarium_plants/actor-map.json").read_text())["indices"]
    for name, index in indices.items():
        assert re.search(r"\{ 'NAME' \"" + re.escape(name) + r"\" \}", blocks[index]), (name, index)


def test_build_attaches_the_catalog_before_returning_the_standalone():
    source = (ROOT / "scripts/build-aquarium-screensaver-levels.py").read_text()
    body = source[source.index("def build(tank"):source.index("PLANTED = ")]
    assert body.index("build_level_binary.sh") < body.index("attach_catalog(tank)") < body.index("return LEVELS")


def test_check_rejects_a_level_without_the_catalog():
    with pytest.raises(ValueError, match="PlantedTankSettings"):
        builder.check_tank_catalog(b"no catalog here", "aquarium_plants_screensaver")


def test_check_rejects_the_planted_flavors_hold_seconds():
    level = b"RPRP RPRP PlantedTankSettings " + b" ".join(
        [b"Seed", b"Water type", b"Growth speed", b"Initial age", b"Textures", b"Sway",
         b"Random seed on entry", b"Seahorses", b"Greeting", b"Hold seconds"])
    with pytest.raises(ValueError, match="Hold seconds"):
        builder.check_tank_catalog(level, "aquarium_plants_screensaver")


@pytest.mark.skipif(not VARIANT.is_file(), reason="run scripts/build-aquarium-screensaver-levels.py first")
def test_variant_standalone_has_one_catalog():
    data = VARIANT.read_bytes()
    assert data.count(b"RPRP") == 2
    assert data.count(b"PlantedTankSettings") == 1
    builder.check_tank_catalog(data, "aquarium_plants_screensaver")


@pytest.mark.skipif(not BUNDLE.is_file(), reason="run scripts/build-aquarium-screensaver-levels.py first")
def test_bundle_has_exactly_the_planted_tanks_catalog():
    data = BUNDLE.read_bytes()
    assert data.count(b"RPRP") == 2
    assert data.count(b"PlantedTankSettings") == 1
    assert b"Hold seconds" not in data


@pytest.mark.skipif(not VARIANT.is_file(), reason="run scripts/build-aquarium-screensaver-levels.py first")
def test_other_variants_carry_no_catalog():
    for tank in builder.TANKS:
        path = LEVELS / (tank + "_screensaver-standalone.iff")
        if tank != "aquarium_plants" and path.is_file():
            assert path.read_bytes().count(b"RPRP") == 0, tank
