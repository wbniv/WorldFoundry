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
    # A visible oral disc and short radiating tentacles make each cup a live
    # coral polyp instead of an empty faceted vase.
    disc = [(x + .32*radius*math.cos(math.tau*i/sides),
             y + .32*radius*math.sin(math.tau*i/sides), z + height*.75)
            for i in range(sides)]
    mesh.face(disc, 'polyp')
    for i in range(sides):
        angle = math.tau*i/sides
        start = (x + .38*radius*math.cos(angle),y + .38*radius*math.sin(angle),z + height*.78)
        end = (x + .92*radius*math.cos(angle),y + .92*radius*math.sin(angle),z + height*1.12)
        mesh.swept_tube([start,end], .013, 'polyp', 5)


def _sea_fan(mesh, base):
    x, y, z = base
    # Radial primary branches and irregular cross-branches form a broad, open
    # gorgonian fan rather than a single trunk with symmetrical side twigs.
    mesh.swept_tube([(x, y, z-.3), (x, y, z+.05), (x, y, z+.22)], .032, 'coralline', 6)
    spokes = []
    for i in range(13):
        a = math.pi * (.10 + .80 * i / 12)
        reach = 1.06 + .08 * math.sin(i * 2.3)
        points = []
        for j in range(6):
            t = j / 5
            radius = reach * t
            points.append((x + .72 * radius * math.cos(a),
                           y + .045 * math.sin(i * 1.7 + t * 4),
                           z + .18 + radius * math.sin(a)))
        mesh.swept_tube(points, .014 if i % 3 else .019, 'coralline', 5)
        spokes.append(points)
        # Fine split tips break the otherwise perfectly radial outer edge.
        for side in (-1, 1):
            tip = points[-1]
            end = (tip[0] + side*.045*math.sin(a) + .018*math.cos(a),
                   tip[1] + side*.012,
                   tip[2] - side*.045*math.cos(a) + .035*math.sin(a))
            mesh.swept_tube([points[-2],tip,end], .013, 'coralline', 5)
    for i in range(12):
        for j in range(1, 5):
            if (i + j) % 5 == 0:
                continue
            a, b = spokes[i][j], spokes[i+1][j]
            middle = ((a[0]+b[0])/2, (a[1]+b[1])/2 - .012,
                      (a[2]+b[2])/2 + .018 * math.sin(i*3+j))
            mesh.swept_tube([a, middle, b], .013, 'coralline', 4)


