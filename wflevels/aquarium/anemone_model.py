"""Single-mesh bubble-tip authoring asset and reference pose math.

Research: docs/reference/sea-anemone-research.md. Runtime integration pending.
Dimensions are scene metres at WORLD_SCALE=10; UVs never encode rig weights.
"""
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import random

@dataclass
class Mesh:
    vertices: list = field(default_factory=list)
    faces: list = field(default_factory=list)
    uvs: list = field(default_factory=list)
    rig: list = field(default_factory=list)
    tentacles: list = field(default_factory=list)

    def vertex(self,p,uv,region,root=(0,0,0),u=0,length=0,phase=0):
        self.vertices.append(tuple(p));self.uvs.append(tuple(uv))
        self.rig.append(dict(region=region,root=tuple(root),u=u,length=length,phase=phase))
        return len(self.vertices)-1


def geometry(count=48,seed=17,sides=6,spans=8):
    if count not in (24,48,72):raise ValueError('Supported density trials: 24, 48, 72')
    if sides<4 or spans<6:raise ValueError('Insufficient curved tube resolution')
    rng=random.Random(seed);m=Mesh()
    # Unified body silhouette: foot -> recessed column -> oral disc -> mouth.
    profile=[(.30,0),(.33,.035),(.23,.09),(.21,.17),(.24,.25),(.33,.32),
             (.47,.36),(.50,.38),(.40,.40),(.27,.405),(.12,.397),(.035,.377)]
    n=32
    for j,(r,z) in enumerate(profile):
        for k in range(n+1):
            a=math.tau*k/n;fold=.007*math.sin(a*7)*max(0,(z-.30)/.10)
            p=((r+fold)*math.cos(a),(r+fold)*math.sin(a),z)
            m.vertex(p,(.03+.43*k/n,.03+.40*j/(len(profile)-1)),0,u=min(1,z/.38))
    for j in range(len(profile)-1):
        for k in range(n):
            a=j*(n+1)+k;m.faces.append((a,a+1,a+n+2,a+n+1))
    # Cap the underside and the small mouth cavity; keep winding outward.
    m.faces.append(tuple(reversed(range(n))))
    m.faces.append(tuple((len(profile)-1)*(n+1)+k for k in range(n)))
    for i in range(count):
        az=i*2.3999632297+rng.uniform(-.13,.13)
        rr=.13+.33*math.sqrt((i+.5)/count)
        root=(rr*math.cos(az),rr*math.sin(az),.375)
        length=rng.uniform(.60,.97)
        lean=rng.uniform(.22,.70);curl=rng.uniform(-.16,.20)
        bulb=0 if i%4==0 else rng.uniform(.026,.044)
        shaft=rng.uniform(.020,.029);phase=rng.uniform(0,1)
        m.tentacles.append(dict(root=root,length=length,azimuth=az,lean=lean,curl=curl,bulb=bulb,phase=phase))
        def center(u):
            outward=length*(lean*u*u+curl*math.sin(math.pi*u)*u)
            return (root[0]+math.cos(az)*outward,root[1]+math.sin(az)*outward,
                    root[2]+length*(u-.23*lean*u*u))
        start=len(m.vertices)
        for j in range(spans+1):
            u=j/spans;c=center(u)
            lo,hi=center(max(0,u-.001)),center(min(1,u+.001))
            tangent=[hi[k]-lo[k] for k in range(3)]
            norm=math.sqrt(sum(x*x for x in tangent));tangent=[x/norm for x in tangent]
            across=(-math.sin(az),math.cos(az),0)
            cross=(tangent[1]*across[2]-tangent[2]*across[1],tangent[2]*across[0]-tangent[0]*across[2],tangent[0]*across[1]-tangent[1]*across[0])
            radius=shaft*(1-.60*u)+bulb*math.exp(-((u-.82)/.115)**2)
            for k in range(sides+1):
                a=math.tau*k/sides
                p=tuple(c[q]+radius*(across[q]*math.cos(a)+cross[q]*math.sin(a)) for q in range(3))
                # Two atlas columns hold distinct shaft/pigment regions, padded.
                uv=(.52+.21*k/sides,.05+.89*u) if i%2==0 else (.76+.21*k/sides,.05+.89*u)
                m.vertex(p,uv,1,root,u,length,phase)
        for j in range(spans):
            for k in range(sides):
                a=start+j*(sides+1)+k;m.faces.append((a,a+1,a+sides+2,a+sides+1))
        m.faces.append(tuple(reversed([start+k for k in range(sides)])))
        m.faces.append(tuple(start+spans*(sides+1)+k for k in range(sides)))
    return m


