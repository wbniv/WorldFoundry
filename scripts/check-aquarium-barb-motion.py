#!/usr/bin/env python3
"""Record real-engine per-frame barb movement, including round-robin boundaries."""
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'wflevels/aquarium'))
import run_aquarium_checks as aq

r=aq.Run()
try:
    names=aq.lev_names()
    actors=[names.index(f'tiger-barb-{k}')+1 for k in range(1,30)]
    fields=[aq.X_POS,aq.Y_POS,aq.Z_POS,aq.ROT_B,aq.ROT_C]
    r.g.watch([(i,mb) for i in actors for mb in fields])
    r.g.hold(None,60)
    frames=r.g.hold(None,160)
    steps=[]; angles=[]
    for (_,a),(_,b) in zip(frames,frames[1:]):
        for i in actors:
            steps.append(math.dist([a[i,mb] for mb in fields[:3]],[b[i,mb] for mb in fields[:3]]))
            angles.append(abs(aq.wrap(b[i,aq.ROT_C]-a[i,aq.ROT_C])))
    # Normal speed 2 BL/s: one 20-Hz tick travels <= .0889 world m.
    # A teleport/correction at a behavior boundary breaks this bound.
    assert max(steps) <= .889*2*aq.DT+.001, max(steps)
    assert max(angles) <= .5*aq.DT+.001, max(angles)
    result={'result':'PASS','fish':29,'simulation_Hz':20,'measured_frames':len(frames),
            'max_step_world_m':max(steps),'p95_step_world_m':sorted(steps)[int(len(steps)*.95)],
            'max_yaw_step_revolutions':max(angles),'normal_step_limit_world_m':.889*2*aq.DT,
            'scope':'stationary-player schooling; includes sparse behavior updates and walls'}
    (Path(aq.OUT)/'barb-motion-regression.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
finally:
    r.g.close()
