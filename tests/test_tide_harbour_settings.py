"""TideHarbourSettings (plan D13 and Q9): the type, its registration, the object in the level, and every field
set, the director stepped and the pose checked.

The type is wfsource/source/oas/tideharboursettings.oas: settings.inc, the clocks' shared Clock sheet
(clocksettings.inc: Camera drift, Slow or Off) and Tide Harbour's own sheet (Dial numerals: Roman, Thai or none;
Gauge board: on or off; Boats and birds: on or off; River panel: on or off), every field live and its first choice the default, and
then one read-only About the map row (the OpenStreetMap credit). One object
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

Q9 = {"drift": ("Slow", "Off"), "numerals": ("Roman", "Thai", "None"), "gauge": ("On", "Off"), "life": ("On", "Off"),
      "panel": ("On", "Off"), "krathong_mode": ("Festival nights", "Every night"), "krathong_count": tuple(str(i) for i in range(tl.KRATHONG_MAX + 1))}
MAP = json.loads((ROOT / "wflevels/tide_harbour/actor-map.json").read_text())
TODAY = tl.wall_day(dt.date(2026, 11, 21))


def test_the_fields_are_q9s_with_the_default_first():
    assert tl.OPTIONS == Q9
    assert tl.DEFAULT_OPTIONS == {**{k: 0 for k in Q9}, "krathong_count": 30}
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


def test_the_phone_asset_lists_the_fields_of_the_placed_object():
    asset = json.loads((ROOT / "android/screensaver/src/clocks/assets/tide-harbour-settings.json").read_text())
    (owner,) = asset["objects"]
    assert owner["owner"] == MAP["indices"][tl.SETTINGS_ACTOR] and owner["type"] == "TideHarbourSettings"
    GLOBAL_FIELDS = {"Show framerate"}      # oas/global_settings.inc: every settings type ends with these, a checkbox with no options
    assert GLOBAL_FIELDS <= {s["key"] for s in owner["settings"]}
    count = next(s for s in owner['settings'] if s['key'] == 'Krathong count')
    assert (count['type'], count['minimum'], count['maximum'], count['value']) == ('integer', '0', str(tl.KRATHONG_MAX), '30')
    got = {s["key"]: ([o["label"] for o in s["options"]], s["value"], s["readonly"]) for s in owner["settings"] if s["key"] not in GLOBAL_FIELDS | {'Krathong count'}}
    want = {label: (list(Q9[k]), str(tl.DEFAULT_OPTIONS[k]), False) for k, label in tl.FIELD_LABELS.items() if k != 'krathong_count'}
    # the read-only About row: the river map's OpenStreetMap attribution (it left the panel in the same change)
    want["About the map"] = (["(c) OpenStreetMap contributors", "ODbL: openstreetmap.org/copyright"], "0", True)
    assert got == want


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
    values = (0, 30, tl.KRATHONG_MAX) if field == 'krathong_count' else range(len(Q9[field]))
    cases = [(TODAY, sod, {field: value}) for value in values for sod in (15 * 3600 + 150.0, 21 * 3600 + 10.0)]
    worst, bad = v.compare(host, ix, ids, cases)
    assert not bad, bad[:10]
    # and the field does something: its last value differs from the default somewhere in the scene
    if not field.startswith('krathong_'):  # launches depend on elapsed frames, not a static clock pose
        a, b = tl.scene(TODAY, cases[0][1]), tl.scene(TODAY, cases[0][1], {field: len(Q9[field]) - 1})
        assert (a.poses, a.visible) != (b.poses, b.visible)


def test_festival_launches_gradually_in_the_real_vm(vm):
    v, host, ix, ids = vm
    day = tl.wall_day(dt.date(2026, 11, 24))
    host.proc.stdin.write(f"M {ids['DELTA_TIME']} 0.1\n")
    host.frame_at(day, 20 * 3600, {'krathong_count': 0})
    options = {'krathong_count': 2}
    for _ in range(10):
        result, ds, rs, _ = host.frame_at(day, 20 * 3600, options, reset_look=False)
        assert (result, ds, rs) == (0, 0, 0)
    assert sum(host.read(tl.VIS[f'krathong_{i}']) for i in range(8)) == 0
    for _ in range(3): host.frame_at(day, 20 * 3600, options, reset_look=False)
    assert sum(host.read(tl.VIS[f'krathong_{i}']) for i in range(8)) == 1
    host.frame_at(day, 20 * 3600, {'krathong_count': 0}, reset_look=False)
    assert sum(host.read(tl.VIS[f'krathong_{i}']) for i in range(8)) == 0
    # Every-night mode must work on an ordinary night; neither mode runs by day.
    ordinary = day + 3
    for _ in range(122): host.frame_at(ordinary, 20 * 3600, {'krathong_count': 1, 'krathong_mode': 1}, reset_look=False)
    assert sum(host.read(tl.VIS[f'krathong_{i}']) for i in range(8)) == 1
    host.frame_at(ordinary, 12 * 3600, {'krathong_count': 1, 'krathong_mode': 1}, reset_look=False)
    assert sum(host.read(tl.VIS[f'krathong_{i}']) for i in range(8)) == 0
    host.proc.stdin.write(f"M {ids['DELTA_TIME']} 0\n")


def test_the_maximum_can_accumulate_without_an_early_departure(vm):
    _, host, _, ids = vm
    day = tl.wall_day(dt.date(2026, 11, 24))
    host.proc.stdin.write(f"M {ids['DELTA_TIME']} 0.1\n")
    host.frame_at(day, 20 * 3600, {'krathong_count': 0})
    for _ in range(1450):
        result, ds, rs, _ = host.frame_at(day, 20 * 3600, {'krathong_count': tl.KRATHONG_MAX}, reset_look=False)
        assert (result, ds, rs) == (0, 0, 0)
    assert sum(host.read(tl.VIS[f'krathong_{i}']) for i in range(tl.KRATHONG_MAX)) == tl.KRATHONG_MAX
    host.frame_at(day, 20 * 3600, {'krathong_count': 0}, reset_look=False)
    host.proc.stdin.write(f"M {ids['DELTA_TIME']} 0\n")


def test_launched_paths_clear_the_tower_quay(vm):
    _, host, ix, ids = vm
    day = tl.wall_day(dt.date(2026, 11, 24))
    host.proc.stdin.write(f"M {ids['DELTA_TIME']} 0.1\n")
    host.frame_at(day, 20 * 3600, {'krathong_count': 0})
    for _ in range(130):
        _, _, _, writes = host.frame_at(day, 20 * 3600, {'krathong_count': 10}, reset_look=False)
    # Quay extends from y = dial_y - 1.92 to tower_y + 5, and each float's
    # radius is at most 0.219. Check actual director output on both sides.
    quay_front, quay_back = tl.DIAL[1] - 1.92, tl.TOWER[1] + 5
    for i in range(10):
        y = writes[(ix[f'krathong_{i}'], ids['Y_POS'])]
        assert y + .22 < quay_front or y - .22 > quay_back
    host.frame_at(day, 20 * 3600, {'krathong_count': 0})
    host.proc.stdin.write(f"M {ids['DELTA_TIME']} 0\n")


def test_a_settings_object_that_does_not_answer_leaves_the_last_values(vm):
    v, host, ix, ids = vm
    last = {"drift": 1, "numerals": 2, "gauge": 1, "life": 1, "panel": 1}
    host.frame_at(TODAY, 54150.0, last)
    _r, dsp, rsp, writes = host.frame_at(TODAY, 54150.5, answer=False)
    assert (dsp, rsp) == (0, 0)
    assert host.read(v.ANSWERED_CELL) == 0
    assert [host.read(c) for c in tl.OPTION_CELLS.values()] == [1, 2, 1, 1, 1, 0, 30]
    want = tl.scene(TODAY, 54150.5, last).poses["cs_wide"]
    assert abs(writes[(ix["cs_wide"], ids["X_POS"])] - want.x) < 1e-3
