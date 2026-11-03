"""Procedural static coral blockouts using the established tank Mesh API."""
import math
import random
from .scene import SEED


def hard_corals(mesh):
    """Add the major massive, branching, and table coral colonies."""
    mesh.ellipsoid((-2.75, -.78, 1.75), (.72, .48, .43), 'porites', 24, 12)
    mesh.ellipsoid((-2.25, -.72, 1.88), (.42, .40, .34), 'porites', 18, 9)
    # Recursively branched cauliflower-like head; one mesh, no actor per branch.
    rng = random.Random(SEED + 101)
    x, y, z = (-3.25, -.82, 3.05)
    for i in range(18):
        angle = math.tau * i / 18
        base = (x + .10 * math.cos(angle), y + .12 * math.sin(angle), z - .38)
        mid = (x + .28 * math.cos(angle), y + .25 * math.sin(angle), z + .02)
        tip = (x + rng.uniform(.42, .60) * math.cos(angle),
               y + rng.uniform(.37, .52) * math.sin(angle), z + rng.uniform(.35, .62))
        mesh.swept_tube([base, mid, tip], .052, 'pocillopora', 6)
        mesh.ellipsoid(tip, (.075, .075, .075), 'pocillopora_tip', 7, 4)
        for sign in (-1, 1):
            fork = (tip[0] + sign * .10 * math.cos(angle + .9),
                    tip[1] + sign * .10 * math.sin(angle + .9), tip[2] + .13)
            mesh.swept_tube([mid, tip, fork], .026, 'pocillopora', 5)
    x, y, z = (3.25, -.72, 2.82)
    mesh.swept_tube([(x,y,z-.65), (x,y,z)], .13, 'acropora', 8)
    # Broad table with a dense crown of short upright branchlets.
    for i in range(13):
        for j in range(13):
            dx, dy = (i-6)*.115, (j-6)*.105
            if dx*dx + dy*dy <= .48:
                mesh.swept_tube([(x+dx*.35,y+dy*.35,z-.06),
                                 (x+dx,y+dy,z+.21 + .05*math.sin(i+j))], .022, 'acropora', 5)
    mesh.ellipsoid((x,y,z-.10), (.84,.68,.10), 'acropora', 24, 7)


def soft_corals(mesh):
    """Blockout for scroll, flowerpot and leather corals, plus a sea fan."""
    x,y,z = (-1.85, -.92, 1.78)
    # Ruffled thin plates curl upwards into recognizable scroll shapes.
    for j in range(3):
        rad = .62 - j*.09
        def point(r, angle):
            return (x + r*math.cos(angle), y + r*.72*math.sin(angle),
                    z + j*.17 + .16*(r/rad)**2 + .045*math.sin(5*angle+j))
        for ring in range(3):
            r0, r1 = rad*ring/3, rad*(ring+1)/3
            for k in range(24):
                t0, t1 = math.tau*k/24, math.tau*(k+1)/24
                if ring == 0:
                    mesh.face([point(0,0),point(r1,t0),point(r1,t1)],'scroll')
                else:
                    mesh.face([point(r0,t0),point(r1,t0),point(r1,t1),point(r0,t1)],'scroll')
    x,y,z = (-4.15, -.85, 2.42)
    mesh.ellipsoid((x,y,z), (.48,.34,.28), 'flowerpot', 18, 9)
    for i in range(20):
        t=math.tau*i/20
        h=.42 + .10*math.sin(i*2.4)
        base=(x+.29*math.cos(t),y+.21*math.sin(t),z+.12)
        tip=(x+.36*math.cos(t),y+.27*math.sin(t),z+h)
        mesh.swept_tube([base,tip], .027, 'flowerpot_tip', 5)
        mesh.ellipsoid(tip, (.055,.055,.065), 'flowerpot_tip', 7, 4)
    x,y,z = (4.0, -.72, 2.76)
    mesh.swept_tube([(x,y,z-.45),(x-.04,y,z-.10),(x,y,z)], .14, 'leather', 8)
    mesh.ellipsoid((x,y,z), (.62,.47,.20), 'leather', 20, 7)
    for i in range(24):
        t=math.tau*i/24
        start=(x+.25*math.cos(t),y+.20*math.sin(t),z+.14)
        end=(x+.58*math.cos(t),y+.43*math.sin(t),z+.18+.04*math.sin(3*t))
        mesh.swept_tube([start,end], .009, 'flowerpot_tip', 4)

