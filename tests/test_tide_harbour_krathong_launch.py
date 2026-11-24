"""Exercise lifecycle semantics independently of rendering."""
import importlib.util
from pathlib import Path
import sys

path = Path(__file__).resolve().parents[1] / 'wflevels/tide_harbour/krathong_launch.py'
spec = importlib.util.spec_from_file_location('krathong_launch', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_gradual_launch_and_count_changes():
    state = module.Launches(4, interval=10, journey=40)
    assert state.step(0, True, 3) == ()
    assert state.step(9, True, 3) == ()
    assert state.step(1, True, 3) == (0,)
    assert len(state.step(20, True, 3)) == 3
    assert len(state.step(1, True, 1)) == 3  # do not remove floats abruptly
    assert len(state.step(30, True, 1)) == 1  # excess floats have departed naturally
    assert len(state.step(10, True, 1)) == 1
    assert state.step(0, True, 0) == ()
    assert state.step(0, True, 3) == ()


def test_disable_clears_and_large_step_observes_departures():
    state = module.Launches(2, interval=10, journey=30)
    assert len(state.step(100, True, 2)) <= 2
    assert state.step(0, False, 2) == ()
    assert state.step(9, True, 2) == ()
