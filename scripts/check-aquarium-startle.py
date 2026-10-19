#!/usr/bin/env python3
"""Check actual player displacement and follower startle timers through the engine bridge."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels/aquarium'))
import run_aquarium_checks as aq
import tiger_barb as tb

r = aq.Run()
timers = [tb.RANGES['state'][0] + 14*k + 12 for k in range(1, 30)]
r.g.watch([(r.dir, mb) for mb in timers + [1277, 1284]])

def examine(frames):
    positions = [tuple(s[(r.pl, mb)] for mb in [aq.X_POS, aq.Y_POS, aq.Z_POS]) for _, s in frames]
    startles = [sum(s.get((r.dir, mb), 0) > 0 for mb in timers) for _, s in frames]
    return {'positions': positions, 'startled_followers': startles,
            'measured_speed_BL_s': [s.get((r.dir, 1277)) for _, s in frames],
            'trigger': [s.get((r.dir, 1284)) for _, s in frames]}

try:
    r.g.hold('RIGHT', 100)
    r.g.hold(None, 30)
    blocked = examine(r.g.hold('A', 4))
    assert max(blocked['startled_followers']) == 0, blocked
    assert max(blocked['measured_speed_BL_s']) < .1, blocked
    r.g.hold(None, 20)
    r.g.hold('LEFT', 40)
    r.g.hold(None, 50)
    free = examine(r.g.hold('A', 4))
    assert max(free['trigger']) == 1, free
    assert max(free['measured_speed_BL_s']) > 5, free
    report = {'blocked': blocked, 'free': free, 'result': 'PASS'}
    target = Path(aq.OUT) / 'startle-regression.json'
    target.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
finally:
    r.g.close()
