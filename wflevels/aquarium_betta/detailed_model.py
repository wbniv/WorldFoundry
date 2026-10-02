"""Opaque halfmoon-inspired runtime betta: eight groups, explicit fin UV weights.

The coordinates are authored in tank units (+X head). UV.y is root-to-tip;
UV.x identifies rays across a fin. No texture sampling or alpha is required.
"""
import math
from mesh import Mesh

COLORS={'betta_body':(.035,.21,.28),'betta_scale':(.10,.37,.43),
        'betta_iris':(.67,.40,.13),'betta_eye':(.014,.020,.025),
        'betta_glint':(.84,.92,.91)}
for j in range(8):
    t=j/7
    COLORS[f'betta_mem{j}']=(.32+.24*t,.045+.10*t,.15+.15*t)
    COLORS[f'betta_ray{j}']=(.36+.25*t,.060+.12*t,.18+.16*t)
COLORS['betta_margin']=(.66,.24,.36)

def membrane(name,nu,nv,point):
    m=Mesh(name);m.uvs=[]
    for side in (-1,1):
        for j in range(nv+1):
            r=j/nv
            for i in range(nu+1):
                u=i/nu;x,y,z=point(u,r)
                ridge=.003*r*r*(.5+.5*math.cos(i*math.pi))
                m.vertices.append((x,y+side*(.013+ridge),z));m.uvs.append((u,r))
    layer=(nu+1)*(nv+1)
    def face(indices,color):m.faces.append(tuple(indices));m.colors.append(color)
    for j in range(nv):
        for i in range(nu):
            a=j*(nu+1)+i;q=(a,a+1,a+nu+2,a+nu+1)
            p0,p1,p2=[m.vertices[k] for k in q[:3]]
            normal_y=(p1[2]-p0[2])*(p2[0]-p0[0])-(p1[0]-p0[0])*(p2[2]-p0[2])
            if normal_y>0:q=tuple(reversed(q))
            ray=i%4==0 or (j>=nv*2//3 and i%2==0)
            color='betta_margin' if j==nv-1 else f'betta_{"ray" if ray else "mem"}{min(7,j*8//nv)}'
            face(q,color);face(tuple(k+layer for k in reversed(q)),color)
    # Perimeter follows the same orientation as the front surface.
    boundary=list(range(nu+1))+[j*(nu+1)+nu for j in range(1,nv+1)]
    boundary += [nv*(nu+1)+i for i in range(nu-1,-1,-1)]+[j*(nu+1) for j in range(nv-1,0,-1)]
    # Select edge winding from the first front quad (not from fin identity).
    if normal_y>0:boundary.reverse()
    for a,b in zip(boundary,boundary[1:]+boundary[:1]):
        face((b,a,a+layer,b+layer),'betta_margin')
    return m

def detailed_models():
    body=Mesh('body')
    body.ellipsoid((0,0,0),(.49,.15,.23),'betta_body',24,12)
    for side in (-1,1):
        for row in range(5):
            theta=-.90+row*.45
            for col in range(8):
                x=-.29+col*.070+(row%2)*.022
                points=[]
                for dx,da in [(-.021,0),(0,-.11),(.021,0),(0,.11)]:
                    xx=x+dx;angle=theta+da;factor=math.sqrt(max(.01,1-(xx/.49)**2))
                    points.append((xx,side*.153*factor*math.cos(angle),.232*factor*math.sin(angle)))
                if side>0:points.reverse()
                body.face(points,'betta_scale')
    body.ellipsoid((-.38,0,-.005),(.20,.085,.105),'betta_body',10,5)
    for side in (-1,1):
        body.ellipsoid((.22,side*.115,-.008),(.13,.050,.15),'betta_body',10,5)
        body.ellipsoid((.36,side*.111,.070),(.050,.030,.050),'betta_iris',8,4)
        body.ellipsoid((.37,side*.134,.075),(.032,.015,.032),'betta_eye',6,3)
        body.ellipsoid((.38,side*.148,.087),(.017,.012,.017),'betta_glint',6,3)
    body.ellipsoid((.475,0,.027),(.045,.066,.024),'betta_scale',10,4)
    def caudal(u,r):
        theta=math.radians(100)+u*math.radians(160)
        radius=.075+(.55+.018*math.sin(u*math.pi*6)+.012*math.sin(u*math.pi*13))*r
        return (-.44+radius*math.cos(theta),.060*r*r*math.sin(u*9+r*3),radius*math.sin(theta))
    def dorsal(u,r):
        x=-.36+.47*u;root=.11+.065*math.sin(math.pi*u)
        return (x-.19*r*(1-u),.055*r*r*math.sin(u*10+1),root+r*(.15+.23*math.sin(math.pi*u)))
    def anal(u,r):
        x=-.38+.65*u;root=-.11-.075*math.sin(math.pi*u)
        return (x-.20*r*(1-u),.060*r*r*math.sin(u*8+2),root-r*(.13+.25*math.sin(math.pi*(u*.88+.09))))
    fins=[membrane('tail',24,8,caudal),membrane('dorsal',16,7,dorsal),membrane('anal',18,7,anal)]
    for side,name in [(-1,'near'),(1,'far')]:
        def pectoral(u,r,side=side):
            theta=(u-.5)*math.pi*.85;radius=.055+.12*r
            return (.25-radius*math.cos(theta),side*(.14+.065*r),-.035+radius*math.sin(theta))
        fins.append(membrane(name+'_pectoral',8,5,pectoral))
    for side,name in [(-1,'near'),(1,'far')]:
        def pelvic(u,r,side=side):
            return (.28-.10*r+(u-.5)*(.085-.045*r),side*(.075+.035*r)+.025*r*r*math.sin(r*5),-.14-.49*r)
        fins.append(membrane(name+'_pelvic',4,10,pelvic))
    return [body]+fins,[(0,0,0)]*8
