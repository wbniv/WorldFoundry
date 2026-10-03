"""A compact sea urchin with a rounded test and radial tapered spines."""
import math
from mesh import Mesh
COLORS=dict(urchin_body=(.16,.10,.23),urchin_spine=(.30,.19,.38),urchin_tip=(.51,.34,.56))
def urchin():
    m=Mesh('sea_urchin')
    m.ellipsoid((0,0,0),(.32,.32,.23),'urchin_body',segments=12,rings=8)
    # Staggered latitude rings avoid a uniform hedgehog grid. The underside stays flat.
    for row,(height,count) in enumerate([(-.22,14),(.12,18),(.44,14),(.73,10),(.94,5)]):
        for i in range(count):
            a=math.tau*(i+.37*row)/count
            d=(math.sqrt(1-height*height)*math.cos(a),math.sqrt(1-height*height)*math.sin(a),height)
            base=(d[0]*.30,d[1]*.30,d[2]*.22)
            length=.24+.07*((i*7+row*3)%5)/4
            tip=tuple(base[j]+d[j]*length for j in range(3))
            ref=(0,0,1) if abs(height)<.9 else (0,1,0)
            u=(d[1]*ref[2]-d[2]*ref[1],d[2]*ref[0]-d[0]*ref[2],d[0]*ref[1]-d[1]*ref[0]);norm=math.sqrt(sum(x*x for x in u));u=tuple(x/norm for x in u)
            v=(d[1]*u[2]-d[2]*u[1],d[2]*u[0]-d[0]*u[2],d[0]*u[1]-d[1]*u[0])
            ring=[tuple(base[j]+.017*(u[j]*math.cos(math.tau*k/4)+v[j]*math.sin(math.tau*k/4)) for j in range(3)) for k in range(4)]
            for k in range(4):m.face([ring[k],ring[(k+1)%4],tip],'urchin_tip' if (i+row)%4==0 else 'urchin_spine')
    return m


def tube_foot():
    """One short underside tube foot; the pad rests at local z=-.23."""
    m=Mesh('urchin_tube_foot')
    m.swept_tube([(0,0,-.15),(0,0,-.195),(0,0,-.22)],.018,'urchin_tip',6)
    m.ellipsoid((0,0,-.219),(.035,.028,.011),'urchin_tip',6,3)
    return m
