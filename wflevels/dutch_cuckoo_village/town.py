"""Model Tulpenkade in metres around the shared clock tower's balcony pivots."""
import math
import random
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent/'clock_common'), str(HERE.parent/'cuckoo_village')]
from clock_mesh import Mesh
import timeline as village


class Town:
    def __init__(self):
        self.models = {}

    def mesh(self, name, at=(0,0,0), visibility=1):
        mesh = Mesh(name)
        self.models[name] = (mesh, at, visibility)
        return mesh


def board(m, x, y, z, w, d, h, color):
    m.box((x-w/2,y-d/2,z), (x+w/2,y+d/2,z+h), color)


def ellipsoid(m, centre, size, color, segments=9, rings=5):
    first = len(m.vertices)
    m.sphere((0,0,0),1,color,segments=segments,rings=rings)
    for i in range(first,len(m.vertices)):
        m.vertices[i]=tuple(centre[j]+v*size[j] for j,v in enumerate(m.vertices[i]))


def spar(m, start, end, width, color):
    """Square timber between arbitrary points, with flat ends."""
    dx,dy,dz=(b-a for a,b in zip(start,end))
    length=math.sqrt(dx*dx+dy*dy+dz*dz)
    normal=math.hypot(dx,dy)
    a=(-dy/normal,dx/normal,0) if normal else (1,0,0)
    b=(dy*a[2]-dz*a[1], dz*a[0]-dx*a[2], dx*a[1]-dy*a[0])
    offsets=[tuple(width*.5*(i*a[k]+j*b[k]/length) for k in range(3)) for i,j in ((1,1),(-1,1),(-1,-1),(1,-1))]
    rings=[[tuple(o[k]+p[k] for k in range(3)) for o in offsets] for p in (start,end)]
    m.face(rings[0][::-1],color)
    m.face(rings[1],color)
    for i in range(4):
        j=(i+1)%4
        m.face([rings[0][i],rings[0][j],rings[1][j],rings[1][i]],color)


def roof(m,x,y,z,w,d,h,color):
    m.prism_xz([(x-w/2,z),(x+w/2,z),(x,z+h)], y-d/2,y+d/2,color)


def pane(m,x,y,z,w,h,color):
    m.quad_y(x-w/2,z,x+w/2,z+h,y,'cream')
    m.quad_y(x-w*.41,z+.045,x+w*.41,z+h-.045,y-.012,color)
    board(m,x,y-.023,z+.045,.026,.018,h-.09,'cream')
    board(m,x,y-.024,z+h*.57,w*.83,.018,.026,'cream')


def house(m,lit,x,y,w,d,h,kind,wall):
    front=y-d/2
    board(m,x,y,.12,w,d,h,wall)
    roof(m,x,y,.12+h,w*1.07,d+.09,w*.46,'tile' if kind%2 else 'slate')
    # The raised front gables mask the sloping roof, with limestone coping along each step.
    for tier in range(3 if kind%3==0 else 0):
        width=w*(.70-tier*.20)
        board(m,x,front,h+.11+tier*.19,width,.14,.19,wall)
        board(m,x,front-.012,h+.275+tier*.19,width+.045,.17,.045,'stone')
    if kind%3==1:
        # Bell gable: concave shoulders with a rounded crown and pale coping.
        profile=[(-.50,0),(.50,0),(.50,.075),(.35,.13),(.245,.25),(.18,.46),(-.18,.46),(-.245,.25),(-.35,.13),(-.50,.075)]
        poly=[(x+a*w,h+.12+b*w) for a,b in profile]
        m.prism_xz(poly,front-.085,front+.035,wall)
        for p,q in zip(poly[2:],poly[3:]):
            m.beam(p,q,.047,front-.105,front-.055,'stone')
        m.disc_y(x,h+.62*w,.085,front-.11,'cream')
    if kind%4==2:
        board(m,x,front-.08,h-.37,.32,.065,.41,'green')
        spar(m,(x,front-.07,h+.23),(x,front-.53,h+.23),.074,'wood')
        spar(m,(x,front-.50,h+.23),(x,front-.50,h-.04),.016,'dark')
    board(m,x,front-.055,h+.08,w+.06,.09,.055,'slate')
    board(m,x+w*.47,front-.07,.15,.035,.036,h-.016,'slate')
    board(m,x+w*.27,y+d*.18,h+.39,.17,.20,.52,wall)
    board(m,x+w*.27,y+d*.18,h+.88,.21,.24,.065,'stone')
    board(m,x,front-.016,.13,.32,.06,.9,'cream')
    board(m,x,front-.057,.14,.26,.025,.81,'green')
    for off in (-.30,.30):
        for floor in (.48,h*.66):
            xx=x+w*off
            pane(m,xx,front-.04,floor,w*.22,.46,'glass')
            # Inset four luminous panes leave the pale glazing bars visible.
            for col in (-1,1):
                for row in (0,1):
                    lit.quad_y(xx+col*w*.055-w*.034,floor+.07+row*.22,
                               xx+col*w*.055+w*.034,floor+.20+row*.22,front-.068,'glow')
    for side in (-1,1):
        for offset in (-.23,.23):
            board(m,x+side*w*.502,y+offset*d,.72,.035,.29,.56,'cream')
            board(m,x+side*(w*.503+.022),y+offset*d,.77,.02,.23,.45,'glass')
    for off in (-.25,.25):
        board(m,x+w*off,y+d*.501,.66,.30,.05,.5,'glass')


