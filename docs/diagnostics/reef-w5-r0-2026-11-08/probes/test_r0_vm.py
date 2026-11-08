"""R0 P2: the one-shot layout writes reach the actors (species VM). The engine runs the Director body
`r0-once reef-tick` every tick; the VM fixture's entry is `reef-tick`, so the entry is widened here."""
import subprocess
import sys
sys.path.insert(0, '/src/tests')
import test_species_movement as t
from test_species_movement import vm  # noqa: F401  (fixture)

_run = subprocess.run
def _widened(args, *a, **k):
    if isinstance(args, list) and args and args[-1] == 'reef-tick':
        args = [*args[:-1], 'r0-once reef-tick']
    return _run(args, *a, **k)

def test_p2_layout_writes(vm, monkeypatch):
    monkeypatch.setattr(t.subprocess, 'run', _widened)
    for actor, x, z in ((10, .2, 0), (21, .2, 0), (41, -4.0, 0), (48, 3.7, 0), (56, 3.7, -4)):
        rows = vm('thai_reef', f'reset 4 0 2\nset 650 {actor}\nstep 3 0 .0166667\n')
        assert abs(rows[-1]['part-x'] - x) < 1e-4 and abs(rows[-1]['part-z'] - z) < 1e-4, (actor, rows[-1])
        assert rows[-1][1112] == 1 if 1112 in rows[-1] else True
