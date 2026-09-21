#!/usr/bin/env python3
"""Build a fresh WF course from sampled arcade collision heights (no Blender)."""
import json
import math
import struct
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = 'marble-madness-3d'
Z_SCALE = math.sqrt(2 / 3) / 8
RADIUS = 0.48

def chunk(tag, payload):
    return tag.encode().ljust(4,b'\0') + struct.pack('<I',len(payload)) + payload + bytes(-len(payload)%4)

def cross(a,b,c):
    u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
    return (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])

class Mesh:
    def __init__(self): self.vertices=[];self.faces=[];self.cache={}
    def vertex(self,p,uv=(0,0)):
        key=tuple(round(v,7) for v in (*p,*uv))
        if key not in self.cache:
            self.cache[key]=len(self.vertices);self.vertices.append((*p,*uv))
        return self.cache[key]
    def tri(self,points,mat=0,uv=None):
        if sum(v*v for v in cross(*points))<1e-12: raise ValueError('degenerate triangle')
        uv=uv or [(0,0)]*3
        ids=[self.vertex(p,t) for p,t in zip(points,uv)]
        # Author right-handed, then reverse for WF's (v2-v0)x(v1-v0) normal.
        self.faces.append((ids[0],ids[2],ids[1],mat))
    def quad(self,points,mat=0):
        self.tri([points[i] for i in (0,1,2)],mat)
        self.tri([points[i] for i in (0,2,3)],mat)
    def write(self,path,materials):
        assert len(self.vertices)<32768
        v=b''.join(struct.pack('<iiIiii',round(u*65536),round(v*65536),0xffffff,*[round(k*65536) for k in (x,y,z)]) for x,y,z,u,v in self.vertices)
        f=b''.join(struct.pack('<hhhh',*face) for face in self.faces)
        m=b''.join(struct.pack('<iI',flags,rgb)+tex.encode().ljust(256,b'\0') for flags,rgb,tex in materials)
        path.write_bytes(chunk('MODL',chunk('VRTX',v)+chunk('MATL',m)+chunk('FACE',f)))

def world(x,y,h): return (y-17,x-17,(h-16384)*Z_SCALE)

def course(data):
    mesh=Mesh();edge_count=Counter();edges={};top=[]
    for x,y,hs in data['cells']:
        pts=[world(x,y,hs[0]),world(x+1,y,hs[1]),world(x+1,y+1,hs[2]),world(x,y+1,hs[3])]
        uvs=[(0,0),(1,0),(1,1),(0,1)]
        # Swap axes into WF, so reverse the native grid's handedness here.
        for ix in ((0,2,1),(0,3,2)):
            if any(hs[i]==0 for i in ix): continue # real holes; no bridge to zero
            p=[pts[i] for i in ix];mesh.tri(p,0,[uvs[i] for i in ix]);top.append(p)
            for a,b in zip(p,p[1:]+p[:1]):
                key=tuple(sorted((a,b)));edge_count[key]+=1;edges[key]=(a,b)
    for key,count in edge_count.items():
        if count!=1: continue
        a,b=edges[key]
        # Close only exposed boundaries; no internal walls between triangles.
        low=-9
        mesh.quad([b,a,(a[0],a[1],low),(b[0],b[1],low)],1+((round(a[0]+a[1]))%3))
    return mesh,top

def sphere():
    m=Mesh();rings=12;segments=24
    def p(i,j):
        a=math.pi*i/rings;b=2*math.pi*j/segments
        return (RADIUS*math.sin(a)*math.cos(b),RADIUS*math.sin(a)*math.sin(b),RADIUS*math.cos(a))
    for i in range(rings):
        for j in range(segments):
            if i>0:m.tri([p(i,j),p(i+1,j),p(i,j+1)])
            if i<rings-1:m.tri([p(i,j+1),p(i+1,j),p(i+1,j+1)])
    return m

def finish_flags():
    # Native object scripts place the two finish flags at (72,64)/(72,68).
    m=Mesh()
    for x in (47,51):
        lo=-36*Z_SCALE;hi=lo+3
        for a,b in (((x-.05,54.95),(x+.05,54.95)),((x+.05,54.95),(x+.05,55.05)),((x+.05,55.05),(x-.05,55.05)),((x-.05,55.05),(x-.05,54.95))):
            m.quad([(a[0],a[1],lo),(b[0],b[1],lo),(b[0],b[1],hi),(a[0],a[1],hi)],0)
        left=x-1.5 if x==47 else x
        for row in range(2):
            for col in range(3):
                a=left+col*.5;z=hi-row*.5
                p=[(a,55,z-.5),(a,55,z),(a+.5,55,z),(a+.5,55,z-.5)]
                m.quad(p,1+(row+col)%2);m.quad(list(reversed(p)),1+(row+col)%2)
    return m

def field(name,val,kind=None):
    if kind is None:kind='I32' if isinstance(val,int) else 'FX32' if isinstance(val,float) else 'STR'
    if kind=='I32': payload=f"{{ 'DATA' {val}l }}"
    elif kind=='FX32':payload=f"{{ 'DATA' {val:.8f}(1.15.16) }}"
    elif kind in ('VEC3','EULR','BOX3'):payload="{ 'DATA' "+' '.join(f'{v:.8f}(1.15.16)' for v in val)+' }'
    else:payload="{ '"+('DATA' if name=='Class Name' else 'STR')+"' "+json.dumps(val)+" }"
    return "{ '"+kind+"' { 'NAME' "+json.dumps(name)+" } "+payload+" }"

