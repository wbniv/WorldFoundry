#!/usr/bin/env python3
"""course_geom.py -- course-description JSON -> triangle soup, pure Python (no bpy).

Deliberately free of Blender so the parts most likely to be wrong -- face winding,
the per-cell diagonal choice, degenerate-triangle rejection, chunking -- can be
exercised without launching Blender:

    python3 course_geom.py course-test.json          # summary
    python3 course_geom.py course-test.json --check   # winding/degeneracy self-check

Course JSON contract (see README.md):

    {
      "name": "practice",
      "cell_size": 1.0,
      "cells": [ {"i": 3, "j": 7, "h": [z00, z10, z11, z01]} ],   # sparse; absent = void
      "spawn": [x, y, z],                                          # marble CENTRE
      "goal":  {"min": [x0,y0,z0], "max": [x1,y1,z1]},
      "kill_z": -3.0
    }

Corner order per cell: (i,j) (i+1,j) (i+1,j+1) (i,j+1).
Cell (i,j) spans X in [i*s,(i+1)*s], Y in [j*s,(j+1)*s].  Z is up (WF convention).

Winding: every face is authored **Blender-CCW seen from outside** (+Z for floors,
away-from-solid for walls/skirts).  `wftools/wf_blender/export_level.py` reverses the
loop order on export to match the engine's `(v2-v0)x(v1-v0)` hand, so "outward in the
viewport" == "outward in the engine".  See docs/level-design-troubleshooting.md
"Mesh face normals & backface culling" -- WF_CULL is ON by default, a back-wound face
VANISHES.
"""

from __future__ import annotations

import json
import math
import os
import sys

# ---------------------------------------------------------------------------
# Material slots.  Index order here IS the Blender material-slot order and the
# MATL chunk order, so keep them in sync with MATERIALS in gen_course.py.
MAT_FLOOR_A = 0
MAT_FLOOR_B = 1
MAT_WALL    = 2
MAT_SKIRT   = 3
MAT_GOAL    = 4
MAT_COUNT   = 5

# Skirt faces drop this far below the lowest floor corner in the course.
SKIRT_DROP = 2.0

# A triangle whose cross-product length (== 2x area) is below this is dropped.
# The engine aborts the level on sub-threshold polygons -- "Probably have a
# polygon which is too small" (math/vector3.hpi:243), see
# docs/level-design-troubleshooting.md.
MIN_CROSS_LEN = 1.0e-3

# Vertex budget per mesh actor.  HARD cap is 32767: export_level.py packs face
# vertex indices as int16 (`struct.pack('<hhhh', v1, v2, v3, mat_idx)`).  We stay
# well under it so a chunk can never straddle the cliff.
MAX_VERTS_PER_CHUNK = 20000
# Cells per chunk.  A cell costs <= 4 floor verts + up to 4 wall/skirt quads;
# with corner sharing the observed cost is ~6-9 verts/cell, so 1500 cells is a
# ~10-14k-vertex chunk -- comfortably inside MAX_VERTS_PER_CHUNK.
CELLS_PER_CHUNK = 1500

_QUANT = 1.0e-5   # vertex weld tolerance, metres


# ---------------------------------------------------------------------------
# Course loading / validation


class CourseError(ValueError):
    pass


def load_course(path):
    """Read + validate a course JSON.  Returns the parsed dict (normalised)."""
    with open(path, 'r', encoding='utf-8') as fh:
        course = json.load(fh)
    return validate_course(course, origin=path)


def validate_course(course, origin='<dict>'):
    def need(key):
        if key not in course:
            raise CourseError('%s: missing required key %r' % (origin, key))
        return course[key]

    cells = need('cells')
    if not cells:
        raise CourseError('%s: "cells" is empty -- nothing to build' % origin)

    size = float(course.get('cell_size', 1.0))
    if size <= 0.0:
        raise CourseError('%s: cell_size must be > 0 (got %r)' % (origin, size))
    course['cell_size'] = size
    course.setdefault('name', os.path.splitext(os.path.basename(origin))[0])

    seen = {}
    for n, c in enumerate(cells):
        for key in ('i', 'j', 'h'):
            if key not in c:
                raise CourseError('%s: cells[%d] missing %r' % (origin, n, key))
        key = (int(c['i']), int(c['j']))
        if key in seen:
            raise CourseError('%s: duplicate cell (i=%d, j=%d) at cells[%d] and cells[%d]'
                              % (origin, key[0], key[1], seen[key], n))
        seen[key] = n
        if len(c['h']) != 4:
            raise CourseError('%s: cells[%d] "h" must have 4 corner heights, got %d'
                              % (origin, n, len(c['h'])))
        c['i'], c['j'] = key
        c['h'] = [float(z) for z in c['h']]

    spawn = need('spawn')
    if len(spawn) != 3:
        raise CourseError('%s: "spawn" must be [x, y, z]' % origin)
    course['spawn'] = [float(v) for v in spawn]

    goal = need('goal')
    for key in ('min', 'max'):
        if key not in goal or len(goal[key]) != 3:
            raise CourseError('%s: goal.%s must be [x, y, z]' % (origin, key))
        goal[key] = [float(v) for v in goal[key]]
    for ax in range(3):
        if goal['max'][ax] < goal['min'][ax]:
            raise CourseError('%s: goal.max[%d] < goal.min[%d]' % (origin, ax, ax))

    course['kill_z'] = float(course.get('kill_z', -10.0))
    return course


