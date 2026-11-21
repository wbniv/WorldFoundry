"""TideHarbourSettings (plan D13 and Q9): the type, its registration, the object in the level, and every field
set, the director stepped and the pose checked.

The type is wfsource/source/oas/tideharboursettings.oas: settings.inc, the clocks' shared Clock sheet
(clocksettings.inc: Camera drift, Slow or Off) and Tide Harbour's own sheet (Dial numerals: Thai, Roman or none;
Gauge board: on or off; Boats and birds: on or off), every field live and its first choice the default. One object
stands in the level; every frame the director reads each field with property@ and copies it into global cells
690 to 693. The VM half sets the object's fields as property@ answers them; scripts/check-tide-harbour.py --options
does the same in the engine with --property launch overrides.
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OAS = ROOT / "wfsource/source/oas"
sys.path.insert(0, str(ROOT / "tests"))

import level_modules  # noqa: E402

tl, _parts, forth = level_modules.load("tide_harbour", "timeline", "parts", "forth")

Q9 = {"drift": ("Slow", "Off"), "numerals": ("Thai", "Roman", "None"), "gauge": ("On", "Off"), "life": ("On", "Off")}
MAP = json.loads((ROOT / "wflevels/tide_harbour/actor-map.json").read_text())
TODAY = tl.wall_day(dt.date(2026, 11, 21))


def test_the_fields_are_q9s_with_the_default_first():
    assert tl.OPTIONS == Q9
    assert tl.DEFAULT_OPTIONS == {k: 0 for k in Q9}
    assert list(tl.FIELD_LABELS) == list(Q9)


def test_one_object_in_the_level_and_the_director_reads_it_with_property_at():
    lev = (ROOT / "wflevels/tide_harbour/tide_harbour.lev").read_text(errors="ignore")
    assert lev.count('{ \'STR\' { \'NAME\' "Class Name" } { \'DATA\' "tideharboursettings" } }') == 1
    fields = MAP["settings_fields"]
    assert set(fields) == set(tl.FIELD_LABELS.values())
    text = forth.director_script(MAP["indices"], fields)
    assert f": th-settings {MAP['indices'][tl.SETTINGS_ACTOR]} ;" in text
    for k, label in tl.FIELD_LABELS.items():
        assert f": th-f-{k} {fields[label]} ;" in text
        assert f"th-settings th-f-{k} property@ if th-opt-{k} th!" in text


def test_the_phone_asset_lists_the_four_fields_of_the_placed_object():
    asset = json.loads((ROOT / "android/screensaver/src/clocks/assets/tide-harbour-settings.json").read_text())
    (owner,) = asset["objects"]
    assert owner["owner"] == MAP["indices"][tl.SETTINGS_ACTOR] and owner["type"] == "TideHarbourSettings"
    got = {s["key"]: ([o["label"] for o in s["options"]], s["value"], s["readonly"]) for s in owner["settings"]}
    assert got == {label: (list(Q9[k]), "0", False) for k, label in tl.FIELD_LABELS.items()}


def test_the_cells_are_global_user_mailboxes_written_only_from_property_at():
    cells = set(tl.OPTION_CELLS.values())
    assert all(2 <= c <= 1900 for c in cells)                     # docs/level-building.md: global user cells
    scratch = set(range(600, 600 + len(forth.CELLS))) | {forth.PREVQ} | set(tl.VIS.values())
    assert not cells & scratch
    text = forth.director_script(forth.default_indices())
    for name in tl.OPTION_CELLS:
        assert f"th-opt-{name} th@" in text
        assert text.count(f"th-opt-{name} th!") == 1                # the poll's copy, nothing else


@pytest.fixture(scope="module")
def vm():
    if shutil.which("cc") is None or shutil.which("c++") is None:
        pytest.skip("needs a C and C++ compiler")
    import verify_tide_harbour_forth as v
    with tempfile.TemporaryDirectory(prefix="th-settings-") as t:
        tmp = Path(t)
        ids, ix = v.build(tmp)
        host = v.Host(tmp, ids)
        host.ix, host.fields = ix, forth.settings_fields()
        yield v, host, ix, ids
        host.close()


@pytest.mark.parametrize("field", list(Q9))
def test_every_value_of_every_field_poses_the_scene_as_the_model_says(vm, field):
    v, host, ix, ids = vm
    cases = [(TODAY, sod, {field: value}) for value in range(len(Q9[field])) for sod in (15 * 3600 + 150.0, 21 * 3600 + 10.0)]
    worst, bad = v.compare(host, ix, ids, cases)
    assert not bad, bad[:10]
    # and the field does something: its last value differs from the default somewhere in the scene
    a, b = tl.scene(TODAY, cases[0][1]), tl.scene(TODAY, cases[0][1], {field: len(Q9[field]) - 1})
    assert (a.poses, a.visible) != (b.poses, b.visible)


def test_a_settings_object_that_does_not_answer_leaves_the_last_values(vm):
    v, host, ix, ids = vm
    last = {"drift": 1, "numerals": 2, "gauge": 1, "life": 1}
    host.frame_at(TODAY, 54150.0, last)
    _r, dsp, rsp, writes = host.frame_at(TODAY, 54150.5, answer=False)
    assert (dsp, rsp) == (0, 0)
    assert host.read(v.ANSWERED_CELL) == 0
    assert [host.read(c) for c in tl.OPTION_CELLS.values()] == [1, 2, 1, 1]
    want = tl.scene(TODAY, 54150.5, last).poses["cs_wide"]
    assert abs(writes[(ix["cs_wide"], ids["X_POS"])] - want.x) < 1e-3
