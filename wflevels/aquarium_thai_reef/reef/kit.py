"""The rock-module kit (plan 2026-11-08 W5b): modules, colliders, site tables, colony clumps.

The Fixed layout is one arrangement of the kit: the three hero modules are today's rock
masses (left, arch, right) with the dressing that grows on each of them, at their Fixed
pivots. Filler modules are extra rock masses that only the Random layout (W5c) shows. Every
piece of a module (its rock, its dressing pieces, its attached animated actors) is authored
relative to the module pivot, so W5c moves a module by writing one pivot and heading.

Coordinates are world units (1 unit = 1 m at the tank's x10 scale). A module pivot is its
foot: the centre of its footprint on the sand (z = SAND_Z). Colliders are boxes centred on
the pivot in x and y, so the two allowed headings (0 and 1/2 revolution) leave them exact
(Jolt never rotates a static body; R0 report section 2).

Nothing here runs in the game; generate.py consumes it and writes actor-map.json.
"""
import functools
import math
import random

from .scene import SEED
from .surface import SAND_Z, _segment_distance, _wobble, arch_path, rock_blobs, ARCH_RADIUS

# Global user mailboxes used as visibility cells (free range 2-599; R0 report section 1).
# One cell per hideable piece: a module (rock + its dressing + its attached life, which always
# show and hide together) or a colony clump.
MODULE_CELL_BASE = 200
CLUMP_CELL_BASE = 210
PARK_Z = -4.0                  # inside the room box (z >= -6), under the sand and the frame

# Heroes keep today's rock and today's colliders exactly: their pivot is the centre of the
# box collider the Fixed reef already uses (RockColliderLeft/Right), which is also within a few
# cm of the rock's footprint centre. The arch had no collider (its cave stays open); its box
# covers the lintel only, above the cleaner station.
HEROES = (
    {'name': 'left', 'rock': 'reef_left', 'pivot': (-3.325, .5, SAND_Z),
     'collider': ((-1.675, -.75, 0.0), (1.675, .75, 1.78)), 'collider_name': 'RockColliderLeft'},
    {'name': 'arch', 'rock': 'reef_arch', 'pivot': (.15, .5, SAND_Z),
     'collider': ((-1.3, -.7, 1.73), (1.3, .7, 2.33)), 'collider_name': 'RockColliderArch'},
    {'name': 'right', 'rock': 'reef_right', 'pivot': (3.325, .5, SAND_Z),
     'collider': ((-1.675, -.75, 0.0), (1.675, .75, 1.78)), 'collider_name': 'RockColliderRight'},
)

# Filler rock masses, in module-local coordinates (pivot at the origin, foot on z = 0):
# (centre, radii) per seeded wobbled blob, as rockscape.rock_blob builds them.
FILLERS = (
    {'name': 'ledge', 'rock': 'reef_ledge', 'seed': 51, 'blobs': (
        ((0.0, 0.0, .30), (1.10, .55, .48)), ((-.62, .10, .55), (.55, .45, .38)),
        ((.68, -.04, .48), (.50, .44, .32)))},
    {'name': 'pillars', 'rock': 'reef_pillars', 'seed': 63, 'blobs': (
        ((-.42, 0.0, .80), (.36, .34, .92)), ((.44, .10, .66), (.33, .32, .76)),
        ((0.0, .05, .22), (.82, .46, .30)))},
    {'name': 'tall', 'rock': 'reef_tall', 'seed': 77, 'blobs': (
        ((0.0, 0.0, .88), (.58, .48, 1.0)), ((.18, .10, 1.72), (.38, .34, .44)),
        ((-.32, -.05, .32), (.55, .45, .40)))},
)
MODULES = tuple(m['name'] for m in HEROES) + tuple(f['name'] for f in FILLERS)


def module_cell(name):
    return MODULE_CELL_BASE + MODULES.index(name)


def filler_park(index):
    """Where a hidden filler module waits at load: inside the room box, under the sand."""
    return (-4.0 + 4.0 * index, 1.5, PARK_Z)


