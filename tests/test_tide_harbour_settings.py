"""Tide Harbour's settings (plan D13 and Q9): every field set, the director stepped, the pose checked.

The fields are Q9's: the common Clock sheet's Camera drift (Slow, the default, or Off) and Tide Harbour's own
Dial numerals (Thai, Roman or none), Gauge board (on or off) and Boats and birds (on or off). The director reads
them from global cells 690-693, where 0 is the default, and never writes them. The TideHarbourSettings object
that will write them (an .oas type including settings.inc, placed in the level, read with property@) needs a
new engine object type and is waiting on Will (the plan's Phase 2 record); until then nothing writes the cells,
so the level runs with the defaults. This test drives the cells directly, in the real zForth VM, and
scripts/check-tide-harbour.py --options does the same in the engine over the debug bridge.
"""
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))
sys.path.insert(0, str(ROOT / "tests"))

import forth  # noqa: E402
import timeline as tl  # noqa: E402

Q9 = {"drift": ("Slow", "Off"), "numerals": ("Thai", "Roman", "None"), "gauge": ("On", "Off"), "life": ("On", "Off")}


def test_the_fields_are_q9s_with_the_default_first():
    assert tl.OPTIONS == Q9
    assert tl.DEFAULT_OPTIONS == {k: 0 for k in Q9}


def test_the_cells_are_global_user_mailboxes_the_director_only_reads():
    cells = set(tl.OPTION_CELLS.values())
    assert all(2 <= c <= 1900 for c in cells)                     # docs/level-building.md: global user cells
    scratch = set(range(600, 600 + len(forth.CELLS))) | {forth.PREVQ} | set(tl.VIS.values())
    assert not cells & scratch
    text = forth.director_script(forth.default_indices())
    for name in tl.OPTION_CELLS:
        assert f"th-opt-{name} th@" in text
        assert f"th-opt-{name} th!" not in text


@pytest.fixture(scope="module")
def vm():
    if shutil.which("cc") is None or shutil.which("c++") is None:
        pytest.skip("needs a C and C++ compiler")
    import verify_tide_harbour_forth as v
    with tempfile.TemporaryDirectory(prefix="th-settings-") as t:
        tmp = Path(t)
        ids, ix = v.build(tmp)
        host = v.Host(tmp, ids)
        yield v, host, ix, ids
        host.close()


@pytest.mark.parametrize("field", list(Q9))
def test_every_value_of_every_field_poses_the_scene_as_the_model_says(vm, field):
    v, host, ix, ids = vm
    day = tl.wall_day(__import__("datetime").date(2026, 11, 21))
    cases = [(day, sod, {field: value}) for value in range(len(Q9[field])) for sod in (15 * 3600 + 150.0, 21 * 3600 + 10.0)]
    worst, bad = v.compare(host, ix, ids, cases)
    assert not bad, bad[:10]
    # and the field does something: its last value differs from the default somewhere in the scene
    a, b = tl.scene(day, cases[0][1]), tl.scene(day, cases[0][1], {field: len(Q9[field]) - 1})
    assert (a.poses, a.visible) != (b.poses, b.visible)
