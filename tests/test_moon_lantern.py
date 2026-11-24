import importlib.util
import math
from pathlib import Path

spec = importlib.util.spec_from_file_location('moon_lantern', Path(__file__).resolve().parents[1]/'wflevels/moon_lantern/model.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_clock_and_shadow_opposition():
    hour, minute = m.clock_phases(10, 8, 22)
    assert math.isclose(hour, (10 + 8/60 + 22/3600)/12)
    assert math.isclose(minute, (8 + 22/60)/60)
    a = m.dial_point(1, hour)
    b = m.dial_point(1, (hour+.5)%1)
    assert math.dist((a[0]+b[0],a[1]+b[1]),(0,0)) < 1e-12


def test_nasa_2000_phase_reference_and_timezone():
    # NASA's 2000 Jan 6 new moon and Jan 21 full moon, UTC; this compact
    # approximation is tested within 0.04 revolution, not as an ephemeris.
    circular_error = lambda a,b: abs((a-b+.5)%1-.5)
    assert circular_error(m.moon_phase(5,18,14,0,0),0) < .04
    assert circular_error(m.moon_phase(20,4,40,0,0),.5) < .04
    assert circular_error(m.moon_phase(6,1,14,0,420),m.moon_phase(5,18,14,0,0)) < 1e-10
