"""Original opaque poster-study mesh, rendered in Blender; not an engine capture.

blender --background --python docs/reference/betta-history-and-biomechanics-poster/render_fish.py
Writes editable .blend, OBJ + MTL, count manifest, side and oblique PNG renders.
Runtime integration/animated mesh verification are separate planned work.
"""
from pathlib import Path
import bpy
import math
import json
from mathutils import Vector

OUT=Path(__file__).resolve().parent/'assets'
OUT.mkdir(exist_ok=True,parents=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name,color,metal=.0,rough=.5):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1)
    m.use_nodes=True
    n=m.node_tree.nodes.get('Principled BSDF')
    n.inputs['Base Color'].default_value=(*color,1)
    n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=rough
    return m

bodymat=material('Opaque deep teal',(.026,.28,.34),.24,.38)
scale=material('Opaque scale highlights',(.15,.48,.5),.22,.43)
fins=[material('Opaque wine fin roots',(.22,.027,.11),.04,.45),material('Opaque crimson membrane',(.55,.048,.17),.06,.48),material('Opaque violet membrane',(.24,.075,.28),.04,.47),material('Opaque pale fin edge',(.77,.34,.44),.02,.55)]
raymat=material('Raised ray ridges',(.79,.23,.34),.07,.48)
eyemat=material('Black eyes',(.008,.018,.023),.08,.19)
irismat=material('Copper iris',(.55,.33,.10),.24,.28)

def uv(name,loc,sz,mat,segments=48,rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=loc)
    obj=bpy.context.object;obj.name=name;obj.scale=sz
    obj.data.materials.append(mat)
    for p in obj.data.polygons:p.use_smooth=True
    return obj

uv('Body and shaped head',(0,0,0),(.93,.23,.33),bodymat)
uv('Tail peduncle',(-.75,0,-.015),(.32,.13,.19),bodymat,32,16)
for side in [-1,1]:
    uv('Gill cover '+str(side),(.40,side*.177,-.015),(.25,.075,.255),scale,24,12)
    uv('Iris '+str(side),(.685,side*.158,.119),(.085,.030,.085),irismat,24,12)
    uv('Eye '+str(side),(.694,side*.180,.125),(.057,.018,.057),eyemat,24,12)
uv('Upturned upper lip',(.9,-.001,.052),(.063,.10,.038),bodymat,24,12)
uv('Lower lip',(.895,-.001,-.024),(.057,.09,.025),scale,24,12)

def curve(name,points,mat,radius=.004):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=1
    c.bevel_depth=radius;c.bevel_resolution=1
    spline=c.splines.new('POLY');spline.points.add(len(points)-1)
    for p,xyz in zip(spline.points,points):p.co=(*xyz,1)
    obj=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(obj);c.materials.append(mat)

