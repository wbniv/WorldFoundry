"""Build an editable Blender art study of Hour Tree at 10:08.

This is a visual study, not yet the runtime asset or its clock script.
"""
import bpy
import math
import random
from mathutils import Vector, Matrix
from pathlib import Path

ROOT = Path('/src')
OUT = ROOT / 'wflevels/hour_tree'
random.seed(30)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def material(name, color, roughness=.7):
    m = bpy.data.materials.new(name); m.diffuse_color = (*color, 1); m.use_nodes = True
    shader = m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    return m

bark = material('bark', (.38,.20,.08))
nodes = bark.node_tree.nodes
texture = nodes.new('ShaderNodeTexImage'); texture.image = bpy.data.images.load(str(OUT/'bark-source.png'))
bark.node_tree.links.new(texture.outputs['Color'], nodes.get('Principled BSDF').inputs['Base Color'])
green = [material('leaf '+str(i), c) for i,c in enumerate(((.19,.38,.035),(.27,.50,.045),(.36,.57,.055),(.25,.43,.025)))]
groundmat = material('meadow',(.20,.32,.08))
rockmat = material('stone',(.31,.29,.22))
flower = material('flowers',(.72,.45,.49))

def curve(name, points, radii, width, mat):
    cu = bpy.data.curves.new(name,'CURVE'); cu.dimensions='3D'; cu.resolution_u=18; cu.bevel_depth=width; cu.bevel_resolution=4; cu.resolution_u=16
    sp=cu.splines.new('BEZIER'); sp.bezier_points.add(len(points)-1)
    for b, p, r in zip(sp.bezier_points, points, radii):
        b.co=p; b.radius=r; b.handle_left_type='AUTO'; b.handle_right_type='AUTO'
    ob=bpy.data.objects.new(name,cu); scene.collection.objects.link(ob); cu.materials.append(mat)
    return ob

# Several interwoven longitudinal curves produce the broad, twisting trunk and roots.
for k in range(5):
    a=k*math.tau/5
    pts=[]
    for j in range(7):
        z=j*1.05; t=a+z*.38
        pts.append((.30*math.cos(t)*(1-z/9)+.62*math.sin(z*.7), .25*math.sin(t)*(1-z/9), z))
    curve('twisted trunk %02d'%k,pts,[1.6,1.3,1.02,.78,.55,.3,.06],.30,bark)
for k in range(9):
    a=math.tau*k/9; r=random.uniform(1.4,2.4)
    curve('root %02d'%k,[(.1*math.cos(a),.1*math.sin(a),.5),(.75*math.cos(a),.75*math.sin(a),.15),(r*math.cos(a),r*math.sin(a),.025)],[1.2,.68,.03],.22,bark)

def leaf(name, pos, direction, scale):
    # A gently cupped, pointed leaf with an actual midrib and soft shading.
    verts=[(0,0,0),(.16,.19,.02),(.43,.28,.04),(.75,.20,.03),(1,0,0),(.75,-.20,.03),(.43,-.28,.04),(.16,-.19,.02),(.43,0,.09)]
    faces=[(i,(i+1)%8,8) for i in range(8)]
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.materials.append(random.choice(green));data.update()
    ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob);ob.location=pos
    along=Vector(direction).normalized()
    facing=Vector((.42,-.85,.30)); facing=(facing-along*facing.dot(along)).normalized()
    across=facing.cross(along).normalized()
    ob.rotation_euler=Matrix((along,across,facing)).transposed().to_euler()
    ob.scale=(scale,scale,scale)
    solid=ob.modifiers.new('leaf thickness','SOLIDIFY');solid.thickness=.012
    return ob

# Irregular spiralling branch locations retain one visually separate branch per hour.
for i in range(12):
    z=2.2+i*.27+random.uniform(-.10,.10); a=math.radians(31+i*137.508); length=random.uniform(2.0,3.3)*(1-.018*i)
    dx,dy=math.cos(a),math.sin(a)
    p0=Vector((.62*math.sin(z*.7),0,z)); p1=p0+Vector((dx*.65,dy*.65,.32)); p2=p0+Vector((dx*length*.68,dy*length*.68,.85)); p3=p0+Vector((dx*length,dy*length,1.0+random.uniform(-.05,.35)))
    branch=curve('hour branch %02d'%(i+1),[p0,p1,p2,p3],[1,.75,.38,.04],.115,bark)
    branch.hide_render = i>10
    for j in range(11):
        t=.12+j*.086; s=-1 if j%2 else 1
        point=p1.lerp(p3,t)+Vector((-dy*s*.15,dx*s*.15,s*.18))
        direction=Vector((dx*.55-dy*.65*s,dy*.55+dx*.65*s,.35+s*.12))
        ob=leaf('branch %02d leaf %02d'%(i+1,j+1),point,direction,random.uniform(.56,.78))
        ob.hide_render = (i<10 and j not in (1,5,9)) or (i>=10 and not (i==10 and j==0))
    if i==10:
        for j in range(3):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=4,radius=.065,location=p3+Vector((0,0,j*.09)))
            bpy.context.object.name='growing bud %d'%(j+1);bpy.context.object.data.materials.append(green[1])

bpy.ops.mesh.primitive_plane_add(size=14, location=(0,0,-.04));bpy.context.object.data.materials.append(groundmat)
for i in range(28):
    a=random.random()*math.tau; r=random.uniform(1.7,5.5);x,y=r*math.cos(a),r*math.sin(a)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=random.uniform(.10,.35),location=(x,y,.04))
    ob=bpy.context.object;ob.scale.z=.45;ob.data.materials.append(rockmat)
for i in range(300):
    x,y=random.uniform(-8,8),random.uniform(-5,6)
    if x*x+y*y<2: continue
    h=random.uniform(.08,.28)
    curve('grass',[(x,y,0),(x+random.uniform(-.08,.08),y,h)],[1,.05],.012,green[i%4])
    if i%10==0:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.055,location=(x,y,h));bpy.context.object.data.materials.append(flower)

world=bpy.data.worlds.new('sky');scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.37,.55,.75,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
bpy.ops.object.light_add(type='AREA',location=(-6,-8,10));bpy.context.object.data.energy=1500;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=7
bpy.ops.object.light_add(type='SUN',location=(0,0,8));bpy.context.object.rotation_euler=(.45,-.65,-.5);bpy.context.object.data.energy=2
bpy.ops.object.camera_add(location=(8,-15,7));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,3.4))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=11.8;scene.camera=cam
# Camera-facing painted landscape provides the distant mountain and sky vista.
backmat=bpy.data.materials.new('distant painted landscape');backmat.use_nodes=True
n=backmat.node_tree.nodes;n.clear();tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(OUT/'landscape-source.png'));em=n.new('ShaderNodeEmission');out=n.new('ShaderNodeOutputMaterial');backmat.node_tree.links.new(tex.outputs['Color'],em.inputs['Color']);backmat.node_tree.links.new(em.outputs[0],out.inputs['Surface'])
forward=cam.rotation_euler.to_quaternion() @ Vector((0,0,-1))
bpy.ops.mesh.primitive_plane_add(size=2,location=cam.location+forward*35);back=bpy.context.object;back.name='distant landscape';back.rotation_euler=cam.rotation_euler;back.scale=(9,6,1);back.data.materials.append(backmat)
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(ROOT/'docs/plans/2026-11-23-hour-tree/blender-study.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'hour_tree_art.blend'))
bpy.ops.render.render(write_still=True)
