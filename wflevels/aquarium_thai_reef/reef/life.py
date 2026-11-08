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
        mesh.swept_tube([start,end], .009, 'polyp', 5)


def _sea_fan(mesh, base):
    x, y, z = base
    # Radial primary branches and irregular cross-branches form a broad, open
    # gorgonian fan rather than a single trunk with symmetrical side twigs.
    mesh.swept_tube([(x, y, z-.3), (x, y, z+.05), (x, y, z+.22)], .032, 'fan_grad', 6)
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
        mesh.swept_tube(points, .014 if i % 3 else .019, 'fan_grad', 5)
        spokes.append(points)
        # Fine split tips break the otherwise perfectly radial outer edge.
        for side in (-1, 1):
            tip = points[-1]
            end = (tip[0] + side*.045*math.sin(a) + .018*math.cos(a),
                   tip[1] + side*.012,
                   tip[2] - side*.045*math.cos(a) + .035*math.sin(a))
            mesh.swept_tube([points[-2],tip,end], .009, 'fan_grad', 5)
    for i in range(12):
        for j in range(1, 5):
            if (i + j) % 5 == 0:
                continue
            a, b = spokes[i][j], spokes[i+1][j]
            middle = ((a[0]+b[0])/2, (a[1]+b[1])/2 - .012,
                      (a[2]+b[2])/2 + .018 * math.sin(i*3+j))
            mesh.swept_tube([a, middle, b], .009, 'fan_grad', 4)


def _clam(mesh, center, limb_ranges=None):
    x, y, z = center
    # Fluted, pale valves open around the vivid blue mantle.  The ribs fan
    # from the low hinge, with a scalloped edge instead of stacked ellipsoids.
    steps = 60
    for side in (-1, 1):
        start = len(mesh.vertices)
        def section(i):
            t = -1 + 2*i/steps
            span = math.sqrt(max(0, 1-t*t))
            px = x + .43*t
            scallop = 1 + .06*math.cos(i*math.pi/3)
            return ((px, y, z),
                    (px, y + side*.15*span, z + .035*span),
                    (px, y + side*.30*span*scallop, z + .13*span))
        for i in range(steps):
            a, b = section(i), section(i+1)
            for band in range(2):
                points = [a[band], b[band], b[band+1], a[band+1]]
                mesh.face(points if side < 0 else list(reversed(points)), 'clam_shell')
        for i in range(3, steps, 6):
            a, b, c = section(i)
            mesh.swept_tube([a, b, c], .008, 'clam_shell', 4)
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
            radius = .009 + .003*(1+math.sin(column*3.1+row))/2
            points = [(x+px+radius*math.cos(math.tau*i/8),
                       y+py+radius*.8*math.sin(math.tau*i/8),z+.151)
                      for i in range(8)]
            mesh.face(points, 'fish_white')
    if limb_ranges is not None:
        limb_ranges.append((start, len(mesh.vertices), (x,y,z+.125), (0,1,0), (0,0,1)))


