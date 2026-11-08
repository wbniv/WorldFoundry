"""Prototype of W3b: seeded, clustered placement of attached reef life.

Design mock-up for the plan, not production code. Ports the Planted Tank's
founder-and-lineage colony scheme (wfsource/source/game/plant_growth.h,
colonies()) from the sand plane onto the rock face: founders are seeded at
random over the camera-facing rock, then each lineage grows by short steps
from a random existing member, with heading jitter, per-kind step sizes and
a crowding radius. Every member is resolved on the rock (reef.placement) and
built with the production builders, so the renders show real geometry.

Distances are world units (1 unit = 1 m at the tank's x10 scale).
"""
import math

from reef import life
from reef.placement import grow_axis, on_rock_face
from reef.scene import PORITES_LOBES, worm_mouths

# kind: founders, members, step range, crowding radius
KINDS = {
    'zoanthid': (4, 100, (.07, .13), .075),
    'cup': (6, 22, (.10, .22), .10),
    'crust': (7, 12, (.30, .55), .32),
}
# Keep clear of the worm boulder, the coral-head base, the cave and the
# cleaner station (the fish's route through the arch).
EXCLUDE = [((-2.75, 1.75), .85), ((-3.25, 2.7), .45), ((0.0, 1.6), 1.05)]


class Random:
    """The Planted Tank's LCG (plant_growth.h), for the same feel."""
    def __init__(self, seed):
        self.value = (seed ^ 0xa511e9b3) & 0xffffffff

    def unit(self):
        self.value = (self.value * 1664525 + 1013904223) & 0xffffffff
        return (self.value >> 8) / 16777216.0

    def between(self, a, b):
        return a + (b - a) * self.unit()


def _usable(x, z):
    if any(math.hypot(x - cx, z - cz) < r for (cx, cz), r in EXCLUDE):
        return None
    try:
        point, normal = on_rock_face(round(x, 3), round(z, 3))
    except ValueError:
        return None
    # Camera-facing and not an overhang underside.
    if normal[1] > -.25 or normal[2] < -.35:
        return None
    if any(math.dist(point, w['surface']) < .12 for w in worm_mouths()):
        return None
    return point, normal


def colonies(seed):
    """{kind: [(x, z, point, normal, lineage)]} for one seed."""
    r = Random(seed)
    out = {}
    taken = []
    for kind, (founders, members, (step_lo, step_hi), crowd) in KINDS.items():
        shoots = []
        tries = 0
        while len(shoots) < founders and tries < 4000:
            tries += 1
            x, z = r.between(-4.9, 4.9), r.between(.95, 2.7)
            hit = _usable(x, z)
            if hit and all(math.hypot(x - s[0], z - s[1]) > 4 * crowd for s in shoots) \
                    and all(math.hypot(x - s[0], z - s[1]) > crowd for s in taken):
                shoots.append((x, z, hit[0], hit[1], len(shoots), r.between(0, math.tau)))
        attempts = 0
        while shoots and len(shoots) < members and attempts < 6000:
            attempts += 1
            p = shoots[int(r.unit() * len(shoots))]
            heading = p[5] + r.between(-1.25, 1.25)
            step = r.between(step_lo, step_hi)
            x, z = p[0] + math.cos(heading) * step, p[1] + math.sin(heading) * step * .75
            if any(math.hypot(x - s[0], z - s[1]) < crowd for s in shoots + taken):
                continue
            hit = _usable(x, z)
            if hit:
                shoots.append((x, z, hit[0], hit[1], p[4], heading))
        out[kind] = shoots
        taken += shoots
    return out


def populate(mesh, seed):
    """life.populate's attached colonies, scattered by colonies(seed); the
    mushroom coral and arch cups stay where W3 put them."""
    from mesh import Mesh
    found = colonies(seed)
    for i, (x, z, point, normal, lineage, heading) in enumerate(found['zoanthid']):
        base = tuple(point[k] - .01 * normal[k] for k in range(3))
        life._placed(mesh, lambda m, i=i: life._zoanthid_polyp(m, i), base, grow_axis(normal, .3), spin=heading)
    for i, (x, z, point, normal, lineage, heading) in enumerate(found['cup']):
        base = tuple(point[k] - .015 * normal[k] for k in range(3))
        life._placed(mesh, lambda m, i=i: life._cup(m, (0, 0, 0), .065, .10 + .02 * (i % 3), 'sponge', 8),
                     base, grow_axis(normal, .3), spin=heading)
    for i, (x, z, point, normal, lineage, heading) in enumerate(found['crust']):
        rx, rz = .14 + .1 * ((i * 7) % 5) / 4, .09 + .06 * ((i * 3) % 4) / 3
        life._encrusting_patch(mesh, (x, 0, z), rx, rz, 'sponge' if lineage % 2 else 'coralline')
    local = Mesh('local')
    life._mushroom_coral(local, (0, 0, 0))
    from reef.placement import upright_position
    life._mushroom_coral(mesh, upright_position('MushroomCoral', min(v[2] for v in local.vertices)))
    return {k: len(v) for k, v in found.items()}
