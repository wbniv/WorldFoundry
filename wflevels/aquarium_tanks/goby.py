"""Adult male Stiphodon ornatus prototype: body plus translucent fins.

Body texture UVs are ordinary atlas coordinates. Fin UV.v is root-to-tip,
compatible with the existing swim-deform primitive; both parts share a span.
No engine changes are required to author or deform these meshes.
"""
import math
from pathlib import Path
from mesh import Mesh

COLORS = dict(goby_body=(1, 1, 1), goby_fin=(1, 1, 1))
BODY_TEXTURE = 'goby_body.tga'
FIN_TEXTURE = 'goby_fins.tga'
SPAN = (-.46, .34)
FIN_OPACITY = .62


class GobyMesh(Mesh):
    def __init__(self, name):
        super().__init__(name)
        self.uvs = []

    def face(self, points, color, uvs=None):
        points = list(points)
        if uvs is None:
            # Side projection, with inset gutters and a separate eye region.
            uvs = [(.04 + .77 * (p[0] + .46) / .8,
                    .10 + .72 * max(0, min(1, (p[2] + .09) / .19)))
                   for p in points]
        super().face(points, color)
        self.uvs.extend(uvs)


def body():
    m = GobyMesh('rainbow_goby_body')
    sections = [(-.34, .012, .025, .004), (-.27, .027, .042, .006),
                (-.16, .042, .060, .008), (-.02, .054, .075, .015),
                (.12, .071, .083, .023), (.24, .073, .078, .027),
                (.31, .049, .056, .012)]
    rings = [[(x, width * math.cos(math.tau * k / 16),
               height * math.sin(math.tau * k / 16) + z)
              for k in range(16)] for x, width, height, z in sections]
    # Centre fans keep the cap normals above the runtime's fixed-point minimum.
    # A 16-gon starts with three nearly collinear rim vertices at the small tail.
    for ring, section, reverse in ((rings[0], sections[0], True),
                                   (rings[-1], sections[-1], False)):
        center = (section[0], 0, section[3])
        for k in range(16):
            edge = [ring[k], ring[(k+1) % 16]]
            if reverse:
                edge.reverse()
            m.face([center, *edge], 'goby_body')
    for a, b in zip(rings, rings[1:]):
        for k in range(16):
            m.face([a[k], a[(k+1) % 16], b[(k+1) % 16], b[k]], 'goby_body')
    # Raised eyes; texture island has an iris/pupil rather than black spheres.
    for sign in (-1, 1):
        start = len(m.vertices)
        m.ellipsoid((.235, sign*.057, .072), (.028, .024, .028),
                    'goby_body', 10, 6)
        for i in range(start, len(m.vertices)):
            p = m.vertices[i]
            m.uvs[i] = (.905 + (p[0]-.235)*1.5,
                        .50 + (p[2]-.072)*1.5)
    # Lower subterminal lip, not a predatory forward gape.
    m.ellipsoid((.313, 0, -.017), (.021, .044, .012), 'goby_body', 10, 4)
    return m


def membrane(m, roots, tips, offset=0, width=.24):
    """Four strips across each ray interval; true rooted V for deformation."""
    for k in range(len(roots)-1):
        for j in range(4):
            t0, t1 = j/4, (j+1)/4
            def point(ray, t):
                return tuple(roots[ray][d]*(1-t)+tips[ray][d]*t for d in range(3))
            u0 = offset + width*k/(len(roots)-1)
            u1 = offset + width*(k+1)/(len(roots)-1)
            m.face([point(k, t0), point(k+1, t0), point(k+1, t1), point(k, t1)],
                   'goby_fin', [(u0, t0), (u1, t0), (u1, t1), (u0, t1)])


def fins():
    m = GobyMesh('rainbow_goby_fins')
    # Two distinct dorsals: high pointed first dorsal and lower long second.
    for lo, hi, heights, offset in ((.01, .19, [.06,.15,.20,.16,.07], 0),
                                  (-.25,-.04,[.025,.10,.105,.09,.04], .25)):
        roots = [(lo+(hi-lo)*k/4, 0, .069) for k in range(5)]
        tips = [(p[0]-.025, 0, p[2]+h) for p,h in zip(roots, heights)]
        membrane(m, roots, tips, offset)
    membrane(m, [(-.335, 0, -.024+.048*k/8) for k in range(9)],
             [(-.46+.026*abs(k-4)/4, 0, -.13+.26*k/8) for k in range(9)], .50)
    membrane(m, [(-.24+.20*k/4, 0, -.048) for k in range(5)],
             [(-.26+.20*k/4, 0, -.10-.02*math.sin(math.pi*k/4)) for k in range(5)], .75)
    for sign in (-1, 1):
        membrane(m, [(.13-.06*k/6, sign*.065, -.01+.016*k/6) for k in range(7)],
                 [(.11-.15*k/6, sign*(.08+.095*math.sin(math.pi*k/6)),
                   -.035-.04*math.sin(math.pi*k/6)) for k in range(7)], .75)
    # Joined pelvic disc: ventral pad, separate from the pectoral fans.
    start = len(m.vertices)
    m.ellipsoid((.075, 0, -.065), (.069, .050, .008), 'goby_fin', 12, 4)
    # Disc does not flap: pin all of its fin deformation weights at zero.
    m.uvs[start:] = [(.82, 0)]*(len(m.vertices)-start)
    return m