def _zoanthid_polyp(mesh, i):
    """One zoanthid polyp at the origin, growing along +z (local frame)."""
    pz = .035 * math.sin(i * 2.1) * .3
    mesh.swept_tube([(0, 0, pz - .02), (0, 0, pz + .09)], .018, 'zoanthid_column', 6)
    first = len(mesh.faces)
    mesh.ellipsoid((0, 0, pz + .11), (.052, .048, .025), 'zoanthid', 7, 4)
    mesh.ellipsoid((0, 0, pz + .13), (.022, .020, .009), 'zoanthid', 6, 3)
    # Head and oral disc map onto one flower-head motif of the zoanthid
    # tile (atlas tile 5: heads every 42 px), viewed along the polyp, so each
    # polyp shows a disc and tentacle ring instead of a sub-texel smear.
    centre = (256 + 42 * (1 + i % 5), 256 + 42 * (1 + (i // 5) % 5))
    if not hasattr(mesh, 'face_uvs'):
        mesh.face_uvs = {}
    for f in range(first, len(mesh.faces)):
        mesh.face_uvs[f] = tuple(((centre[0] + 19 * mesh.vertices[v][0] / .052) / 1024,
                                  (centre[1] + 19 * mesh.vertices[v][1] / .052) / 1024)
                                 for v in mesh.faces[f])
    # Short tentacles frame each oral disc instead of a smooth button.
    for tentacle in range(8):
        angle = math.tau*tentacle/8 + i*.17
        start = (.034*math.cos(angle), .031*math.sin(angle), pz+.125)
        end = (.065*math.cos(angle), .060*math.sin(angle), pz+.135+.007*math.sin(i+tentacle))
        mesh.swept_tube([start, end], .009, 'zoanthid_column', 5)


def _placed(target, build, base, axis, spin=0.0):
    """Build into a local frame (base at the origin, growing +z), then move it
    onto base with +z along axis. Explicit face UVs travel with the faces."""
    from mesh import Mesh          # the shared primitive mesh (wflevels/aquarium_tanks)
    from .placement import frame
    tmp = Mesh('local')
    build(tmp)
    e1, e2, a = frame(axis)
    c, s_ = math.cos(spin), math.sin(spin)
    e1, e2 = (tuple(c*e1[k] + s_*e2[k] for k in range(3)), tuple(-s_*e1[k] + c*e2[k] for k in range(3)))
    explicit = getattr(tmp, 'face_uvs', {})
    for index, (face, key) in enumerate(zip(tmp.faces, tmp.colors)):
        pts = [tuple(base[k] + v[0]*e1[k] + v[1]*e2[k] + v[2]*a[k] for k in range(3))
               for v in (tmp.vertices[i] for i in face)]
        target.face(pts, key)
        if index in explicit:
            if not hasattr(target, 'face_uvs'):
                target.face_uvs = {}
            target.face_uvs[len(target.faces) - 1] = explicit[index]


def _zoanthids(mesh, center):
    """A zoanthid carpet on the rock face around (x, z): every polyp sits on
    the surface and grows out of it (plan W3)."""
    from .placement import grow_axis, on_rock_face
    x, _, z = center
    for i in range(34):
        a = i * 2.399963
        r = .08 + .31 * math.sqrt((i + .5) / 34)
        base, normal = on_rock_face(x + r * math.cos(a), z + r * math.sin(a) * .62)
        base = tuple(base[k] - .01 * normal[k] for k in range(3))
        _placed(mesh, lambda m, i=i: _zoanthid_polyp(m, i), base, grow_axis(normal, .3), spin=i * .7)


# Christmas tree worms (Spirobranchus): the tube is buried in the Porites
# boulder; only a calcareous collar, the operculum and two spiral crowns show.
# Mouths, axes, sizes and colour morphs come from scene.worm_mouths().
WORM_CELL = 8                 # atlas cell (atlas.py): 8 morph rows of 32 px
WORM_TURNS = 4.5              # helical turns of radioles per crown
WORM_SEGMENTS = 36            # ribbon segments per crown (8 per turn)
WORM_CORE_SIDES = 4


def _v_add(*vs):
    return tuple(sum(v[i] for v in vs) for i in range(3))


def _v_mul(v, k):
    return tuple(x * k for x in v)


def _v_unit(v):
    m = math.sqrt(sum(x * x for x in v))
    return tuple(x / m for x in v)


def _v_cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _v_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def worm_frame(axis):
    """Unit axis plus two perpendiculars; e1 runs roughly screen-right."""
    e1 = _v_unit(_v_cross(axis, (0, -1, 0)))
    e2 = _v_cross(axis, e1)
    return e1, e2


def worm_height(size):
    return .17 * size


def _uv_face(mesh, points, uvs, key='worm'):
    mesh.face(points, key)
    if not hasattr(mesh, 'face_uvs'):
        mesh.face_uvs = {}
    mesh.face_uvs[len(mesh.faces) - 1] = tuple(uvs)


def _oriented(points, uvs, outward):
    """Order a quad so its right-hand normal points along outward."""
    a, b, c = points[0], points[1], points[2]
    n = _v_cross(tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3)))
    if _v_dot(n, outward) < 0:
        return list(reversed(points)), list(reversed(uvs))
    return list(points), list(uvs)


def worm_crowns(mesh, origin, ranges=None):
    """Twin spiral crowns for every worm, in coordinates local to origin.

    Each crown is a thin core cone wrapped by a two-sided helical ribbon of
    radioles with a jagged outer edge. UVs are explicit (mesh.face_uvs):
    u runs along the helix, v from the radiole roots to their tips inside the
    worm's morph row. ranges, if given, receives one dict per worm with its
    vertex range, local mouth, axis and crown height (for worm_rig).
    """
    from .scene import worm_mouths
    cell_u0 = (WORM_CELL % 4) * 256 / 1024
    for worm in worm_mouths():
        start = len(mesh.vertices)
        mouth = tuple(worm['mouth'][i] - origin[i] for i in range(3))
        axis, size = worm['axis'], worm['size']
        e1, _ = worm_frame(axis)
        height, base_r = worm_height(size), .055 * size
        row_v0 = ((WORM_CELL // 4) * 256 + 32 * worm['morph']) / 1024
        v_root, v_tip = row_v0 + 4 / 1024, row_v0 + 28 / 1024
        for side in (-1, 1):
            # The two spirals splay slightly from the shared mouth.
            c_axis = _v_unit(_v_add(axis, _v_mul(e1, side * .10)))
            c1, c2 = worm_frame(c_axis)
            # Lifted a little along the axis so the off-centre base clears the coral.
            base = _v_add(mouth, _v_mul(e1, side * .03 * size), _v_mul(axis, .012 * size))

            def centre(t):
                return _v_add(base, _v_mul(c_axis, t * height))

            def core_r(t):
                return base_r * .32 * (1 - t)

            def radial(angle):
                return _v_add(_v_mul(c1, math.cos(angle)), _v_mul(c2, math.sin(angle)))

            # Core cone.
            rings = (0, .4, .75)
            for ri in range(len(rings)):
                t0 = rings[ri]
                for k in range(WORM_CORE_SIDES):
                    a0 = math.tau * k / WORM_CORE_SIDES
                    a1 = math.tau * (k + 1) / WORM_CORE_SIDES
                    u0 = cell_u0 + (.04 + .92 * k / WORM_CORE_SIDES) * .25
                    u1 = cell_u0 + (.04 + .92 * (k + 1) / WORM_CORE_SIDES) * .25
                    p00 = _v_add(centre(t0), _v_mul(radial(a0), core_r(t0)))
                    p01 = _v_add(centre(t0), _v_mul(radial(a1), core_r(t0)))
                    if ri + 1 < len(rings):
                        t1 = rings[ri + 1]
                        p10 = _v_add(centre(t1), _v_mul(radial(a0), core_r(t1)))
                        p11 = _v_add(centre(t1), _v_mul(radial(a1), core_r(t1)))
                        pts, uvs = _oriented([p00, p01, p11, p10],
                                             [(u0, v_root)] * 2 + [(u1, v_root)] * 2,
                                             radial((a0 + a1) / 2))
                    else:
                        apex = centre(1.0)
                        pts, uvs = _oriented([p00, p01, apex],
                                             [(u0, v_root), (u1, v_root), (u0, v_tip)],
                                             radial((a0 + a1) / 2))
                    _uv_face(mesh, pts, uvs)
            # Helical ribbon of radioles, two-sided so back-face culling
            # never hides the far side of a whorl.
            phase = 0 if side < 0 else math.pi
            inner, outer, us = [], [], []
            for k in range(WORM_SEGMENTS + 1):
                f = k / WORM_SEGMENTS
                t = .1 + .86 * f
                angle = phase + side * WORM_TURNS * math.tau * f
                d = radial(angle)
                reach = base_r * (1 - .82 * t)
                inner.append(_v_add(centre(t), _v_mul(d, core_r(t))))
                outer.append(_v_add(centre(t), _v_mul(d, reach), _v_mul(c_axis, -.18 * reach)))
                us.append(cell_u0 + (.04 + .92 * f) * .25)
            for k in range(WORM_SEGMENTS):
                quad = [inner[k], outer[k], outer[k + 1], inner[k + 1]]
                uvs = [(us[k], v_root), (us[k], v_tip), (us[k + 1], v_tip), (us[k + 1], v_root)]
                for facing in (c_axis, _v_mul(c_axis, -1)):
                    pts, puv = _oriented(quad, uvs, facing)
                    _uv_face(mesh, pts, puv)
        if ranges is not None:
            ranges.append({'start': start, 'end': len(mesh.vertices), 'mouth': mouth,
                           'axis': axis, 'height': height})


def worm_collars(mesh):
    """Static calcareous collars and opercula at every worm mouth (world space)."""
    from .scene import worm_mouths
    for worm in worm_mouths():
        n, s = worm['normal'], worm['size']
        e1 = _v_unit(_v_cross(n, (0, -1, 0)))
        e2 = _v_cross(n, e1)
        base = _v_add(worm['surface'], _v_mul(n, -.01 * s))
        top = _v_add(worm['surface'], _v_mul(n, .012 * s))
        sides = 8
        def ring(centre, radius):
            return [_v_add(centre, _v_mul(e1, radius * math.cos(math.tau * k / sides)),
                           _v_mul(e2, radius * math.sin(math.tau * k / sides))) for k in range(sides)]
        out_lo, out_hi = ring(base, .03 * s), ring(top, .027 * s)
        in_hi, in_lo = ring(top, .019 * s), ring(_v_add(top, _v_mul(n, -.02 * s)), .019 * s)
        for k in range(sides):
            j = (k + 1) % sides
            mid = _v_unit(_v_add(_v_mul(e1, math.cos(math.tau * (k + .5) / sides)),
                                 _v_mul(e2, math.sin(math.tau * (k + .5) / sides))))
            for quad, facing in (([out_lo[k], out_lo[j], out_hi[j], out_hi[k]], mid),
                                 ([out_hi[k], out_hi[j], in_hi[j], in_hi[k]], n),
                                 ([in_hi[k], in_hi[j], in_lo[j], in_lo[k]], _v_mul(mid, -1))):
                pts, _ = _oriented(quad, [(0, 0)] * 4, facing)
                mesh.face(pts, 'sand')
        # Operculum: a small spined cap resting on the collar's upper rim.
        cap_c = _v_add(top, _v_mul(e2, .026 * s), _v_mul(n, .004 * s))
        cap = ring(cap_c, .013 * s)
        cap_top = _v_add(cap_c, _v_mul(n, .006 * s))
        for k in range(sides):
            j = (k + 1) % sides
            pts, _ = _oriented([cap[k], cap[j], cap_top], [(0, 0)] * 3, n)
            mesh.face(pts, 'sand')
        for spine in (-1, 1):
            root = _v_add(cap_top, _v_mul(e1, spine * .005 * s))
            tip = _v_add(root, _v_mul(n, .012 * s), _v_mul(e1, spine * .004 * s))
            side_a = _v_add(root, _v_mul(e2, .003 * s))
            side_b = _v_add(root, _v_mul(e2, -.003 * s))
            for tri in ([side_a, side_b, tip], [side_b, side_a, tip]):
                mesh.face(tri, 'sand')


def feather_dusters(mesh, center, ranges=None):
    """Four banded fan worms, with independently retractable crowns."""
    x, y, z = center
    for worm in range(4):
        cx, cy, cz = x + (worm-1.5)*.42, y, z + (worm % 2)*.12
        begin = len(mesh.vertices)
        mesh.swept_tube([(cx,cy,cz-.24),(cx,cy,cz+.02)], .035, 'duster_tube', 6)
        for ray in range(19):
            angle = math.pi * (.04 + .92*ray/18)
            outer = (cx+.25*math.cos(angle), cy, cz+.28*math.sin(angle))
            inner = (cx+.07*math.cos(angle), cy, cz+.07*math.sin(angle))
            mid = tuple((a+b)*.5 for a,b in zip(inner, outer))
            mesh.swept_tube([inner, mid], .014, 'duster_light' if ray % 2 else 'duster_dark', 4)
            mesh.swept_tube([mid, outer], .014, 'duster_dark' if ray % 2 else 'duster_light', 4)
        if ranges is not None:
            ranges.append((begin, len(mesh.vertices), (cx,cy,cz-.24)))


def _feather_star(mesh, center, ranges=None):
    x, y, z = center
    mesh.ellipsoid((x, y, z), (.14, .12, .09), 'star_grad', 12, 6)
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
        mesh.swept_tube(points, .013, 'star_grad', 5)
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
                # Pinnules keep the tan polyp tile: two tones read as feathery.
                mesh.swept_tube([p, tip], .007, 'polyp', 5)
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
        mesh.swept_tube([(p[0],p[1],p[2]+.008) for p in ridge], .010, 'polyp', 5)


NUDI_LENGTH, NUDI_WIDTH, NUDI_HEIGHT = .30, .15, .04   # mantle half-length, half-width, dome height
NUDI_RIDGE_HEIGHT = .012
NUDI_GRID = (36, 14)                                     # mantle samples along, across


def _nudi_height(u, v):
    """Mantle surface height at mantle coordinates u, v in [0, 1]: a low
    dome plus the raised ridges, using the atlas's own ridge layout."""
    from .atlas import NUDI_CELL_W, NUDI_RIDGE_V, nudi_ridge_centre, nudi_ridge_width
    q = 1 - (2 * u - 1) ** 2 - (2 * v - 1) ** 2
    if q <= 0:
        return 0.0
    dome = NUDI_HEIGHT * math.sqrt(q)
    x = u * NUDI_CELL_W
    ridge = max(max(0.0, 1 - ((v - nudi_ridge_centre(k, x)) / nudi_ridge_width(k, x)) ** 2)
                for k in range(len(NUDI_RIDGE_V)))
    return dome + NUDI_RIDGE_HEIGHT * ridge * min(1.0, 3 * math.sqrt(q))


def _nudibranch(mesh, center):
    """Phyllidia varicosa (front = -x). The mantle is a height field whose
    ridges rise exactly where atlas cell 12 paints them, and a 3D tubercle
    sits on every painted tubercle, so geometry and texture agree.
    Colours: docs/reference/thai-reef-skin-colours.md."""
    from .atlas import NUDI_CELL_H, NUDI_CELL_W, nudi_tubercles
    x, y, z = center
    if not hasattr(mesh, 'face_uvs'):
        mesh.face_uvs = {}
    nu, nv = NUDI_GRID

    def point(i, j):
        u, v = i / nu, j / nv
        # Elliptical outline: squeeze each column to the mantle's oval.
        half = math.sqrt(max(0.0, 1 - (2 * u - 1) ** 2))
        vv = .5 + (v - .5) * max(half, 1e-3)
        return ((x - NUDI_LENGTH + 2 * NUDI_LENGTH * u, y - NUDI_WIDTH + 2 * NUDI_WIDTH * vv,
                 z + _nudi_height(u, vv)), (u, vv))

    def uv(m):
        # Atlas cell 12 (x 0-255, y 768-1023), painted mantle rows 0-191.
        return ((m[0] * NUDI_CELL_W + .5) / 1024, (768 + m[1] * NUDI_CELL_H + .5) / 1024)

    for i in range(nu):
        for j in range(nv):
            corners = [point(i, j), point(i + 1, j), point(i + 1, j + 1), point(i, j + 1)]
            pts = list(dict.fromkeys(c[0] for c in corners))
            if len(pts) < 3:
                continue
            uvs = [uv(c[1]) for c in corners if c[0] in pts]
            uvs = list(dict.fromkeys(uvs))[:len(pts)] if len(uvs) != len(pts) else uvs
            pts, uvs = _oriented(pts, uvs, (0, 0, 1))
            mesh.face(pts, 'nudi_body')
            mesh.face_uvs[len(mesh.faces) - 1] = tuple(uvs)
    # A flat sole closes the underside (never seen from the tank camera).
    rim = [point(i, 0) for i in range(nu + 1)] + [point(i, nv) for i in range(nu, -1, -1)]
    rim = list({r[0]: r for r in rim}.values())
    sole = [((p[0], p[1], z), uv(m)) for p, m in reversed(rim)]
    mesh.face([p for p, _ in sole], 'nudi_body')
    mesh.face_uvs[len(mesh.faces) - 1] = tuple(t for _, t in sole)
    # Yellow-capped tubercles, one on every painted tubercle.
    su, sv = 2 * NUDI_LENGTH / NUDI_CELL_W, 2 * NUDI_WIDTH / NUDI_CELL_H
    for tx, ty, radius in nudi_tubercles():
        u, v = tx / NUDI_CELL_W, ty / NUDI_CELL_H
        if 1 - (2 * u - 1) ** 2 - (2 * v - 1) ** 2 < .15:
            continue
        px, py = x - NUDI_LENGTH + 2 * NUDI_LENGTH * u, y - NUDI_WIDTH + 2 * NUDI_WIDTH * v
        r = radius * .85
        mesh.ellipsoid((px, py, z + _nudi_height(u, v) + r * sv * .4), (r * su, r * sv, r * sv * .9),
                       'nudi_tubercle', 6, 3)
    for side in (-1, 1):
        u0 = .11
        base = (x - NUDI_LENGTH + 2 * NUDI_LENGTH * u0, y + side * .035, z + _nudi_height(u0, .5 + side * .12))
        tip = (base[0] - .03, base[1] + side * .012, base[2] + .07)
        mesh.swept_tube([base, tip], .011, 'nudi_tubercle', 5)
        mesh.ellipsoid(tip, (.014, .014, .016), 'nudi_tubercle', 6, 4)


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
    color = {'sponge': 'crust_sponge', 'coralline': 'crust_coralline'}[color]
    x,y,z = center
    rng = random.Random(SEED + round((x + 6)*1000) + round(z*100))
    radii = [rng.uniform(.65,1.2) for _ in range(15)]
    from .placement import on_rock_face
    centre_y = on_rock_face(x, z)[0][1]

    def point(i, fraction):
        angle = math.tau*(i % 15)/15
        radius = radii[i % 15]*fraction
        relief = .008*(1-fraction) + .006*math.sin(3*angle+fraction*4)*fraction*(1-fraction)
        # Conform to the rock: at most about 1 world cm proud of its surface.
        # Where the outline runs past the rock's silhouette, pull it inward
        # until there is rock behind it, so the crust never overhangs water.
        scale = 1.0
        while True:
            px = x + rx*radius*scale*math.cos(angle)
            pz = z + rz*radius*scale*math.sin(angle)
            try:
                surface_y = on_rock_face(round(px, 4), round(pz, 4))[0][1]
            except ValueError:
                surface_y = None
            if surface_y is not None and abs(surface_y - centre_y) < .25:
                return (px, surface_y - relief, pz)
            if scale <= .05:
                return (x, centre_y - relief, z)
            scale -= .1
    for i in range(15):
        mesh.face([point(0,0),point(i,1/3),point(i+1,1/3)],color)
        for ring in (1,2):
            a,b=ring/3,(ring+1)/3
            mesh.face([point(i,a),point(i,b),point(i+1,b),point(i+1,a)],color)


def populate(mesh):
    """Add visible static colonies; dynamic animals are authored separately.
    Everything attached is placed on its host surface (reef.placement)."""
    from mesh import Mesh
    from .placement import grow_axis, on_rock_face, on_rock_top, upright_position
    _zoanthids(mesh, (-3.55, -1.25, 1.55))
    _zoanthids(mesh, (2.0, -1.05, 1.55))
    _zoanthids(mesh, (4.0, -.95, 1.70))
    # Small orange cup-coral clusters on the exposed rock faces and cave edge,
    # each cup on the surface and growing out of it.
    for x, z in ((-4.4, 1.18), (-3.6, 1.25), (-1.9, 1.5), (1.75, 1.5), (3.1, 1.22), (4.4, 1.34)):
        for i in range(3):
            base, normal = on_rock_face(x + (i-1)*.11, z + .025*(i % 2))
            base = tuple(base[k] - .015 * normal[k] for k in range(3))
            _placed(mesh, lambda m, i=i: _cup(m, (0, 0, 0), .065, .10 + .02*i, 'sponge', 8),
                    base, grow_axis(normal, .3), spin=i)
    # Encrusting sponge and coralline crusts, conformed onto the rock face.
    for x, z, rx, rz, color in (
        (-4.55, 1.35, .25, .16, 'sponge'), (-3.8, 2.00, .22, .14, 'coralline'),
        (-3.05, 1.25, .27, .14, 'sponge'), (-2.0, 2.55, .20, .12, 'coralline'),
        (1.7, 1.20, .23, .15, 'sponge'), (2.35, 2.20, .20, .14, 'coralline'),
        (3.25, 1.22, .27, .14, 'sponge'), (4.4, 2.15, .22, .13, 'coralline'),
    ):
        _encrusting_patch(mesh, (x, 0, z), rx, rz, color)
    # The mushroom coral lies free on the sand.
    local = Mesh('local'); _mushroom_coral(local, (0, 0, 0))
    _mushroom_coral(mesh, upright_position('MushroomCoral', min(v[2] for v in local.vertices)))
    # Tubastraea cups ring the top of the arch.
    for i in range(6):
        angle = math.tau * i / 6
        base, normal = on_rock_top(.72 + .22 * math.cos(angle), -.8 + .12 * math.sin(angle) - .6, min_up=.5)
        base = tuple(base[k] - .02 * normal[k] for k in range(3))
        _placed(mesh, lambda m, i=i: _cup(m, (0, 0, 0), .12, .19 + .04 * (i % 2), 'coralline', 10),
                base, grow_axis(normal, .6), spin=angle)
