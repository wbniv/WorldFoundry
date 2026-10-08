"""Exercise the actual Forth locomotion core without engine extensions."""
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('anemone_zfhost',ROOT/'docs/reference/swarming-poster/zfhost.py')
zfhost=importlib.util.module_from_spec(spec);spec.loader.exec_module(zfhost)

@pytest.fixture
def controller():
    h=zfhost.Host()
    assert h.load(ROOT/'wflevels/aquarium/anemone_controller.fth')=='ok'
    assert h.eval('an-reset')=='ok'
    h.write(729,1);h.write(730,1);h.write(732,.05)
    yield h;h.close()

def step(h,n=1):
    for _ in range(n):assert h.eval('an-step')=='ok'

def test_direction_moves_then_release_settles(controller):
    h=controller;h.write(726,1);step(h,40)
    assert h.read(722)>.1
    h.write(726,0);step(h,60)
    assert abs(h.read(724))<1e-5
    assert h.read(738)==0


def test_diagonal_is_not_faster(controller):
    h=controller;h.write(726,1);h.write(727,1);step(h,30)
    vx,vy=h.read(724,2)
    assert (vx*vx+vy*vy)**.5<=.090001


def test_crawl_cannot_leave_legal_patch(controller):
    h=controller;h.write(726,1);h.write(727,1);step(h,600)
    assert abs(h.read(722))<=.750001
    assert abs(h.read(723))<=.350001


def test_hold_withdraws_without_retrigger_then_recovers(controller):
    h=controller;h.write(728,1);step(h,60)
    assert h.read(721)>.99 and h.read(738)==2
    h.write(728,0);step(h,250)
    assert h.read(721)<.01 and h.read(738)==0


def test_focus_transfer_swallow_until_all_buttons_released(controller):
    h=controller;h.write(726,1);h.write(728,1);h.write(730,0)
    step(h);assert h.read(731)==1
    assert h.read(726,3)==[0,0,0]
    h.write(726,1);step(h);assert h.read(731)==1
    h.write(726,0);step(h);assert h.read(731)==0
    h.write(726,1);step(h,20);assert h.read(722)>.03


def test_inactive_focus_does_not_use_fish_input(controller):
    h=controller;h.write(729,0);h.write(726,1);h.write(728,1);step(h,20)
    assert h.read(722)==0 and h.read(721)==0


def test_long_tick_is_bounded_and_phase_wraps(controller):
    h=controller;h.write(732,12);h.write(726,1);step(h)
    assert 0<=h.read(720)<1
    assert abs(h.read(722))<.03
