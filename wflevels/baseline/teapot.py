"""The Utah teapot as a ladder of triangle meshes, with no Blender dependency.

The reference is Martin Newell's 32-patch bicubic Bézier teapot, read verbatim from
data/teapotCGA.bpt (provenance in data/README.md). tessellate(n) evaluates every patch
on an (n+1) x (n+1) grid, welds the vertices shared along patch edges, splits each cell
into two triangles and drops the triangles that collapse at the lid and bottom cusps, so
the face count is exactly 64*n*n - 8*n at every level.

Winding: the engine culls back faces, and this data needs no correction. Splitting every
cell as (a, b, c), (a, c, d) already gives one consistent, outward-facing orientation on
every shell (checked per shell in tests/test_baseline_teapots.py). A first prototype
suggested the patches disagreed; an orientation pass written to fix that flipped nothing
at any level and was removed.
"""
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data' / 'teapotCGA.bpt'
PATCHES = 32


def load_patches(path=DATA):
    """Return 32 patches, each a list of 16 (x, y, z) control points (row-major 4 x 4)."""
    lines = Path(path).read_text().splitlines()
    if int(lines[0]) != PATCHES:
        raise ValueError('expected %d patches, found %s' % (PATCHES, lines[0]))
    points = [tuple(map(float, line.split())) for line in lines[1:] if len(line.split()) == 3]
    if len(points) != PATCHES * 16:
        raise ValueError('expected %d control points, found %d' % (PATCHES * 16, len(points)))
    return [points[i * 16:(i + 1) * 16] for i in range(PATCHES)]


def face_count(n):
    """Faces at tessellation level n: 32 patches * 2n^2 triangles, minus 8n cusp triangles.

    At n = 1 four more triangles are collinear (the flat strip across the spout tip, in
    patches 18 and 19) and have no area, so they are dropped too: 52 faces, not 56.
    """
    return 64 * n * n - 8 * n - (4 if n == 1 else 0)


def _bernstein(u):
    v = 1.0 - u
    return (v * v * v, 3 * u * v * v, 3 * u * u * v, u * u * u)


def _evaluate(patch, s, t):
    bs, bt = _bernstein(s), _bernstein(t)
    out = [0.0, 0.0, 0.0]
    for i in range(4):
        for j in range(4):
            w = bs[i] * bt[j]
            point = patch[i * 4 + j]
            out[0] += w * point[0]
            out[1] += w * point[1]
            out[2] += w * point[2]
    return out


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _area(vertices, triangle):
    a, b, c = (vertices[i] for i in triangle)
    x = _cross(_sub(b, a), _sub(c, a))
    return 0.5 * (x[0] * x[0] + x[1] * x[1] + x[2] * x[2]) ** 0.5


def tessellate(n, scale=1.0, patches=None):
    """Return (vertices, triangles) at tessellation level n, scaled, outward-wound.

    n = 1 gives 52 faces (every patch one quad) and is the coarsest level.
    """
    if n < 1 or int(n) != n:
        raise ValueError('tessellation level must be a positive integer')
    patches = patches or load_patches()
    index, vertices, triangles = {}, [], []

    def vertex(point):
        key = tuple(round(c, 6) + 0.0 for c in point)  # + 0.0 folds -0.0 into 0.0
        if key not in index:
            index[key] = len(vertices)
            vertices.append(tuple(c * scale for c in key))
        return index[key]

    for patch in patches:
        grid = [[vertex(_evaluate(patch, s / n, t / n)) for t in range(n + 1)] for s in range(n + 1)]
        for s in range(n):
            for t in range(n):
                a, b, c, d = grid[s][t], grid[s][t + 1], grid[s + 1][t + 1], grid[s + 1][t]
                for triangle in ((a, b, c), (a, c, d)):
                    if len(set(triangle)) == 3:
                        triangles.append(triangle)
    triangles = [t for t in triangles if _area(vertices, t) > 1e-12]
    used = sorted({i for t in triangles for i in t})
    renumber = {old: new for new, old in enumerate(used)}
    vertices = [vertices[i] for i in used]
    triangles = [tuple(renumber[i] for i in t) for t in triangles]
    return vertices, triangles


def label_texts(path=None):
    """One floor label per rung of the ladder, from baseline.json, e.g. "240 faces"."""
    import json
    config = json.loads((Path(__file__).resolve().parent / 'baseline.json').read_text())['teapots']
    return ['%d faces' % face_count(n) for n in config['segments']]
