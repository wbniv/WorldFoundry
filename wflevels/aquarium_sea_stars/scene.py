"""Four static groups, known sand and glass planes and three undressed outcrops."""
import math
import random
from config import ROCKS

def box(mesh,lo,hi,color):
    x,y,z=lo; X,Y,Z=hi
    v=((x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z))
    for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
        mesh.face([v[i] for i in f],color)

def build(Mesh,rock_blob):
    groups={n:Mesh(n) for n in ('sea_shell','sea_rocks','sea_grass','sea_ledge')}
    shell=groups['sea_shell']
    box(shell,(-6,-3,0),(6,3,.775),'sand')
    box(shell,(-6.1,-3.1,-.22),(6.1,3.1,0),'frame')
    for i in range(3):
        z=-1+i*4
        shell.face([(-16,3.2,z),(16,3.2,z),(16,3.2,z+4),(-16,3.2,z+4)],'water'+str(i))
    # Export-time rock generator reused without reef/coral dressing.
    rocks=groups['sea_rocks']; rng=random.Random(20261110)
    for x,y,rx,ry,h in ROCKS:
        rock_blob(rocks,(x,y,.8+h*.45),(rx,ry,h*.65),rng,segments=24,rings=12)
        for j in range(12):
            a=rng.uniform(0,math.tau); r=rng.uniform(.2,.8)
            rocks.ellipsoid((x+rx*r*math.cos(a),y+ry*r*math.sin(a),.85+h*.55),(.09,.07,.018),'crust',6,3)
    box(groups['sea_ledge'],(2.6,-.05,1.0),(4.0,.65,1.12),'rock')
    for x in (2.7,3.9): box(groups['sea_ledge'],(x,-.02,.775),(x+.13,.60,1.0),'rock')
    grass=groups['sea_grass']
    for cx,cy in ((-5.05,2.1),(0,2.2),(5.05,2.1)):
        for i in range(16):
            x=cx+rng.uniform(-.30,.30); y=cy+rng.uniform(-.22,.22)
            height=rng.uniform(.9,1.8); bend=rng.uniform(-.4,.4)
            for j in range(5):
                a=j/5;b=(j+1)/5
                w=.025*(1-.6*a)
                pts=[(x+bend*a*a-w,y,.775+height*a),(x+bend*a*a+w,y,.775+height*a),
                     (x+bend*b*b+w*.85,y,.775+height*b),(x+bend*b*b-w*.85,y,.775+height*b)]
                grass.face(pts,'grass');grass.face(list(reversed(pts)),'grass')
    return groups

def uv(color,points):
    cell={'sand':10,'rock':11,'crust':11,'grass':12,'frame':13,'water0':13,'water1':14,'water2':15}[color]
    x,y=cell%4,cell//4
    if color.startswith('water'):
        band=int(color[-1]);bottom=-1+band*4
        return [((x+.5)/4,(y+.02+.96*max(0,min(1,(p[2]-bottom)/4)))/4) for p in points]
    return [((x+.06+.88*((p[0]*.31+p[1]*.13)%1))/4,(y+.06+.88*((p[1]*.19+p[2]*.31)%1))/4) for p in points]
