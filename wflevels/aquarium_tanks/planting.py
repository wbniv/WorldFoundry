"""Grouped static foliage, rooted at substrate height; no creature geometry."""
import math
import os
import random
from mesh import Mesh
COLORS=dict(plant_deep=(.10,.29,.17),plant_green=(.22,.48,.23),plant_light=(.43,.63,.29),
            plant_red=(.46,.23,.18),plant_stem=(.19,.34,.14))

def leaf(mesh,base,tip,width,key):
    # A folded, closed leaf has real thickness and readable shading on both sides.
    dx,dy,dz=[tip[i]-base[i] for i in range(3)]
    length=math.hypot(dx,dz);side=(dz/length*width,0,-dx/length*width)
    center=tuple(base[i]+(tip[i]-base[i])*.52 for i in range(3))
    left=tuple(center[i]+side[i] for i in range(3));right=tuple(center[i]-side[i] for i in range(3))
    ridge=(center[0],center[1]-.05,center[2]);back=(center[0],center[1]+.025,center[2])
    perimeter=[base,left,tip,right]
    for i in range(4):
        a,b=perimeter[i],perimeter[(i+1)%4]
        mesh.face([a,b,ridge],key)
        mesh.face([b,a,back],'plant_deep')

def baseline_planting(sand):
    groups=[]
    broad=Mesh('plant_broad_groups')
    for k,x in enumerate([-5.0,-4.0,-2.8,2.7,3.9,5.0]):
        for j in range(4):
            px=x+(j-1.5)*.16;py=.25+(j%3)*.29;h=1.3+((k*3+j*2)%6)*.25
            broad.tube([(px,py,sand),(px+.1,py,sand+h)],.024,'plant_stem',5)
            for n,side in enumerate([-1,1,-1]):
                z=sand+h*(.28+n*.26)
                leaf(broad,(px,py,z),(px+side*(.48+n*.05),py-.12,z+.45),.20,'plant_light' if (k+j)%3==0 else 'plant_green')
    groups.append(broad)
    stems=Mesh('plant_rear_stems')
    for k,x in enumerate([-4.7,-3.5,-1.7,-.6,.6,1.7,3.5,4.7]):
        h=2.2+(k%3)*.35;y=1.05
        stems.tube([(x,y,sand),(x+.12,y,sand+h)],.023,'plant_stem',5)
        for j in range(5):
            z=sand+.3+j*(h-.45)/5
            for side in [-1,1]:
                leaf(stems,(x,y,z),(x+side*.35,y-.12,z+.34),.12,'plant_red' if k in (2,5) else 'plant_green')
    groups.append(stems)
    carpet=Mesh('plant_foreground')
    for k in range(25):
        x=-5.3+k*.44;y=-.75+(k%3)*.12
        for j in range(3):
            a=math.tau*j/3+k*.4
            leaf(carpet,(x,y,sand+.01),(x+.20*math.cos(a),y+.10*math.sin(a),sand+.24+(k%4)*.03),.055,'plant_light')
    groups.append(carpet)
    return groups


# Density and geometry share placements so their device comparison isolates detail.
DENSE_COUNTS = dict(broad=64, stems=128, carpet=192)

