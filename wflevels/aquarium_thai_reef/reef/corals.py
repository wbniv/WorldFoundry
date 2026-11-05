"""Procedural static coral blockouts using the established tank Mesh API."""
import math
import random
from .scene import SEED


def _massive_coral(mesh, center, radii, segments, rings):
    """A gently lobed Porites colony, with shared positions displaced equally."""
    first = len(mesh.vertices)
    mesh.ellipsoid(center, radii, 'porites', segments, rings)
    for index in range(first, len(mesh.vertices)):
        point = mesh.vertices[index]
        u = tuple((point[i] - center[i]) / radii[i] for i in range(3))
        # Smooth, multi-scale growth contours retain the massive colony shape.
        relief = (1 + .055 * math.sin(7*u[0]+4*u[2])*math.cos(5*u[1]-2*u[2])
                  + .025 * math.sin(13*u[0]+7*u[1]+3*u[2]))
        mesh.vertices[index] = tuple(center[i] + (point[i]-center[i])*relief for i in range(3))


def hard_corals(mesh):
    """Add the major massive, branching, and table coral colonies."""
    _massive_coral(mesh, (-2.75, -.78, 1.75), (.72, .48, .43), 32, 16)
    _massive_coral(mesh, (-2.25, -.72, 1.88), (.42, .40, .34), 24, 12)
    # Recursively branched cauliflower-like head; one mesh, no actor per branch.
    rng = random.Random(SEED + 101)
    x, y, z = (-3.25, -.82, 3.05)
    mesh.ellipsoid((x, y, z-.32), (.34, .28, .19), 'pocillopora', 12, 7)
    for i in range(25):
        angle = i * 2.399963
        reach = rng.uniform(.23, .54)
        base = (x + .12 * math.cos(angle), y + .10 * math.sin(angle), z - .28)
        mid = (x + reach*.65 * math.cos(angle), y + reach*.55 * math.sin(angle),
               z + rng.uniform(-.02, .15))
        tip = (x + reach * math.cos(angle), y + reach*.8 * math.sin(angle),
               z + rng.uniform(.18, .48))
        mesh.swept_tube([base, mid, tip], rng.uniform(.035, .052), 'pocillopora', 6)
        mesh.ellipsoid(tip, (.064, .058, .072), 'pocillopora_tip', 7, 4)
        fork = (tip[0] + .12 * math.cos(angle + 1.0),
                tip[1] + .10 * math.sin(angle + 1.0), tip[2] + rng.uniform(.08, .17))
        mesh.swept_tube([mid, fork], .024, 'pocillopora', 5)
        mesh.ellipsoid(fork, (.045, .045, .055), 'pocillopora_tip', 6, 4)
        # Small, irregular secondary branchlets make the outer colony read as
        # branching coral rather than a bundle of round-ended cylinders.
        for side in (-1, 1):
            twig_angle = angle + side*.7
            start = (tip[0]*.72 + mid[0]*.28, tip[1]*.72 + mid[1]*.28,
                     tip[2]*.72 + mid[2]*.28)
            end = (tip[0]+.08*math.cos(twig_angle), tip[1]+.07*math.sin(twig_angle),
                   tip[2]+.07+.025*math.sin(i+side))
            mesh.swept_tube([start,end], .016, 'pocillopora', 5)
            mesh.ellipsoid(end, (.024,.022,.030), 'pocillopora_tip', 6, 4)
    x, y, z = (3.25, -.72, 2.82)
    mesh.swept_tube([(x,y,z-.65), (x,y,z-.29), (x,y,z-.12)], .13, 'acropora', 8)
    # The table is supported by an irregular radial network, with forked
    # branches at its rim, rather than a solid elliptical plate.
    for i in range(16):
        angle = math.tau * i / 16
        reach = .63 + .08 * math.sin(i * 2.4)
        points = [(x, y, z-.14),
                  (x + .38*reach*math.cos(angle), y + .30*reach*math.sin(angle), z-.08),
                  (x + reach*math.cos(angle), y + .78*reach*math.sin(angle), z+.04)]
        mesh.swept_tube(points, .033, 'acropora', 6)
        for side in (-1, 1):
            end = (points[-1][0] + side*.09*math.sin(angle),
                   points[-1][1] - side*.07*math.cos(angle), z+.19 + .03*math.sin(i+side))
            mesh.swept_tube([points[1], points[-1], end], .019, 'acropora', 5)
    # An offset, lightly jittered crown keeps branch rows from reading as a grid.
    for i in range(13):
        for j in range(13):
            dx = (i-6)*.115 + rng.uniform(-.024, .024)
            dy = (j-6)*.105 + rng.uniform(-.024, .024)
            if dx*dx + dy*dy <= .48:
                mesh.swept_tube([(x+dx*.35,y+dy*.35,z-.06),
                                 (x+dx,y+dy,z+.16 + rng.uniform(.02,.11))], .022, 'acropora', 5)


