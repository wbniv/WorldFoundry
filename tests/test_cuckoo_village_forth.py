"""The generated Cuckoo Village director, run in the real zForth VM (tests/verify_cuckoo_village_forth.py), and the
season reference it is checked against (timeline.christmas_season)."""
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
import timeline as tl  # noqa: E402


def day(y, m, d):
    return (dt.date(y, m, d) - tl.DAY0).days


def test_the_season_runs_from_1_december_through_6_january_and_wraps_the_year():
    assert not tl.christmas_season(day(2026, 11, 30))
    assert tl.christmas_season(day(2026, 12, 1)) and tl.christmas_season(day(2026, 12, 31))
    assert tl.christmas_season(day(2027, 1, 1)) and tl.christmas_season(day(2027, 1, 6))
    assert not tl.christmas_season(day(2027, 1, 7)) and not tl.christmas_season(day(2027, 6, 15))


def test_leap_years_do_not_move_the_season():
    for year in (2000, 2024, 2028, 2096):
        assert tl.christmas_season(day(year, 12, 1)) and not tl.christmas_season(day(year, 11, 30))
        assert tl.christmas_season(day(year + 1, 1, 6)) and not tl.christmas_season(day(year + 1, 1, 7))


@pytest.mark.skipif(shutil.which("cc") is None or shutil.which("c++") is None, reason="needs a C and C++ compiler")
def test_the_director_in_the_real_vm_agrees_with_the_season_reference():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "verify_cuckoo_village_forth.py")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert " 0 failures" in r.stdout, r.stdout[-500:]
