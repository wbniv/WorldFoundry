"""Optional fixtures. Export exclusion is explicit, not inferred from viewport hiding."""
import math

def add_fixtures(preset, actor, Geometry, material, label):
    group='DIAGNOSTICS'
    fixtures=[]
    for name,pos,lo,hi,colour in [
        ('CollisionBox',(12,5,.5),(-.5,-.5,-.5),(.5,.5,.5),(.7,.5,.3)),
        ('ThinWall',(16,5,1),(-1,-.1,-1),(1,.1,1),(.6,.65,.7)),
        ('CameraWall',(0,8,2),(-4,-.2,-2),(4,.2,2),(.3,.4,.5))]:
        g=Geometry(name);g.box(lo,hi,material(name,colour))
        fixtures.append(actor(name,'statplat',group,g.mesh(),pos,bounds=(*lo,*hi)))
    for i,height in enumerate([.1,.2,.4]):
        g=Geometry('step'+str(i));g.box((0,0,0),(1,2,height),material('steps',(.5,.55,.65)))
        fixtures.append(actor('Step'+str(i),'statplat',group,g.mesh(),(12+i*2,12,0),bounds=(0,0,0,1,2,height)))
    # Static mesh binding installs triangle-mesh collision. These wedges exercise
    # that path; slope traversal still requires runtime verification.
    for i,degrees in enumerate([15,30,45]):
        h=2*math.tan(math.radians(degrees));g=Geometry('wedge'+str(i));m=material('wedge',(.5,.7,.5))
        for v in [[(0,0,0),(0,2,0),(2,2,h),(2,0,h)],[(0,0,0),(2,0,h),(2,0,0)],[(0,2,0),(2,2,0),(2,2,h)],[(2,0,0),(2,0,h),(2,2,h),(2,2,0)],[(0,0,0),(2,0,0),(2,2,0),(0,2,0)]]:g.face(v,m)
        fixtures.append(actor('Wedge'+str(degrees),'statplat',group,g.mesh(),(22+i*4,10,0),bounds=(0,0,0,2,2,h)))
    g=Geometry('uv');g.face([(0,0,0),(2,0,0),(2,2,0),(0,2,0)],material('uv',(1,1,1),'uv.tga'),[(0,0),(1,0),(1,1),(0,1)])
    fixtures.append(actor('UVSwatch','platform',group,g.mesh(),(12,0,.03),fields={'Mass':0.0}))
    for obj in fixtures:
        obj['wf_baseline_excluded']=preset!='diagnostics'
        obj.hide_set(preset!='diagnostics');obj.hide_render=preset!='diagnostics'
    # Future moving and room-transition fixtures remain explicit pending features.
