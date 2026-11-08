"""Procedural juvenile boxfish and humbug meshes, in local tank units."""
import math


def _disc(mesh, x, y, z, r, color):
    mesh.face([(x + r * math.cos(math.tau * i / 12), y,
                z + r * math.sin(math.tau * i / 12)) for i in range(12)], color)


def boxfish(Mesh, fin_ranges=None):
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
        # Rounded pectoral fin instead of a single triangular spur.
        start = len(m.vertices)
        m.face([(-.03,y,.025), (-.08,side*.20,.035), (-.13,side*.24,-.015),
                (-.11,side*.23,-.065), (-.05,y,-.06)], 'fish')
        if fin_ranges is not None:
            fin_ranges.append((start, len(m.vertices), (-.05, y, 0), (0, side, 0), (0, 0, 1)))
        _disc(m, .225, side*.105, -.025, .012, 'fish_dark')
    # Fan-shaped caudal fin with a softly rounded trailing edge.
    tail_root = (-.22,0,0)
    tail_edge = [(-.32,0,.105),(-.365,0,.10),(-.39,0,.055),
                 (-.40,0,0),(-.39,0,-.055),(-.365,0,-.10),(-.32,0,-.105)]
    start = len(m.vertices)
    for i in range(len(tail_edge)-1):
        m.face([tail_root,tail_edge[i],tail_edge[i+1]], 'fish')
    if fin_ranges is not None:
        fin_ranges.append((start, len(m.vertices), tail_root, (-1, 0, 0), (0, 0, 1)))
    # A short projecting snout and a dark mouth are readable in side view.
    m.face([(.22,-.045,-.015),(.29,-.035,-.025),(.29,.035,-.025),(.22,.045,-.015)], 'fish')
    for side in (-1,1):
        _disc(m,.275,side*.036,-.025,.011,'fish_dark')
    for vertices, root, direction in (([(-.06,0,.16),(-.14,0,.25),(.01,0,.16)], (-.06,0,.16), (0,0,1)),
                                      ([(-.09,0,-.16),(-.16,0,-.235),(.01,0,-.16)], (-.09,0,-.16), (0,0,-1))):
        start = len(m.vertices)
        m.face(vertices, 'fish')
        if fin_ranges is not None:
            fin_ranges.append((start, len(m.vertices), root, direction, (0,1,0)))
    return m


def humbug(Mesh):
    m = Mesh('reef_humbug')
    # Elliptical rings along the body, with alternating broad black bars.
    xs = (-.32,-.25,-.18,-.11,-.04,.03,.10,.17,.24,.30)
    for j in range(len(xs)-1):
        color = 'fish_dark' if j in (1, 4, 7) else 'humbug_white'
        def ring(x):
            r = math.sqrt(max(0, 1 - (x / .34) ** 2))
            return [(x, .105*r*math.cos(math.tau*i/12), .22*r*math.sin(math.tau*i/12)) for i in range(12)]
        a,b=ring(xs[j]),ring(xs[j+1])
        for i in range(12):
            k=(i+1)%12
            m.face([a[i],a[k],b[k],b[i]],color)
    # Forked caudal, dorsal and anal fins make the striped silhouette read as
    # a damselfish from the wide tank camera.
    m.face([(-.29,0,0),(-.45,0,.13),(-.40,0,0)],'humbug_white')
    m.face([(-.29,0,0),(-.40,0,0),(-.45,0,-.13)],'humbug_white')
    m.face([(-.22,0,.15),(-.16,0,.26),(.04,0,.29),(.20,0,.17)],'fish_dark')
    m.face([(-.20,0,-.14),(-.12,0,-.25),(.05,0,-.25),(.18,0,-.14)],'fish_dark')
    for side in (-1,1):
        # A pale eye ring and a smaller dark pupil remain legible against
        # either a dark body bar or the light face.
        _disc(m,.20,side*.092,.07,.029,'fish_white')
        _disc(m,.205,side*.094,.07,.016,'fish_dark')
        _disc(m,.285,side*.048,-.025,.010,'fish_dark')
        m.face([(.08,side*.09,.01),(-.06,side*.16,-.04),(.03,side*.10,-.10)],'fish_white')
        # A second, smaller fin layer gives the pectoral fin a tapered edge.
        m.face([(.07,side*.095,.005),(-.045,side*.155,-.045),
                (.025,side*.105,-.075)],'fish_dark')
    return m
