"""Local mesh primitives for the three new Aquarium tanks."""
import math

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


    def swept_tube(self, points, radius, color, sides=5):
        """One connected tube with only two end caps, instead of capped segments."""
        rings=[]
        for k,p in enumerate(points):
            lo=points[max(0,k-1)];hi=points[min(len(points)-1,k+1)]
            d=tuple(hi[i]-lo[i] for i in range(3))
            length=math.sqrt(sum(v*v for v in d));d=tuple(v/length for v in d)
            ref=(0,0,1) if abs(d[2])<.9 else (0,1,0)
            u=(d[1]*ref[2]-d[2]*ref[1],d[2]*ref[0]-d[0]*ref[2],d[0]*ref[1]-d[1]*ref[0])
            length=math.sqrt(sum(v*v for v in u));u=tuple(v/length for v in u)
            v=(d[1]*u[2]-d[2]*u[1],d[2]*u[0]-d[0]*u[2],d[0]*u[1]-d[1]*u[0])
            rings.append([tuple(p[j]+radius*(u[j]*math.cos(math.tau*i/sides)+v[j]*math.sin(math.tau*i/sides)) for j in range(3)) for i in range(sides)])
        self.face(list(reversed(rings[0])),color);self.face(rings[-1],color)
        for a,b in zip(rings,rings[1:]):
            for i in range(sides):self.face([a[i],a[(i+1)%sides],b[(i+1)%sides],b[i]],color)
