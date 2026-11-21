"""Content rule: no species is in two aquarium tanks, and every tank has a list."""
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIES = json.loads((ROOT / "wflevels/aquarium_species.json").read_text())
TANKS = {k: v for k, v in SPECIES.items() if not k.startswith("_")}
TWINS = {"aquarium_thai_reef_anime": "aquarium_thai_reef"}  # same roster, other style


def test_every_manifest_tank_has_a_species_list():
    manifest = (ROOT / "wflevels/aquarium-menu.manifest").read_text()
    ids = re.findall(r"^level (aquarium\w*?)-standalone\.iff", manifest, re.M)
    assert ids and set(ids) == set(TANKS)


def test_no_species_in_two_tanks():
    seen = defaultdict(list)
    for tank, names in TANKS.items():
        assert tank in TWINS or names, f"{tank} has no species"
        for n in names:
            seen[n.lower()].append(tank)
    dup = {n: t for n, t in seen.items() if len(t) > 1}
    assert not dup, dup
