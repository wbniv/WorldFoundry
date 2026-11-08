"""Analytic host surfaces of the reef, for placing things on them (plan W3).

The rock masses are the same seeded, wobbled ellipsoids rockscape.py builds
(the exported rock is their voxel union, within about half a voxel); the
arch lintel is its swept tube; the sand is the shell's top plane. Ray casts
here resolve placements at export time: nothing scans for surfaces at run time.

Distances are world units (1 unit = 1 m at the tank's x10 scale = 10 cm real).
"""
import functools
import math
import random

from .scene import ROCK_MASSES, SEED, from_mockup

SAND_Z = .72
ARCH_RADIUS = .36


def _wobble(theta, phi, phase):
    return (1 + .12 * math.sin(3 * theta + phase) * math.sin(phi)
            + .075 * math.cos(5 * theta - 2 * phi + phase)
            + .045 * math.sin(8 * theta + 3 * phi)
            + .025 * math.sin(11 * theta - 5 * phi + phase))


@functools.lru_cache(maxsize=None)
def rock_blobs():
    """(group, centre, radii, phase) for every rock blob, as rockscape builds them."""
    out = []
    for group, group_seed in (('left', 11), ('right', 23), ('arch', 37)):
        rng = random.Random(SEED + group_seed)
        masses = ROCK_MASSES[group]
        if group == 'arch':
            masses = masses[:2] + masses[3:]
        for x, y, rx, ry in masses:
            centre = from_mockup(x, y, .5)
            radii = (rx / 1600 * 11.2, .48 + rx / 500, ry / 900 * 4.95)
            out.append((group, centre, radii, rng.uniform(0, math.tau)))
    return tuple(out)


@functools.lru_cache(maxsize=None)
def arch_path():
    return tuple(from_mockup(x, y, .15) for x, y in
                 ((625, 665), (680, 520), (760, 430), (855, 430), (945, 520), (1000, 660)))


def _segment_distance(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    t = sum((p[i] - a[i]) * ab[i] for i in range(3)) / sum(c * c for c in ab)
    t = max(0.0, min(1.0, t))
    return math.dist(p, [a[i] + ab[i] * t for i in range(3)])


def rock_inside(p):
    """True when p is inside the rock (any blob, or the arch lintel)."""
    for _, c, r, phase in rock_blobs():
        q = [(p[i] - c[i]) / r[i] for i in range(3)]
        k = math.sqrt(sum(v * v for v in q))
        if k < 1e-9:
            return True
        if k > 1.3:
            continue
        phi = math.acos(max(-1.0, min(1.0, q[2] / k)))
        theta = math.atan2(q[1], q[0])
        if k < _wobble(theta, phi, phase):
            return True
    path = arch_path()
    return any(_segment_distance(p, path[i], path[i + 1]) < ARCH_RADIUS for i in range(len(path) - 1))


def ray_rock(origin, direction, max_distance=8.0, step=.01):
    """First rock hit along a ray: (point, distance) or None."""
    d = math.sqrt(sum(c * c for c in direction))
    direction = [c / d for c in direction]
    if rock_inside(origin):
        return None
    t = 0.0
    while t < max_distance:
        p = [origin[i] + direction[i] * t for i in range(3)]
        if rock_inside(p):
            lo, hi = t - step, t
            for _ in range(20):
                mid = (lo + hi) / 2
                if rock_inside([origin[i] + direction[i] * mid for i in range(3)]):
                    hi = mid
                else:
                    lo = mid
            return tuple(origin[i] + direction[i] * hi for i in range(3)), hi
        t += step
    return None


def rock_field(p):
    """Approximate signed distance to the rock: negative inside."""
    best = 9.0
    for _, c, r, phase in rock_blobs():
        q = [(p[i] - c[i]) / r[i] for i in range(3)]
        k = math.sqrt(sum(v * v for v in q))
        if k < 1e-9:
            return -min(r)
        if k > 2.0:
            continue
        phi = math.acos(max(-1.0, min(1.0, q[2] / k)))
        theta = math.atan2(q[1], q[0])
        best = min(best, (k - _wobble(theta, phi, phase)) * min(r))
    path = arch_path()
    for i in range(len(path) - 1):
        best = min(best, _segment_distance(p, path[i], path[i + 1]) - ARCH_RADIUS)
    return best


def rock_normal(p, h=.01):
    """Outward unit normal at a rock surface point (gradient of rock_field)."""
    g = []
    for axis in range(3):
        a = list(p); b = list(p)
        a[axis] += h; b[axis] -= h
        g.append(rock_field(a) - rock_field(b))
    m = math.sqrt(sum(c * c for c in g)) or 1.0
    return tuple(c / m for c in g)


def rock_gap(p):
    """Distance from p to the rock surface along the cheapest axis ray:
    0 on the surface, positive outside (floating), negative inside."""
    inside = rock_inside(p)
    best = None
    for axis in range(3):
        for sign in (-1, 1):
            direction = [0.0, 0.0, 0.0]
            direction[axis] = sign
            t, step = 0.0, .005
            while t < .6:
                q = [p[i] + direction[i] * t for i in range(3)]
                if rock_inside(q) != inside:
                    best = t if best is None else min(best, t)
                    break
                t += step
    if best is None:
        return -.6 if inside else .6
    return -best if inside else best