def boat(m,length,width,cargo=False):
    for height,factor in ((.06,.68),(.22,1)):
        pts=[(x*length,y*width,height) for x,y in ((-.5,0),(-.38,-.48),(.35,-.48),(.5,0),(.35,.48),(-.38,.48))]
        ring=[(x*factor,y*factor,z) for x,y,z in pts]
        if height==.06:
            bottom=ring
        else:
            for i in range(6):
                j=(i+1)%6
                m.face([bottom[i],bottom[j],ring[j],ring[i]],'wood')
            m.face(ring,'oak')
    if cargo:
        for i,col in enumerate(('red','cream','yellow')):
            xx=(i-1)*length*.22
            board(m,xx,0,.23,length*.20,width*.70,.16,'wood')
            for k in range(6):
                ellipsoid(m,(xx+(k%3-1)*.12,(k//3-.5)*.19,.46),(.075,.075,.12),col,6,3)


def tree(m,x,y,scale,blossom):
    m.column_z(x,y,.16,.16+1.08*scale,.075*scale,'wood',7)
    for dx,dy,z in ((-.3,.05,1.28),(.28,.05,1.36),(.02,-.18,1.63)):
        ellipsoid(m,(x+dx*scale,y+dy*scale,z*scale),(.46*scale,.42*scale,.43*scale),'pink' if blossom else 'tree',8,4)


def flower_beds(t):
    randomizer=random.Random(913)
    for group in range(4):
        m=t.mesh('TulipBeds'+str(group))
        for row in range(5):
            y=-7.0+row*.38
            x0=-10+group*5.2
            board(m,x0+2.15,y,.125,4.7,.30,.04,'mud')
            for plant in range(15):
                x=x0+plant*.31+randomizer.uniform(-.03,.03)
                if group==0 and plant<5 and row<4:
                    continue
                height=randomizer.uniform(.22,.32)
                m.prism_xz([(x-.13,.18),(x+.015,.18),(x-.08,.18+height*.88)],y-.015,y+.012,'leaf')
                m.prism_xz([(x-.01,.18),(x+.08,.18),(x+.13,.18+height)],y-.01,y+.015,'green')
                # Tulip cup flares from a point to a scalloped rim.
                color=('red','cream','yellow','red')[group]
                ring=[(x+.072*math.cos(i*math.pi/3),y+.072*math.sin(i*math.pi/3),.2+height+.04*(i%2)) for i in range(6)]
                for i in range(6):
                    m.face([(x,y,.15+height),ring[(i+1)%6],ring[i]],color)
                m.face(ring,color)


def mill(t,name,x,y,large):
    base=t.mesh(name+'Body',(x,y,.12))
    if large:
        for k in range(5):
            base.column_z(0,0,k*.51,(k+1)*.51,1.05-.12*k,'dark',12)
        base.column_z(0,0,1.12,1.22,1.12,'white',16)
        for a in range(12):
            angle=a*math.tau/12
            pt=(1.07*math.cos(angle),1.07*math.sin(angle))
            spar(base,(*pt,1.2),(*pt,1.48),.04,'cream')
            end=(1.07*math.cos(angle+math.tau/12),1.07*math.sin(angle+math.tau/12))
            spar(base,(*pt,1.48),(*end,1.48),.04,'cream')
        roof(base,0,0,2.50,1.33,1.32,.52,'slate')
        hub_z,offset,radius=2.43,-.83,1.89
    else:
        for dx in (-.36,.36):
            for dy in (-.31,.31):
                spar(base,(dx,dy,0),(0,0,.85),.105,'oak')
        board(base,0,0,.63,.88,.72,.85,'rose')
        roof(base,0,0,1.47,.97,.85,.36,'slate')
        pane(base,0,-.375,.93,.27,.32,'glass')
        for k in range(5):
            board(base,0,.66-k*.054,.07+k*.13,.30,.075,.035,'oak')
        hub_z,offset,radius=1.41,-.45,1.08
    sails=t.mesh(name+'Sails',(x,y+offset,hub_z+.12))
    for blade in range(4):
        a=blade*math.pi/2
        def point(r,w):
            return (r*math.sin(a)+w*math.cos(a),r*math.cos(a)-w*math.sin(a))
        for w in (0,.14*radius):
            sails.beam(point(radius*.13,w),point(radius,w),.032,-.04,.025,'cream')
        for k in range(4,11):
            sails.beam(point(radius*k/10,0),point(radius*k/10,.14*radius),.026,-.045,.035,'white')
    sails.cylinder_y(0,0,.096,-.10,.06,'gold',10)


def person(m,x,y,z,coat='coat',height=1):
    def egg(dx,dy,dz,a,b,c,col):
        ellipsoid(m,(x+dx*height,y+dy*height,z+dz*height),(a*height,b*height,c*height),col,8,4)
    for dx in (-.075,.075):
        egg(dx,-.035,.075,.072,.11,.074,'oak')
    egg(0,0,.26,.16,.105,.21,coat)
    egg(0,-.012,.50,.104,.09,.12,'skin')
    egg(0,0,.595,.127,.115,.053,'dark')
    for dx in (-.15,.15):
        egg(dx,-.056,.29,.047,.076,.12,coat)
        egg(dx,-.105,.22,.046,.046,.049,'skin')


def clock_tower(t):
    m=t.mesh('Stadhuis')
    board(m,0,.47,.12,3.6,2.54,1.98,'brick')
    roof(m,0,.47,2.09,3.76,2.69,.88,'tile')
    board(m,0,-.10,.16,2.35,1.93,5.06,'stone')
    for z,width in ((1.96,2.56),(2.48,2.68),(3.44,2.48),(4.93,2.46),(5.92,2.53)):
        board(m,0,-.10,z,width,2.03,.095,'cream')
    for x in (-.81,0,.81):
        m.quad_y(x-.31,.23,x+.31,1.42,-1.078,'dark')
        m.disc_y(x,1.42,.31,-1.079,'dark')
        for j in range(5):
            board(m,x+(j-2)*.091,-1.10,.30,.055,.05,.69+j*.115,'brass')
    board(m,0,-1.46,village.FIG_Z0-.13,2.68,.96,.13,'stone')
    for x in village.FIG_X:
        m.quad_y(x-.245,village.FIG_Z0,x+.245,3.19,-1.08,'umber')
        m.disc_y(x,3.19,.245,-1.081,'umber')
    for x in (-1.26,-.59,0,.59,1.26):
        board(m,x,-1.86,village.FIG_Z0,.045,.04,.14,'cream')
    board(m,0,-1.86,village.FIG_Z0+.14,2.60,.045,.035,'brass')
    cx,cy,cz=village.DIAL
    m.disc_y(cx,cz,.60,cy+.011,'cobalt',48)
    m.disc_y(cx,cz,.56,cy+.008,'cream',48)
    for i in range(60):
        a=i*math.tau/60
        direction=(math.sin(a),math.cos(a))
        p=lambda r:(r*direction[0],cz+r*direction[1])
        m.beam(p(.427 if i%5==0 else .51),p(.54),.034 if i%5==0 else .013,cy+.002,cy+.006,'cobalt')
    for name,length,width,y in [('hour_hand',.345,.050,cy-.007),('minute_hand',.475,.030,village.MINUTE_Y)]:
        h=t.mesh(name,(cx,y,cz))
        h.prism_xz([(-width,-.06),(width,-.06),(width*.8,length*.76),(0,length),(-width*.8,length*.76)],-.009,0,'cobalt')
        h.disc_y(0,0,.058,-.012,'brass')
    # Four open arcades form the bell chamber above the solid dial stage.
    for side in range(4):
        s=Mesh('arcade')
        for x in (-1.04,-.35,.35,1.04):
            board(s,x,-.99,5.03,.12,.15,.91,'stone')
        for x in (-.70,0,.70):
            for sign in (-1,1):
                s.beam((x+sign*.30,5.63),(x,5.93),.075,-1.068,-.93,'cream')
            s.beam((x,5.65),(x,5.88),.035,-1.07,-.94,'cream')
            s.column_z(x,-.72,5.39,5.43,.16,'brass',10)
            s.column_z(x,-.72,5.43,5.6,.115,'brass',10)
        a=side*math.pi/2
        for face,c in zip(s.faces,s.colors):
            m.face([(x*math.cos(a)-y*math.sin(a),-.1+x*math.sin(a)+y*math.cos(a),z) for x,y,z in (s.vertices[i] for i in face)],c)
    corners=[(-1.22,-1.18,6.02),(1.22,-1.18,6.02),(1.22,.98,6.02),(-1.22,.98,6.02)]
    for i,p in enumerate(corners):
        m.face([p,corners[(i+1)%4],(0,-.1,7.19)],'slate')
        m.column_z(p[0]*.88,p[1]*.88,5.98,6.27,.082,'cream',6)
    m.column_z(0,-.1,7.14,7.53,.028,'gold',7)
    m.prism_xz([(-.28,7.40),(.24,7.48),(-.17,7.56)],-.13,-.08,'gold')
    for i,(name,x) in enumerate(zip(village.FIG_NAMES,village.FIG_X)):
        f=t.mesh(name,(x,village.FIG_HOME_Y,village.FIG_Z0))
        person(f,0,0,0,('green','rose','coat','umber')[i],.95)
        if i==0:
            board(f,0,-.17,.23,.33,.18,.047,'oak')
            for dx in (-.09,0,.09):
                ellipsoid(f,(dx,-.17,.30),(.045,.045,.05),'gold')
        elif i==1:
            for j,c in enumerate(('cream','red','yellow')):
                dx=.08+j*.075
                spar(f,(.13,-.15,.24),(dx,-.15,.48+j*.043),.018,'leaf')
                ellipsoid(f,(dx,-.15,.50+j*.043),(.052,.048,.068),c,7,3)
        elif i==2:
            board(f,.15,-.13,.24,.027,.027,.45,'oak')
            board(f,.22,-.13,.54,.16,.024,.135,'cobalt')
        else:
            for j in range(3):
                f.cylinder_y(.15,.235,.092-j*.017,-.17-j*.01,-.14,'oak',12)
    bx,by,bz=village.BIRD_REST
    m.quad_y(-.19,bz-.025,.19,bz+.25,-1.13,'dark')
    hatch=t.mesh('Hatch',(-.20,-1.15,bz-.025))
    board(hatch,.19,0,0,.38,.04,.29,'green')
    bird=t.mesh(village.BIRD_NAME,village.BIRD_REST,213)
    ellipsoid(bird,(0,-.03,.07),(.103,.14,.089),'oak')
    ellipsoid(bird,(0,-.13,.16),(.072,.072,.076),'cream')
    spar(bird,(0,-.18,.16),(0,-.26,.15),.045,'gold')


BRIDGE=(-5.9,-4.35,.22)
SPAN=2.65
BERTHS=(-9.45,3.75)
WATER_Y=-3.05


def waterways(t):
    land=t.mesh('Banks')
    board(land,0,1.5,-.72,24,19,.58,'wood')
    board(land,0,1.5,-.15,23.85,18.85,.15,'water')
    for x,y,w,d,col in [(0,-6.12,23.75,3.55,'grass'),(-2.65,4.57,18.45,12.54,'pave'),(10.08,4.57,3.55,12.54,'grass')]:
        board(land,x,y,-.07,w,d,.20,col)
    for y in (-4.36,-1.71):
        for i in range(41):
            x=-11.65+i*.58
            board(land,x,y,.032,.566,.14,.108,'stone')
            if i%4==0:
                land.column_z(x,y,.04,.42,.06,'oak',8)
    for y in (4.5,9.2):
        # Masonry arch, with a through opening above the canal.
        for i in range(12):
            a,b=i*math.pi/12,(i+1)*math.pi/12
            pts=[(7.43+r*math.cos(v),.1+r*.47*math.sin(v)) for r,v in ((.94,a),(1.18,a),(1.18,b),(.94,b))]
            land.prism_xz(pts,y-.38,y+.38,'brick' if i%2 else 'rose')
        for side in (-1,1):
            for i in range(9):
                x=6.29+i*.28
                z=.16+.5*math.sin(math.pi*i/8)
                board(land,x,y+side*.36,z,.28,.085,.13,'stone')
    x,y,z=BRIDGE
    leaf=t.mesh('BridgeLeaf',BRIDGE)
    arm=t.mesh('BridgeBeam',(x,y,z+1.90))
    chains=t.mesh('BridgeChains',(x,y+SPAN,z))
    for i in range(19):
        board(leaf,0,(i+.5)*SPAN/19,-.055,1.17,SPAN/19-.008,.085,'oak')
    for dx in (-.59,.59):
        board(land,x+dx,y,.13,.13,.17,2.09,'white')
        spar(land,(x+dx,y-.55,.14),(x+dx,y,1.6),.08,'white')
        board(arm,dx,.83,0,.103,3.66,.13,'white')
        spar(chains,(dx,0,.026),(dx,0,1.95),.031,'dark')
        for k in range(5):
            board(leaf,dx,k*SPAN/4,0,.043,.043,.32,'white')
        board(leaf,dx,SPAN/2,.32,.053,SPAN,.038,'white')
    board(arm,0,-.83,-.09,1.40,.31,.30,'green')
    board(land,x,y,2.21,1.42,.16,.10,'white')
    barge=t.mesh('BulbBarge',(BERTHS[0],WATER_Y,0))
    boat(barge,2.05,.65,True)
    wake=t.mesh('Wake',(BERTHS[0],WATER_Y,.012),215)
    for sign in (-1,1):
        for end in (-1,1):
            spar(wake,(end*.65,sign*.30,0),(end*1.17,sign*.48,0),.026,'ripple')
    for i,(xx,yy) in enumerate(((6.7,-1.93),(7.44,5.8))):
        boat(t.mesh('Dinghy'+str(i),(xx,yy,0)),1.22,.48)
    for i in range(6):
        board(land,3.9+(i-2.5)*.23,-4.15,.16,.21,.72,.095,'oak')
    for xx in (3.25,4.55):
        land.column_z(xx,-3.92,0,.44,.078,'oak')
    board(land,4.3,-4.24,.255,.32,.28,.21,'wood')


MARKET=(-.15,5.85)
def stalls(t):
    m=t.mesh('WeighHouse')
    x,y=MARKET
    board(m,x,y+.76,.13,2.63,1.5,2.13,'brick')
    roof(m,x,y+.76,2.24,2.78,1.64,.94,'tile')
    m.quad_y(x-.80,.18,x+.80,1.73,y-.009,'dark')
    for side in (-1,1):
        board(m,x+side*.94,y-.05,.15,.26,.12,1.65,'green')
    for i in range(11):
        board(m,x+(i-5)*.246,y-.50,1.77,.246,1.03,.08,'cream' if i%2 else 'red')
    for xx in (x-1.20,x+1.20):
        board(m,xx,y-.94,.14,.052,.052,1.63,'green')
    y-=.65
    board(m,x-.77,y,.57,.92,.45,.09,'oak')
    for dx in (-1.12,-.44):
        board(m,x+dx,y,.13,.07,.34,.45,'wood')
    for dx,count in ((-1.05,3),(-.76,2)):
        for j in range(count):
            m.column_z(x+dx,y,.66+j*.115,.765+j*.115,.145,'cheese',16)
    person(m,x-.48,y+.24,.14,'green',1.19)
    board(m,x+.36,y,.14,.075,.075,1.26,'wood')
    beam=t.mesh('Balance',(x+.36,y,1.36))
    board(beam,0,0,-.022,.95,.055,.044,'brass')
    for name,dx in [('CheesePan',-.45),('WeightPan',.45)]:
        pan=t.mesh(name,(x+.36+dx,y,.67))
        pan.column_z(0,0,0,.043,.185,'brass',14)
        for px in (-.15,.15):
            spar(pan,(px,0,.035),(0,0,.68),.016,'dark')
        if dx>0:
            pan.column_z(0,0,.046,.17,.075,'dark')
    wheel=t.mesh('WeighedWheel',(x-.39,y,.66))
    wheel.column_z(0,0,0,.113,.147,'cheese',18)
    hand=t.mesh('MerchantHand',(x-.39,y,.73))
    ellipsoid(hand,(0,.13,.005),(.07,.14,.057),'green')
    ellipsoid(hand,(0,.03,0),(.056,.056,.045),'skin')
    for xx,yy in [(2.65,4.75),(-2.8,5.3)]:
        for i in range(7):
            board(m,xx+(i-3)*.21,yy,1.33,.21,.82,.075,'green' if i%2==0 else 'cream')
        for dx in (-.63,.63):
            board(m,xx+dx,yy,.13,.055,.055,1.21,'oak')
        board(m,xx,yy,.64,1.42,.62,.08,'oak')
        for j,c in enumerate(('red','cream','yellow')):
            xx1=xx+(j-1)*.40
            m.column_z(xx1,yy,.72,.94,.12,'glass')
            for k in range(4):
                ellipsoid(m,(xx1+.10*math.cos(k*1.6),yy+.10*math.sin(k*1.6),1.04),(.065,.06,.11),c,6,3)
    board(m,x-2,y-1,.47,.86,.45,.08,'oak')
    for dx in (-.22,.22):
        m.cylinder_y(x-2,.36,.19,y-1+dx-.024,y-1+dx+.024,'wood',14)
    for k in range(2):
        m.column_z(x-2+k*.26,y-1,.56,.68,.15,'cheese',16)


def build():
    t=Town()
    waterways(t)
    clock_tower(t)
    flower_beds(t)
    mill(t,'PostMill',-10.03,-6.03,False)
    mill(t,'PolderMill',10.0,1.58,True)
    stalls(t)
    lights=[t.mesh('LitWindows'+str(i),visibility=200+i) for i in range(8)]
    rows=[(-.22,[-10.7,-8.85,-7.0,-4.08,-2.42,2.49,4.29]),
          (3.30,[-10.7,-8.92,-4.68,4.98,9.8]),(6.14,[-10.7,-8.92,-4.68,4.98,9.8]),
          (9.28,[-10.7,-8.8,-6.96,-5.11,-3.27,-1.43,.41,2.25,4.09,5.9,9.85])]
    count=0
    for row,xx in rows:
        for x in xx:
            m=t.mesh('Gable%02d'%count,(x,row,0))
            # Lit panes share a visibility actor per stagger; convert their local vertices to world space.
            lit=lights[count%len(lights)]
            offset=len(lit.vertices)
            house(m,lit,0,0,1.38+.13*(count%3),1.55,1.50+.27*(count%4),count,('brick','rose','umber','brick')[count%4])
            for i in range(offset,len(lit.vertices)):
                a,b,c=lit.vertices[i]
                lit.vertices[i]=(a+x,b+row,c)
            count+=1
    m=t.mesh('Courtyard')
    board(m,-6.85,4.7,.135,2.35,2.9,.04,'grass')
    for x,y in ((-7.64,5.5),(-5.98,5.45),(-8.3,2),(-10.9,7.5),(3.28,7.5),(9.9,8.01)):
        tree(m,x,y,.91,y>5)
    for xx in (-7.76,-5.93):
        board(m,xx,4.54,.35,.36,.84,.08,'oak')
        board(m,xx+.14,4.54,.42,.065,.84,.30,'green')
    m.column_z(-6.81,3.69,.13,.88,.10,'dark')
    spar(m,(-6.81,3.69,.83),(-6.50,3.69,.55),.05,'dark')
    yard=t.mesh('Slipway')
    for dx in (-.61,.61):
        for dy in (-.57,.57):
            board(yard,5.99+dx,.04+dy,.14,.09,.09,1.18,'oak')
        spar(yard,(5.99+dx,-1.89,.04),(5.99+dx,.75,.47),.075,'wood')
    roof(yard,5.99,.04,1.33,1.57,1.47,.54,'tile')
    boat(t.mesh('YardHull',(5.99,.04,.42)),1.45,.53)
    for xx,yy in ((5.7,3.31),(9.11,6.12),(4.44,-.99)):
        spar(yard,(xx,yy,.14),(xx,yy,2.24),.09,'wood')
        spar(yard,(xx,yy,2.21),(xx-.52,yy,2.21),.075,'wood')
        spar(yard,(xx-.49,yy,2.20),(xx-.49,yy,1.74),.017,'dark')
        board(yard,xx-.3,yy-.25,.14,.34,.39,.32,'oak')
    for xx,yy in ((-2.9,-1.38),(2.15,-1.37),(-7.58,2.25),(2.85,3.7)):
        yard.column_z(xx,yy,.14,1.1,.041,'dark')
        board(yard,xx,yy,1.10,.14,.14,.18,'cream')
        person(yard,xx+.24,yy,.14,'coat')
    rng=random.Random(592)
    water=t.mesh('WaterGlints')
    rain=t.mesh('Raindrops',visibility=214)
    rings=[t.mesh('RainRings'+str(frame),visibility=217+frame) for frame in range(3)]
    reflections=[t.mesh('Lamplight'+str(i),visibility=200+i) for i in range(8)]
    for i in range(8):
        x=-9.85+i*2.76
        for j in range(5):
            board(reflections[i],x+.11*math.sin(j*2.3),-1.92-j*.15,.016,.26-.024*j,.034,.002,'glow')
    for i in range(36):
        xx=rng.uniform(-10.70,6.23)
        yy=rng.uniform(-1.02,7.90)
        height=rng.uniform(1.56,3.66)
        spar(rain,(xx,yy,height),(xx+.055,yy+.015,height+.17),.020,'rain')

    for i in range(64):
        xx=rng.uniform(-11.45,11.45)
        yy=rng.uniform(-4.19,-1.88)
        board(water,xx,yy,.009,.20+rng.random()*.36,.028,.005,'ripple')
        zz=rng.uniform(.08,1.96)
        spar(rain,(xx,yy,zz),(xx+.047,yy+.012,zz+.13),.016,'rain')
        if i%2==0:
            for j in range(8):
                a=j*math.tau/8
                b=(j+1)*math.tau/8
                for frame,mesh in enumerate(rings):
                    radius=.055+.042*((frame+i)%3)
                    spar(mesh,(xx+radius*math.cos(a),yy+radius*.66*math.sin(a),.018),
                         (xx+radius*math.cos(b),yy+radius*.66*math.sin(b),.018),.016,'ripple')
    drip=t.mesh('Runoff',(-4.01,2.49,0),216)
    for i in range(6):
        ellipsoid(drip,(0,0,.26+i*.21),(.027,.028,.058),'rain',6,3)
    return t
