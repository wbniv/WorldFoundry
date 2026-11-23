import importlib.util
import math
from pathlib import Path

spec=importlib.util.spec_from_file_location('metronomes',Path(__file__).resolve().parents[1]/'wflevels/metronome_forest/model.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_hour_and_minute_counting():
    assert m.hour_columns(10)==10
    assert m.hour_columns(0)==m.hour_columns(12)==12
    for minute in (0,1,8,30,59):
        assert sum(m.is_green(c,r,minute) for c in range(12) for r in range(5))==minute
    assert [sum(m.is_green(c,r,8) for r in range(5)) for c in range(12)]==[5,3]+[0]*10


def test_wave_realigns_with_position_and_velocity_continuity():
    eps=1e-5
    for i in range(60):
        assert m.arm_angle(i,0)==0
        assert abs(m.arm_angle(i,60-eps))<.001
        assert math.isclose(m.arm_angle(i,eps)/eps,-m.arm_angle(i,60-eps)/eps,rel_tol=1e-5)


def test_camera_path_loops_smoothly():
    assert math.dist(m.camera_pose(0),m.camera_pose(60))<1e-9
    for t in range(0,60,10):
        a,b,c=(m.camera_pose(t-.001),m.camera_pose(t),m.camera_pose(t+.001))
        assert all(abs((y-x)-(z-y))<.00001 for x,y,z in zip(a,b,c))
