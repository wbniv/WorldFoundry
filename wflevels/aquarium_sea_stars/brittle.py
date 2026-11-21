"""Ophiarachna asset anatomy and shared Blender/DFRM arm poses.

A small disc with five independent, tapering, articulated limbs. The linear
mesh is the skinning bind pose; the presented animal always uses its curved
Hide or Row clip. Each arm has 16 joints, allowing distal hooks and S bends.
"""
import math
from config import SPECIES
SAMPLES=16
# Per-joint lateral turns, in degrees: distinct relaxed S bends and distal hooks.
REST=(
    (0,4,4,3,0,-3,-4,-2,1,4,7,12,16,20,24,28),
    (0,-3,-3,-4,-2,0,3,5,8,11,15,19,23,26,28,30),
    (0,4,5,6,5,2,-2,-5,-8,-12,-16,-20,-24,-28,-30,-30),
    (0,-5,-4,-2,1,4,6,7,8,9,10,12,15,18,22,25),
    (0,3,5,5,3,0,-3,-6,-9,-13,-17,-22,-25,-28,-30,-32),
)

def sample_count(kind):return SAMPLES if kind=='brittle' else 4

def root_and_step(kind):
    s=SPECIES[kind];root=s['disc']*(.90 if kind=='brittle' else .65)
    return root,(s['radius']-root)/sample_count(kind)

def bone_point(kind,arm,sample):
    root,step=root_and_step(kind);angle=math.tau*arm/5
    return ((root+step*sample)*math.cos(angle),(root+step*sample)*math.sin(angle),0)

def binding(kind,p):
    spec=SPECIES[kind];x,y,z=p
    if math.hypot(x,y)<spec['disc']*(.98 if kind=='brittle' else .8):return None
    arm=int(math.floor(math.atan2(y,x)/math.tau*5+.5))%5
    along=x*math.cos(math.tau*arm/5)+y*math.sin(math.tau*arm/5)
    root,step=root_and_step(kind)
    return arm,max(0,min(sample_count(kind)-1,int((along-root)/step)))

def angles(arm,sample,frame=0,clip='hide'):
    if sample==0:return (0,0,0)
    phase=math.tau*frame/60
    lateral=REST[arm][sample]
    # More movement in the proximal/middle arm; the distal coil stays present.
    if clip=='row':
        lateral+=10*math.sin(phase+arm*1.7-sample*.38)*math.sin(math.pi*sample/SAMPLES)
    else:lateral+=1.2*math.sin(phase+arm*.7-sample*.35)
    # Tips can arch off the substrate, rather than being painted flat on it.
    flex=(1.0 if sample>=12 else 0)+(.6 if clip=='hide' else 1.7)*math.sin(phase+arm-sample*.4)*max(0,(sample-9)/6)
    return (flex,lateral,0)

def apply_pose(skeleton,clip='hide',frame=0):
    import bpy
    skeleton.animation_data_create()
    skeleton.animation_data.action=bpy.data.actions['brittle_'+clip]
    bpy.context.scene.frame_set(frame+1)
    bpy.context.view_layer.update()

def mesh(Mesh):
    spec=SPECIES['brittle'];out=Mesh('star_brittle')
    # The disc is a separate body, not a widened junction between five sea-star arms.
    out.ellipsoid((0,0,.018),(spec['disc'],spec['disc'],.055),'brittle_disc',40,14)
    root,step=root_and_step('brittle');length=spec['radius']-root
    segments,sides=48,8
    for arm in range(5):
        a=math.tau*arm/5;ca,sa=math.cos(a),math.sin(a)
        def ring(j):
            t=j/segments;u=root+length*t
            width=spec['width']*(1-t)**.95+.003
            height=.020*(1-t)+.0025
            return [(u*ca-width*math.cos(math.tau*k/sides)*sa,
                     u*sa+width*math.cos(math.tau*k/sides)*ca,
                     .002+height*math.sin(math.tau*k/sides)) for k in range(sides)]
        rings=[ring(j) for j in range(segments+1)]
        out.face(list(reversed(rings[0])),f'brittle_arm{arm}')
        out.face(rings[-1],f'brittle_arm{arm}')
        for j in range(segments):
            for k in range(sides):
                out.face([rings[j][k],rings[j][(k+1)%sides],rings[j+1][(k+1)%sides],rings[j+1][k]],f'brittle_arm{arm}')
        for j in range(2,46):
            t=j/segments;u=root+length*t;w=spec['width']*(1-t)**.95+.003
            # Four short lateral spines per segment, tapering toward the tip.
            for side in (-1,1):
                for level in (-1,1):
                    p=(u*ca-side*w*sa,u*sa+side*w*ca,.002+level*.008*(1-t))
                    reach=.030*(1-.65*t)
                    q=(p[0]-side*reach*sa-.009*ca,p[1]+side*reach*ca-.009*sa,p[2]+level*.007*(1-t))
                    out.tube((p,q),.0026*(1-.65*t),'brittle_spine',3)
    return out

def uv(color,points):
    # Cell 4: spotted olive disc at left; longitudinal arm bands at right.
    if color=='brittle_spine':return [(0.215,.42)]*len(points)
    if color=='brittle_disc':
        r=SPECIES['brittle']['disc']
        return [((.25+.22*p[0]/r)/4,(1+.5+.44*p[1]/r)/4) for p in points]
    arm=int(color[-1]);a=math.tau*arm/5;ca,sa=math.cos(a),math.sin(a)
    root,step=root_and_step('brittle');length=step*SAMPLES
    result=[]
    for x,y,z in points:
        t=max(0,min(1,(x*ca+y*sa-root)/length));width=SPECIES['brittle']['width']*(1-t)**.95+.003
        lateral=(-x*sa+y*ca)/width
        result.append(((.52+.44*t)/4,(1+.5+.42*max(-1,min(1,lateral)))/4))
    return result
