import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('lava', Path(__file__).resolve().parents[1] / 'wflevels/lava_lamp_digits/model.py')
lava = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lava)


def test_time_reading_and_rollovers():
    assert lava.reading(9, 59) == (0, 9, 5, 9)
    assert lava.reading(10, 0) == (1, 0, 0, 0)
    assert lava.reading(23, 59) == (2, 3, 5, 9)
    assert lava.reading(0, 0) == (0, 0, 0, 0)
    assert all(lava.DIGITS[n] for n in range(10))


def test_transition_and_hold():
    assert lava.phase(0) == ('forming', 0.)
    assert lava.phase(6) == ('holding', 1.)
    assert lava.phase(53.99) == ('holding', 1.)
    assert lava.phase(54) == ('melting', 1.)
    assert lava.phase(59.999)[1] < .00001
    assert lava.phase(3)[1] == .5
    assert lava.phase(57)[1] == .5
