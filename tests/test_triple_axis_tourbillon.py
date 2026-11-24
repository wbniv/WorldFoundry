import importlib.util
import math
from pathlib import Path

spec=importlib.util.spec_from_file_location('tourbillon',Path(__file__).resolve().parents[1]/'wflevels/triple_axis_tourbillon/model.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_dial_at_noon_and_ten_eight():
    assert m.phases(12,0,0)==dict(hour=0,minute=0,outer=0,middle=0,inner=0)
    p=m.phases(10,8,22)
    assert math.isclose(p['hour'],(10+8/60+22/3600)/12)
    assert math.isclose(p['minute'],(8+22/60)/60)


def test_cages_align_every_six_minutes_and_wrap_smoothly():
    for minute in (0,6,12,30,54):
        p=m.phases(0,minute,0)
        assert all(p[k]==0 for k in ('outer','middle','inner'))
    a=m.phases(0,5,59.999);b=m.phases(0,6,0)
    for key in ('outer','middle','inner'):
        assert abs((a[key]-b[key]+.5)%1-.5)<.0001


def test_camera_spline_is_closed_and_smooth():
    assert math.dist(m.camera_pose(0),m.camera_pose(60))<1e-9
    for t in range(0,60,10):
        a,b,c=(m.camera_pose(t-.001),m.camera_pose(t),m.camera_pose(t+.001))
        assert all(abs((y-x)-(z-y))<.00001 for x,y,z in zip(a,b,c))
