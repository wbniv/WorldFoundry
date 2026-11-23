"""The Cuckoo Village parts catalogue (scripts/cuckoo-village-catalogue.py, wflevels/cuckoo_village/catalogue_entries.py).

Regression guard: a part added to the level without saying what it is. `inventory.json` beside the catalogue is the built level's actor list
(CUCKOO_INVENTORY=<file> with the level builder); every actor in it must have a card, every card's actors must exist, and every section a
card cuts out of a bigger mesh must be one the part builders really record.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
import bavaria as bv  # noqa: E402
import catalogue_entries as ce  # noqa: E402

INVENTORY = ROOT / "docs/reference/cuckoo-village-parts/inventory.json"
LATE = {"CuckooVillageSettings"}                 # the builder adds the settings object after the inventory is taken


def script():
    spec = importlib.util.spec_from_file_location("cuckoo_village_catalogue", ROOT / "scripts/cuckoo-village-catalogue.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_entry_ids_are_unique_and_every_entry_says_something():
    ids = [e["id"] for e in ce.ENTRIES]
    assert len(ids) == len(set(ids))
    for e in ce.ENTRIES:
        assert e["what"].strip() and e["title"].strip() and e["actors"], e["id"]
        assert e["kind"] in ("actor", "section", "engine")


def test_every_actor_of_the_level_has_a_card():
    inventory = json.loads(INVENTORY.read_text())
    names = {o["name"] for o in inventory}
    covered = ce.covered_actors()
    assert names - covered == set(), f"parts with no card: {sorted(names - covered)}"
    assert covered - names - LATE == set(), f"cards for parts that do not exist: {sorted(covered - names - LATE)}"


def test_every_section_card_names_a_section_the_builders_record():
    tower_art = (ROOT / "wflevels/cuckoo_village_layout/tower_art.py").read_text()
    tower_labels = set(re.findall(r"mark\('([^']+)'\)", tower_art))
    parts = bv.all_parts(0.19, [((x * 3.0, 0.0, 0.0), 0.0, 1.0) for x in range(13)], lambda x, y: 0.0)
    bavaria_labels = {label: name for name, p in parts.items() for label, _ in p.sections}
    for e in ce.ENTRIES:
        if e["kind"] != "section" or not e.get("section"):
            continue
        label = e["section"]
        if e["actors"][0] == "tower_case":
            assert label in tower_labels, f"{e['id']}: tower_art.py has no mark({label!r})"
        else:
            assert bavaria_labels.get(label) == e["actors"][0], f"{e['id']}: bavaria.py has no section {label!r} in {e['actors'][0]}"


def test_bavaria_sections_start_in_order_and_inside_the_part():
    parts = bv.all_parts(0.19, [((x * 3.0, 0.0, 0.0), 0.0, 1.0) for x in range(13)], lambda x, y: 0.0)
    for name, p in parts.items():
        starts = [s for _, s in p.sections]
        assert starts == sorted(starts), name
        assert all(0 <= s <= len(p.faces) for s in starts), name


def test_the_page_has_a_card_for_every_entry_even_with_no_pictures(tmp_path):
    page = script().build_html({}, tmp_path, None)
    for e in ce.ENTRIES:
        assert f'id="{e["id"]}"' in page, e["id"]
        assert e["title"].replace("&", "&amp;") in page or e["title"] in page
    assert "not rendered" in page