# --- host surfaces per module -------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def module_blobs(name):
    """(centre, radii, phase) of a module's blobs, in WORLD coordinates for heroes and in
    module-local coordinates for fillers."""
    for hero in HEROES:
        if hero['name'] == name:
            return tuple((c, r, phase) for group, c, r, phase in rock_blobs() if group == name)
    filler = next(f for f in FILLERS if f['name'] == name)
    rng = random.Random(SEED + filler['seed'])
    return tuple((c, r, rng.uniform(0, math.tau)) for c, r in filler['blobs'])


def module_field(name, p):
    """Approximate signed distance from p to a module's analytic rock (negative inside)."""
    best = 9.0
    for c, r, phase in module_blobs(name):
        q = [(p[i] - c[i]) / r[i] for i in range(3)]
        k = math.sqrt(sum(v * v for v in q))
        if k < 1e-9:
            return -min(r)
        phi = math.acos(max(-1.0, min(1.0, q[2] / k)))
        theta = math.atan2(q[1], q[0])
        best = min(best, (k - _wobble(theta, phi, phase)) * min(r))
    if name == 'arch':
        path = arch_path()
        for i in range(len(path) - 1):
            best = min(best, _segment_distance(p, path[i], path[i + 1]) - ARCH_RADIUS)
    return best


def _normal(name, p, h=.01):
    g = []
    for axis in range(3):
        a = list(p); b = list(p)
        a[axis] += h; b[axis] -= h
        g.append(module_field(name, a) - module_field(name, b))
    m = math.sqrt(sum(c * c for c in g)) or 1.0
    return tuple(c / m for c in g)


def _ray(name, origin, direction, max_distance, step=.02):
    t = 0.0
    if module_field(name, origin) < 0:
        return None
    while t < max_distance:
        p = [origin[i] + direction[i] * t for i in range(3)]
        if module_field(name, p) < 0:
            lo, hi = t - step, t
            for _ in range(18):
                mid = (lo + hi) / 2
                if module_field(name, [origin[i] + direction[i] * mid for i in range(3)]) < 0:
                    hi = mid
                else:
                    lo = mid
            return tuple(origin[i] + direction[i] * hi for i in range(3))
        t += step
    return None


def hero_pivot(name):
    return next(h['pivot'] for h in HEROES if h['name'] == name)


@functools.lru_cache(maxsize=None)
def site_table(name, count=16, spacing=.28):
    """Attachment points and outward normals on one module, in MODULE-LOCAL coordinates
    (pivot at the origin, sand at z = 0).

    Resolved on the module's own analytic surface with W3's method (ray casts against the
    seeded blobs, gradient normals), as the W3 placements are. Sites face the camera side or
    up (n.y <= -0.2 or n.z >= 0.45), sit at least 0.12 above the sand, and keep `spacing`
    apart. Order is deterministic (seeded), so W5c can take the first k sites."""
    hero = name in (h['name'] for h in HEROES)
    # Heroes' blobs are in world space (sand at SAND_Z); fillers' are local (sand at 0).
    origin = hero_pivot(name) if hero else (0.0, 0.0, 0.0)
    sand = SAND_Z if hero else 0.0
    blobs = module_blobs(name)
    x_lo = min(c[0] - r[0] for c, r, _ in blobs)
    x_hi = max(c[0] + r[0] for c, r, _ in blobs)
    if name == 'arch':
        x_lo = min(x_lo, min(p[0] for p in arch_path()) - ARCH_RADIUS)
        x_hi = max(x_hi, max(p[0] for p in arch_path()) + ARCH_RADIUS)
    rng = random.Random(SEED + 900 + MODULES.index(name))
    sites = []
    for _ in range(600):
        x = rng.uniform(x_lo, x_hi)
        if rng.random() < .5:                      # camera-side face
            hit = _ray(name, (x, origin[1] - 3.5, rng.uniform(sand + .15, sand + 2.6)), (0, 1, 0), 7.0)
        else:                                      # top
            hit = _ray(name, (x, origin[1] + rng.uniform(-1.6, 1.2), sand + 4.0), (0, 0, -1), 4.5)
        if hit is None or hit[2] < sand + .12:
            continue
        n = _normal(name, hit)
        if not (n[1] <= -.2 or n[2] >= .45):
            continue
        local = (hit[0] - origin[0], hit[1] - origin[1], hit[2] - sand)
        if all(math.dist(local, q['p']) >= spacing for q in sites):
            sites.append({'p': tuple(round(v, 4) for v in local), 'n': tuple(round(v, 4) for v in n)})
            if len(sites) == count:
                break
    return tuple(sites)


