"""The dial represents real wall-clock changes, not a fixed mockup."""
import importlib.util
import datetime
import json
from pathlib import Path
import zoneinfo

path = Path(__file__).resolve().parents[1] / 'wflevels/globe_sun_ring/model.py'
spec = importlib.util.spec_from_file_location('globe_clock_model', path)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def test_home_meridian_reads_civil_time_across_midnight():
    for hour, minute, second in [(0, 0, 0), (10, 8, 22), (12, 0, 0), (23, 59, 59)]:
        turn = model.globe_turn(hour, minute, second)
        assert abs(model.ring_hour(model.HOME_LONGITUDE, turn) - model.civil_hours(hour, minute, second)) < 1e-9


def test_globe_rotates_continuously_once_per_day():
    a = model.globe_turn(10, 8, 0)
    b = model.globe_turn(10, 8, 1)
    assert abs((b - a) % 1.0 - 1 / 86400) < 1e-9
    assert model.globe_turn(0, 0) == model.globe_turn(24, 0)


def test_city_lights_follow_the_sunward_hemisphere():
    for hour in (0, 3, 9, 12, 15, 21):
        turn = model.globe_turn(hour, 0)
        assert model.city_lit(model.HOME_LONGITUDE, turn) == (hour < 6 or hour > 18)
        assert model.city_lit(model.HOME_LONGITUDE + 180, turn) != model.city_lit(model.HOME_LONGITUDE, turn)


def test_representatives_cover_iana_offsets_in_all_four_seasons():
    offsets = set()
    for name in zoneinfo.available_timezones():
        zone = zoneinfo.ZoneInfo(name)
        for month in (1, 4, 7, 10):
            instant = datetime.datetime(2026, month, 1, tzinfo=datetime.timezone.utc)
            offsets.add(int(instant.astimezone(zone).utcoffset().total_seconds() // 60))
    assert offsets <= model.HOME_BY_OFFSET.keys()
    assert model.home_for_offset(420)[0] == 'Bangkok'
    assert model.home_for_offset(345)[0] == 'Kathmandu'


def test_each_representative_meridian_matches_local_dial_time():
    for _, latitude, longitude in model.HOME_BY_OFFSET.values():
        assert -90 <= latitude <= 90 and -180 <= longitude <= 180
        for hour, minute in ((0, 0), (10, 8), (12, 0), (23, 59)):
            phase = model.globe_turn(hour, minute, longitude=longitude)
            assert abs(model.ring_hour(longitude, phase) - model.civil_hours(hour, minute)) < 1e-9


def test_globe_settings_are_registered_and_expose_live_controls():
    root = path.parents[2]
    registry = (root / 'wfsource/source/oas/objects.mac').read_text()
    assert registry.count('OBJECTENTRY(GlobeSunRingSettings,0)') == 1
    doc = json.loads((root / 'wflevels/globe_sun_ring/settings-capabilities.json').read_text())
    owner, = doc['objects']
    assert owner['type'] == 'GlobeSunRingSettings'
    fields = {field['key']: field for field in owner['settings']}
    assert fields['City lights']['value'] == 'true'
    assert fields['Camera drift']['value'] == '0'
    assert fields['Show framerate']['value'] == 'false'
