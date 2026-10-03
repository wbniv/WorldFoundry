"""Volumetric animal models. +X is the fish head; jelly bells face +Z."""
import math
from mesh import Mesh

COLORS = dict(body=(.12,.40,.56), hi=(.27,.65,.72), tail=(.65,.20,.37), fin=(.43,.23,.50),
              ray=(.90,.46,.58), eye=(.015,.022,.025), glint=(.9,.95,.90),
              brown=(.40,.12,.12), patch=(.62,.41,.29), pale=(.75,.58,.40),
              dark=(.25,.19,.16), jelly=(.65,.81,.86), edge=(.84,.92,.93),
              motif=(.70,.39,.59), trail=(.49,.68,.77))

# Art settings for the existing moon-jelly model, not measured biology.
# Scoped to the jellyfish generator; other tanks keep opaque materials.
JELLY_OPACITY = dict(jelly=.22, edge=.32, trail=.12, motif=.72)


def membrane(name, outline, key, thickness=.028):
    m=Mesh(name)
    # Both faces and the perimeter are closed, so fins stay visible when turning.
    front=[(x,-thickness/2,z) for x,z in outline]
    back=[(x,thickness/2,z) for x,z in outline]
    m.face(front,key); m.face(list(reversed(back)),key)
    for i in range(len(outline)):
        j=(i+1)%len(outline)
        m.face([front[i],back[i],back[j],front[j]],key)
    return m


def fish(kind):
    body=Mesh('body')
    if kind=='betta':
        body.ellipsoid((0,0,0),(.48,.16,.23),['body','hi','hi','body','body','body','body','body'],12,6)
        tail=membrane('tail',[(0,.08),(-.70,.55),(-.81,.34),(-.72,0),(-.81,-.34),(-.68,-.52),(0,-.08)],'tail')
        for z in [-.43,-.22,0,.22,.43]:
            tail.tube([(-.05,0,0),(-.69,-.022,z)],.012,'ray',3)
        top=membrane('dorsal',[(-.34,.13),(-.30,.51),(-.03,.60),(.25,.25)],'fin')
        bottom=membrane('anal',[(-.36,-.14),(-.30,-.57),(.17,-.49),(.31,-.16)],'fin')
        for side in [-1,1]:
            body.tube([(.26,side*.09,-.13),(.29,side*.12,-.40),(.40,side*.12,-.51)],.018,'ray',4)
        width=.17
    else:
        body.ellipsoid((0,0,0),(.52,.21,.27),'pale',12,10)
        # Bands follow cross-sections along the body's length.
        for i in range(len(body.colors)):
            body.colors[i]='pale' if (i//12)%2 else 'brown'
        body.ellipsoid((.35,0,-.025),(.23,.20,.19),'pale',10,6)
        for x,h in [(-.38,.60),(-.25,.78),(-.10,.90),(.06,.82),(.21,.64)]:
            body.tube([(x,0,.18),(x-.13,0,h)],.022,'pale',4)
            body.tube([(x-.13,0,h*.70),(x-.13,0,h*.88)],.025,'brown',4)
        for side in [-1,1]:
            body.tube([(.33,side*.12,.12),(.46,side*.14,.32)],.02,'brown',4)
        tail=membrane('tail',[(0,.1),(-.42,.34),(-.57,.24),(-.55,-.22),(-.42,-.31),(0,-.08)],'pale',.04)
        for z in [-.22,0,.22]:
            tail.tube([(-.06,0,0),(-.48,-.025,z)],.015,'brown',4)
        top=Mesh('near_fin'); bottom=Mesh('far_fin')
        for part,side in [(top,-1),(bottom,1)]:
            rays=[(-.65,side*.72,-.18),(-.49,side*.88,-.38),(-.26,side*.96,-.48),
                  (.02,side*.91,-.42),(.26,side*.76,-.27),(.40,side*.55,-.06)]
            for i,(a,b) in enumerate(zip(rays,rays[1:])):
                part.face([(0,0,0),a,b],'brown' if i%2 else 'pale')
                part.face([b,a,(0,0,0)],'brown' if i%2 else 'pale')
            for x,y,z in rays:
                part.tube([(0,0,0),(x,y,z)],.017,'pale',4)
        width=.20
    for side in [-1,1]:
        body.ellipsoid((.33,side*width,.065),(.053,.035,.056),'eye',8,4)
        body.ellipsoid((.345,side*(width+.026),.083),(.016,.012,.016),'glint',6,3)
    offsets=[(0,0,0),(-.38,0,0),(0,0,0),(0,0,0)]
    return [body,tail,top,bottom],offsets


def jelly():
    bell=Mesh('bell')
    rings=[]
    for j in range(5):
        angle=math.pi/2*j/4
        r=.48*math.sin(angle); z=.30*math.cos(angle)
        rings.append([(r*math.cos(math.tau*i/16),r*math.sin(math.tau*i/16),z) for i in range(16)])
    for j in range(4):
        for i in range(16):
            a=[rings[j][i],rings[j+1][i],rings[j+1][(i+1)%16],rings[j][(i+1)%16]]
            a=list(dict.fromkeys(tuple(round(v,8) for v in p) for p in a))
            if len(a)>=3: bell.face(a,'edge' if j==0 else 'jelly')
    bell.face(list(reversed(rings[-1])),'trail')
    # Four opaque internal motif forms visible from above and three-quarter view.
    for x,y in [(-.11,-.11),(-.11,.11),(.11,-.11),(.11,.11)]:
        bell.ellipsoid((x,y,.267),(.084,.072,.024),'motif',6,3)
    arms=Mesh('arms')
    for i in range(4):
        angle=math.tau*i/4
        pts=[(.13*math.cos(angle)+.08*math.sin(j*1.4+i),.13*math.sin(angle)+.04*math.cos(j+i),-.04-j*.20) for j in range(6)]
        arms.swept_tube(pts,.041,'edge',5)
    for i in range(12):
        a=math.tau*i/12
        bell.swept_tube([(.43*math.cos(a),.43*math.sin(a),0),(.46*math.cos(a),.46*math.sin(a),-.16),(.40*math.cos(a),.40*math.sin(a),-.28)],.012,'trail',3)
    return [bell,arms],[(0,0,0)]*2


def models(kind):
    return jelly() if kind=='jellyfish' else fish(kind)
