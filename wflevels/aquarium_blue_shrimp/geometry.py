"""Procedural shrimp geometry, independent of the concurrently edited aquarium.

Coordinates: +X head, +Y far side, +Z up. Body origin is at its feet on
the substrate. Tail origin is its hinge. All geometry is opaque and colored.
"""
import math

PALETTE = {
    'cobalt': (.055, .30, .85), 'blue': (.08, .48, .98),
    'highlight': (.28, .74, 1.0), 'shadow': (.025, .16, .48),
    'leg': (.11, .46, .73), 'antenna': (.35, .72, .85),
    'eye': (.015, .025, .035), 'glint': (.8, .95, 1.0),
}
PARTS = ('body', 'tail', 'legs-near', 'legs-far', 'antennae')
OFFSETS = ((0, 0, 0), (-.15, 0, .16), (0, -.05, .105),
           (0, .05, .105), (.23, 0, .19))


class Mesh:
    def __init__(self, name):
        self.name, self.vertices, self.faces, self.colors = name, [], [], []

    def face(self, points, color):
        start = len(self.vertices)
        self.vertices.extend(tuple(p) for p in points)
        self.faces.append(tuple(range(start, len(self.vertices))))
        self.colors.append(color)

    def ellipsoid(self, center, radii, color, segments=10, rings=6):
        def point(i, j):
            a, b = math.tau*i/segments, math.pi*j/rings
            return (center[0]+radii[0]*math.cos(b),
                    center[1]+radii[1]*math.sin(b)*math.cos(a),
                    center[2]+radii[2]*math.sin(b)*math.sin(a))
        for j in range(rings):
            for i in range(segments):
                points = [point(i, j), point(i, j+1), point(i+1, j+1), point(i+1, j)]
                # Collapse pole duplicates so every emitted triangle has area.
                points = list(dict.fromkeys(tuple(round(v, 9) for v in p) for p in points))
                if len(points) >= 3:
                    self.face(points, color if isinstance(color, str) else color[i % len(color)])

    def tube(self, points, radius, color, sides=5):
        for a, b in zip(points, points[1:]):
            d = tuple(b[i]-a[i] for i in range(3))
            length = math.sqrt(sum(v*v for v in d))
            if length < 1e-8:
                continue
            d = tuple(v/length for v in d)
            ref = (0, 0, 1) if abs(d[2]) < .9 else (0, 1, 0)
            u = (d[1]*ref[2]-d[2]*ref[1], d[2]*ref[0]-d[0]*ref[2], d[0]*ref[1]-d[1]*ref[0])
            mag = math.sqrt(sum(v*v for v in u))
            u = tuple(v/mag for v in u)
            v = (d[1]*u[2]-d[2]*u[1], d[2]*u[0]-d[0]*u[2], d[0]*u[1]-d[1]*u[0])
            def ring(p):
                return [tuple(p[j]+radius*(u[j]*math.cos(math.tau*i/sides)+v[j]*math.sin(math.tau*i/sides))
                              for j in range(3)) for i in range(sides)]
            ra, rb = ring(a), ring(b)
            self.face(list(reversed(ra)), color)
            self.face(rb, color)
            for i in range(sides):
                self.face([ra[i], ra[(i+1)%sides], rb[(i+1)%sides], rb[i]], color)


def shrimp_meshes():
    body = Mesh('shrimp_body')
    body.ellipsoid((.08, 0, .17), (.22, .085, .10),
                   ['blue', 'highlight', 'highlight', 'blue', 'cobalt', 'shadow', 'shadow', 'cobalt'], 8, 4)
    body.tube([(.21, 0, .20), (.37, 0, .225)], .015, 'highlight')  # rostrum
    for side in (-1, 1):
        body.tube([(.22, side*.05, .20), (.27, side*.073, .265)], .012, 'blue')
        body.ellipsoid((.27, side*.073, .265), (.025, .024, .027), 'eye', 6, 3)
        body.face([(.270,side*.099,.267),(.286,side*.099,.267),
                   (.286,side*.099,.283),(.270,side*.099,.283)][::-side], 'glint')
    tail = Mesh('shrimp_tail')
    rings=[]
    for i in range(7):
        x,z = .025-.045*i, -.005*i-.0015*i*i
        w,h = .078-.007*i, .073-.006*i
        rings.append([(x,w*math.cos(math.tau*j/8),z+h*math.sin(math.tau*j/8)) for j in range(8)])
    colors=['blue','highlight','highlight','blue','cobalt','shadow','shadow','cobalt']
    tail.face(rings[0], 'cobalt')
    tail.face(list(reversed(rings[-1])), 'blue')
    for k,(a,b) in enumerate(zip(rings,rings[1:])):
        for j in range(8):
            tail.face([a[j],b[j],b[(j+1)%8],a[(j+1)%8]],
                      'cobalt' if k%2 and j==0 else colors[j])
    for side in (-1, 0, 1):
        y=side*.049
        front=[(-.24,y-.016,-.062),(-.33,y-.030,-.070),(-.36,y+.020,-.070),(-.24,y+.016,-.062)][::-1]
        back=[(x,y,z-.020) for x,y,z in front]
        tail.face(front,'blue')
        tail.face(list(reversed(back)),'shadow')
        for j in range(4):
            tail.face([front[j],back[j],back[(j+1)%4],front[(j+1)%4]],'cobalt')
    legs = []
    for side, name in [(-1, 'shrimp_legs_near'), (1, 'shrimp_legs_far')]:
        part = Mesh(name)
        for i in range(5):
            x = .145-.060*i
            part.tube([(x, 0, 0), (x-.025, side*.085, -.025),
                       (x+.02, side*.135, -.097)], .014, 'leg', 3)
        # Two small grazing claws in front of the walking legs.
        for i in range(2):
            x = .17+.035*i
            part.tube([(x, 0, .01), (x+.055, side*.065, -.065), (x+.09, side*.08, -.09)], .014, 'highlight', 3)
        legs.append(part)
    ant = Mesh('shrimp_antennae')
    for side in (-1, 1):
        ant.tube([(0, side*.025, 0), (.13, side*.09, .07),
                  (.29, side*.16, .10), (.46, side*.21, .075)], .010, 'antenna', 3)
        ant.tube([(0, side*.02, -.018), (.11, side*.045, .01), (.24, side*.08, -.035)], .010, 'highlight', 3)
    return [body, tail, *legs, ant]
