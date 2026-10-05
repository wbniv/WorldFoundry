"""Textured short-spined regular urchin; rigid shafts and soft contact feet."""
import math
from pathlib import Path
from mesh import Mesh
COLORS=dict(urchin_surface=(1,1,1),urchin_foot=(1,1,1))
TEXTURE='urchin_surfaces.tga'

class UrchinMesh(Mesh):
    def __init__(self,name):
        super().__init__(name);self.uvs=[]
    def face(self,points,color,uvs=None):
        points=list(points)
        if uvs is None:
            if color=='urchin_foot':
                uvs=[((180+32*math.atan2(p[1],p[0])/math.pi)/256,(216+min(25,max(-25,p[2]*100)))/256) for p in points]
            else:
                a=[math.atan2(p[1],p[0])/math.tau%1 for p in points]
                if max(a)-min(a)>.5:a=[x+1 if x<.5 else x for x in a]
                uvs=[((7+112*x)/256,(14+173*min(1,max(0,(p[2]+.23)/.46)))/256) for p,x in zip(points,a)]
        super().face(points,color);self.uvs.extend(uvs)

def spine_specs():
    """Stable identities for subsequent basal pivot actors."""
    out=[]
    for row,(h,count) in enumerate([(-.26,14),(.12,18),(.44,14),(.73,10),(.94,5)]):
        for i in range(count):
            a=math.tau*(i+.37*row)/count
            d=(math.sqrt(1-h*h)*math.cos(a),math.sqrt(1-h*h)*math.sin(a),h)
            out.append(dict(root=(d[0]*.302,d[1]*.302,d[2]*.218),direction=d,length=.195+.068*((i*7+row*3)%7)/6,radius=.0135,secondary=False))
    for i in range(40):
        h=-.32+1.23*(i+.5)/40;a=i*2.3999632297+.31
        d=(math.sqrt(1-h*h)*math.cos(a),math.sqrt(1-h*h)*math.sin(a),h)
        out.append(dict(root=(d[0]*.31,d[1]*.31,d[2]*.224),direction=d,length=.058+.029*(i%5)/4,radius=.0065,secondary=True))
    return out

def add_spine(m,s):
    root,d,L,r=s['root'],s['direction'],s['length'],s['radius'];sides=4 if s['secondary'] else 8
    ref=(0,0,1) if abs(d[2])<.9 else (0,1,0)
    u=(d[1]*ref[2]-d[2]*ref[1],d[2]*ref[0]-d[0]*ref[2],d[0]*ref[1]-d[1]*ref[0]);n=math.sqrt(sum(v*v for v in u));u=tuple(v/n for v in u)
    v=(d[1]*u[2]-d[2]*u[1],d[2]*u[0]-d[0]*u[2],d[0]*u[1]-d[1]*u[0]);rings=[]
    for t,f in ((0,1.45),(.10,1),(.69,.54)):
        rings.append([tuple(root[j]+d[j]*L*t+r*f*(u[j]*math.cos(math.tau*k/sides)+v[j]*math.sin(math.tau*k/sides)) for j in range(3)) for k in range(sides)])
    def uv(k,t):return ((141+105*k/sides)/256,(22+154*t)/256)
    if s['secondary']:
        tip=tuple(root[j]+d[j]*L for j in range(3))
        for k in range(sides):m.face([rings[0][k],rings[0][(k+1)%sides],tip],'urchin_surface',[uv(k,0),uv(k+1,0),uv(k+.5,1)])
        return
    for j,(a,b) in enumerate(zip(rings,rings[1:])):
        t0,t1=(0,.1) if j==0 else (.1,.69)
        for k in range(sides):m.face([a[k],a[(k+1)%sides],b[(k+1)%sides],b[k]],'urchin_surface',[uv(k,t0),uv(k+1,t0),uv(k+1,t1),uv(k,t1)])
    tip=tuple(root[j]+d[j]*L for j in range(3))
    for k in range(sides):m.face([rings[-1][k],rings[-1][(k+1)%sides],tip],'urchin_surface',[uv(k,.69),uv(k+1,.69),uv(k+.5,1)])

def urchin():
    m=UrchinMesh('sea_urchin');m.ellipsoid((0,0,0),(.32,.32,.23),'urchin_surface',18,12)
    for s in spine_specs():add_spine(m,s)
    return m

def tube_foot():
    """Disc-rooted foot, local +X stem; existing actor transforms aim the root."""
    m=UrchinMesh('urchin_tube_foot')
    m.swept_tube([(.006,0,0),(.034,0,.002),(.068,0,.002),(.1,0,0)],.0125,'urchin_foot',6)
    m.ellipsoid((0,0,0),(.011,.024,.024),'urchin_foot',6,3)
    return m

def write_texture(folder):
    """Deterministic 256-square atlas: plate pores, shaft ridges and pale feet."""
    from PIL import Image
    image=Image.new('RGB',(256,256))
    for y in range(256):
        for x in range(256):
            grain=((x*37+y*71+x*y*13)%17-8)*.65
            if x<128:
                u=x/128;lat=y/192;plate=.5+.5*math.cos(math.tau*5*u)
                pore=math.exp(-((math.sin(math.tau*10*u)/.17)**2+(math.sin(math.tau*12*lat)/.25)**2));shade=.7+.3*math.sin(math.pi*min(1,lat))
                rgb=[(94+23*plate-27*pore)*shade,(56+14*plate-20*pore)*shade,(130+26*plate-29*pore)*shade]
            elif y<192:
                ridge=.5+.5*math.cos(math.tau*(x-141)/13);tip=max(0,(y-145)/35)
                rgb=[105+28*ridge+25*tip,65+17*ridge+20*tip,142+31*ridge+14*tip]
            else:
                ring=.5+.5*math.cos((x-128)*.3);rgb=[163+20*ring,173+24*ring,150+26*ring]
            image.putpixel((x,y),tuple(round(max(0,min(255,c+grain))) for c in rgb))
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    image.save(folder/TEXTURE);image.save(folder/'urchin-surfaces-source.png')