# --- splitting today's dressing by host module ---------------------------------------------

def _components(mesh):
    """Face clusters: faces joined by shared vertex positions, then by touching bounding
    boxes (so a polyp's tentacles stay with its head)."""
    parent = list(range(len(mesh.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a
    owner = {}
    for f, face in enumerate(mesh.faces):
        for v in face:
            key = tuple(round(c, 5) for c in mesh.vertices[v])
            if key in owner:
                union(owner[key], f)
            else:
                owner[key] = f
    groups = {}
    for f in range(len(mesh.faces)):
        groups.setdefault(find(f), []).append(f)
    clusters = list(groups.values())
    # Join clusters whose bounding boxes touch (2 cm margin), using a coarse grid.
    boxes = []
    for faces in clusters:
        pts = [mesh.vertices[v] for f in faces for v in mesh.faces[f]]
        boxes.append(([min(p[a] for p in pts) - .02 for a in range(3)],
                      [max(p[a] for p in pts) + .02 for a in range(3)]))
    cparent = list(range(len(clusters)))

    def cfind(i):
        while cparent[i] != i:
            cparent[i] = cparent[cparent[i]]
            i = cparent[i]
        return i
    cell = .25
    grid = {}
    for i, (lo, hi) in enumerate(boxes):
        if max(hi[a] - lo[a] for a in range(3)) > 1.0:
            continue                               # a large mass: joins by vertices only
        for gx in range(int(math.floor(lo[0] / cell)), int(math.floor(hi[0] / cell)) + 1):
            for gy in range(int(math.floor(lo[1] / cell)), int(math.floor(hi[1] / cell)) + 1):
                for gz in range(int(math.floor(lo[2] / cell)), int(math.floor(hi[2] / cell)) + 1):
                    grid.setdefault((gx, gy, gz), []).append(i)
    for members in grid.values():
        for a in range(len(members)):
            la, ha = boxes[members[a]]
            for b in range(a + 1, len(members)):
                lb, hb = boxes[members[b]]
                if all(la[k] <= hb[k] and lb[k] <= ha[k] for k in range(3)):
                    ra, rb = cfind(members[a]), cfind(members[b])
                    if ra != rb:
                        cparent[rb] = ra
    merged = {}
    for i, faces in enumerate(clusters):
        merged.setdefault(cfind(i), []).extend(faces)
    return list(merged.values())


def host_of_point(p):
    """The hero module whose rock is nearest to p."""
    return min((h['name'] for h in HEROES), key=lambda name: module_field(name, p))


def split_by_host(mesh):
    """{hero name: [face indices]} for one dressing group, assigning whole clusters by the
    rock nearest to the cluster's lowest point (where it attaches)."""
    out = {h['name']: [] for h in HEROES}
    for faces in _components(mesh):
        low = min((mesh.vertices[v] for f in faces for v in mesh.faces[f]), key=lambda p: p[2])
        out[host_of_point(low)].extend(faces)
    for faces in out.values():
        faces.sort()
    return out


MAX_PIECE_VERTICES = 18000    # FACE indices are signed 16-bit (geometry.py)
DRESSING_KINDS = {'reef_hard': 'hard', 'reef_soft': 'life', 'reef_sponges': 'life',
                  'reef_life': 'life'}


def dressing_pieces(groups, Mesh, face_uvs):
    """Per-hero dressing meshes, in WORLD coordinates, carrying each face's UVs from its
    original group (some UV modes use per-mesh bounds), so the Fixed look is unchanged.
    Returns {piece name: (hero name, kind, mesh)}; 'hard' pieces keep reef_hard's outline."""
    sources = [name for name in groups if name.startswith(('reef_hard', 'reef_soft', 'reef_sponges', 'reef_life'))]
    collected = {(h['name'], kind): [] for h in HEROES for kind in ('hard', 'life')}
    for name in sources:
        mesh = groups[name]
        kind = 'hard' if name == 'reef_hard' else 'life'
        uvs = face_uvs(mesh)
        for hero, faces in split_by_host(mesh).items():
            for f in faces:
                collected[(hero, kind)].append(([mesh.vertices[v] for v in mesh.faces[f]],
                                                mesh.colors[f], uvs[f]))
    pieces = {}
    for (hero, kind), faces in collected.items():
        if not faces:
            continue
        base = f'reef_{kind}_{hero}'
        current = Mesh(base)
        current.face_uvs = {}
        parts = [current]
        for points, color, uv in faces:
            if len(current.vertices) + len(points) > MAX_PIECE_VERTICES:
                current = Mesh(f'{base}_{len(parts)}')
                current.face_uvs = {}
                parts.append(current)
            current.face(points, color)
            current.face_uvs[len(current.faces) - 1] = tuple(tuple(c) for c in uv)
        for part in parts:
            pieces[part.name] = (hero, kind, part)
    return pieces


# --- filler rock meshes and colony clumps ----------------------------------------------------

def filler_mesh(Mesh, filler):
    """A filler module's blockout rock in module-local coordinates (foot on z = 0)."""
    from .rockscape import rock_blob
    mesh = Mesh(filler['rock'])
    # One generator for all blobs, drawn in order: rock_blob takes exactly one phase per blob,
    # so module_blobs() reproduces the same phases for the analytic surface.
    rng = random.Random(SEED + filler['seed'])
    for c, r in filler['blobs']:
        rock_blob(mesh, c, r, rng)
    return mesh


CLUMPS = (('zoanthid', 3), ('cups', 3), ('crust', 3))


def clump_mesh(Mesh, kind):
    """One colony clump at the origin, growing along +z (W5c rotates +z onto a site normal)."""
    from .life import _cup, _zoanthid_polyp, _placed
    mesh = Mesh(f'kit_{kind}')
    if kind == 'zoanthid':
        for i in range(4):
            a, r = i * 2.399963, .03 + .08 * math.sqrt((i + .5) / 4)
            _placed(mesh, lambda m, i=i: _zoanthid_polyp(m, i), (r * math.cos(a), r * math.sin(a), -.01),
                    (0, 0, 1), spin=i * .7)
    elif kind == 'cups':
        for i in range(3):
            a = math.tau * i / 3
            _placed(mesh, lambda m, i=i: _cup(m, (0, 0, 0), .065, .10 + .02 * i, 'sponge', 8),
                    (.09 * math.cos(a), .09 * math.sin(a), -.015), (0, 0, 1), spin=i)
    else:
        rng = random.Random(SEED + 313)
        radii = [rng.uniform(.65, 1.2) for _ in range(15)]

        def point(i, fraction):
            angle = math.tau * (i % 15) / 15
            radius = radii[i % 15] * fraction
            relief = .008 * (1 - fraction) + .006 * math.sin(3 * angle + fraction * 4) * fraction * (1 - fraction)
            return (.24 * radius * math.cos(angle), .16 * radius * math.sin(angle), relief)
        for i in range(15):
            mesh.face([point(0, 0), point(i, 1 / 3), point(i + 1, 1 / 3)], 'crust_coralline')
            for ring in (1, 2):
                a, b = ring / 3, (ring + 1) / 3
                mesh.face([point(i, a), point(i, b), point(i + 1, b), point(i + 1, a)], 'crust_coralline')
    return mesh


def clump_park(serial):
    return (-5.0 + .8 * serial, 2.0, PARK_Z + .5)

