#!/usr/bin/env python3
"""make_test_course.py -- write course-test.json, the synthetic pipeline test course.

Exercises every geometry case the generator has to handle before the real
arcade course JSON lands:

  * sloped floor quads      leg 1 descends z=8 -> z=0 over 24 cells along +X (18.4 deg)
  * trough lanes            leg 1's two outer lanes sit WALL_H above the centre, as
                            corner-continuous 45-degree ramps -- the arcade trough profile
  * a 90-degree bend        junction pad tilted downhill in +Y, so the marble turns the
                            corner under gravity alone; leg 2 then runs +Y for 10 cells
  * vertical cliff walls    a 1-cell RIM at +2 m around every hard boundary; a rim cell is
                            a separate cell, so the shared edge is a true height
                            discontinuity and the generator emits a vertical wall quad
  * a 2 m cliff drop        mid-way down leg 2, between cells j=8 and j=9
  * void edges              every outer boundary of the rim gets a skirt
  * a goal platform         flat, at the far end of leg 2

Run:
    python3 make_test_course.py [-o course-test.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

CELL = 1.0
WALL_H = 1.0        # leg-1 trough lane rise (corner-continuous -> 45-degree ramp)
RIM_H = 2.0         # rim-cell rise above its neighbouring floor -> vertical wall

# --- leg 1: +X trough -------------------------------------------------------
L1_I0, L1_I1 = 0, 23          # inclusive cell i range
L1_J0, L1_J1 = 0, 3           # 4 cells wide -> corner rows jc = 0..4
L1_TOP_Z = 8.0
L1_DROP_PER_CELL = 8.0 / 24.0  # z = 8 at ic=0, z = 0 at ic=24

# --- junction: pad that turns the path from +X to +Y ------------------------
JN_I0, JN_I1 = 24, 27
JN_J0, JN_J1 = 0, 3

# --- leg 2: +Y run ----------------------------------------------------------
L2_I0, L2_I1 = 24, 27
L2_J0, L2_J1 = 4, 13
Y_SLOPE = 0.2                 # per metre, shared by junction and leg 2 (11.3 deg)
CLIFF_AT_J = 9                # cells j >= this sit on the lower surface
CLIFF_DROP = 2.0
FLAT_FROM_JC = 12             # goal platform: corner rows >= this are flat


def leg1_corner(ic, jc):
    """Leg-1 trough surface at corner-lattice point (ic, jc)."""
    z = L1_TOP_Z - min(ic, 24) * L1_DROP_PER_CELL
    if jc in (L1_J0, L1_J1 + 1):
        z += WALL_H
    return z


def y_surface(jc):
    """Junction + leg-2 upper surface: one continuous downhill in +Y."""
    return -Y_SLOPE * jc


def leg2_lower(jc):
    """Leg-2 lower surface, flattening into the goal platform."""
    return -Y_SLOPE * min(jc, FLAT_FROM_JC) - CLIFF_DROP


def junction_corner(ic, jc):
    """Junction pad.  Its -Y boundary is a LANE (a 1 m corner-continuous ramp), not a
    rim wall: -Y faces the SW-iso camera, and a 2 m wall there would hide the marble."""
    del ic
    return y_surface(jc) + (WALL_H if jc == JN_J0 else 0.0)


def leg2_corner(j_cell, jc, ic):
    """Height depends on the OWNING CELL as well as the corner -- that is what makes
    the cliff a true vertical discontinuity instead of a one-cell ramp.  The -X
    boundary is a lane for the same camera-side reason as the junction's -Y."""
    z = leg2_lower(jc) if j_cell >= CLIFF_AT_J else y_surface(jc)
    return z + (WALL_H if ic == L2_I0 else 0.0)


def _flat(i, j, z):
    return {'i': i, 'j': j, 'h': [z, z, z, z]}


def build_cells():
    cells = []

    # leg 1 -- corner-continuous trough
    for i in range(L1_I0, L1_I1 + 1):
        for j in range(L1_J0, L1_J1 + 1):
            cells.append({'i': i, 'j': j, 'h': [
                leg1_corner(i, j), leg1_corner(i + 1, j),
                leg1_corner(i + 1, j + 1), leg1_corner(i, j + 1)]})

    # junction -- tilted downhill in +Y so the corner is taken under gravity
    for i in range(JN_I0, JN_I1 + 1):
        for j in range(JN_J0, JN_J1 + 1):
            cells.append({'i': i, 'j': j, 'h': [
                junction_corner(i, j), junction_corner(i + 1, j),
                junction_corner(i + 1, j + 1), junction_corner(i, j + 1)]})

    # leg 2 -- same downhill, with the 2 m cliff between cells j=8 and j=9
    for i in range(L2_I0, L2_I1 + 1):
        for j in range(L2_J0, L2_J1 + 1):
            cells.append({'i': i, 'j': j, 'h': [
                leg2_corner(j, j, i), leg2_corner(j, j, i + 1),
                leg2_corner(j, j + 1, i + 1), leg2_corner(j, j + 1, i)]})

    # rim -- one cell wide, RIM_H above the floor it abuts.  Every one of these
    # produces a full-height vertical wall quad on its inward edge.  Only the FAR
    # (+X, +Y) boundaries get rims; the near ones are lanes, see junction_corner().
    for j in range(JN_J0, L2_J1 + 1):                       # +X side, j = 0..13
        z = (y_surface(j) if j < CLIFF_AT_J else leg2_lower(j))
        cells.append(_flat(L2_I1 + 1, j, z + RIM_H))
    for i in range(L2_I0, L2_I1 + 1):                       # far end, past the goal
        cells.append(_flat(i, L2_J1 + 1, leg2_lower(L2_J1 + 1) + RIM_H))

    return cells


def build_course():
    cells = build_cells()
    # Spawn: centre of the trough at the top of leg 1, marble centre = floor + radius.
    # gen_course.py raises this further if the Jolt zone-volume heuristic would
    # otherwise swallow the course (see course_geom.spawn_clearance_z).
    spawn_x, spawn_y = 0.5, 2.0
    floor_z = leg1_corner(0, 2) - L1_DROP_PER_CELL * 0.5
    goal_z = leg2_lower(L2_J1 + 1)
    return {
        'name': 'mm3d-test',
        'cell_size': CELL,
        'cells': cells,
        'spawn': [spawn_x, spawn_y, round(floor_z + 0.5, 4)],
        # Goal = the flat platform at the end of leg 2 (cells j = 12, 13).  The Z band
        # hugs the platform (resting marble centre = floor + radius) so the marble has
        # to actually ARRIVE, not merely fly through the column above it.
        'goal': {'min': [float(L2_I0), float(FLAT_FROM_JC), round(goal_z - 0.6, 4)],
                 'max': [float(L2_I1 + 1), float(L2_J1 + 1), round(goal_z + 1.5, 4)]},
        'kill_z': -9.0,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-o', '--out',
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         'course-test.json'),
                    help='output path (default: ./course-test.json)')
    args = ap.parse_args(argv)

    course = build_course()
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(course, fh, indent=1, sort_keys=False)
        fh.write('\n')
    print('wrote %s  (%d cells, spawn=%r, goal=%r, kill_z=%g)'
          % (args.out, len(course['cells']), course['spawn'],
             course['goal'], course['kill_z']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