def actor(name,cls,pos=(0,0,0),bbox=(-.1,-.1,-.1,.1,.1,.1),**attrs):
    movement={'player':22,'statplat':5,'room':3,'camera':13,'camshot':16,'light':23,'levelobj':15,'director':20,'target':3}[cls]
    fields=["{ 'NAME' "+json.dumps(name)+" }",field('Class Name',cls),field('Position',pos,'VEC3'),field('Orientation',attrs.pop('orientation',(0,0,0)),'EULR'),field('Global Bounding Box',bbox,'BOX3')]
    defaults={'MovementClass':movement,'Mobility':'Anchored','Model Type':'None','Movement Mailbox':1,'Visibility Mailbox':1,'Mass':0.0}
    defaults.update(attrs)
    for key,val in defaults.items():fields.append(field(key,val,'FILE' if key=='Mesh Name' else None))
    return "{ 'OBJ'\n"+'\n'.join(fields)+'\n}'

def generate():
    data=json.loads((HERE/'practice.json').read_text());m,top=course(data)
    m.write(HERE/'terrain.iff',[(2,0xffffff,'grid.tga'),(0,0xffbc16,''),(0,0xf46913,''),(0,0xbf3909,'')])
    finish_flags().write(HERE/'finish.iff',[(0,0xffd64a,''),(0,0xffffff,''),(0,0x151522,'')])
    ball=sphere();ball.write(HERE/'marble.iff',[(0,0x508dff,'')])
    # Authored texture, not arcade pixel art. Native cell boundaries are retained.
    pixels=bytearray()
    for y in range(32):
        for x in range(32):
            gray=64 if x<2 or y<2 else 203
            pixels.extend((gray,gray,gray))
    (HERE/'grid.tga').write_bytes(struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,32,32,24,0x20)+pixels)
    bbox=tuple(min(v[i] for v in m.vertices) for i in range(3))+tuple(max(v[i] for v in m.vertices) for i in range(3))
    script='\\ wf\n'+'\n'.join(line for line in (HERE/'player.fth').read_text().splitlines() if not line.lstrip().startswith('\\'))
    objects=[
        actor('Room','room',bbox=(-120,-120,-35,190,190,150)),
        actor('Course','statplat',bbox=bbox,**{'Mesh Name':'terrain.iff','Model Type':'Mesh'}),
        actor('Marble','player',pos=(0,0,RADIUS+.05),bbox=(-RADIUS,)*3+(RADIUS,)*3,orientation=(0,0,3.92699082),**{
            'Mobility':'Physics','Model Type':'Mesh','Mesh Name':'marble.iff','Mass':1.0,
            'Turn Rate':0.0,'Running Acceleration':16.0,'Running Deceleration':0.012,
            'Max Ground Speed':9.0,'Air Acceleration':4.0,'Max Air Speed':12.0,
            'Horiz Air Drag':0.0,'Vert Air Drag':0.0,'Falling Acceleration':18.0,
            'Step Size':0.0,'Jumping Acceleration':0.0,'hp':32767.0,
            'Script Controls Input':1,'Script':script,'Number Of Local Mailboxes':24}),
        actor('Camera','camera',pos=(50,50,40),**{'Mobility':'Camera','FoggingStartDistance':250.0,'FoggingCompleteDistance':350.0}),
        actor('Follow','camshot',pos=(20,20,16.32993),**{'Target':'Anchor','Follow':'Anchor','Track Object':'Marble','Rotation':0,
            'Position X':1,'Position Y':1,'Position Z':1,'FOV':12.0,'Hither':0.1,'Yon':350.0}),
        actor('Sun','light',orientation=(0,-.907571,3.92699),**{'lightType':0,'lightRed':.70,'lightGreen':.70,'lightBlue':.70}),
        actor('Ambient','light',**{'lightType':1,'lightRed':.38,'lightGreen':.38,'lightBlue':.38}),
        actor('Level','levelobj'),
        actor('Anchor','target'),
        actor('Finish flags','statplat',bbox=(45,54,-4,53,56,0),**{'Mesh Name':'finish.iff','Model Type':'Mesh'}),
    ]
    (HERE/(NAME+'.lev')).write_text("{ 'LVL'\n"+'\n'.join(objects)+'\n}\n')
    (HERE/(NAME+'-standalone.iff.txt')).write_text("{ 'L4'\n { 'ALGN' .align( 2048 ) }\n { 'RAM' 'OBJD' 300000l 'PERM' 2000000l 'ROOM' 8000000l 'FLAG' 1l 1l }\n { 'ALGN' .align( 2048 ) }\n [ \""+NAME+".iff\" ]\n}\n")
    print(f'Practice: {len(data["cells"])} source cells, {len(top)} surface triangles, {len(m.faces)} total triangles, {len(m.vertices)} vertices')
    print('Bounds:',bbox)

if __name__=='__main__':generate()
