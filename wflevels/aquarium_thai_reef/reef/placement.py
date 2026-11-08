"""Where attached reef life sits: one table, resolved against the host
surfaces at export (plan W3). Nothing here runs in the game.

Every sessile animal, coral or crust that should touch rock or sand is
listed with an authored hint and a host. resolve() turns the hint into a
surface point and normal (reef.surface); builders and generate.py place
things from the result, and actor-map.json records it. Distances are world
units (1 unit = 1 m at the tank's x10 scale = 10 cm real).
"""
import functools
import math

from .surface import SAND_Z, ray_rock, rock_normal

UP = (0.0, 0.0, 1.0)


def _unit(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


# No rock comes further forward than y = -0.6 (the exported masses reach
# -0.56), so camera-side rays start at -1.0.
FACE_RAY_START_Y = -1.0


@functools.lru_cache(maxsize=None)
def on_rock_face(x, z, y_start=FACE_RAY_START_Y):
    """First rock surface seen from the camera side at (x, z): (point, normal)."""
    hit = ray_rock((x, y_start, z), (0, 1, 0), max_distance=3.0, step=.02)
    if hit is None:
        raise ValueError(f'no rock at x={x} z={z}')
    return hit[0], rock_normal(hit[0])


@functools.lru_cache(maxsize=None)
def on_rock_top(x, y_hint, min_up=.6, reach=1.4, step=.02):
    """Front-most upward-facing rock top at x, scanning back from y_hint.
    Returns (point, normal) where the normal's z is at least min_up."""
    y = y_hint
    while y < y_hint + reach:
        hit = ray_rock((x, y, 3.4), (0, 0, -1), max_distance=2.7, step=.02)
        if hit is not None and hit[0][2] > SAND_Z + .05:
            n = rock_normal(hit[0])
            if n[2] >= min_up:
                return hit[0], n
        y += step
    raise ValueError(f'no upward rock top behind x={x} y={y_hint}')


def on_sand(x, y):
    return (x, y, SAND_Z), UP


def frame(axis):
    """Orthonormal (e1, e2, axis) with e1 roughly along world x."""
    axis = _unit(axis)
    ref = (1.0, 0.0, 0.0) if abs(axis[0]) < .9 else (0.0, 1.0, 0.0)
    e2 = _unit((axis[1]*ref[2]-axis[2]*ref[1], axis[2]*ref[0]-axis[0]*ref[2], axis[0]*ref[1]-axis[1]*ref[0]))
    e1 = (e2[1]*axis[2]-e2[2]*axis[1], e2[2]*axis[0]-e2[0]*axis[2], e2[0]*axis[1]-e2[1]*axis[0])
    return e1, e2, axis


def grow_axis(normal, up_bias=.3):
    """Direction attached life grows: out of the surface, leaning up."""
    return _unit((normal[0], normal[1], normal[2] + up_bias))


# Upright actors: (host, x, y hint). Their position is the surface point
# minus the builder's lowest local point, sunk by SINK so the base meets the
# voxel-remeshed rock (which differs from the analytic surface by about 1 cm).
SINK = .03
UPRIGHT = {
    'FlowerpotCoral': ('rock_top', -4.15, -.85),
    'SeaFan': ('rock_top', -4.45, -.55),
    'LeatherCoral': ('rock_top', 4.0, -.72),
    'FeatherStar': ('rock_top', 1.75, -.35),
    'FeatherDusters': ('rock_top', -1.96, -.4),
    'GiantClam': ('sand', 1.82, -1.15),
    'HermitCrab': ('sand', 1.295, -1.0),
    'BarrelSponge': ('rock_top', 4.75, -.72),
    'MushroomCoral': ('sand', -2.1, -1.0),
    'PocilloporaHead': ('rock_top', -3.25, -.82),
    'TableCoral': ('rock_top', 3.25, -.72),
}
# Static corals built inline by corals.hard_corals: their lowest local point
# does not depend on the random branch draws (the cauliflower head's base
# ellipsoid bottom; the table coral's stalk end).
HOST_LOCAL_MIN = {'PocilloporaHead': -.32 - .19, 'TableCoral': -.65}
# Where the cauliflower head was authored; its residents (the guard crab and
# the humbug pair) move with it, so every crab and humbug distance survives.
POCILLOPORA_AUTHORED = (-3.25, -.82, 3.05)


@functools.lru_cache(maxsize=None)
def coral_centre(name):
    return upright_position(name, HOST_LOCAL_MIN[name])


def host_shift():
    """How far the cauliflower head moved from where it was authored."""
    c = coral_centre('PocilloporaHead')
    return tuple(round(c[i] - POCILLOPORA_AUTHORED[i], 5) for i in range(3))
# Extra sink beyond SINK: the giant clam's valves are buried to 40 % of their
# 0.13 height (0.052 in all); the mushroom coral rests on the sand surface.
EXTRA_SINK = {'GiantClam': .022, 'MushroomCoral': -.02}


@functools.lru_cache(maxsize=None)
def surface_for(name):
    host, x, y = UPRIGHT[name]
    return on_rock_top(x, y) if host == 'rock_top' else on_sand(x, y)


def upright_position(name, local_min_z):
    """World position for an upright builder whose lowest local z is local_min_z."""
    (px, py, pz), _ = surface_for(name)
    return (round(px, 5), round(py, 5), round(pz - local_min_z - SINK - EXTRA_SINK.get(name, 0.0), 5))


# Moving animals on sand: the nudibranch crawls along the foot of the left
# rock (the rock tops are too lumpy and steep for an untilted slug), and the
# cleaner shrimp wait on the cave floor under the arch.
NUDIBRANCH_PATH = {'x': -4.0, 'y': -.75, 'amplitude': .32}
CLEANER_STATION_XY = (-.7, -.15)


def _local_min_z(name):
    """Lowest local z of an actor's builder at the origin (lazy imports)."""
    from mesh import Mesh
    from . import corals, invertebrates, life, sponges
    builders = {'FlowerpotCoral': corals.flowerpot, 'SeaFan': life._sea_fan,
                'LeatherCoral': corals.leather_coral, 'FeatherStar': life._feather_star,
                'FeatherDusters': life.feather_dusters, 'GiantClam': life._clam,
                'HermitCrab': invertebrates.hermit_crab, 'MushroomCoral': life._mushroom_coral,
                'Nudibranch': life._nudibranch, 'Shrimp': invertebrates.banded_shrimp}
    m = Mesh('local')
    if name == 'BarrelSponge':
        sponges.populate(m, (0, 0, 0))
    else:
        builders[name](m, (0, 0, 0))
    return min(v[2] for v in m.vertices)


@functools.lru_cache(maxsize=None)
def actor_position(name):
    """Resolved world position of an attached or ground-dwelling actor."""
    if name == 'Nudibranch':
        p = NUDIBRANCH_PATH
        return (p['x'], p['y'], round(SAND_Z - _local_min_z('Nudibranch') - .004, 5))
    if name == 'Shrimp':
        x, y = CLEANER_STATION_XY
        return (x, y, round(SAND_Z - _local_min_z('Shrimp') - .01, 5))
    return upright_position(name, _local_min_z(name))


# anchor name -> actor whose resolved position it reports
ANCHOR_ACTORS = {'flowerpot': 'FlowerpotCoral', 'sea_fan_left': 'SeaFan',
                 'leather_coral': 'LeatherCoral', 'feather_star': 'FeatherStar',
                 'feather_duster': 'FeatherDusters', 'giant_clam': 'GiantClam',
                 'hermit_crab': 'HermitCrab', 'barrel_sponge': 'BarrelSponge',
                 'mushroom_coral': 'MushroomCoral', 'nudibranch': 'Nudibranch',
                 'cleaner_station': 'Shrimp'}