def write_textures(folder):
    """Editable 256² albedo: silver scales, blue cheek, patterned orange rays.

    Colour zones follow adult-male references rather than a uniform blue stripe.
    Four fin columns match membrane() U islands; V stays root-to-tip for motion.
    """
    from PIL import Image
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for filename in (BODY_TEXTURE, FIN_TEXTURE):
        image = Image.new('RGB', (256, 256))
        for y in range(256):
            for x in range(256):
                u, v = x/256, y/256
                grain = ((x*37+y*71+x*y*13)%23-11)*.48
                if filename == BODY_TEXTURE:
                    t,z = (u-.04)/.77, (v-.10)/.72
                    # Staggered overlapping scale crescents, approx. 30 along trunk.
                    row = math.floor(z*14)
                    sx = ((t*35 + (row%2)*.5)%1)-.5
                    sy = ((z*14)%1)-.48
                    rim = math.exp(-((math.hypot(sx*.95,sy*.75)-.43)/.062)**2)
                    glint = math.exp(-(((sx+.10)/.24)**2+((sy-.24)/.18)**2))
                    dorsal = max(0,min(1,(z-.57)/.40))
                    belly = max(0,min(1,(.33-z)/.28))
                    rgb = [182-75*dorsal+25*belly,
                           176-83*dorsal+27*belly,
                           155-82*dorsal+31*belly]
                    scale_mask = max(0,min(1,(.80-t)*8))
                    rgb = [c+scale_mask*(-43*rim+36*glint) for c in rgb]
                    # Broken brown posterior bars; not the old continuous black stripe.
                    bars = (.5+.5*math.cos(t*math.tau*16+z*1.5))**5
                    bars *= max(0,min(1,(.72-t)*8))*math.exp(-((z-.50)/.40)**4)
                    rgb = [c*(1-.32*bars) for c in rgb]
                    cheek = math.exp(-(((t-.835)/.12)**4+((z-.41)/.24)**4))
                    cheek *= .88+.12*math.sin(x*.57)*math.cos(y*.61)
                    blue = [21+32*glint, 147+63*glint, 196+45*glint]
                    rgb = [c*(1-cheek)+b*cheek for c,b in zip(rgb,blue)]
                    # Fine curved opercular edge and scattered iridescent scale tips.
                    gill = math.exp(-((t-(.723+.042*(z-.45)**2))/.009)**2)
                    gill *= math.exp(-((z-.47)/.33)**6)
                    rgb = [c*(1-.45*gill) for c in rgb]
                    if u > .83:
                        dx,dy = (u-.905)/.043,(v-.5)/.043
                        r = math.hypot(dx,dy)
                        iris = 12*math.sin(math.atan2(dy,dx)*25)
                        rgb = [155+iris, 157+iris, 105+iris]
                        if r<.80: rgb = [145+iris, 179+iris, 173+iris]
                        if r<.54: rgb = [5,10,13]
                        if .81<r<.96: rgb = [28,49,55]
                        if math.hypot(dx+.23,dy-.24)<.14: rgb = [220,235,229]
                else:
                    column = min(3,int(u*4))
                    across = (u-column*.25)/.24
                    rays = (6,10,17,15)[column]
                    ray = math.exp(-((math.sin(math.pi*across*rays))/.15)**2)
                    edge = math.exp(-((v-.94)/.035)**2)
                    if column == 0:
                        # Orange membrane with dark first-dorsal rays and cyan margin.
                        rgb = [186-145*ray, 119-84*ray, 41-13*ray]
                    elif column == 1:
                        spot = ray*(.5+.5*math.cos(v*math.tau*7+across*2))**10
                        rgb = [181+51*spot, 99+119*spot, 28+180*spot]
                    elif column == 2:
                        spot = ray*(.5+.5*math.cos(v*math.tau*9+across*1.5))**6
                        rgb = [177-109*spot+25*ray, 157-119*spot+12*ray, 100-76*spot]
                    else:
                        spot = ray*(.5+.5*math.cos(v*math.tau*9))**7
                        rgb = [163+51*ray-144*spot, 180+41*ray-142*spot, 166+50*ray-127*spot]
                    rgb = [c*(1-edge)+e*edge for c,e in zip(rgb,(92,208,231))]
                    # Pelvic disc occupies the rooted corner; no eye/stripe texture.
                    if column==3 and v<.06: rgb = [175,186,167]
                rgb = [c+grain for c in rgb]
                image.putpixel((x,y),tuple(round(max(0,min(255,c))) for c in rgb))
        image.save(folder/filename)
