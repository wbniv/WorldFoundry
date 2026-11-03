"""Static, source-led Gulf reef invertebrate blockout forms."""
import math
import random

from .scene import SEED, anchor_map


def _cup(mesh, center, radius, height, color, sides=12):
    x, y, z = center
    outer = []
    inner = []
    for i in range(sides):
        a = math.tau * i / sides
        r = radius * (1 + .08 * math.sin(5 * a))
        outer.append((x + r * math.cos(a), y + r * math.sin(a), z + height))
        inner.append((x + .66 * r * math.cos(a), y + .66 * r * math.sin(a), z + height * .72))
    for i in range(sides):
        a = math.tau * i / sides
        nxt = (i + 1) % sides
        low_a = (x + radius * .5 * math.cos(a), y + radius * .5 * math.sin(a), z)
        low_b = (x + radius * .5 * math.cos(math.tau * nxt / sides),
                 y + radius * .5 * math.sin(math.tau * nxt / sides), z)
        mesh.face([low_a, low_b, outer[nxt], outer[i]], color)
        mesh.face([outer[i], outer[nxt], inner[nxt], inner[i]], 'polyp')


def _sea_fan(mesh, base):
    x, y, z = base
    rng = random.Random(SEED + 401)
    crown = (x, y, z + 1.35)
    mesh.swept_tube([(x, y, z - .3), (x, y, z + .5), crown], .035, 'coralline', 6)
    for side in (-1, 1):
        for j in range(7):
            h = .22 + j * .16
            span = .12 + j * .045
            start = (x, y, z + h)
            tip = (x + side * span, y, z + h + .34 + rng.uniform(-.04, .04))
            mid = (x + side * span * .5, y, z + h + .2)
            mesh.swept_tube([start, mid, tip], .018, 'coralline', 5)
            if j in (2, 4, 6):
                for twig_side in (-1, 1):
                    branch = (tip[0] + twig_side * .14, y,
                              tip[2] + .11 + rng.uniform(-.03, .03))
                    mesh.swept_tube([mid, tip, branch], .012, 'coralline', 4)


def _clam(mesh, center):
    x, y, z = center
    # Fluted, pale valves open around the vivid blue mantle.  The ribs fan
    # from the low hinge, with a scalloped edge instead of stacked ellipsoids.
    steps = 20
    for side in (-1, 1):
        def section(i):
            t = -1 + 2*i/steps
            span = math.sqrt(max(0, 1-t*t))
            px = x + .43*t
            scallop = 1 + .10*math.cos(i*math.pi)
            return ((px, y, z),
                    (px, y + side*.15*span, z + .035*span),
                    (px, y + side*.30*span*scallop, z + .13*span))
        for i in range(steps):
            a, b = section(i), section(i+1)
            for band in range(2):
                points = [a[band], b[band], b[band+1], a[band+1]]
                mesh.face(points if side < 0 else list(reversed(points)), 'sand')
        for i in range(1, steps, 2):
            a, b, c = section(i)
            mesh.swept_tube([a, b, c], .008, 'sand', 4)
    center_point = (x, y, z + .125)
    edge = []
    for i in range(24):
        angle = math.tau*i/24
        wave = 1 + .09*math.sin(8*angle)
        edge.append((x + .36*math.cos(angle), y + .205*wave*math.sin(angle),
                     z + .13 + .025*math.sin(8*angle)))
    for i, point in enumerate(edge):
        mesh.face([center_point, point, edge[(i+1) % len(edge)]], 'clam')


def _zoanthids(mesh, center):
    x, y, z = center
    rng = random.Random(SEED + 402)
    for i in range(34):
        a = i * 2.399963
        r = .08 + .31 * math.sqrt((i + .5) / 34)
        px, py = x + r * math.cos(a), y + r * math.sin(a) * .62
        pz = z + .035 * math.sin(i * 2.1)
        mesh.swept_tube([(px, py, pz), (px, py, pz + .09)], .018, 'zoanthid', 6)
        mesh.ellipsoid((px, py, pz + .11), (.052, .048, .025), 'zoanthid', 7, 4)
        mesh.ellipsoid((px, py, pz + .13), (.022, .020, .009), 'polyp', 6, 3)


