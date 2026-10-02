"""Grouped static foliage, rooted at substrate height; no creature geometry."""
import math
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

def planting(sand):
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
