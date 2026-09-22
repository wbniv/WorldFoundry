#!/usr/bin/env python3
"""Convert a decoded arcade course (mm_merge_course.py output) into the
course JSON contract consumed by gen_course.py.

Scale (see README.md "Units"):
    1 arcade XY unit = UNIT_M metres            (default 0.1 m; 8 units = 1 cell = 0.8 m)
    1 arcade height unit = UNIT_M * 0.8165 m    (2:1 iso == 30 deg camera elevation:
                                                 a vertical world unit projects to
                                                 cos(30) * sqrt(2) = 1.2247 px, and the
                                                 arcade draws 1 height unit as 1 px)
The arcade viewer sits on the +X+Y side of the course (larger X+Y is lower on
screen).  The WF level camera sits at (-d,-d,+h) looking toward +X+Y, so the
course is point-mirrored (X,Y) -> (-X,-Y): a 180 degree turn, no handedness
change, and screen-right stays Y-X.

Usage: mm_course_to_level.py course-practice.json course.json \
           --spawn 139.97 140 --goal 77 64 81 68 [--unit 0.1]
"""
import argparse
import json

ISO_Z = 0.8165


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--unit', type=float, default=0.1, help='metres per arcade XY unit')
    ap.add_argument('--spawn', nargs=2, type=float, required=True, metavar=('X', 'Y'), help='arcade units')
    ap.add_argument('--goal', nargs=4, type=int, required=True, metavar=('CX0', 'CY0', 'CX1', 'CY1'), help='cell range, exclusive upper')
    ap.add_argument('--name', default='practice')
    ap.add_argument('--radius', type=float, default=0.5, help='marble radius (m) used to lift the spawn')
    a = ap.parse_args()
    src = json.load(open(a.src))
    u = a.unit
    cell = 8 * u
    hz = u * ISO_Z
    cells = []
    hs = []
    for c in src['cells']:
        i, j = c['i'], c['j']
        h00, h10, h11, h01 = c['h']
        # mirror: cell (i,j) spanning [i,i+1]x[j,j+1] -> [-i-1,-i]x[-j-1,-j]
        # corner order stays (i',j') (i'+1,j') (i'+1,j'+1) (i',j'+1):
        #   (i',j')     = (-i-1,-j-1) <- old (i+1,j+1) = h11
        #   (i'+1,j')   = (-i,  -j-1) <- old (i,  j+1) = h01
        #   (i'+1,j'+1) = (-i,  -j  ) <- old (i,  j  ) = h00
        #   (i',j'+1)   = (-i-1,-j  ) <- old (i+1,j  ) = h10
        cells.append({'i': -i - 1, 'j': -j - 1, 'h': [h11 * hz, h01 * hz, h00 * hz, h10 * hz]})
        hs += c['h']
    sx, sy = a.spawn
    # ground height at spawn: average of the spawn cell's corners
    ci, cj = int(sx // 8), int(sy // 8)
    spawn_cell = next((c for c in src['cells'] if c['i'] == ci and c['j'] == cj), None)
    gz = (sum(spawn_cell['h']) / 4 * hz) if spawn_cell else 0.0
    gx0, gy0, gx1, gy1 = a.goal
    goal_cells = [c for c in src['cells'] if gx0 <= c['i'] < gx1 and gy0 <= c['j'] < gy1]
    gzs = [h * hz for c in goal_cells for h in c['h']] or [0.0]
    out = {
        'name': a.name,
        'cell_size': cell,
        'cells': cells,
        'spawn': [-sx * u, -sy * u, gz + a.radius + 0.05],
        'goal': {'min': [-gx1 * cell, -gy1 * cell, min(gzs) - 0.5], 'max': [-gx0 * cell, -gy0 * cell, max(gzs) + 3.0]},
        'kill_z': min(hs) * hz - 2.0,
        'source': {'arcade_level': src.get('level'), 'unit_m': u, 'height_unit_m': hz, 'mirrored': True},
    }
    json.dump(out, open(a.dst, 'w'))
    print(f"{len(cells)} cells, cell_size={cell} m, spawn={out['spawn']}, goal={out['goal']}, kill_z={out['kill_z']:.2f}")


if __name__ == '__main__':
    main()