def cell_map(course):
    """(i,j) -> [z00, z10, z11, z01]."""
    return {(c['i'], c['j']): c['h'] for c in course['cells']}


def min_height(course):
    return min(min(c['h']) for c in course['cells'])


def cell_in_goal_xy(course, i, j):
    """True when the cell CENTRE's XY lies inside the goal AABB's XY footprint."""
    s = course['cell_size']
    cx, cy = (i + 0.5) * s, (j + 0.5) * s
    gmin, gmax = course['goal']['min'], course['goal']['max']
    return gmin[0] <= cx <= gmax[0] and gmin[1] <= cy <= gmax[1]


# ---------------------------------------------------------------------------
# Triangle soup


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def tri_normal(p0, p1, p2):
    """Blender's hand: (v1-v0) x (v2-v0).  Returns (nx, ny, nz, length)."""
    n = _cross(_sub(p1, p0), _sub(p2, p0))
    return n[0], n[1], n[2], _len(n)


class FaceSoup:
    """Accumulates triangles as (p0, p1, p2, material_index, owner_cell)."""

    def __init__(self):
        self.tris = []
        self.dropped_degenerate = 0

    def add_tri(self, p0, p1, p2, mat, owner, want=None):
        nx, ny, nz, ln = tri_normal(p0, p1, p2)
        if ln < MIN_CROSS_LEN:
            self.dropped_degenerate += 1
            return False
        if want is not None:
            # Flip so the normal agrees with the requested outward direction.
            if nx * want[0] + ny * want[1] + nz * want[2] < 0.0:
                p1, p2 = p2, p1
        self.tris.append((p0, p1, p2, mat, owner))
        return True

    def add_quad(self, p0, p1, p2, p3, mat, owner, want=None):
        """Quad p0->p1->p2->p3 as two triangles; degenerate halves are dropped,
        which is exactly the 'only one edge endpoint differs' wall case."""
        n = 0
        n += 1 if self.add_tri(p0, p1, p2, mat, owner, want) else 0
        n += 1 if self.add_tri(p0, p2, p3, mat, owner, want) else 0
        return n


def _floor_tris(soup, course, i, j, h, mat):
    """One cell -> two triangles, split on the more-planar diagonal.

    Corners CCW seen from +Z: c00 (i,j) -> c10 (i+1,j) -> c11 (i+1,j+1) -> c01 (i,j+1).
    Both candidate splits below preserve that CCW order, so both give +Z normals.
    """
    s = course['cell_size']
    x0, x1 = i * s, (i + 1) * s
    y0, y1 = j * s, (j + 1) * s
    c00 = (x0, y0, h[0])
    c10 = (x1, y0, h[1])
    c11 = (x1, y1, h[2])
    c01 = (x0, y1, h[3])

    def deviation(ta, tb):
        """Angle (rad) between two triangles' unit normals; inf if either is degenerate."""
        na = tri_normal(*ta)
        nb = tri_normal(*tb)
        if na[3] < MIN_CROSS_LEN or nb[3] < MIN_CROSS_LEN:
            return float('inf')
        dot = (na[0] * nb[0] + na[1] * nb[1] + na[2] * nb[2]) / (na[3] * nb[3])
        return math.acos(max(-1.0, min(1.0, dot)))

    # Diagonal A: c00-c11.  Diagonal B: c10-c01.
    a = ((c00, c10, c11), (c00, c11, c01))
    b = ((c00, c10, c01), (c10, c11, c01))
    split = a if deviation(*a) <= deviation(*b) else b
    for tri in split:
        soup.add_tri(tri[0], tri[1], tri[2], mat, (i, j), want=(0.0, 0.0, 1.0))


