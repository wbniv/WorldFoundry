"""Single source of scene placements for both future reef styles.

The x/z proportions follow the plan's 1600 x 900 wide-view mockup. Depth is
authored separately: the camera is in front of the negative-y tank face.
These are design anchors, not physics or identification evidence.
"""
from dataclasses import dataclass
import functools
import math
import random

SEED = 20261102
TANK = (12.0, 6.0, 5.5)


def from_mockup(x, y, depth=0.0):
    """Map mockup points to the inner tank, in world units."""
    return (round((x / 1600.0 - .5) * 11.2, 5), round(depth, 5),
            round(.18 + (900.0 - y) / 900.0 * 4.95, 5))


@dataclass(frozen=True)
class Anchor:
    name: str
    taxon: str
    x: int
    y: int
    depth: float = 0.0

    @property
    def position(self):
        return from_mockup(self.x, self.y, self.depth)


# Dropped unverified blue sea star and ascidian, and sea cucumber at Will's
# request. The unnamed gorgonian and genus-level corals await Phase 0's final
# species/model decisions; do not treat these labels as species identifications.
ANCHORS = (
    Anchor('coralline', 'Corallinales', 230, 610, .5),
    Anchor('flowerpot', 'Goniopora sp.', 175, 500, .4),
    Anchor('cauliflower', 'Pocillopora damicornis', 250, 360, .35),
    # The host colony is at (-3.25, -.82, 3.05); keep the crab on its
    # camera-facing branches rather than buried in the rock behind it.
    Anchor('guard_crab', 'Trapezia cymodoce', 357, 351, -1.12),
    Anchor('humbug_pair', 'Dascyllus aruanus', 335, 250, -.15),
    Anchor('scroll_coral', 'Turbinaria sp.', 470, 455, .5),
    Anchor('feather_duster', 'Sabellastarte sp.', 520, 560, .15),
    Anchor('zoanthids', 'Zoanthus sp.', 330, 610, .1),
    Anchor('nudibranch', 'Phyllidia varicosa', 260, 690, -.25),
    Anchor('mushroom_coral', 'Fungiidae', 520, 835, -.8),
    Anchor('sea_fan_left', 'gorgonian', 100, 400, 1.0),
    Anchor('leather_coral', 'Sarcophyton sp.', 760, 380, .7),
    Anchor('cup_coral', 'Tubastraea coccinea', 790, 540, .65),
    Anchor('cleaner_station', 'Stenopus hispidus', 700, 590, -.15),
    Anchor('boulder_coral', 'Porites lutea', 680, 760, .0),
    Anchor('tree_worms', 'Spirobranchus sp.', 775, 715, -.15),
    Anchor('feather_star', 'Lamprometra palmata', 930, 380, .3),
    Anchor('boxfish_spawn', 'Ostracion cubicus', 900, 290, -.5),
    Anchor('table_coral', 'Acropora sp.', 1290, 360, .45),
    Anchor('giant_clam', 'Tridacna squamosa', 1060, 805, -.9),
    Anchor('hermit_crab', 'Dardanus lagopodes', 985, 852, -1.0),
    Anchor('barrel_sponge', 'Xestospongia testudinaria', 1480, 650, .5),
)

ROCK_MASSES = {
    'left': ((300,650,230,170),(210,560,130,120),(390,545,140,110),
             (300,470,120,90),(470,660,120,110)),
    'right': ((1250,630,230,170),(1340,520,140,130),(1170,560,130,110),
              (1260,445,110,90),(1430,670,120,120)),
    'arch': ((640,670,90,115),(985,660,95,120),(810,478,250,52),
             (700,452,70,40),(925,448,85,45)),
}


# The two lobes of the Porites boulder: centre, radii. corals.hard_corals
# builds them and worm_mouths() places the Christmas tree worms on them.
PORITES_LOBES = (((-2.75, -.78, 1.75), (.72, .48, .43)),
                 ((-2.25, -.72, 1.88), (.42, .40, .34)))
WORM_COUNT = 15
WORM_SEED = 20261108
WORM_MORPHS = 8
# Scroll coral (corals.soft_corals) stands in front of the small lobe's right
# side; worms there would be hidden behind its plates.
_SCROLL_LEFT_EDGE_X = -2.32


def porites_relief(u):
    """Radial growth-contour factor for a unit-sphere direction u."""
    return (1 + .055 * math.sin(7*u[0]+4*u[2])*math.cos(5*u[1]-2*u[2])
            + .025 * math.sin(13*u[0]+7*u[1]+3*u[2]))


