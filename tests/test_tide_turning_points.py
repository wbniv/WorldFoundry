"""The committed turning-point counts are what count_turns.py computes from the shipped constants.

The poster and the research quote wflevels/tide_harbour/turning_points.json, and a tide board that shows "the
next high water" relies on its threshold. A refit that forgets to rerun count_turns.py would leave them stale.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / 'wflevels' / 'tide_harbour'


def load():
    spec = importlib.util.spec_from_file_location('count_turns', FIT / 'tide_fit' / 'count_turns.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_counts_match_the_shipped_constants():
    ct = load()
    committed = json.loads((FIT / 'turning_points.json').read_text())
    const = json.loads((FIT / 'tide_constants.json').read_text())
    assert committed['min_swing_m'] == ct.MIN_SWING_M
    assert committed['years']['2026'] == ct.count_year(const, 2026), 'run tide_fit/count_turns.py --json turning_points.json'


def test_the_threshold_keeps_about_as_many_turns_as_the_table_lists():
    years = json.loads((FIT / 'turning_points.json').read_text())['years']
    for year, row in years.items():
        assert row['model_turns'] > row['table_events'], year          # the wiggles are real
        assert abs(row['kept_minus_table']) <= 5, (year, row)           # and the threshold removes them, not real events
        assert row['kept_minus_table_by_min_swing_cm']['10'] < -50, year   # a 10 cm threshold drops listed events


def test_drop_wiggles_removes_the_smallest_pair_first():
    ct = load()
    assert ct.drop_wiggles([1.0, 2.0, 1.98, 2.01, 1.0], 0.04) == [1.0, 2.01, 1.0]
    assert ct.drop_wiggles([1.0, 2.0, 1.0], 0.04) == [1.0, 2.0, 1.0]
