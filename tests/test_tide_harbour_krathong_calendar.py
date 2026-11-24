"""Festival-night dates are local evenings, including after midnight."""
from datetime import date
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'wflevels/tide_harbour/krathong_calendar.py'
spec = importlib.util.spec_from_file_location('krathong_calendar', path)
calendar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calendar)


def day(y, m, d):
    return (date(y, m, d) - calendar.DAY_ZERO).days


def test_2026_evening_and_following_morning():
    d = day(2026, 11, 24)
    assert calendar.festival_night(d, 20 * 3600, -15)
    assert calendar.festival_night(d + 1, 2 * 3600, -30)
    assert not calendar.festival_night(d, 12 * 3600, 50)
    assert not calendar.festival_night(d, 2 * 3600, -30)
    assert not calendar.festival_night(d + 1, 20 * 3600, -15)


def test_forecasts_and_coverage_boundaries():
    for y, m, d in ((2027, 11, 13), (2028, 11, 1), (2029, 11, 20)):
        assert calendar.festival_night(day(y, m, d), 20 * 3600, -5)
        assert not calendar.festival_night(day(y, m, d) + 1, 20 * 3600, -5)
    assert not calendar.festival_night(day(2030, 11, 10), 20 * 3600, -5)
