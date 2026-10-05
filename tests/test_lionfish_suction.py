"""Exercise actual Forth flow integration; no engine code is modified."""
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
# Reuse the existing built host/bootstrap from the primary checkout.
PRIMARY=ROOT.parents[1] if ROOT.parent.name=='.worktrees' else ROOT
spec=importlib.util.spec_from_file_location('existing_zfhost',PRIMARY/'docs/reference/swarming-poster/zfhost.py')
zfhost=importlib.util.module_from_spec(spec);spec.loader.exec_module(zfhost)

@pytest.fixture
def flow():
    h=zfhost.Host()
    assert h.load(ROOT/'wflevels/aquarium_tanks/lionfish_suction.fth')=='ok'
    for i,v in {6:.005,7:1,8:.13,9:1,18:.2}.items():h.write(1300+i,v)
    yield h;h.close()

def step(h,n=1):
    for _ in range(n):assert h.eval('lf-step')=='ok'

def test_acceleration_retains_initial_velocity_and_curves_off_axis(flow):
    h=flow;h.write(1300,.12);h.write(1301,.06);h.write(1304,.3)
    step(h);x,y=h.read(1300,2);vx,vy=h.read(1303,2)
    assert 0<x<.12 and y>.06 and vx<0 and vy>0 # initial sideways momentum survives
    step(h,20);x2,y2=h.read(1300,2)
    assert x2<x and y2<y # flow subsequently bends the path toward the aperture

@pytest.mark.parametrize('x,clear',[(-.12,1),(.12,0)])
def test_no_flow_behind_head_or_through_obstruction(flow,x,clear):
    h=flow;h.write(1300,x);h.write(1309,clear);step(h,10)
    assert h.read(1300)==pytest.approx(x,abs=1e-6)
    assert h.read(1303,3)==[0,0,0]

def test_far_prey_is_not_reeled_across_tank(flow):
    h=flow;h.write(1300,4);step(h,20)
    assert abs(h.read(1300)-4)<.0001

def test_pulse_decay_and_swimming_drive(flow):
    h=flow;h.write(1300,.12);h.write(1307,0);h.write(1315,4);step(h,10)
    assert h.read(1300)>.12 and h.read(1303)>0
