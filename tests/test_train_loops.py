import importlib.util
import json
import math
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'wflevels/train_loops/model.py'
spec = importlib.util.spec_from_file_location('train_loops_model', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_all_leads_align_at_noon_and_midnight():
    for hour in (0, 12):
        assert m.phases(hour, 0, 0) == {'hour': 0, 'minute': 0, 'express': 0}
        assert all(m.pose(radius, 0)[:2] == (0, radius) for radius in m.RADII.values())


def test_phases_at_ten_eight_twenty_two_and_quarters():
    p = m.phases(10, 8, 22)
    assert math.isclose(p['hour'], (10+8/60+22/3600)/12)
    assert math.isclose(p['minute'], (8+22/60)/60)
    assert math.isclose(p['express'], 22/60)
    assert m.phases(3, 15, 30)['express'] == .5


def test_rollover_and_tangent_motion_are_continuous():
    a, b = m.phases(23, 59, 59.999), m.phases(0, 0, 0)
    for key, radius in m.RADII.items():
        p, q = m.pose(radius, a[key]), m.pose(radius, b[key])
        assert math.dist(p[:2], q[:2]) < .001
    x, y, turn = m.pose(4, .25)
    assert math.isclose(x, 4) and abs(y) < 1e-10 and math.isclose(turn, .5)


def test_carriages_follow_at_fixed_spacing():
    lead = .02
    behind = m.trailing_phase(lead, .25)
    assert math.isclose((lead-behind) % 1, .25/math.tau)
    assert behind > lead  # wrapped over twelve, without jumping position


def test_settings_and_train_roster_are_exported():
    root=path.parents[2]
    settings=json.loads((root/'wflevels/train_loops/settings-capabilities.json').read_text())
    owner,=settings['objects']
    assert owner['type']=='TrainLoopsSettings'
    fields={entry['key']:entry for entry in owner['settings']}
    assert fields['Camera drift']['value']=='0'
    assert fields['Show framerate']['value']=='false'
    registry=json.loads((root/'wflevels/train_loops/actor-map.json').read_text())
    loops=[v['loop'] for v in registry['vehicles']]
    assert loops.count('hour')==2
    assert loops.count('minute')==4
    assert loops.count('express')==1


def test_camera_spline_is_closed_smooth_and_visits_the_layout():
    assert math.dist(m.camera_pose(0), m.camera_pose(60)) < 1e-9
    eps = .001
    for boundary in range(0, 60, 10):
        left, mid, right = (m.camera_pose(boundary-eps), m.camera_pose(boundary),
                            m.camera_pose(boundary+eps))
        assert math.dist(left, right) < .01
        for a,b,c in zip(left,mid,right):
            assert abs((b-a) - (c-b)) < 1e-5
    poses = [m.camera_pose(t) for t in range(60)]
    assert min(p[2] for p in poses) < 5
    assert max(abs(p[0]) for p in poses) > 8
    assert max(p[1] for p in poses) > 2
