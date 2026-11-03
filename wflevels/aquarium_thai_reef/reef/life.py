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
    # Two fluted valves cradle the vivid, scalloped mantle.
    mesh.ellipsoid((x, y, z), (.44, .31, .11), 'clam', 20, 7)
    mesh.ellipsoid((x, y - .015, z + .14), (.36, .25, .11), 'clam', 20, 7)
    mesh.ellipsoid((x, y - .025, z + .2), (.30, .205, .055), 'clam', 18, 6)
    for side in (-1, 1):
        for i in range(7):
            t = (i / 6 - .5) * 1.45
            end = (x + side * (.16 + .16 * math.cos(t)),
                   y - .02, z + .16 + .13 * math.sin(t))
            mesh.swept_tube([(x, y, z + .04), end], .012, 'sand', 4)


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


def _worm_crowns(mesh, center, count=3):
    x, y, z = center
    for worm in range(count):
        wx = x + (worm - (count - 1) / 2) * .23
        wz = z + .08 * (worm % 2)
        mesh.swept_tube([(wx, y, wz - .15), (wx, y, wz + .16)], .028, 'sand', 6)
        # Paired spiral plumes read as feather crowns at tank distance.
        for side in (-1, 1):
            points = []
            for step in range(13):
                t = step / 12
                angle = t * math.pi * 2.5
                points.append((wx + side * (.035 + .16 * t) * math.cos(angle),
                              y + .10 * t * math.sin(angle), wz + .15 + .34 * t))
            mesh.swept_tube(points, .016, 'polyp', 5)
            for j in range(1, 7):
                t = j / 7
                p = points[int(t * 12)]
                for sign in (-1, 1):
                    tip = (p[0] + sign * .075, p[1], p[2] + .055)
                    mesh.swept_tube([p, tip], .008, 'coralline', 4)


def _feather_star(mesh, center):
    x, y, z = center
    mesh.ellipsoid((x, y, z), (.14, .12, .09), 'coralline', 12, 6)
    for arm in range(10):
        a = math.tau * arm / 10
        points = []
        for j in range(5):
            t = j / 4
            radius = .12 + .72 * t
            points.append((x + radius * math.cos(a + .08 * math.sin(t * math.pi)),
                           y + .10 * math.sin(a) * t,
                           z + .10 * math.sin(t * math.pi)))
        mesh.swept_tube(points, .025, 'coralline', 5)
        for j in range(1, 8):
            p = points[min(3, j // 2)]
            t = j / 8
            for sign in (-1, 1):
                tip = (p[0] - sign * .15 * math.sin(a),
                       p[1] + sign * .12 * math.cos(a), p[2] + .035 + .05 * t)
                mesh.swept_tube([p, tip], .008, 'polyp', 4)


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
    _sea_fan(mesh, (-4.45, -.55, 2.82))
    _clam(mesh, (a['giant_clam'][0], -1.15, .82))
    _zoanthids(mesh, (-3.55, -1.25, 1.55))
    _nudibranch(mesh, (-4.0, -1.65, 1.05))
    _worm_crowns(mesh, (-1.9, -.95, 2.0), 3)
    _feather_star(mesh, (1.75, -.35, 2.8))
    _mushroom_coral(mesh, (-2.1, -1.0, .86))
    for i in range(6):
        angle = math.tau * i / 6
        center = (.72 + .22 * math.cos(angle), -.8 + .12 * math.sin(angle), 2.25)
        _cup(mesh, center, .12, .19 + .04 * (i % 2), 'coralline', 10)
    # Static first-pass fish geometry. Separate mesh actors and their movement,
    # reactions and controller are still required by the next reef phases.
    _humbug(mesh, (-3.05, -1.8, 4.12), .78)
    _humbug(mesh, (-3.62, -1.45, 3.82), .70)
    _juvenile_boxfish(mesh, (1.62, -1.9, 3.62))
