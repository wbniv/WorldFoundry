"""The generated Cuckoo Village director, run in the real zForth VM (tests/verify_cuckoo_village_forth.py), and the
season reference it is checked against (timeline.christmas_season). Candles: lit in season always, and out of season
only when the Candles all year switch is On."""
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
    assert " 0 failures" in r.stdout and "flames: 0 failures" in r.stdout and "flowers: 0 failures" in r.stdout, r.stdout[-500:]


def test_the_candle_switch_only_adds_the_rest_of_the_year():
    """Will, 2026-11-22: always on from 1 December to 6 January, and the setting turns them on at other times.
    The reference rule, then the director's cell in the VM (the test above) must agree with it."""
    for d, switch, want in ((day(2026, 12, 25), False, True), (day(2026, 12, 25), True, True),
                            (day(2026, 7, 4), False, False), (day(2026, 7, 4), True, True),
                            (day(2027, 1, 6), False, True), (day(2027, 1, 7), False, False)):
        assert (tl.christmas_season(d) or switch) is want, (tl.date_of(d), switch)
    assert tl.SETTINGS_DEFAULTS["Candles all year"] == 0
    assert tl.SETTINGS_DEFAULTS["Detailed flowers"] == 1                     # the detailed flowers are the default
