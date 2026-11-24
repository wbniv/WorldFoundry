"""Build the editable krathong reference and its Blender render."""
import bpy, math, random
from mathutils import Vector
from pathlib import Path

out = Path(__file__).resolve().parent
random.seed(9)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def material(name, color, rough=.55, emission=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1); p.inputs['Roughness'].default_value=rough
    if emission:
        p.inputs['Emission Color'].default_value=(*color,1); p.inputs['Emission Strength'].default_value=emission
    return m
leaf=material('Banana leaf',(.12,.29,.045)); leaf2=material('Leaf fold highlights',(.27,.43,.07)); edge=material('Leaf ribs',(.43,.51,.12)); base=material('Banana stalk',(.49,.39,.19)); wax=material('Candle wax',(.95,.76,.45)); wick=material('Charred wick',(.045,.023,.012)); yellow=material('Marigold gold',(1,.48,.035)); orange=material('Marigold orange',(.9,.22,.018)); pink=material('Lotus pink',(.83,.13,.25)); white=material('Jasmine cream',(.94,.86,.65)); flame=material('Flame gold',(1,.24,.018),emission=4); core=material('Flame core',(1,.78,.19),emission=7); water=material('Water',(.018,.095,.12),.22)
def assign(obj,mat): obj.data.materials.append(mat); return obj
def sphere(name,loc,scale,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; assign(o,mat); bpy.ops.object.shade_smooth(); return o
def cylinder(name,loc,r,depth,mat,vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=name; assign(o,mat); bevel=o.modifiers.new('Soft edge','BEVEL'); bevel.width=.025; bevel.segments=3; o.modifiers.new('Normals','WEIGHTED_NORMAL'); return o
def tube(name,points,r,mat):
    c=bpy.data.curves.new(name,'CURVE'); c.dimensions='3D'; c.resolution_u=12; c.bevel_depth=r; c.bevel_resolution=2; s=c.splines.new('POLY'); s.points.add(len(points)-1)
    for p,v in zip(s.points,points): p.co=(*v,1)
    o=bpy.data.objects.new(name,c); bpy.context.collection.objects.link(o); assign(o,mat); return o
def petal(name,ang,r0,length,width,z,raise_z,mat):
    verts=[]; faces=[]; n=10; m=6
    for i in range(n+1):
        t=i/n; radial=r0+length*t; w=width*(math.sin(math.pi*t)**.7)
        for j in range(m+1):
            u=(j/m*2-1); x=radial*math.cos(ang)-u*w*math.sin(ang); y=radial*math.sin(ang)+u*w*math.cos(ang); zz=z+raise_z*t*t+.06*(1-u*u)*math.sin(math.pi*t); verts.append((x,y,zz))
    for i in range(n):
        for j in range(m): a=i*(m+1)+j; faces.append((a,a+1,a+m+2,a+m+1))
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update(); o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); assign(o,mat); sol=o.modifiers.new('Leaf thickness','SOLIDIFY'); sol.thickness=.008; return o
cylinder('Banana stalk float', (0,0,.13),1,.26,base)
cylinder('Leaf-covered top',(0,0,.28),.98,.06,leaf)
for i in range(20):
    a=2*math.pi*i/20; petal('Outer folded leaf %02d'%i,a,.53,.63,.18,.30,.32,leaf2 if i%3==0 else leaf)
    tube('Fold seam',[(.58*math.cos(a),.58*math.sin(a),.31),(.92*math.cos(a),.92*math.sin(a),.42),(1.16*math.cos(a),1.16*math.sin(a),.62)],.006,edge)
for i in range(16): petal('Inner leaf %02d'%i,2*math.pi*(i+.5)/16,.25,.55,.14,.33,.23,leaf2 if i%2 else leaf)
for k in range(14):
    a=2*math.pi*k/14; x,y=.70*math.cos(a),.70*math.sin(a); col=yellow if k%3 else orange
    sphere('Marigold heart',(x,y,.46),(.10,.10,.07),col)
    for j in range(12):
        b=2*math.pi*j/12; sphere('Marigold petal',(x+.075*math.cos(b),y+.075*math.sin(b),.48+random.uniform(-.025,.025)),(.055,.055,.035),col)
for k in range(8):
    a=2*math.pi*k/8; x,y=.39*math.cos(a),.39*math.sin(a)
    for j in range(5):
        b=j*2*math.pi/5; sphere('Jasmine petal',(x+.045*math.cos(b),y+.045*math.sin(b),.43),(.038,.038,.026),white)
    sphere('Flower center',(x,y,.452),(.025,.025,.02),yellow)
cylinder('Wax candle',(0,0,.63),.075,.57,wax,32); cylinder('Wick',(0,0,.945),.009,.08,wick,12)
sphere('Candle flame',(0,0,1.08),(.08,.08,.19),flame); sphere('Bright flame core',(0,-.02,1.03),(.038,.038,.10),core)
for i in range(3):
    x=-.20+i*.07; tube('Incense stick',[(x,.15,.35),(x-.025,.15,1.12+i*.04)],.009,wick); sphere('Incense glowing tip',(x-.025,.15,1.12+i*.04),(.016,.016,.016),flame)
cylinder('Presentation water',(0,0,-.055),8,.05,water,96)
world=bpy.context.scene.world; world.color=(.08,.08,.08)
def light(name,loc,power,color,size):
    bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.color=color; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector((0,0,.3))-o.location).to_track_quat('-Z','Y').to_euler()
light('Warm key',(2,-3,5),550,(1,.77,.48),4); light('Cool fill',(-4,-1,3),420,(.42,.65,1),5); light('Rim',(0,4,4),650,(1,.64,.3),3)
bpy.ops.object.camera_add(location=(3.6,-5.4,3.6)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,0,.45))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='ORTHO'; cam.data.ortho_scale=3.4
scene=bpy.context.scene; scene.camera=cam; scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.render.resolution_x=1000; scene.render.resolution_y=800; scene.render.resolution_percentage=100
scene.world.color=(.055,.055,.055); scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(out/'krathong-blender.png')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'krathong.blend')); bpy.ops.render.render(write_still=True)