# Neighbour offsets and, for each, the two corner indices of THIS cell that lie
# on the shared edge and the matching corner indices of the NEIGHBOUR cell.
#   corners: 0=(i,j) 1=(i+1,j) 2=(i+1,j+1) 3=(i,j+1)
_EDGES = (
    # (di, dj, outward_xy,   self_corners, neigh_corners)
    (+1,  0, (1.0, 0.0, 0.0), (1, 2), (0, 3)),   # +X edge: self c10/c11 vs neigh c00/c01
    (0, +1, (0.0, 1.0, 0.0), (3, 2), (0, 1)),    # +Y edge: self c01/c11 vs neigh c00/c10
    (-1,  0, (-1.0, 0.0, 0.0), (0, 3), (1, 2)),  # -X edge
    (0, -1, (0.0, -1.0, 0.0), (0, 1), (3, 2)),   # -Y edge
)


def _edge_points(course, i, j, ci0, ci1):
    """World XY of this cell's corner indices ci0, ci1 (Z supplied by the caller)."""
    s = course['cell_size']
    xy = ((i * s, j * s), ((i + 1) * s, j * s),
          ((i + 1) * s, (j + 1) * s), (i * s, (j + 1) * s))
    return xy[ci0], xy[ci1]


def build_soup(course):
    """course dict -> FaceSoup covering floors, cliff walls and void skirts."""
    cells = cell_map(course)
    soup = FaceSoup()
    skirt_z = min_height(course) - SKIRT_DROP

    for (i, j), h in sorted(cells.items()):
        mat = MAT_GOAL if cell_in_goal_xy(course, i, j) else \
            (MAT_FLOOR_A if (i + j) % 2 == 0 else MAT_FLOOR_B)
        _floor_tris(soup, course, i, j, h, mat)

    for (i, j), h in sorted(cells.items()):
        for di, dj, outward, (ca, cb), (na, nb) in _EDGES:
            nbr = cells.get((i + di, j + dj))
            (xa, ya), (xb, yb) = _edge_points(course, i, j, ca, cb)

            if nbr is None:
                # Void edge -> skirt down to the course floor.  Outward normal is
                # the edge's outward XY direction (away from the solid cell).
                soup.add_quad((xa, ya, h[ca]), (xb, yb, h[cb]),
                              (xb, yb, skirt_z), (xa, ya, skirt_z),
                              MAT_SKIRT, (i, j), want=outward)
                continue

            # Shared edge: emit the cliff wall ONCE, owned by the +X / +Y side so
            # each pair is visited exactly once.
            if di < 0 or dj < 0:
                continue
            za_self, zb_self = h[ca], h[cb]
            za_nbr, zb_nbr = nbr[na], nbr[nb]
            if abs(za_self - za_nbr) < 1e-9 and abs(zb_self - zb_nbr) < 1e-9:
                continue   # flush -- no gap to close

            # Outward = away from the SOLID side, i.e. from the higher cell
            # towards the lower one.  add_quad flips to match `want`.
            higher_is_self = (za_self + zb_self) >= (za_nbr + zb_nbr)
            want = outward if higher_is_self else tuple(-v for v in outward)
            soup.add_quad((xa, ya, max(za_self, za_nbr)),
                          (xb, yb, max(zb_self, zb_nbr)),
                          (xb, yb, min(zb_self, zb_nbr)),
                          (xa, ya, min(za_self, za_nbr)),
                          MAT_WALL, (i, j), want=want)
    return soup


# ---------------------------------------------------------------------------
# Chunking + welded vertex arrays


class Chunk:
    """One mesh actor's worth of welded geometry."""

    def __init__(self, index):
        self.index = index
        self.verts = []          # [(x, y, z)]
        self.faces = []          # [(v0, v1, v2, material_index)]
        self._weld = {}

    def _vert(self, p):
        key = (int(round(p[0] / _QUANT)), int(round(p[1] / _QUANT)), int(round(p[2] / _QUANT)))
        vi = self._weld.get(key)
        if vi is None:
            vi = len(self.verts)
            self._weld[key] = vi
            self.verts.append((float(p[0]), float(p[1]), float(p[2])))
        return vi

    def add(self, p0, p1, p2, mat):
        a, b, c = self._vert(p0), self._vert(p1), self._vert(p2)
        if a == b or b == c or a == c:
            return False     # collapsed by the weld
        self.faces.append((a, b, c, mat))
        return True

    def bounds(self):
        xs = [v[0] for v in self.verts]
        ys = [v[1] for v in self.verts]
        zs = [v[2] for v in self.verts]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def materials_used(self):
        return sorted({f[3] for f in self.faces})