def placements():
    rng = random.Random(2703)
    result = []
    for kind, count in DENSE_COUNTS.items():
        for k in range(count):
            if kind == 'stems':
                x = -5.10 + (k % 32) * 10.20 / 31 + rng.uniform(-.12,.12)
                y = .52 + (k // 32) * .19 + rng.uniform(-.025,.025)
                height = rng.uniform(3.20,3.75)
            elif kind == 'broad':
                x = -5.10 + (k % 16) * 10.20 / 15 + rng.uniform(-.12,.12)
                y = -.10 + (k // 16) * .18
                height = rng.uniform(.9,1.9)
            else:
                x = -5.20 + (k % 48) * 10.40 / 47 + rng.uniform(-.03,.03)
                y = -1.15 + (k // 48) * .23
                # Preserve a small local route around the starting urchin.
                if abs(x) < .65 and y < -.55:
                    x += -1.0 if x < 0 else 1.0
                height = rng.uniform(.24,.43)
            result.append(dict(kind=kind, index=k, x=x, y=y, height=height,
                               phase=rng.uniform(0,math.tau)))
    return result


def curved_leaf(mesh, base, tip, width, key, sections=4, across=2):
    """Closed curved leaf, tapered tips, cupped midrib and rolled edges."""
    dx,dy,dz = [tip[i]-base[i] for i in range(3)]
    mag = math.hypot(dx,dz)
    side = (dz/mag,0,-dx/mag)
    grids = []
    for back in (False,True):
        rows=[]
        for j in range(sections+1):
            t=j/sections; bulge=0.0 if j in (0,sections) else math.sin(math.pi*t)
            row=[]
            for k in range(across+1):
                q=k/across*2-1
                span=width*bulge**.75*q
                # Twist reverses along the length; cup survives silhouette review.
                point=(base[0]+dx*t+side[0]*span,
                       base[1]+dy*t+.13*bulge + width*.25*q*q*bulge
                       + width*.24*q*bulge*(t-.35) + (.004 if back else -.004)*bulge,
                       base[2]+dz*t+side[2]*span + .055*bulge)
                row.append(point)
            rows.append(row)
        grids.append(rows)
    def face(points,color):
        unique=list(dict.fromkeys(tuple(round(v,9) for v in p) for p in points))
        if len(unique)>=3:mesh.face(unique,color)
    for back,rows in enumerate(grids):
        for j in range(sections):
            for k in range(across):
                points=[rows[j][k],rows[j+1][k],rows[j+1][k+1],rows[j][k+1]]
                face(points if back else points[::-1], 'plant_deep' if back else key)
    for k in (0,across):
        for j in range(sections):
            face([grids[0][j][k],grids[1][j][k],grids[1][j+1][k],grids[0][j+1][k]],key)


def dense_planting(sand, detailed=True):
    groups=[Mesh(f'plant_chunk_{k:02d}') for k in range(8)]
    for p in placements():
        kind,k,x,y,h,phase = (p[n] for n in ('kind','index','x','y','height','phase'))
        col=min(3,max(0,int((x+5.5)/2.75)))
        mesh=groups[col+(0 if kind=='stems' else 4)]
        draw=curved_leaf if detailed else leaf
        if kind=='stems':
            lean=.11*math.sin(phase)
            points=[(x+lean*t,y+.06*math.sin(t*math.pi),sand+h*t) for t in [0,.25,.5,.75,1]]
            if detailed:mesh.swept_tube(points,.018,'plant_stem',6)
            else:mesh.tube([points[0],points[-1]],.018,'plant_stem',5)
            for j in range(6):
                t=.13+j*.14;z=sand+h*t
                for side in (-1,1):
                    tip=(x+lean*t+side*(.32+.10*math.sin(phase+j)),y-.07,z+.35)
                    color='plant_red' if k%11 in (0,1) else 'plant_light' if (k+j)%5==0 else 'plant_green'
                    kwargs=dict(sections=2,across=1) if detailed else {}
                    draw(mesh,(x+lean*t,y,z),tip,.10,color,**kwargs)
        elif kind=='broad':
            for j in range(8):
                a=phase+math.tau*j/8;length=h*(.65+.35*((j*3)%7)/6)
                tip=(x+math.cos(a)*.60,y+math.sin(a)*.21,sand+length)
                base=(x,y,sand+.015)
                if detailed:
                    mesh.swept_tube([base,(x+math.cos(a)*.14,y+math.sin(a)*.04,sand+length*.35)],.014,'plant_stem',5)
                draw(mesh,base,tip,.17+.035*(j%3),'plant_light' if j%3==0 else 'plant_green',**(dict(sections=6,across=2) if detailed else {}))
        else:
            for j in range(5):
                a=phase+math.tau*j/5
                tip=(x+math.cos(a)*.17,y+math.sin(a)*.09,sand+h*(.70+j*.07))
                draw(mesh,(x,y,sand+.012),tip,.043,'plant_light',**(dict(sections=2,across=1) if detailed else {}))
    return groups


def planting(sand, mode=None):
    mode=mode or os.environ.get('PLANTED_TANK_DETAIL','runtime')
    if mode=='runtime':
        groups=[]
        for k in range(8):
            m=Mesh(f'plant_chunk_{k:02d}')
            m.face([(-5.9,-1.4,sand),(5.9,-1.4,sand),(5.9,1.4,4.82),(-5.9,1.4,4.82)],'plant_green')
            groups.append(m)
        return groups
    if mode=='baseline':return baseline_planting(sand)
    if mode not in ('density','detailed'):raise ValueError(f'Unknown planting mode: {mode}')
    return dense_planting(sand, detailed=mode=='detailed')
