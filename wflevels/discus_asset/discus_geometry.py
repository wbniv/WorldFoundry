"""Discus mesh data, without Blender: the one source for model.py and the Aquarium tank.

Moved verbatim out of model.py (2026-11-22, docs/plans/2026-11-22-discus-tank.md) so the
Discus tank (wflevels/aquarium/discus_school.py) and its tests read the same vertices,
faces and UVs as the editable model. Coordinates are metres, +X nose, +Z up.
"""
import math


def mesh_data():
    """Return (verts, faces): the body and every fin in one list, as model.py builds them."""
    verts = []; faces = []

    def meshpart(v, f):
        offset = len(verts); verts.extend(v); faces.extend(tuple(offset+i for i in face) for face in f)
    # Body: ellipsoidal, laterally compressed. +X nose, +Z up, in metres.
    n = 48; rings = 28; v = []; f = []
    for i in range(rings+1):
        x = -.065+.125*i/rings
        r = math.sin(math.pi*i/rings)**.63
        for j in range(n):
            a = math.tau*j/n; v.append((x, .018*r*math.cos(a), .073*r*math.sin(a)))
    for i in range(rings):
        for j in range(n):
            a = i*n+j; b = i*n+(j+1) % n; c = (i+1)*n+(j+1) % n; d = (i+1)*n+j
            if i == 0: f.append((a, c, d))
            elif i == rings-1: f.append((a, b, c))
            else: f.append((a, b, c, d))
    meshpart(v, f)

    def fin(points):
        # Fan triangulation, both faces for thin opaque fins.
        center = tuple(sum(p[k] for p in points)/len(points) for k in range(3)); v = [center]+points; f = []
        for i in range(len(points)):
            face = (0, 1+i, 1+(i+1) % len(points)); a, b, c = (v[k] for k in face); ny = (b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]); f.append(face if ny < 0 else tuple(reversed(face)))
        meshpart(v, f)
    # Overlap fin roots under the body at the caudal peduncle.
    fin([(-.085,0,.048),(-.055,0,.060),(-.045,0,-.060),(-.085,0,-.048),(-.075,0,0)])
    # Dorsal and anal surfaces curl around the body into posterior extensions.
    fin([(.035,0,.045),(.02,0,.068),(-.005,0,.085),(-.038,0,.088),(-.065,0,.075),(-.084,0,.048),(-.071,0,.021),(-.052,0,.049),(-.02,0,.070),(.01,0,.065)])
    fin([(.025,0,-.053),(.005,0,-.075),(-.025,0,-.09),(-.055,0,-.086),(-.082,0,-.056),(-.072,0,-.020),(-.05,0,-.052),(-.02,0,-.069),(.005,0,-.067)])
    fin([(-.06,0,.018),(-.08,0,.032),(-.10,0,.038),(-.105,0,.02),(-.107,0,0),(-.105,0,-.02),(-.10,0,-.038),(-.08,0,-.032),(-.06,0,-.018)])
    for side in (-1, 1):
        fin([(.025,side*.015,.005),(.012,side*.029,.002),(-.004,side*.037,-.017),(.013,side*.026,-.024),(.026,side*.015,-.01)])
        fin([(.024,side*.008,-.058),(.012,side*.013,-.075),(.001,side*.014,-.112),(.018,side*.009,-.083)])
    return verts, faces


def uv(x, z):
    """Texture coordinate of a source-space vertex. WF convention: V measured down from texture top."""
    return (x+.11)/.18, (.12-z)/.24