def membrane(name,nu,nv,point):
    # Thin closed opaque surface: both faces and perimeter, finite separation.
    vertices=[]
    for side in [-1,1]:
        for j in range(nv+1):
            r=j/nv
            for i in range(nu+1):
                x,y,z=point(i/nu,r)
                vertices.append((x,y+side*.004,z))
    layer=(nu+1)*(nv+1);faces=[];bands=[]
    for side in range(2):
        for j in range(nv):
            for i in range(nu):
                a=side*layer+j*(nu+1)+i
                q=(a,a+1,a+nu+2,a+nu+1)
                faces.append(q if side else q[::-1]);bands.append(j/nv)
    perimeter=list(range(nu+1))+[j*(nu+1)+nu for j in range(1,nv+1)]+[nv*(nu+1)+i for i in range(nu-1,-1,-1)]+[j*(nu+1) for j in range(nv-1,0,-1)]
    for a,b in zip(perimeter,perimeter[1:]+perimeter[:1]):faces.append((a,b,b+layer,a+layer));bands.append(1)
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    for m in fins:mesh.materials.append(m)
    for polygon,r in zip(mesh.polygons,bands):
        polygon.use_smooth=True
        polygon.material_index=0 if r<.22 else 1 if r<.62 else 2 if r<.90 else 3
    for i in range(0,nu+1,max(1,nu//20)):
        points=[]
        for j in range(1,nv+1):
            x,y,z=point(i/nu,j/nv);points.append((x,y-.006,z))
        curve(name+' ray '+str(i),points,raymat,.003)
    return obj

def caudal(u,r):
    theta=math.pi/2+u*math.pi
    radius=.035+1.2*r
    # Curved free edge; phase delay/root weighting gives an actual posed membrane.
    return (-.86+radius*math.cos(theta),.06*r*r*math.sin(u*9+r*3),-.015+radius*math.sin(theta))
membrane('Caudal fan',48,14,caudal)

def dorsal(u,r):
    x=-.65+1.13*u
    root=.17+.13*math.sin(u*math.pi)
    height=.20+.52*math.sin(math.pi*u)**.6
    return (x-.22*r, .05*r*r*math.sin(u*10+1),root+r*height)
membrane('Dorsal sail',28,12,dorsal)

def anal(u,r):
    x=-.71+1.31*u
    root=-.16-.14*math.sin(u*math.pi)
    height=.23+.50*math.sin(math.pi*(u*.88+.09))**.7
    return (x-.25*r,.065*r*r*math.sin(u*8+2),root-r*height)
membrane('Anal skirt',32,12,anal)
for side in [-1,1]:
    def pectoral(u,r,side=side):
        theta=(u-.5)*math.pi*.85
        return (.43-r*.46*math.cos(theta),side*(.21+.16*r)+.045*r*r*math.sin(u*7),-.06+r*.39*math.sin(theta))
    membrane('Pectoral '+('left' if side<0 else 'right'),16,8,pectoral)
    def pelvic(u,r,side=side):
        return (.39-.41*r+(u-.5)*.12*(1-r*.85),side*(.09+.07*r)+.035*r*r*math.sin(r*5),-.23-.93*r)
    membrane('Pelvic ribbon '+('left' if side<0 else 'right'),6,14,pelvic)

# Small opaque scale ridges follow the ellipsoidal body, never painted-on alpha.
for row in range(7):
    angle=-1.1+row*.34
    for col in range(15):
        x=-.62+col*.077+(row%2)*.032
        if x>.48:continue
        pts=[]
        for k in range(7):
            t=math.pi*.3+math.pi*1.4*k/6
            xx=x+.03*math.cos(t)
            a=angle+.063*math.sin(t)
            factor=math.sqrt(max(.01,1-(xx/.94)**2))
            pts.append((xx,-.235*factor*math.cos(a),.335*factor*math.sin(a)))
        curve('Scale ridge',pts,scale,.0032)

# Convert all curves to reusable real geometry; export only the fish meshes.
bpy.ops.object.select_all(action='DESELECT')
for ob in list(bpy.context.scene.objects):
    if ob.type=='CURVE':
        ob.select_set(True);bpy.context.view_layer.objects.active=ob
        bpy.ops.object.convert(target='MESH');ob.select_set(False)
meshes=[ob for ob in bpy.context.scene.objects if ob.type=='MESH']
counts={ob.name:sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in meshes}
(OUT/'model-manifest.json').write_text(json.dumps(dict(kind='Original opaque static poster-study model; runtime integration pending',primary_fin_groups=7,triangles=sum(counts.values()),mesh_count=len(meshes),triangles_by_mesh=counts,poses='same authored mesh, two camera views; no translucency'),indent=2)+'\n')
for ob in meshes:ob.select_set(True)
bpy.ops.wm.obj_export(filepath=str(OUT/'betta-study.obj'),export_selected_objects=True,export_materials=True)

scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.render.film_transparent=True
scene.render.resolution_x=2200;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.world.color=(.35,.35,.35)
scene.view_settings.view_transform='Standard'
def area(name,loc,power,size):
    bpy.ops.object.light_add(type='AREA',location=loc);ob=bpy.context.object;ob.name=name;ob.data.energy=power;ob.data.shape='DISK';ob.data.size=size
    ob.rotation_euler=(Vector((-.3,0,0))-ob.location).to_track_quat('-Z','Y').to_euler()
area('Soft key',(1,-4,5),500,5)
area('Fin rim',(-3,2,4),350,4)
area('Gentle face fill',(4,-3,.4),100,3)
bpy.ops.object.camera_add(location=(0,-9,.4));camera=bpy.context.object;scene.camera=camera
camera.data.type='ORTHO';camera.data.ortho_scale=4.0
def render(name,loc):
    camera.location=loc
    camera.rotation_euler=(Vector((-.45,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
render('betta-side.png',(-.45,-9,.45))
render('betta-oblique.png',(3,-8,2.4))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'betta-study.blend'))
print('POSTER_MODEL_TRIANGLES',sum(counts.values()))