def _clam(mesh, center, limb_ranges=None):
    x, y, z = center
    # Fluted, pale valves open around the vivid blue mantle.  The ribs fan
    # from the low hinge, with a scalloped edge instead of stacked ellipsoids.
    steps = 20
    for side in (-1, 1):
        start = len(mesh.vertices)
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
            mesh.swept_tube([a, b, c], .013, 'sand', 4)
        if limb_ranges is not None:
            limb_ranges.append((start, len(mesh.vertices), (x,y,z), (0,side,0), (0,0,1)))
    start = len(mesh.vertices)
    center_point = (x, y, z + .125)
    edge = []
    for i in range(24):
        angle = math.tau*i/24
        wave = 1 + .09*math.sin(8*angle)
        edge.append((x + .36*math.cos(angle), y + .205*wave*math.sin(angle),
                     z + .13 + .025*math.sin(8*angle)))
    for i, point in enumerate(edge):
        mesh.face([center_point, point, edge[(i+1) % len(edge)]], 'clam')
    # Pale mantle markings sit on the blue tissue and follow its oval outline.
    # Their irregular spacing makes the animal read as a patterned clam at the
    # wide tank view without assigning another actor or texture page.
    for row in range(-2, 3):
        for column in range(-4, 5):
            px = .071*column + .009*math.sin(row*2.3+column)
            py = .055*row + .006*math.sin(column*1.8)
            if (px/.32)**2 + (py/.17)**2 > .85:
                continue
            radius = .017 + .003*(1+math.sin(column*3.1+row))/2
            points = [(x+px+radius*math.cos(math.tau*i/8),
                       y+py+radius*math.sin(math.tau*i/8),z+.151)
                      for i in range(8)]
            for i in range(8):
                mesh.face([(x+px,y+py,z+.151),points[i],points[(i+1)%8]], 'fish_white')
    if limb_ranges is not None:
        limb_ranges.append((start, len(mesh.vertices), (x,y,z+.125), (0,1,0), (0,0,1)))


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
        # Short tentacles frame each oral disc instead of a smooth button.
        for tentacle in range(8):
            angle = math.tau*tentacle/8 + i*.17
            start = (px+.034*math.cos(angle),py+.031*math.sin(angle),pz+.125)
            end = (px+.065*math.cos(angle),py+.060*math.sin(angle),
                   pz+.135+.007*math.sin(i+tentacle))
            mesh.swept_tube([start,end], .013, 'zoanthid', 5)


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
                # Individual radioles project from each tier, softening the
                # stacked-strip silhouette while preserving the single rigged
                # crown and its existing per-worm vertex range.
                for direction in (-1, 1):
                    for ray in range(3):
                        root_x = cx + direction*width*(.28 + .24*ray)
                        tip_x = root_x + direction*(.030 + .008*ray)*(1-tier/7)
                        mesh.face([(root_x, wy-.026, z0),
                                   (tip_x, wy-.026, z0+.010),
                                   (root_x+direction*.004, wy-.026, z0+.020)],
                                  ('polyp', 'coralline', 'sponge')[worm % 3])
        if ranges is not None:
            ranges.append((start, len(mesh.vertices)))


def feather_dusters(mesh, center, ranges=None):
    """Four banded fan worms, with independently retractable crowns."""
    x, y, z = center
    for worm in range(4):
        cx, cy, cz = x + (worm-1.5)*.42, y, z + (worm % 2)*.12
        begin = len(mesh.vertices)
        mesh.swept_tube([(cx,cy,cz-.24),(cx,cy,cz+.02)], .035, 'sand', 6)
        for ray in range(19):
            angle = math.pi * (.04 + .92*ray/18)
            outer = (cx+.25*math.cos(angle), cy, cz+.28*math.sin(angle))
            inner = (cx+.07*math.cos(angle), cy, cz+.07*math.sin(angle))
            mid = tuple((a+b)*.5 for a,b in zip(inner, outer))
            mesh.swept_tube([inner, mid], .014, 'fish_white' if ray % 2 else 'sponge', 4)
            mesh.swept_tube([mid, outer], .014, 'sponge' if ray % 2 else 'fish_white', 4)
        if ranges is not None:
            ranges.append((begin, len(mesh.vertices), (cx,cy,cz-.24)))


def _feather_star(mesh, center, ranges=None):
    x, y, z = center
    mesh.ellipsoid((x, y, z), (.14, .12, .09), 'coralline', 12, 6)
    # Lamprometra palmata has 27–41 arms in the cited description; model 30.
    for arm in range(30):
        start = len(mesh.vertices)
        a = math.pi * (.06 + .88 * arm / 29)
        points = []
        for j in range(5):
            t = j / 4
            radius = .12 + (.60 + .11 * math.sin(arm * 2.1)) * t
            points.append((x + radius * math.cos(a + .08 * math.sin(t * math.pi)),
                           y + .06 * math.sin(a) * t,
                           z + radius * math.sin(a) + .10 * math.sin(t * math.pi)))
        mesh.swept_tube(points, .013, 'coralline', 5)
        # Closely spaced, alternating pinnules make each arm feathery rather
        # than reading as a few widely spaced sticks.
        for j in range(1, 10):
            t = j / 10
            segment = min(3, int(t*4))
            fraction = t*4 - segment
            p = tuple(points[segment][k]*(1-fraction) + points[segment+1][k]*fraction
                      for k in range(3))
            for sign in (-1, 1):
                length = .055 + .045*math.sin(math.pi*t)
                tip = (p[0] - sign*length*math.sin(a), p[1]+.012*sign*math.sin(arm),
                       p[2] + sign*length*math.cos(a) + .025*t)
                mesh.swept_tube([p, tip], .013, 'polyp', 5)
        if ranges is not None:
            ranges.append((start, len(mesh.vertices)))