def porites_point(lobe, theta, phi):
    """Surface point of a relief-displaced lobe at sphere angles theta, phi."""
    (c, r) = PORITES_LOBES[lobe]
    u = (math.sin(phi) * math.cos(theta), math.sin(phi) * math.sin(theta), math.cos(phi))
    k = porites_relief(u)
    return tuple(c[i] + r[i] * u[i] * k for i in range(3))


def _unit(v):
    m = math.sqrt(sum(x * x for x in v))
    return tuple(x / m for x in v)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def porites_normal(lobe, theta, phi, h=1e-4):
    """Outward unit normal of the displaced lobe surface (numerical)."""
    p = porites_point(lobe, theta, phi)
    dt = [a - b for a, b in zip(porites_point(lobe, theta + h, phi), p)]
    dp = [a - b for a, b in zip(porites_point(lobe, theta, phi + h), p)]
    n = _unit(_cross(dp, dt))
    c = PORITES_LOBES[lobe][0]
    if sum(n[i] * (p[i] - c[i]) for i in range(3)) < 0:
        n = tuple(-x for x in n)
    return n


def inside_lobe(lobe, p, margin=1.0):
    (c, r) = PORITES_LOBES[lobe]
    return sum(((p[i] - c[i]) / r[i]) ** 2 for i in range(3)) < margin


@functools.lru_cache(maxsize=None)
def worm_mouths():
    """Tube mouths of the Christmas tree worms, one dict per worm.

    Seeded dart throwing on the two Porites lobes. A mouth is kept when its
    outward normal faces the camera (n.y <= -0.35), faces up (n.z >= 0.3)
    and is not on a steep flank (|n.x| <= 0.55), it is not buried in the
    other lobe, it is clear of the scroll coral, and it is at least 0.14 from every other mouth. Crown axis =
    normalize(n + 0.7 up), so crowns lean toward the light. Morphs are
    assigned greedily so a worm never shares a morph with its 3 nearest
    neighbours. Returns a tuple of dicts: surface, mouth, normal, axis, size,
    morph.
    """
    rng = random.Random(WORM_SEED)
    worms = []
    tries = 0
    while len(worms) < WORM_COUNT:
        tries += 1
        if tries > 200000:
            raise RuntimeError('could not place every worm mouth')
        lobe = 0 if rng.random() < .72 else 1
        theta = rng.uniform(0, math.tau)
        phi = math.acos(rng.uniform(-1, 1))
        p = porites_point(lobe, theta, phi)
        n = porites_normal(lobe, theta, phi)
        if n[1] > -.35 or n[2] < .3 or abs(n[0]) > .55 or p[0] > _SCROLL_LEFT_EDGE_X:
            continue
        if inside_lobe(1 - lobe, p, 1.03):
            continue
        if any(math.dist(p, w['surface']) < .14 for w in worms):
            continue
        axis = _unit((n[0], n[1], n[2] + .7))
        worms.append({'surface': p, 'mouth': tuple(p[i] + .005 * n[i] for i in range(3)),
                      'normal': n, 'axis': axis, 'size': round(rng.uniform(.85, 1.2), 4),
                      'lobe': lobe})
    counts = [0] * WORM_MORPHS
    nearest = [set(sorted(range(len(worms)), key=lambda j: math.dist(w['surface'], worms[j]['surface']))[1:4])
               for w in worms]
    for i, w in enumerate(worms):
        # Symmetric: avoid every worm that is near i, or that has i near it.
        near = nearest[i] | {j for j in range(len(worms)) if i in nearest[j]}
        taken = {worms[j]['morph'] for j in near if 'morph' in worms[j]}
        choice = min((m for m in range(WORM_MORPHS) if m not in taken), key=lambda m: (counts[m], m))
        w['morph'] = choice
        counts[choice] += 1
    return tuple(worms)


def worm_origin():
    """WormCrowns actor position: the centroid of the worm mouths."""
    mouths = [w['mouth'] for w in worm_mouths()]
    return tuple(round(sum(m[i] for m in mouths) / len(mouths), 5) for i in range(3))


def anchor_map():
    anchors = {a.name: a.position for a in ANCHORS}
    # The worms are placed by worm_mouths(), not by the mockup anchor.
    anchors['tree_worms'] = worm_origin()
    return anchors