def pose_vertex(p,rig,phase=0,flow_x=.045,flow_y=.018,withdraw=0):
    """Reference, non-runtime deformation. Rest pose in; no accumulated drift.

    Phase in turns, flow is fraction of local length, withdraw normalized.
    Root invariance and finite values are mandatory; no texture UV changes.
    """
    if not all(math.isfinite(v) for v in (*p,phase,flow_x,flow_y,withdraw)):
        raise ValueError('Non-finite pose')
    withdraw=max(0,min(1,withdraw))
    if rig['region']==0:
        # Foot stays on the rock while exposed tissue contracts.
        w=max(0,min(1,p[2]/.38))
        return (p[0]*(1-.12*withdraw*w),p[1]*(1-.12*withdraw*w),p[2]*(1-.60*withdraw*w))
    root=rig['root'];u=rig['u'];length=rig['length'];local=tuple(p[k]-root[k] for k in range(3))
    # One shared slow flow, subordinate local lag; no six independent metronomes.
    shared=math.sin(math.tau*phase-u*.65)
    localwave=.12*math.sin(math.tau*(phase+rig['phase'])-u*1.8)
    weight=u*u*(1-withdraw)
    movedroot=pose_vertex(root,dict(region=0),withdraw=withdraw)
    return (movedroot[0]+local[0]*(1-.65*withdraw)+length*weight*flow_x*(shared+localwave),
            movedroot[1]+local[1]*(1-.65*withdraw)+length*weight*flow_y*(shared+localwave),
            movedroot[2]+local[2]*(1-.78*withdraw))


def write_textures(folder):
    from PIL import Image
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGBA',(256,256));rng=random.Random(17)
    for y in range(256):
        v=y/255
        for x in range(256):
            u=x/255
            shaft=x>=128;t=max(0,min(1,(v-.05)/.89))
            stripe=.035*math.sin(u*math.tau*22+.4*math.sin(v*13))
            grain=rng.uniform(-.017,.017);speck=.09 if rng.random()<.018 else 0
            if shaft:
                b=(.48+.22*t,.20+.16*t,.29+.14*t)
                collar=.11*math.exp(-((t-.81)/.075)**2)*(1+.25*math.sin(x*1.7))
            else:
                b=(.40+.22*v,.19+.13*v,.23+.11*v);collar=0
            rgb=[round(255*max(0,min(1,c+stripe+grain+speck+collar))) for c in b]
            image.putpixel((x,y),(*rgb,255))
    image.save(folder/'anemone_tissue.tga');image.save(folder/'anemone_tissue.png')
    return image


def write_manifest(folder,count=48):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);m=geometry(count)
    metadata=dict(version=1,status='authoring asset; runtime integration pending',seed=17,
        tentacle_count=count,vertices=len(m.vertices),triangles=sum(len(f)-2 for f in m.faces),
        texture='anemone_tissue.tga',texture_size=[256,256],visible_meshes=1,
        tentacles=m.tentacles,rig=m.rig)
    (folder/'anemone-rig.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return m,metadata

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);ap.add_argument('--count',type=int,default=48)
    a=ap.parse_args();write_textures(a.out);_,data=write_manifest(a.out,a.count)
    print(json.dumps({k:data[k] for k in ['tentacle_count','vertices','triangles','visible_meshes','status']}))
