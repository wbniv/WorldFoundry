from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


spec = spec_from_file_location('hour_tree_model', Path(__file__).resolve().parents[1] / 'wflevels/hour_tree/model.py')
model = module_from_spec(spec)
spec.loader.exec_module(model)


def test_hour_tree_reading_and_boundaries():
    assert model.reading(10, 8) == {'completed_branches': 10, 'growing_branch': 11, 'leaves': 1, 'buds': 3}
    assert model.reading(11, 59) == {'completed_branches': 11, 'growing_branch': 12, 'leaves': 11, 'buds': 4}
    assert model.reading(12, 0) == model.reading(0, 0) == {'completed_branches': 0, 'growing_branch': 1, 'leaves': 0, 'buds': 0}