def _mushroom_coral(mesh, center):
    x, y, z = center
    # A shallow, scalloped disc and raised radial septa give the solitary
    # coral a more organic surface than a smooth flattened ellipsoid.
    def point(angle, fraction):
        edge = 1 + .07*math.sin(9*angle) + .035*math.sin(17*angle+.4)
        return (x + .47*fraction*edge*math.cos(angle),
                y + .32*fraction*edge*math.sin(angle),
                z + .075*(1-fraction*fraction) + .012*fraction*math.sin(9*angle))
    for i in range(32):
        a, b = math.tau*i/32, math.tau*(i+1)/32
        for ring in range(4):
            p, q = ring/4, (ring+1)/4
            if ring == 0:
                mesh.face([point(a,0),point(a,q),point(b,q)], 'coralline')
            else:
                mesh.face([point(a,p),point(a,q),point(b,q),point(b,p)], 'coralline')
        ridge = [point(a,f) for f in (.12,.4,.7,.95)]
        mesh.swept_tube([(p[0],p[1],p[2]+.008) for p in ridge], .013, 'polyp', 5)


def _nudibranch(mesh, center):
    x, y, z = center
    # Phyllidia's dark mantle carries broken pale ridges and yellow tubercles;
    # keep those markings in geometry so they remain visible at tank scale.
    mesh.ellipsoid((x, y, z), (.31, .16, .10), 'fish_dark', 16, 8)
    mesh.ellipsoid((x - .23, y, z + .055), (.12, .105, .10), 'fish_dark', 10, 6)
    for side in (-1, 1):
        ridge = []
        for i in range(7):
            t = i/6
            ridge.append((x-.22+.44*t, y+side*(.075+.018*math.sin(t*math.pi)),
                          z+.075+.025*math.sin(t*math.pi)))
        mesh.swept_tube(ridge, .012, 'clam', 5)
    for i in range(13):
        t = i / 12
        px = x - .2 + .42 * t
        py = y + .10 * math.sin(t * math.pi * 2)
        pz = z + .09 + .035 * math.sin(t * math.pi)
        mesh.swept_tube([(px, py, pz), (px, py, pz + .08)], .016, 'clam', 5)
        mesh.ellipsoid((px, py, pz + .09), (.029, .029, .037), 'fish', 6, 4)
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


def _encrusting_patch(mesh, center, rx, rz, color):
    """An irregular crust with a low, uneven surface on the rock face."""
    x,y,z = center
    rng = random.Random(SEED + round((x + 6)*1000) + round(z*100))
    radii = [rng.uniform(.65,1.2) for _ in range(15)]
    def point(i, fraction):
        angle = math.tau*(i % 15)/15
        radius = radii[i % 15]*fraction
        relief = .018*(1-fraction) + .016*math.sin(3*angle+fraction*4)*fraction*(1-fraction)
        return (x+rx*radius*math.cos(angle), y-.07-relief,
                z+rz*radius*math.sin(angle))
    for i in range(15):
        mesh.face([point(0,0),point(i,1/3),point(i+1,1/3)],color)
        for ring in (1,2):
            a,b=ring/3,(ring+1)/3
            mesh.face([point(i,a),point(i,b),point(i+1,b),point(i+1,a)],color)


def populate(mesh):
    """Add visible static colonies; dynamic animals are authored separately."""
    a = anchor_map()
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
        _encrusting_patch(mesh, (x,y,z), rx, rz, color)
    _mushroom_coral(mesh, (-2.1, -1.0, .86))
    for i in range(6):
        angle = math.tau * i / 6
        center = (.72 + .22 * math.cos(angle), -.8 + .12 * math.sin(angle), 2.25)
        _cup(mesh, center, .12, .19 + .04 * (i % 2), 'coralline', 10)
