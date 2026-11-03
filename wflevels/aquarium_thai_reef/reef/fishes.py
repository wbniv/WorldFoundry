"""Procedural juvenile boxfish and humbug meshes, in local tank units."""
import math


def _disc(mesh, x, y, z, r, color):
    mesh.face([(x + r * math.cos(math.tau * i / 12), y,
                z + r * math.sin(math.tau * i / 12)) for i in range(12)], color)


def boxfish(Mesh):
    m = Mesh('reef_boxfish')
    # Rounded, rigid box cross-sections retain the juvenile silhouette without
    # bending the body when it swims. Its fins remain separate visual details.
    rings = []
    for x, radius in ((-.23,.67),(-.20,1),(.15,1),(.22,.86),(.24,.60)):
        ring = []
        for i in range(16):
            angle = math.tau * i / 16
            c, s = math.cos(angle), math.sin(angle)
            y = .14 * radius * math.copysign(abs(c) ** .6, c)
            z = .16 * radius * math.copysign(abs(s) ** .6, s)
            ring.append((x,y,z))
        rings.append(ring)
    m.face(list(reversed(rings[0])), 'fish')
    m.face(rings[-1], 'fish')
    for a,b in zip(rings,rings[1:]):
        for i in range(16):
            j = (i+1) % 16
            m.face([a[i],a[j],b[j],b[i]], 'fish')
    for side in (-1, 1):
        y = side * .142
        for x,z in ((-.14,-.08),(-.04,-.08),(.06,-.08),(-.14,.02),(-.04,.02),(.06,.02),(-.14,.11),(-.04,.11)):
            _disc(m, x, y, z, .018, 'fish_dark')
        _disc(m, .15, side * .144, .08, .033, 'fish_white')
        _disc(m, .16, side * .146, .08, .018, 'fish_dark')
        m.face([(-.03,y,0),(-.1,side*.25,-.03),(-.08,y,-.08)], 'fish')
    m.face([(-.22,0,0),(-.36,0,.10),(-.36,0,-.10)], 'fish')
    m.face([(-.06,0,.16),(-.14,0,.25),(.01,0,.16)], 'fish')
    return m


def humbug(Mesh):
    m = Mesh('reef_humbug')
    # Elliptical rings along the body, with alternating broad black bars.
    xs = (-.32,-.25,-.18,-.11,-.04,.03,.10,.17,.24,.30)
    for j in range(len(xs)-1):
        color = 'fish_dark' if j in (1, 4, 7) else 'fish_white'
        def ring(x):
            r = math.sqrt(max(0, 1 - (x / .34) ** 2))
            return [(x, .105*r*math.cos(math.tau*i/12), .22*r*math.sin(math.tau*i/12)) for i in range(12)]
        a,b=ring(xs[j]),ring(xs[j+1])
        for i in range(12):
            k=(i+1)%12
            m.face([a[i],a[k],b[k],b[i]],color)
    m.face([(-.29,0,0),(-.44,0,.11),(-.44,0,-.11)],'fish_white')
    for side in (-1,1):
        _disc(m,.20,side*.09,.07,.023,'fish_dark')
    return m
