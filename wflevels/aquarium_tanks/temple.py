"""Thai temple-style aquarium pavilion: architecture only, no figures or statues.

Base rests at local z=0. Roof tiers, curved finials, gold gable trim and columns
provide the silhouette; the interior is an empty open pavilion.
"""
from mesh import Mesh

COLORS={'temple_white':(.78,.76,.65),'temple_shadow':(.52,.50,.44),
        'temple_red':(.76,.10,.06),'temple_red_hi':(.90,.20,.10),
        'temple_gold':(.90,.64,.20),'temple_dark':(.23,.13,.10)}


def cuboid(m,lo,hi,key):
    a,b,c=lo;x,y,z=hi
    v=[(a,b,c),(x,b,c),(x,y,c),(a,y,c),(a,b,z),(x,b,z),(x,y,z),(a,y,z)]
    for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
        m.face([v[i] for i in f],key)


def pavilion():
    m=Mesh('siam_pavilion')
    cuboid(m,(-.94,-.32,0),(.94,.32,.13),'temple_shadow')
    cuboid(m,(-.84,-.29,.13),(.84,.29,.22),'temple_white')
    cuboid(m,(-.74,-.25,.22),(.74,.25,.30),'temple_gold')
    # An empty open hall supported by six square columns.
    for x in [-.61,0,.61]:
        for y in [-.20,.20]:
            cuboid(m,(x-.052,y-.052,.30),(x+.052,y+.052,1.18),'temple_white')
            cuboid(m,(x-.077,y-.070,.30),(x+.077,y+.070,.41),'temple_gold')
            cuboid(m,(x-.077,y-.070,1.08),(x+.077,y+.070,1.19),'temple_gold')
    cuboid(m,(-.73,-.25,1.17),(.73,.25,1.25),'temple_dark')
    # Gable ridge runs along Y, so the front camera sees its triangular facade.
    for tier,(half,depth,eave,peak) in enumerate([(.96,.35,1.22,1.94),(.70,.28,1.65,2.20)]):
        for side in [-1,1]:
            outer=side*half
            m.face([(0,-depth,peak),(outer,-depth,eave),(outer,depth,eave),(0,depth,peak)],'temple_red_hi' if side<0 else 'temple_red')
            m.face([(0,depth,peak),(outer,depth,eave),(outer,-depth,eave),(0,-depth,peak)],'temple_red')
            for y in [-depth,depth]:
                m.tube([(outer,y,eave),(side*half*.56,y,(eave+peak)/2),(0,y,peak)],.027,'temple_gold',4)
                # Chofa-inspired swept tips, kept broad enough for fixed-point triangles.
                m.tube([(outer,y,eave),(outer+side*.13,y,eave+.12),(outer+side*.17,y,eave+.32)],.028,'temple_gold',4)
            m.tube([(outer,-depth,eave),(outer,depth,eave)],.024,'temple_gold',4)
            for k in range(1,5):
                x=side*half*k/5;z=peak+(eave-peak)*k/5+.012
                m.tube([(x,-depth,z),(x,depth,z)],.014,'temple_red',4)
        m.tube([(0,-depth,peak),(0,depth,peak)],.029,'temple_gold',4)
    # Front gable is a simple geometric red/gold panel, without religious imagery.
    m.face([(-.48,-.283,1.66),(.48,-.283,1.66),(0,-.283,2.12)],'temple_red')
    m.face([(0,-.279,2.12),(.48,-.279,1.66),(-.48,-.279,1.66)],'temple_red')
    m.tube([(-.48,-.30,1.66),(0,-.30,2.12),(.48,-.30,1.66)],.026,'temple_gold',4)
    m.tube([(0,-.30,1.71),(0,-.30,1.96)],.025,'temple_gold',4)
    return m
