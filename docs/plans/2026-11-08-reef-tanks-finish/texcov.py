#!/usr/bin/env python3
"""Texel-coverage audit for the Thai reef generator meshes (plan W2).

For each static group and actor, prints the share of face area whose exported
UVs (reef/uvmap.py) cover a single texel (a flat swatch) and the share in
faces spanning fewer than 3 texels. --check exits 1 if
any creature W2 reskins is still above 20 % on either measure.
Usage: python3 docs/plans/2026-11-08-reef-tanks-finish/texcov.py [--check]
"""
import sys, math, collections
from pathlib import Path
if any(a in ('-h', '--help') for a in sys.argv[1:]):
    print(__doc__); sys.exit(0)
R=str(Path(__file__).resolve().parents[3])
sys.path.insert(0,R+'/wflevels/aquarium_tanks'); sys.path.insert(0,R+'/wflevels/aquarium_thai_reef')
from mesh import Mesh
from reef.geometry import build_groups
from reef.fishes import boxfish, humbug
from reef import life, invertebrates, corals, uvmap
from reef.scene import worm_origin
FLAT={'fish_dark','fish_white'}
def area(vs):
    a=[0,0,0]
    for i in range(1,len(vs)-1):
        u=[vs[i][k]-vs[0][k] for k in range(3)]; w=[vs[i+1][k]-vs[0][k] for k in range(3)]
        c=(u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]); a=[a[k]+c[k] for k in range(3)]
    return 0.5*math.sqrt(sum(x*x for x in a))
RESULTS={}
def report(name, m):
    """Measure the exported UVs (reef.uvmap), in texels of the 1024 atlas."""
    uvs=uvmap.face_uvs(m)
    tot=0; flat=0; small=0; keys=collections.Counter()
    for f,k,uv in zip(m.faces,m.colors,uvs):
        a=area([m.vertices[i] for i in f]); tot+=a; keys[k]+=a
        extent=max(max(u for u,_ in uv)-min(u for u,_ in uv), max(v for _,v in uv)-min(v for _,v in uv))*1024
        if extent<.5: flat+=a          # one texel: a flat swatch
        elif extent<3: small+=a        # a face spanning under 3 texels
    RESULTS[name]=(100*flat/tot,100*small/tot)
    top=', '.join(f'{k} {100*v/tot:.0f}%' for k,v in keys.most_common(4))
    print(f'{name:15s} faces {len(m.faces):6d}  flat-swatch {100*flat/tot:5.1f}%  sub-3-texel {100*small/tot:5.1f}%  | {top}')
for n,g in build_groups(Mesh).items():
    if n!='reef_shell': report(n,g)
for n,mk in (('Boxfish',boxfish),('Humbug',humbug)): report(n,mk(Mesh))
for n,b in (('SeaFan',life._sea_fan),('FeatherStar',life._feather_star),('Nudibranch',life._nudibranch),('WormCrowns',lambda m,_: life.worm_crowns(m, worm_origin())),('FeatherDusters',life.feather_dusters),('Flowerpot',corals.flowerpot),('Leather',corals.leather_coral),('GiantClam',life._clam),('GuardCrab',invertebrates.guard_crab),('Shrimp',invertebrates.banded_shrimp),('HermitCrab',invertebrates.hermit_crab)):
    m=Mesh(n.lower()); b(m,(0,0,0)); report(n,m)

if '--check' in sys.argv[1:]:
    W2=('WormCrowns','GuardCrab','Shrimp','HermitCrab','Nudibranch','FeatherDusters','reef_life','reef_life_1')
    bad=[n for n in W2 if max(RESULTS[n])>20]
    print('FAIL: '+', '.join(bad) if bad else 'PASS: every W2 creature <= 20 %')
    sys.exit(1 if bad else 0)
