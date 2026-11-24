"""Local-time envelope is continuous, bounded, and independent of history."""
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'wflevels/cuckoo_village'))
import daynight as cycle


def test_key_times_and_both_transitions():
    assert cycle.appearance(0) == (0.0, 0.0)
    assert cycle.appearance(12 * 3600) == (1.0, 0.0)
    assert cycle.appearance(6 * 3600) == (0.5, 1.0)
    assert cycle.appearance(18 * 3600) == (0.5, 1.0)
    for boundary in (cycle.DAWN_START, cycle.DAWN_END, cycle.DUSK_START, cycle.DUSK_END):
        before, after = cycle.appearance(boundary - 0.001), cycle.appearance(boundary + 0.001)
        assert all(abs(a - b) < 1e-6 for a, b in zip(before, after))


def test_time_jumps_midnight_and_day_wrap():
    for t in range(0, cycle.DAY_SECONDS, 137):
        daylight, warmth = cycle.appearance(t)
        assert 0 <= daylight <= 1 and 0 <= warmth <= 1
        assert cycle.appearance(t + cycle.DAY_SECONDS) == (daylight, warmth)
        assert cycle.appearance(t - cycle.DAY_SECONDS) == (daylight, warmth)
    assert math.isclose(cycle.appearance(-1)[0], cycle.appearance(cycle.DAY_SECONDS - 1)[0])


def test_director_tracks_time_jumps_in_the_real_vm():
    import verify_cuckoo_village_forth as vm
    with tempfile.TemporaryDirectory() as temp:
        ids, indices = vm.build(Path(temp))
        host = vm.Host(Path(temp), ids, indices)
        try:
            for t in (43200, 19800, 21600, 23400, 63000, 64800, 66600, 0, 21600):
                writes = host.frame_at(vm.day_of(2026, 12, 25), t)
                daylight, warmth = cycle.appearance(t)
                assert abs(writes[(indices['AlpineSkyDay'], 3051)] - daylight) < 1e-5
                assert abs(writes[(indices['AlpineSkyWarm'], 3051)] - .45 * warmth) < 1e-5
                for name, base, day, warm in (
                    ('SunLight', (.20, .22, .30), (.80, .78, .72), (.12, .035, 0)),
                    ('AmbientLight', (.23, .25, .32), (.42, .42, .42), (.035, .008, 0)),
                ):
                    for i in range(3):
                        want = base[i] + (day[i] - base[i]) * daylight + warm[i] * warmth
                        assert abs(writes[(indices[name], 3048 + i)] - want) < 1e-5
        finally:
            host.close()
