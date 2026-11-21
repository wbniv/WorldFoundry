"""Continuous five-armed sea-star surfaces, atlas and exported DFRM v2 binding."""
import math
import struct
from config import SPECIES
import brittle
KEYS = tuple(SPECIES)
SIZE = 512

def mesh(Mesh, kind):
    if kind=='brittle':return brittle.mesh(Mesh)
    spec = SPECIES[kind]
    out = Mesh('star_'+kind)
    radius, disc, height = (spec[k] for k in ('radius','disc','height'))
    segments = {'linckia':160,'sand':120}.get(kind,100)
    rings = 9
    width = spec['width']
    tip = {'linckia':.065,'chip':.035,'fromia':.025,'sand':.018,'cushion':.09}[kind]
    def inside(r,theta):
        if r <= disc: return True
        delta = (theta + math.pi/5) % (math.tau/5) - math.pi/5
        u,v = r*math.cos(delta),abs(r*math.sin(delta))
        end = radius-tip
        if u > end: return (u-end)**2+v*v <= tip*tip
        if u < 0: return False
        t=max(0,min(1,u/end))
        w=width*(1-t)+tip*t
        return v <= w
    def outline(theta):
        if kind=='cushion':
            return radius*(.91+.09*math.cos(5*theta))
        lo,hi=disc,radius
        for _ in range(22):
            mid=(lo+hi)/2
            if inside(mid,theta):lo=mid
            else:hi=mid
        return lo
    outlines = [outline(math.tau*i/segments) for i in range(segments)]
    def point(i,j,top):
        i%=segments
        theta = math.tau*i/segments
        f=j/rings; r=f*outlines[i]
        delta=(theta+math.pi/5)%(math.tau/5)-math.pi/5
        u,v=r*math.cos(delta),r*math.sin(delta)
        if kind=='cushion':
            z=height*math.sqrt(max(0,1-f*f))
        else:
            t=max(0,min(1,u/(radius-tip)))
            w=width*(1-t)+tip*t
            cap = max(0,1-(max(0,u-radius+tip)/tip)**2)
            arm=height*(1-.45*t)*math.sqrt(max(0,1-(v/w)**2))*math.sqrt(cap)
            dome=height*math.sqrt(max(0,1-(r/disc)**2))
            z=max(arm,dome)
        # Pin the shared outer seam so upper and lower surfaces are watertight.
        if j==rings:z=0
        if not top:
            # Sculpted oral depression and five longitudinal grooves.
            groove=math.exp(-(v/.035)**2)*(.7 if r>.1 else 1)
            z=-.022*(1-f*f)+.012*groove*(1-f)
        return (r*math.cos(theta),r*math.sin(theta),z)
    for top in (True,False):
        material = kind if top else 'underside'
        for i in range(segments):
            for j in range(rings):
                pts = [point(i,j,top),point(i,j+1,top),point(i+1,j+1,top),point(i+1,j,top)]
                pts = list(dict.fromkeys(tuple(round(v,8) for v in p) for p in pts))
                if len(pts) >= 3:
                    out.face(pts if top else list(reversed(pts)),material)
    if kind == 'chip':
        for arm in range(5):
            a = math.tau*arm/5
            for t in (.37,.58,.78):
                r = radius*t
                z = height*(1-.45*t)
                # Dark tapered knobs, not simply flat spots.
                rr = .065*(1-.3*t)
                base = [(r*math.cos(a)+rr*math.cos(math.tau*i/8),r*math.sin(a)+rr*math.sin(math.tau*i/8),z-.01) for i in range(8)]
                tip = (r*math.cos(a),r*math.sin(a),z+.10)
                for i in range(8): out.face([base[i],base[(i+1)%8],tip],'knob')
        out.ellipsoid((0,0,height+.025),(.075,.075,.08),'knob',8,4)
    if kind == 'linckia':
        for arm in range(5):
            a = math.tau*arm/5
            eye_z=point(arm*segments//5,rings-1,True)[2]*(1-.965)*rings+.002
            out.ellipsoid((radius*.965*math.cos(a),radius*.965*math.sin(a),eye_z),(.009,.009,.003),'eye',6,4)
    if kind == 'sand':
        for i in range(120):
            a = math.tau*i/120
            p = point(i,9,True)
            out.ellipsoid((p[0],p[1],.003),(.014,.014,.012),'plate',5,3)
    return out

def uv_face(kind,color,points):
    if kind=='brittle':return brittle.uv(color,points)
    cell = {'underside':6,'knob':7,'eye':8,'plate':9}.get(color,KEYS.index(kind))
    x,y = cell%4,cell//4
    radius = SPECIES[kind]['radius']
    if color in ('knob','eye','plate'):
        return [((x+.5)/4,(y+.5)/4)]*len(points)
    return [((x+.5+.46*p[0]/radius)/4,(y+.5+.46*p[1]/radius)/4) for p in points]

def write_atlas(path):
    pixels = bytearray()
    for y in range(SIZE):
        for x in range(SIZE):
            cell = x//128 + 4*(y//128)
            u,v = (x%128-64)/60,(y%128-64)/60
            noise = ((x*73856093 ^ y*19349663) & 255)/255-.5
            if cell < 6:
                kind = KEYS[cell]
                c = SPECIES[kind]['color']
                grain = 1 + .14*noise + .045*math.sin(x*.17)*math.cos(y*.21)
                if kind == 'fromia' and ((x*37+y*13)%43 < 2): grain=.38
                if kind == 'sand': grain += .10*math.sin(x*.7)*math.sin(y*.8)
                if kind == 'brittle':
                    lx,ly=x%128,y%128
                    if lx<64:
                        spot=math.hypot((lx%11)-5,(ly%12)-6)
                        c=(71,109,59) if not 2.6<spot<3.7 else (38,57,29)
                    else:
                        c=(93,128,67) if (lx-64)%5 else (174,177,113)
                        if (lx-64)%5==1:grain*=.70
                if kind == 'cushion':
                    cellx=(x%128)//11; celly=(y%128)//10
                    cx=cellx*11+5+(celly%2)*3;cy=celly*10+5
                    d=math.hypot((x%128)-cx,(y%128)-cy)
                    if 3.5<d<4.8:grain=.48
                if kind=='linckia' and (x+int(y/3)*2)%7==0 and y%6==0:grain=.78
                c = tuple(int(min(255,max(1,k*grain))) for k in c)
            elif cell == 6:
                # Five oral grooves converge on the central mouth; paired
                # pale tube-foot rows remain visible on the front glass.
                a = math.atan2(v,u); r = math.hypot(u,v)
                side = abs(math.sin(a*5/2))*r
                c = (114,169,202)
                if side < .055: c=(51,104,147)
                if .055<side<.085 and int(r*48)%3==0: c=(211,225,211)
                if r<.065: c=(35,61,82)
            else:
                c={7:(66,43,32),8:(171,39,28),9:(213,204,179),10:(205,191,154),11:(113,108,88),12:(49,93,54),13:(19,40,56),14:(32,67,83),15:(46,84,99)}[cell]
                if cell>=13:
                    stops=((13,29,40),(23,48,64),(31,65,84),(42,84,101))
                    t=(y%128)/127
                    c=tuple(round(stops[cell-13][k]*(1-t)+stops[cell-12][k]*t) for k in range(3))
                if cell in (10,11,12):
                    grain=1+.13*noise+.05*math.sin(x*.2+y*.1)
                    if cell==10:grain+=.055*math.sin(x*.26+math.sin(y*.11)*1.4)
                    if cell==11:
                        grain+=.12*math.sin(x*.31)*math.sin(y*.27)
                        patch=math.sin(x*.073+.7*math.sin(y*.13))*math.cos(y*.091)+noise*.12
                        if patch>.83:c=(140,105,131)
                        elif patch<-.87:c=(82,92,64)
                    c=tuple(max(1,min(255,int(k*grain))) for k in c)
            pixels.extend((c[2],c[1],c[0]))
    header = struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,SIZE,SIZE,24,32)
    path.write_bytes(header+pixels)

