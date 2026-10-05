"""Lionfish authoring asset: one mesh, named regions, shared texture coordinates.

Named point attributes export to optional LRIG v1 metadata, independent of UVs.
The approved native rig consumes them. +X faces the head, +Z is dorsal.
"""
import json
import math
from pathlib import Path
from mesh import Mesh

PALETTES = [
    {'name':'wine-cream','dark':(.23,.065,.047),'light':(.91,.80,.61)},
    {'name':'umber-sand','dark':(.12,.075,.055),'light':(.78,.71,.53)},
    {'name':'chestnut-ivory','dark':(.35,.10,.064),'light':(.94,.88,.72)},
]

def palette_for(seed, fish_id):
    # A bijective offset for consecutive IDs keeps the initial pair distinct.
    offset=((int(seed)*1664525)&0xffffffff)%len(PALETTES)
    return (offset+int(fish_id))%len(PALETTES)

def geometry():
    m=Mesh('lionfish');m.uvs=[];m.regions=[];m.weights=[]
    def vertex(p,uv,region,weight=0):
        i=len(m.vertices);m.vertices.append(p);m.uvs.append(uv)
        m.regions.append(region);m.weights.append(weight);return i
    def face(ids,mat='body'):
        # Fan roots collapse geometrically but retain distinct UV/root weights.
        unique=[];seen=set()
        for i in ids:
            key=tuple(round(v,9) for v in m.vertices[i])
            if key not in seen:seen.add(key);unique.append(i)
        if len(unique)>=3:m.faces.append(tuple(unique));m.colors.append(mat)
    def surface(nu,nv,point,region,mat='body'):
        start=len(m.vertices)
        for j in range(nv+1):
            for i in range(nu+1):
                u,v=i/nu,j/nv;p=point(u,v)
                vertex(p,(u,v),region,v*v)
        for j in range(nv):
            for i in range(nu):
                a=start+j*(nu+1)+i;face((a,a+1,a+nu+2,a+nu+1),mat)
    # Connected body rings with a head-heavy profile and narrow caudal peduncle.
    nu,nv=30,20
    for j in range(nv+1):
        t=j/nv;x=-.56+1.19*t
        envelope=max(.005,math.sin(math.pi*t))**.65
        width=(.13+.105*t)*envelope; depth=(.18+.12*t)*envelope
        for i in range(nu+1):
            a=math.tau*i/nu;y=width*math.cos(a);z=depth*math.sin(a)-.025*t
            region='jaw' if x>.34 and z<-.035 else 'head' if x>.35 else 'trunk'
            weight=max(0,min(1,(x-.34)/.22)) if region in ('jaw','head') else 0
            vertex((x,y,z),(t,i/nu),region,weight)
    for j in range(nv):
        for i in range(nu):
            a=j*(nu+1)+i;face((a,a+1,a+nu+2,a+nu+1))
    # Mouth rim/interior, a separate geometry island within the same mesh.
    for j in range(3):
        for i in range(25):
            a=math.tau*i/24;r=(.045,.030,.014)[j]
            vertex((.626-j*.035,r*math.cos(a),-.025+r*.8*math.sin(a)),(.96,.5),
                   'jaw' if math.sin(a)<0 else 'head',1)
    start=len(m.vertices)-75
    for j in range(2):
        for i in range(24):
            a=start+j*25+i;face((a,a+1,a+26,a+25),'mouth')
    def tube(points,radius,region,mat='body',sides=5):
        start=len(m.vertices)
        for j,p in enumerate(points):
            t=j/(len(points)-1);r=radius*(1-.88*t)
            for i in range(sides+1):
                a=math.tau*i/sides
                vertex((p[0]+r*math.cos(a),p[1]+r*math.sin(a),p[2]),(t,i/sides),region,t*t)
        for j in range(len(points)-1):
            for i in range(sides):
                a=start+j*(sides+1)+i;face((a,a+1,a+sides+2,a+sides+1),mat)
    # Thirteen dorsal spines, with restrained attached sheath geometry.
    for i in range(13):
        x=.34-.057*i;h=.25+.26*math.sin(math.pi*(i+1)/14)
        tube([(x-.14*t*t,0,.22+h*t) for t in (0,.33,.67,1)],.010,'spines')
    for side in (-1,1):
        # Anatomical pelvic spine: one per side; soft fan is separate.
        tube([(.23,side*.10,-.12),(.14,side*.20,-.35),(.03,side*.22,-.47)],.009,'pelvic')
        tube([(.44,side*.12,.12),(.41,side*.13,.24),(.35,side*.14,.29)],.014,'head')
        # Curved fans. UV coordinates are simultaneously meaningful surface
        # coordinates (across ray/root-to-tip); they are never overwritten.
        def pectoral(u,r,s=side):
            a=-.80+2.0*u
            return (.27-r*(.55+.33*math.cos(a)),s*(.15+r*(.45+.24*math.sin(math.pi*u))),
                    -.04+r*(.17-.54*u)+.025*math.sin(math.pi*r)*math.sin(math.pi*u))
        surface(32,12,pectoral,'pectoral_left' if side<0 else 'pectoral_right','fin')
    surface(24,8,lambda u,r:(-.51-r*(.27+.07*math.sin(math.pi*u)),
            .025*math.sin(math.pi*r)*math.sin(math.tau*u), (u-.5)*(.08+.52*r)), 'tail','fin')
    surface(16,6,lambda u,r:(-.47+.31*u,.018*math.sin(math.pi*u)*r,.12+r*(.14+.13*math.sin(math.pi*u))), 'dorsal','fin')
    surface(16,6,lambda u,r:(-.40+.33*u,.012*r,-.10-r*(.12+.12*math.sin(math.pi*u))), 'anal','fin')
    for i in range(3):
        x=-.17-.075*i;tube([(x,0,-.12),(x-.055,0,-.29)],.007,'anal')
    # Eye discs follow skull motion, not the lower jaw.
    for side in (-1,1):
        def eye_point(x,z):
            t=(x+.56)/1.19;e=max(.005,math.sin(math.pi*t))**.65
            width=(.13+.105*t)*e;depth=(.18+.12*t)*e
            y=width*math.sqrt(max(0,1-((z+.025*t)/depth)**2))+.003
            return (x,side*y,z)
        center=len(m.vertices);vertex(eye_point(.43,.065),(.5,.5),'head',.55)
        for i in range(17):
            a=math.tau*i/16
            vertex(eye_point(.43+.031*math.cos(a),.065+.035*math.sin(a)),(.5,.5),'head',.55)
        for i in range(16):face((center,center+1+i,center+2+i),'eye')
    return m

