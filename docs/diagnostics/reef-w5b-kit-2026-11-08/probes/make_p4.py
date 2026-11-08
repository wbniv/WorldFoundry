#!/usr/bin/env python3
"""R0 probe P4 (plan W5b): the worst set the Random layout can show at once, on the kit level.

Usage: python3 build-docker/r0/make_p4.py
Copies today's (W5b) wflevels/aquarium_thai_reef*/ into build-docker/r0/{K0,P4}/<style>/.
K0  the kit level unchanged (Fixed layout: 3 heroes shown, fillers and clumps hidden)
P4  K0 + a one-shot Director write on the first tick: the two largest fillers (with their
    colliders) moved into view behind the heroes and shown, and every colony clump moved onto
    filler site points and shown. Heroes stay at their Fixed pivots (shown by reef-kit-init).
Positions only (no rotation writes), so the probe APK's libraries need no rotation fix.
"""
import json
import shutil
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
    print(__doc__); raise SystemExit(0)
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
GUARD = 1113                      # next to reef-kit-init's 1112; unassigned
SPOTS = ((-1.15, 1.95), (2.35, 1.95))   # behind the left/arch gap and the arch/right gap


def build(probe, style):
    src, dst = ROOT / 'wflevels' / style, OUT / probe / style
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', 'reef', '*.py', 'textile.log.htm'))
    if probe == 'K0':
        return
    amap = json.loads((dst / 'actor-map.json').read_text())
    worst = amap['kit_budget']['worst_visible']['pieces']
    fillers = [m for m in amap['kit']['modules'] if m['role'] == 'filler' and m['rock'] in worst]
    assert len(fillers) == 2, fillers
    w = 'write-actor-mailbox'
    body = ''
    sites = []
    for (x, y), module in zip(SPOTS, fillers):
        pivot = (x, y, .72)
        for actor in module['piece_actors'] + [module['collider_actor']]:
            body += f' {x} INDEXOF_X_POS {actor} {w} {y} INDEXOF_Y_POS {actor} {w} .72 INDEXOF_Z_POS {actor} {w}\n'
        body += f' 1 {module["cell"]} tk!\n'
        sites += [tuple(pivot[i] + s['p'][i] for i in range(3)) for s in module['sites']]
    for clump, p in zip(amap['kit']['clumps'], sites):
        a = clump['actor_index']
        body += (f' {p[0]:.4f} INDEXOF_X_POS {a} {w} {p[1]:.4f} INDEXOF_Y_POS {a} {w} {p[2]:.4f} INDEXOF_Z_POS {a} {w}'
                 f' 1 {clump["cell"]} tk!\n')
    once = f': r0-p4 {GUARD} tk@ 0 = if\n{body} 1 {GUARD} tk! then ;\n'
    lev = dst / f'{style}.lev'
    text = lev.read_text()
    needle = '\\nreef-tick\\n" } }'
    assert text.count(needle) == 1
    text = text.replace(needle, '\\n' + once.replace('\n', '\\n') + 'r0-p4\\nreef-tick\\n" } }')
    lev.write_text(text)


for probe in ('K0', 'P4'):
    for style in ('aquarium_thai_reef', 'aquarium_thai_reef_anime'):
        build(probe, style)
        print(probe, style)