def bind(path,kind,dfrm):
    if kind == 'cushion': return
    data = path.read_bytes()
    off,vertices = 8,None
    while off < len(data):
        tag,size = struct.unpack_from('<4sI',data,off)
        if tag == b'VRTX':
            vertices = [tuple(v/65536 for v in struct.unpack_from('<iii',data,off+20+i)) for i in range(0,size,24)]
        if tag == b'DFRM': raise ValueError('already bound')
        off += 8+((size+3)&~3)
    if not vertices: raise ValueError('no vertices')
    spec = SPECIES[kind]
    count=brittle.sample_count(kind)
    chains=[]
    for arm in range(5):
        chains.append([dict(head=brittle.bone_point(kind,arm,i),tail=brittle.bone_point(kind,arm,i+1),
                            z_axis=(0,0,1),limits=(90,90,70,70)) for i in range(count)])
    bindings=[]
    for p in vertices:
        owner=brittle.binding(kind,p)
        bindings.append((dfrm.NONE,0,0) if owner is None else (dfrm.ON_SAMPLE,count*owner[0]+owner[1],1))
    if kind=='brittle':
        clips=[dict(name=clip,loop=True,frames=[
            [angle for arm in range(5) for i in range(count) for angle in brittle.angles(arm,i,frame,clip)]
            for frame in range(61)]) for clip in ('hide','row')]
        knots=(0,4,8,12,15)
    else:
        clips=[dict(name='glide',loop=True,frames=[
            [angle for arm in range(5) for i in range(count) for angle in (3*math.sin(math.tau*frame/30-i*.7) if i else 0,0,0)]
            for frame in range(31)])]
        knots=(0,1,2,3)
    payload=dfrm.build_chunk_curves(chains,vertices,bindings,clips=clips,knots=knots)
    chunk=b'DFRM'+struct.pack('<I',len(payload))+payload+b'\0'*(-len(payload)%4)
    path.write_bytes(b'MODL'+struct.pack('<I',len(data)-8+len(chunk))+data[8:]+chunk)
