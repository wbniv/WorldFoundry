"""P4: the one-shot write moves the fillers and clumps (species VM, entry widened to r0-p4 reef-tick)."""
import json, subprocess, sys
sys.path.insert(0, '/src/tests')
import test_species_movement as t
from test_species_movement import vm  # noqa: F401
_run = subprocess.run
def _widened(args, *a, **k):
    if isinstance(args, list) and args and args[-1] == 'reef-tick':
        args = [*args[:-1], 'r0-p4 reef-tick']
    return _run(args, *a, **k)
def test_p4_moves(vm, monkeypatch):
    monkeypatch.setattr(t.subprocess, 'run', _widened)
    amap = json.load(open('/src/build-docker/r0/P4/aquarium_thai_reef/actor-map.json'))
    fillers = [m for m in amap['kit']['modules'] if m['role'] == 'filler' and m['rock'] in amap['kit_budget']['worst_visible']['pieces']]
    for (x, y), m in zip(((-1.15, 1.95), (2.35, 1.95)), fillers):
        for actor in m['piece_actors'] + [m['collider_actor']]:
            row = vm('thai_reef', f'reset 4 0 2\nset 650 {actor}\nstep 2 0 .0166667\n')[-1]
            assert abs(row['part-x'] - x) < 1e-3 and abs(row['part-y'] - y) < 1e-3, (actor, row['part-x'], row['part-y'])
    c = amap['kit']['clumps'][-1]['actor_index']
    row = vm('thai_reef', f'reset 4 0 2\nset 650 {c}\nstep 2 0 .0166667\n')[-1]
    assert row['part-z'] > .72