def write_textures(folder):
    from PIL import Image
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    body,fin=Image.new('RGBA',(256,256)),Image.new('RGBA',(256,256))
    for y in range(256):
        v=y/255
        for x in range(256):
            u=x/255
            stripe=math.sin(math.tau*(u*11+.11*math.sin(v*math.tau*2)+.035*math.sin(u*29+v*8)))
            band=max(0,min(1,(stripe+.1)*2+.5))
            scales=.025*math.sin(u*210+math.sin(v*120))*math.sin(v*120)
            b=round(255*max(.04,min(1,.16+.80*band+scales)))
            body.putpixel((x,y),(b,b,b,255))
            ray=max(0,math.cos(u*math.tau*16))**14
            spot=max(0,math.cos(u*math.tau*19+v*5)*math.cos(v*math.tau*7))**10
            f=round(255*max(.04,min(1,.80-.55*ray-.35*spot)))
            fin.putpixel((x,y),(f,f,f,255))
    body.save(folder/'lionfish_body.tga');fin.save(folder/'lionfish_fins.tga')

def write_manifest(folder):
    m=geometry();p=Path(folder);p.mkdir(parents=True,exist_ok=True)
    data={'vertices':len(m.vertices),'triangles':sum(len(f)-2 for f in m.faces),
          'dorsal_spines':13,'anal_spines':3,'pelvic_spines':2,
          'regions':m.regions,'weights':m.weights,'palettes':PALETTES,
          'texture_maps':['lionfish_body.tga','lionfish_fins.tga'],
          'status':'single-mesh native runtime rig implemented'}
    (p/'lionfish-rig.json').write_text(json.dumps(data,indent=2)+'\n')
    return m,data

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);a=ap.parse_args()
    write_textures(a.out);_,data=write_manifest(a.out)
    print(json.dumps({k:data[k] for k in ['vertices','triangles','dorsal_spines','status']}))

REGIONS=('trunk','head','jaw','pectoral_left','pectoral_right','tail','dorsal','anal','pelvic','spines')
def rig_attributes(data,mesh):
    region=data.attributes.new('wf_lion_region','INT','POINT')
    weight=data.attributes.new('wf_lion_weight','FLOAT','POINT')
    pivot=data.attributes.new('wf_lion_pivot','FLOAT_VECTOR','POINT')
    # Adding a CustomData layer can invalidate earlier RNA handles.
    region=data.attributes['wf_lion_region'];weight=data.attributes['wf_lion_weight'];pivot=data.attributes['wf_lion_pivot']
    for i,(p,r,w) in enumerate(zip(mesh.vertices,mesh.regions,mesh.weights)):
        region.data[i].value=REGIONS.index(r);weight.data[i].value=w
        if r.startswith('pectoral'):root=(.27,-.15 if r.endswith('left') else .15,-.04)
        elif r in ('head','jaw'):root=(.34,0,-.035)
        elif r=='tail':root=(-.51,0,0)
        elif r=='spines':root=(p[0]+.14*w,0,.22)
        else:root=p
        pivot.data[i].vector=root

def packed_palette(seed,fish_id):
    p=PALETTES[palette_for(seed,fish_id)]
    def packed(rgb):
        r,g,b=(round(v*255) for v in rgb);return (r<<16)|(g<<8)|b
    return packed(p['dark']),packed(p['light'])
