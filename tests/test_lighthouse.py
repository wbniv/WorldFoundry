import importlib.util
import math
from pathlib import Path

spec = importlib.util.spec_from_file_location('lighthouse', Path(__file__).resolve().parents[1]/'wflevels/lighthouse/model.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_time_reading():
    boat, beam = m.phases(8,22)
    assert math.isclose(boat, (8+22/60)/60)
    assert math.isclose(beam, 22/60)
    assert [m.lit_windows(h) for h in (0,1,10,11,12,13,23)] == [0,1,10,11,0,1,11]


def test_orbits_and_rollovers():
    assert m.point(1,0) == (0,1)
    assert math.isclose(m.point(1,.25)[0],1)
    assert math.dist(m.point(1,m.phases(59,59.999)[0]), m.point(1,m.phases(0,0)[0])) < .00001
    assert math.dist(m.point(1,m.phases(59,59.999)[1]), m.point(1,m.phases(0,0)[1])) < .0002
    # At minute m, the beam catches the boat at second 60*m/59.
    for minute in (0,8,30,58):
        second = 60*minute/59
        assert math.isclose(*m.phases(minute,second), abs_tol=1e-10)


def test_camera_smooth_loop():
    for t in range(0,60,10):
        a,b,c = (m.camera_pose(t-.001),m.camera_pose(t),m.camera_pose(t+.001))
        assert all(abs((y-x)-(z-y)) < .00001 for x,y,z in zip(a,b,c))
