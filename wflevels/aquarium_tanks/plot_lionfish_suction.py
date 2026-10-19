#!/usr/bin/env python3
"""Plot actual Forth flow-helper trajectories; illustrative game coefficients."""
from pathlib import Path
import importlib.util
import json
import math
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
PRIMARY=ROOT.parents[1] if ROOT.parent.name=='.worktrees' else ROOT
spec=importlib.util.spec_from_file_location('zfhost',PRIMARY/'docs/reference/swarming-poster/zfhost.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
OUT=ROOT/'docs/plans/2026-10-05-lionfish-realism';OUT.mkdir(parents=True,exist_ok=True)
fig,ax=plt.subplots(figsize=(8,4.8),layout='constrained');traces={}
for label,y,vy,color in [('Centered',0,0,'#177e89'),('Off axis + sideways momentum',.06,.30,'#ae5b30'),('Stronger transverse escape',.09,.80,'#805798')]:
    h=mod.Host();assert h.load(ROOT/'wflevels/aquarium_tanks/lionfish_suction.fth')=='ok'
    for k,v in {0:.12,1:y,3:0,4:vy,6:.005,8:.13,9:1,18:.2}.items():h.write(1300+k,v)
    points=[]
    for k in range(32):
        t=k*.005;points.append([t,h.read(1300),h.read(1301),h.read(1303),h.read(1304)])
        h.write(1307,max(0,math.sin(math.pi*t/.08)) if t<.08 else 0)
        assert h.eval('lf-step')=='ok'
    h.close();traces[label]=points
    ax.plot([p[1] for p in points],[p[2] for p in points],label=label,color=color,lw=2)
    for i in [0,8,16,24,31]:ax.scatter(points[i][1],points[i][2],s=16,color=color)
ax.axvline(0,color='#263f45',lw=2,label='Mouth plane')
ax.set(xlabel='Forward distance from mouth (scene units)',ylabel='Transverse offset (scene units)',title='Transient suction: velocity integration, not a position tween')
ax.grid(alpha=.2);ax.legend(fontsize=9,loc='lower right')
fig.text(.015,.005,'Dots every 40 ms. Actual Forth helper; illustrative pulse/coefficients, not measured lionfish hydrodynamics.',fontsize=8)
fig.savefig(OUT/'suction-trajectories.svg');fig.savefig(OUT/'suction-trajectories.png',dpi=160)
(OUT/'suction-trajectories.json').write_text(json.dumps(traces,indent=2)+'\n')
print(OUT/'suction-trajectories.svg')