def worm_centers(center, count=15):
    x, y, z = center
    result = []
    for worm in range(count):
        col, row = worm % 5, worm // 5
        wx = x + (col - 2) * .25 + .03 * math.sin(worm * 2.3)
        wy = y - .025 * row
        wz = z + (row - 1) * .24 + .03 * math.sin(worm * 1.7)
        result.append((wx, wy, wz))
    return result


def _worm_crowns(mesh, center, count=15, ranges=None):
    for worm, (wx, wy, wz) in enumerate(worm_centers(center, count)):
        start = len(mesh.vertices)
        mesh.swept_tube([(wx, wy, wz - .08), (wx, wy, wz + .04)], .018, 'sand', 6)
        # Two small, tiered conical plumes per worm. Their jagged fringes
        # suggest the spiral radioles without overlapping adjacent crowns.
        for side in (-1, 1):
            cx = wx + side * .045
            for tier in range(5):
                z0 = wz + .025 + tier*.033
                z1 = z0 + .014
                width = .052 * (1 - tier/6)
                upper = width * .52
                mesh.face([(cx-width, wy-.025, z0), (cx+width, wy-.025, z0),
                           (cx+upper, wy-.025, z1), (cx-upper, wy-.025, z1)],
                          ('polyp', 'coralline', 'sponge')[worm % 3])
        if ranges is not None:
            ranges.append((start, len(mesh.vertices)))


def _feather_star(mesh, center):
    x, y, z = center
    mesh.ellipsoid((x, y, z), (.14, .12, .09), 'coralline', 12, 6)
    # Lamprometra palmata has 27–41 arms in the cited description; model 30.
    for arm in range(30):
        a = math.pi * (.06 + .88 * arm / 29)
        points = []
        for j in range(5):
            t = j / 4
            radius = .12 + (.60 + .11 * math.sin(arm * 2.1)) * t
            points.append((x + radius * math.cos(a + .08 * math.sin(t * math.pi)),
                           y + .06 * math.sin(a) * t,
                           z + radius * math.sin(a) + .10 * math.sin(t * math.pi)))
        mesh.swept_tube(points, .013, 'coralline', 5)
        for j in range(1, 5):
            p = points[j]
            t = j / 5
            for sign in (-1, 1):
                tip = (p[0] - sign * .10 * math.sin(a), p[1],
                       p[2] + sign * .10 * math.cos(a) + .035 * t)
                mesh.swept_tube([p, tip], .006, 'polyp', 4)


def _mushroom_coral(mesh, center):
    x, y, z = center
    mesh.ellipsoid((x, y, z), (.47, .32, .075), 'coralline', 24, 6)
    for i in range(16):
        a = math.tau * i / 16
        end = (x + .43 * math.cos(a), y + .29 * math.sin(a), z + .025)
        mesh.swept_tube([(x, y, z + .02), end], .009, 'polyp', 4)


def _nudibranch(mesh, center):
    x, y, z = center
    mesh.ellipsoid((x, y, z), (.31, .16, .10), 'zoanthid', 16, 8)
    mesh.ellipsoid((x - .23, y, z + .055), (.12, .105, .10), 'polyp', 10, 6)
    for i in range(13):
        t = i / 12
        px = x - .2 + .42 * t
        py = y + .10 * math.sin(t * math.pi * 2)
        pz = z + .09 + .035 * math.sin(t * math.pi)
        mesh.swept_tube([(px, py, pz), (px, py, pz + .12)], .018, 'polyp', 5)
        mesh.ellipsoid((px, py, pz + .13), (.033, .033, .046), 'polyp', 6, 4)
    for side in (-1, 1):
        mesh.swept_tube([(x-.28,y,z+.12),(x-.31,y+side*.05,z+.24)], .012, 'clam', 4)


def _humbug(mesh, center, scale=1.0):
    """A small three-bar humbug silhouette, facing right."""
    x, y, z = center
    mesh.ellipsoid((x, y, z), (.43*scale, .17*scale, .27*scale), 'sand', 18, 10)
    # Three dark vertical bars wrap around the white body as narrow ellipsoids.
    for offset in (-.20, .02, .23):
        mesh.ellipsoid((x+offset*scale, y-.012*scale, z),
                       (.065*scale, .177*scale, .275*scale), 'rock', 10, 7)
    mesh.face([(x+.38*scale,y,z), (x+.67*scale,y,z+.23*scale),
               (x+.67*scale,y,z-.23*scale)], 'sand')
    for dz in (-.10, .10):
        mesh.face([(x-.04*scale,y,z+dz), (x+.14*scale,y,z+dz+.19*scale),
                   (x+.23*scale,y,z+dz)], 'polyp')
    mesh.ellipsoid((x-.31*scale,y-.15*scale,z+.095*scale),
                   (.035*scale,.025*scale,.035*scale), 'clam', 8, 5)


