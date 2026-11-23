import importlib.util
import json
import math
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'wflevels/anamorphic_shards/model.py'
spec = importlib.util.spec_from_file_location('shards_model', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_wall_time_and_all_digit_masks():
    assert m.digits(0, 8) == (0, 0, 0, 8)
    assert m.digits(23, 59) == (2, 3, 5, 9)
    assert len(set(m.MASKS)) == 10 and all(0 < v < 128 for v in m.MASKS)


def test_fragments_align_but_separate_from_another_view():
    for d in range(4):
        for s in range(7):
            pieces = m.fragments(d, s)
            assert len({piece[0][1] for piece in pieces}) == 3
            aligned = [m.project(v) for piece in pieces for v in piece]
            shifted = [m.project(v, 2.0) for piece in pieces for v in piece]
            delta = [a[0] - b[0] for a, b in zip(aligned, shifted)]
            assert max(delta) - min(delta) > .5


def test_minute_loop_has_stationary_hold_and_smooth_join():
    assert all(m.camera_x(t) == 0 for t in (0, 1, 2, 3.99))
    assert math.isclose(m.camera_x(60), 0, abs_tol=1e-12)
    assert m.camera_x(32) > 2.6
    assert abs(m.camera_x(4.001) - m.camera_x(4)) < 1e-7
    assert abs(m.camera_x(59.999) - m.camera_x(60)) < 1e-7


def test_exported_settings_offer_drift_and_global_framerate():
    root = path.parents[2]
    doc = json.loads((root / 'android/screensaver/src/clocks/assets/anamorphic-shards-settings.json').read_text())
    owner, = doc['objects']
    assert owner['type'] == 'AnamorphicShardsSettings'
    fields = {field['key']: field for field in owner['settings']}
    assert fields['Camera drift']['value'] == '0'
    assert [(o['id'], o['label']) for o in fields['Camera drift']['options']] == [('0', 'Slow'), ('1', 'Off')]
    assert fields['Show framerate']['value'] == 'false'