def soft_corals(mesh):
    """Blockout for scroll, flowerpot and leather corals, plus a sea fan."""
    x,y,z = (-1.85, -.92, 1.78)
    # Nested, asymmetric ruffled plates with uneven edges and deeper curls.
    for j in range(3):
        rad = .62 - j*.09
        def point(r, angle):
            f = r/rad
            edge = 1 + f*(.10*math.sin(5*angle+j) + .04*math.sin(11*angle-j))
            return (x + r*edge*math.cos(angle), y + r*.72*edge*math.sin(angle),
                    z + j*.17 + .19*f*f + f*(.065*math.sin(5*angle+j)
                                               + .025*math.sin(11*angle-j)))
        for ring in range(5):
            r0, r1 = rad*ring/5, rad*(ring+1)/5
            for k in range(32):
                t0, t1 = math.tau*k/32, math.tau*(k+1)/32
                if ring == 0:
                    mesh.face([point(0,0),point(r1,t0),point(r1,t1)],'scroll')
                else:
                    mesh.face([point(r0,t0),point(r1,t0),point(r1,t1),point(r0,t1)],'scroll')


def flowerpot(mesh, center, ranges=None):
    x,y,z = center
    mesh.ellipsoid((x,y,z), (.48,.34,.28), 'flowerpot', 18, 9)
    for i in range(20):
        start = len(mesh.vertices)
        t=math.tau*i/20
        h=.42 + .10*math.sin(i*2.4)
        base=(x+.29*math.cos(t),y+.21*math.sin(t),z+.12)
        tip=(x+.36*math.cos(t),y+.27*math.sin(t),z+h)
        mesh.swept_tube([base,tip], .027, 'flowerpot_tip', 5)
        # Short radiating tentacles give each polyp its flower-like crown.
        mesh.ellipsoid(tip, (.035,.035,.025), 'flowerpot_tip', 8, 4)
        for petal in range(8):
            a = math.tau*petal/8 + t*.3
            end = (tip[0]+.075*math.cos(a), tip[1]+.075*math.sin(a),
                   tip[2]+.018+.008*math.sin(3*a))
            mesh.swept_tube([tip,end], .013, 'flowerpot_tip', 5)
        if ranges is not None:
            ranges.append((start, len(mesh.vertices), base))


def leather_coral(mesh, center, ranges=None):
    x,y,z = center
    range_start = len(mesh.vertices)
    mesh.swept_tube([(x,y,z-.45),(x-.04,y,z-.10),(x,y,z)], .14, 'leather', 8)
    # A wavy, scalloped crown with small projecting polyps, rather than an
    # oval cap and long, evenly spaced spokes.
    def crown(t, fraction):
        edge = 1 + .09*math.sin(5*t+.4) + .045*math.sin(11*t)
        return (x+.62*fraction*edge*math.cos(t), y+.47*fraction*edge*math.sin(t),
                z+.18*(1-fraction*fraction)+.045*fraction*math.sin(5*t+.4))
    for i in range(32):
        a,b = math.tau*i/32, math.tau*(i+1)/32
        for ring in range(4):
            p,q=ring/4,(ring+1)/4
            if ring == 0:
                mesh.face([crown(a,0),crown(a,q),crown(b,q)], 'leather')
            else:
                mesh.face([crown(a,p),crown(a,q),crown(b,q),crown(b,p)], 'leather')
    for ring, count in ((.35,12),(.65,20),(.88,28)):
        for i in range(count):
            t = math.tau*(i+.35*(ring>.5))/count
            start = crown(t,ring)
            end = (start[0]+.016*math.cos(t),start[1]+.016*math.sin(t),
                   start[2]+.045+.012*math.sin(i*2.1))
            mesh.swept_tube([start,end], .013, 'flowerpot_tip', 5)
    if ranges is not None:
        ranges.append((range_start, len(mesh.vertices), (x,y,z-.45)))