def _juvenile_boxfish(mesh, center):
    """Bright juvenile yellow boxfish, with the characteristic dark spots."""
    x, y, z = center
    # A compact, deep body and squared-off snout read as Ostracion rather than
    # a generic streamlined fish even at the wide tank camera distance.
    mesh.ellipsoid((x,y,z), (.39,.27,.34), 'fish', 16, 10)
    mesh.face([(x+.30,y,z+.14), (x+.56,y,z+.20), (x+.50,y,z-.18),
               (x+.30,y,z-.14)], 'clam')
    mesh.face([(x-.34,y,z), (x-.62,y,z+.20), (x-.60,y,z-.20)], 'fish')
    mesh.face([(x-.06,y-.20,z-.05), (x+.15,y-.30,z-.20),
               (x+.25,y-.17,z-.11)], 'polyp')
    # A regular spot pattern is intentionally separate from atlas noise so the
    # juvenile's black spots remain legible from the gameplay camera.
    for sx in (-.20,-.04,.12,.25):
        for sz in (-.19,-.04,.12,.24):
            if (sx,sz) in ((-.20,-.19),(.25,.24)):
                continue
            mesh.ellipsoid((x+sx,y-.247,z+sz),(.027,.012,.027),'rock',7,4)
    mesh.ellipsoid((x+.28,y-.235,z+.08),(.035,.018,.035),'rock',8,5)


def populate(mesh):
    """Add visible static colonies; dynamic animals are authored separately."""
    a = anchor_map()
    _clam(mesh, (a['giant_clam'][0], -1.15, .82))
    _zoanthids(mesh, (-3.55, -1.25, 1.55))
    _zoanthids(mesh, (2.0, -1.05, 1.55))
    _zoanthids(mesh, (4.0, -.95, 1.70))
    # Small orange cup-coral clusters occupy the exposed faces and cave edge.
    # They share the static life mesh instead of consuming individual actors.
    for x, y, z in ((-4.4,-1.2,1.18), (-3.6,-1.25,1.25), (-1.9,-1.15,1.5),
                    (1.75,-1.15,1.5), (3.1,-1.22,1.22), (4.4,-1.1,1.34)):
        for i in range(3):
            _cup(mesh, (x + (i-1)*.11, y, z + .025*(i % 2)),
                 .065, .10 + .02*i, 'sponge', 8)
    # Encrusting sponge and coralline form irregular crusts on the exposed
    # rock, rather than circular objects sitting in front of it.
    for x, y, z, rx, rz, color in (
        (-4.55,-.90,1.35,.25,.16,'sponge'), (-3.8,-1.0,2.00,.22,.14,'coralline'),
        (-3.05,-1.05,1.25,.27,.14,'sponge'), (-2.0,-.92,2.55,.20,.12,'coralline'),
        (1.7,-.90,1.20,.23,.15,'sponge'), (2.35,-1.0,2.20,.20,.14,'coralline'),
        (3.25,-1.0,1.22,.27,.14,'sponge'), (4.4,-.90,2.15,.22,.13,'coralline'),
    ):
        rng = random.Random(SEED + round((x + 6) * 1000) + round(z * 100))
        edge = []
        for i in range(15):
            angle = math.tau * i / 15
            radius = rng.uniform(.65, 1.2)
            edge.append((x + rx * radius * math.cos(angle), y - .07,
                         z + rz * radius * math.sin(angle)))
        for i, point in enumerate(edge):
            mesh.face([(x, y - .085, z), point, edge[(i + 1) % len(edge)]], color)
    _mushroom_coral(mesh, (-2.1, -1.0, .86))
    for i in range(6):
        angle = math.tau * i / 6
        center = (.72 + .22 * math.cos(angle), -.8 + .12 * math.sin(angle), 2.25)
        _cup(mesh, center, .12, .19 + .04 * (i % 2), 'coralline', 10)