def build_chunks(course, cells_per_chunk=CELLS_PER_CHUNK):
    """Partition the course into one or more Chunks.

    Faces are owned by exactly one cell (walls by the +X/+Y side), so a shared
    wall lands in one chunk only -- never duplicated, never dropped.
    """
    soup = build_soup(course)
    order = {key: n for n, key in enumerate(sorted(cell_map(course)))}

    chunks = []
    for p0, p1, p2, mat, owner in soup.tris:
        ci = order[owner] // cells_per_chunk
        while len(chunks) <= ci:
            chunks.append(Chunk(len(chunks)))
        chunks[ci].add(p0, p1, p2, mat)

    over = [c for c in chunks if len(c.verts) > MAX_VERTS_PER_CHUNK]
    if over:
        raise CourseError(
            'chunk(s) %s exceed MAX_VERTS_PER_CHUNK=%d (int16 face indices cap a mesh '
            'actor at 32767 verts) -- lower CELLS_PER_CHUNK'
            % ([c.index for c in over], MAX_VERTS_PER_CHUNK))
    return chunks, soup


def course_bounds(chunks):
    """World AABB over every chunk."""
    mns = [c.bounds()[0] for c in chunks]
    mxs = [c.bounds()[1] for c in chunks]
    return (tuple(min(m[ax] for m in mns) for ax in range(3)),
            tuple(max(m[ax] for m in mxs) for ax in range(3)))


def spawn_clearance_z(chunks, spawn, radius):
    """Lowest spawn Z whose marble AABB is NOT fully enclosed by any chunk body.

    `JoltCharacterCreate` (wfsource/source/physics/jolt/jolt_backend.cc:686) walks the
    existing STATIC bodies and permanently EXCLUDES from this character's collision any
    body whose world AABB fully contains the character's spawn AABB -- the "zone volume"
    heuristic for region-marker boxes.  A terrain chunk contains a marble resting on it,
    so without this lift the course can be silently excluded and the marble falls through.

    Fix: make the marble poke out of the top of every chunk that could enclose it.
    Only chunks whose XY AABB contains the marble's XY AABB can match.
    """
    need = spawn[2]
    for ch in chunks:
        mn, mx = ch.bounds()
        if not (mn[0] <= spawn[0] - radius and mx[0] >= spawn[0] + radius and
                mn[1] <= spawn[1] - radius and mx[1] >= spawn[1] + radius):
            continue          # cannot enclose in XY -> cannot be excluded
        need = max(need, mx[2] - radius + 0.05)
    return need


# ---------------------------------------------------------------------------


def self_check(course, chunks, soup):
    """Assert the invariants the engine will punish us for getting wrong."""
    problems = []
    n_floor = n_wall = n_skirt = 0
    for p0, p1, p2, mat, _owner in soup.tris:
        nx, ny, nz, ln = tri_normal(p0, p1, p2)
        if ln < MIN_CROSS_LEN:
            problems.append('degenerate triangle survived: %r %r %r' % (p0, p1, p2))
            continue
        if mat in (MAT_FLOOR_A, MAT_FLOOR_B, MAT_GOAL):
            n_floor += 1
            if nz <= 0.0:
                problems.append('floor triangle is not +Z wound: n=(%.3f,%.3f,%.3f)' % (nx, ny, nz))
        elif mat == MAT_WALL:
            n_wall += 1
            if abs(nz) > 1e-6 * ln:
                problems.append('wall triangle is not vertical: nz=%.6g' % nz)
        elif mat == MAT_SKIRT:
            n_skirt += 1
            if abs(nz) > 1e-6 * ln:
                problems.append('skirt triangle is not vertical: nz=%.6g' % nz)
    for ch in chunks:
        if len(ch.verts) > 32767:
            problems.append('chunk %d has %d verts > int16 face-index cap'
                            % (ch.index, len(ch.verts)))
    return problems, (n_floor, n_wall, n_skirt)


