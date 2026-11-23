import importlib.util
import math
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'wflevels/bamboo_tipper_pond/model.py'
spec=importlib.util.spec_from_file_location('bamboo_model',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_clock_orbits_and_rollover():
    assert m.phases(0,0,0)==m.phases(12,0,0)==(0,0)
    h,k=m.phases(10,8,22)
    assert math.isclose(h,(10+8/60+22/3600)/12)
    assert math.isclose(k,(8+22/60)/60)
    a=m.phases(11,59,59.999);b=m.phases(12,0,0)
    assert all(math.dist(m.orbit(3,x),m.orbit(3,y))<.001 for x,y in zip(a,b))


def test_tipper_cycle():
    assert m.tip_angle(0)==m.tip_angle(3)==0
    assert m.tip_angle(1)==m.tip_angle(2)==.10
    assert m.fill(0)==m.fill(3)==0
    assert m.fill(59) > .98


def test_camera_path_closes_and_approaches_tipper():
    assert math.dist(m.camera_pose(0),m.camera_pose(60))<1e-9
    assert m.camera_pose(30)[0]>6
    eps=.001
    for t in range(0,60,10):
        a,b,c=(m.camera_pose(t-eps),m.camera_pose(t),m.camera_pose(t+eps))
        assert all(abs((y-x)-(z-y))<1e-5 for x,y,z in zip(a,b,c))