def selftest():
    """Unit checks for the edge cases the demo course does not happen to contain.

    Regression guard for the wall-emission rules: a flush shared edge must emit
    NOTHING, an edge where only ONE endpoint differs must collapse to a single
    triangle (the other half is degenerate), and a void edge must skirt.
    """
    failures = []

    def mini(cells, name):
        return validate_course({
            'name': name, 'cell_size': 1.0, 'cells': cells,
            'spawn': [0.5, 0.5, 1.0],
            'goal': {'min': [99.0, 99.0, 99.0], 'max': [100.0, 100.0, 100.0]},
            'kill_z': -10.0,
        }, origin=name)

    def wall_tris(cells, name):
        soup = build_soup(mini(cells, name))
        return sum(1 for t in soup.tris if t[3] == MAT_WALL), soup.dropped_degenerate

    # flush: identical shared-edge heights -> no wall at all
    n, _ = wall_tris([{'i': 0, 'j': 0, 'h': [0, 0, 0, 0]},
                      {'i': 1, 'j': 0, 'h': [0, 1, 1, 0]}], 'flush')
    if n != 0:
        failures.append('flush shared edge emitted %d wall triangle(s), expected 0' % n)

    # one endpoint only: cell A's c11 differs, c10 matches -> exactly ONE triangle
    n, dropped = wall_tris([{'i': 0, 'j': 0, 'h': [0, 0, 1, 0]},
                            {'i': 1, 'j': 0, 'h': [0, 0, 0, 0]}], 'one-endpoint')
    if n != 1:
        failures.append('single-endpoint step emitted %d wall triangle(s), expected 1' % n)
    if dropped != 1:
        failures.append('single-endpoint step dropped %d degenerate, expected 1' % dropped)

    # both endpoints: full quad -> two triangles
    n, _ = wall_tris([{'i': 0, 'j': 0, 'h': [0, 2, 2, 0]},
                      {'i': 1, 'j': 0, 'h': [0, 0, 0, 0]}], 'two-endpoint')
    if n != 2:
        failures.append('two-endpoint step emitted %d wall triangle(s), expected 2' % n)

    # a lone cell is surrounded by void: 4 edges x 2 triangles of skirt
    soup = build_soup(mini([{'i': 0, 'j': 0, 'h': [0, 0, 0, 0]}], 'lone'))
    n_skirt = sum(1 for t in soup.tris if t[3] == MAT_SKIRT)
    if n_skirt != 8:
        failures.append('lone cell emitted %d skirt triangle(s), expected 8' % n_skirt)

    # wall outward normal points AWAY from the higher (solid) cell
    soup = build_soup(mini([{'i': 0, 'j': 0, 'h': [2, 2, 2, 2]},
                            {'i': 1, 'j': 0, 'h': [0, 0, 0, 0]}], 'outward'))
    for p0, p1, p2, mat, _o in soup.tris:
        if mat != MAT_WALL:
            continue
        nx, _ny, _nz, _ln = tri_normal(p0, p1, p2)
        if nx <= 0.0:
            failures.append('wall between a high -X cell and a low +X cell faces -X (nx=%.3f)' % nx)
    return failures


def _usage():
    print(__doc__.strip())
    print('\nusage: python3 course_geom.py <course.json> [--check]')
    print('       python3 course_geom.py --selftest')


def main(argv):
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        _usage()
        return 0
    if argv[1] == '--selftest':
        failures = selftest()
        for f in failures:
            print('FAIL: %s' % f)
        print('FAIL: %d' % len(failures) if failures else
              'PASS: wall/skirt emission edge cases')
        return 1 if failures else 0
    course = load_course(argv[1])
    chunks, soup = build_chunks(course)
    mn, mx = course_bounds(chunks)
    print('course      : %s (%d cells, cell_size=%g)'
          % (course['name'], len(course['cells']), course['cell_size']))
    print('triangles   : %d  (dropped %d degenerate)' % (len(soup.tris), soup.dropped_degenerate))
    print('chunks      : %d  verts=%s  faces=%s'
          % (len(chunks), [len(c.verts) for c in chunks], [len(c.faces) for c in chunks]))
    print('bounds      : (%.2f, %.2f, %.2f) .. (%.2f, %.2f, %.2f)' % (mn + mx))
    print('spawn       : %r' % (course['spawn'],))
    print('spawn min z : %.3f (zone-volume clearance, radius 0.5)'
          % spawn_clearance_z(chunks, course['spawn'], 0.5))
    print('kill_z      : %g' % course['kill_z'])
    if '--check' in argv:
        problems, counts = self_check(course, chunks, soup)
        print('faces       : floor=%d wall=%d skirt=%d' % counts)
        if problems:
            for p in problems[:20]:
                print('FAIL: %s' % p)
            print('FAIL: %d problem(s)' % len(problems))
            return 1
        print('PASS: winding, verticality and index-cap invariants hold')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
