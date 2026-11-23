"""Generate an editable asset scene and export a World Foundry test level.

Run with Blender from the repository root; see README.md. +Z is up, front is -Y.
"""
import json, math, random, sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'wftools'))
import wf_blender
import wf_blender.operators as wf_ops
import wf_core

random.seed(48)
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()
bpy.ops.wf.import_level(filepath=str(ROOT/'wflevels/snowgoons-blender/snowgoons-blender.lev'))
classes={'director':'Director','camera':'Camera','levelobj':'LevelObj','matte':'Matte','light':'SunLight','room':'Room','camshot':'cs_wide','target':'LookAt','player':'Player'}
seen=set()
for o in list(bpy.context.scene.objects):
    cls=Path(o.get('wf_schema_path','')).stem
    if cls not in classes or cls in seen:
        bpy.data.objects.remove(o,do_unlink=True); continue
    seen.add(cls); o.name=classes[cls]
    schema=ROOT/'wfsource/source/oas'/f'{cls}.oad'
    if schema.is_file():
        o['wf_schema_path']=str(schema); wf_ops._seed_defaults(o,wf_core.load_schema(str(schema)))
    o.location=(0,-20,1); o.rotation_euler=(0,0,0); o.scale=(1,1,1)
    o.hide_render=True; o['wf_Mass']=0.0; o['wf_Model Type']='None'; o['wf_Script']=''; o['wf_original_bbox']=(-.1,-.1,-.1,.1,.1,.1);o['wf_had_authored_bbox']=True
assert seen==set(classes),seen
bpy.data.objects['Room']['wf_Adjacent Room 1']=''
bpy.data.objects['Player']['wf_Tool A']=''
mat=bpy.data.materials.new('village_atlas'); mat.use_nodes=True
img=bpy.data.images.load(str(HERE/'village_atlas.tga'),check_existing=True)
img.filepath='//village_atlas.tga'
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=img
uvnode=mat.node_tree.nodes.new('ShaderNodeUVMap');uvnode.uv_map='UVMap'
mapping=mat.node_tree.nodes.new('ShaderNodeMapping');mapping.inputs['Scale'].default_value=(1,-1,1);mapping.inputs['Location'].default_value=(0,1,0)
mat.node_tree.links.new(uvnode.outputs['UV'],mapping.inputs['Vector']);mat.node_tree.links.new(mapping.outputs['Vector'],node.inputs['Vector'])
mat.node_tree.links.new(node.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
parts=[]
glows=[]
def uv(obj,tile):
    # Each primitive is mapped into one atlas tile with inset to avoid bleeding.
    mesh=obj.data; mesh.materials.clear();mesh.materials.append(mat)
    layer=mesh.uv_layers.active or mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        normal=poly.normal; axis=max(range(3),key=lambda i:abs(normal[i])); axes=[i for i in range(3) if i!=axis]
        coords=[[mesh.vertices[mesh.loops[li].vertex_index].co[i] for i in axes] for li in poly.loop_indices]
        mins=[min(c[i] for c in coords) for i in range(2)]; spans=[max(max(c[i] for c in coords)-mins[i],1e-6) for i in range(2)]
        for li,c in zip(poly.loop_indices,coords): layer.data[li].uv=((tile%4+.03+.94*(c[0]-mins[0])/spans[0])/4,(tile//4+.03+.94*(c[1]-mins[1])/spans[1])/4)
    parts.append(obj); return obj

def cube(loc,scale,tile):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return uv(o,tile)
def cylinder(loc,r,depth,tile,vertices=12,rot=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc,rotation=rot);o=bpy.context.object;bpy.ops.object.transform_apply(location=False,rotation=True,scale=True);return uv(o,tile)
def cone(loc,r,depth,tile):
    bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=r,radius2=.02,depth=depth,location=loc);return uv(bpy.context.object,tile)
def beam(a,b,width,depth,tile):
    a,b=Vector(a),Vector(b);o=cube((a+b)/2,(width,depth,(b-a).length),tile);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return o

def roof(cx,cy,z,w,d,h):
    # Two thin roof slabs: ridge on x=0, roof axis along Y.
    for sign in (-1,1):
        inner=(cx,z+h); outer=(cx+sign*w/2,z)
        v=[(inner[0],cy-d/2,inner[1]),(outer[0],cy-d/2,outer[1]),(outer[0],cy+d/2,outer[1]),(inner[0],cy+d/2,inner[1])]
        v += [(x,y,zz-.10) for x,y,zz in v]
        faces=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)] if sign<0 else [(3,2,1,0),(4,5,6,7),(1,5,4,0),(2,6,5,1),(3,7,6,2),(0,4,7,3)]
        mesh=bpy.data.meshes.new('roof');mesh.from_pydata(v,[],faces);mesh.update()
        o=bpy.data.objects.new('roof',mesh);bpy.context.scene.collection.objects.link(o);uv(o,2)
    beam((cx,cy-d/2,z+h),(cx,cy+d/2,z+h),.13,.13,0)

def gable(z,w,d,h):
    vertices=[(-w/2,-d/2,z),(w/2,-d/2,z),(0,-d/2,z+h),(-w/2,d/2,z),(w/2,d/2,z),(0,d/2,z+h)]
    faces=[(0,1,2),(5,4,3),(0,3,4,1),(1,4,5,2),(2,5,3,0)]
    data=bpy.data.meshes.new('gable');data.from_pydata(vertices,[],faces);data.update()
    o=bpy.data.objects.new('gable',data);bpy.context.scene.collection.objects.link(o);uv(o,1)

def finish(name,origin=(0,0,0)):
    global parts
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();o=bpy.context.object;o.name=name
    bpy.context.scene.cursor.location=origin;bpy.ops.object.origin_set(type='ORIGIN_CURSOR');parts=[];return o

def window(x,y,z,w=.48,h=.56,face=-1):
    cube((x,y,z),(w+.12,.09,h+.12),0);cube((x,y+face*.055,z),(w,.035,h),11)
    cube((x,y+face*.077,z),(w-.025,.008,h-.025),6);glows.append(parts.pop())
    cube((x,y+face*.08,z),(.035,.04,h),8);cube((x,y+face*.08,z),(w,.04,.035),8)
    for side in (-1,1):
        cube((x+side*(w/2+.14),y,z),(.20,.10,h+.08),9)
        for dz in (-.16,0,.16):cube((x+side*(w/2+.14),y+face*.06,z+dz),(.18,.02,.025),0)

def side_window(x,y,z,face):
    cube((x,y,z),(.10,.56,.68),0)
    cube((x+face*.06,y,z),(.035,.42,.54),11)
    cube((x+face*.08,y,z),(.008,.395,.515),6);glows.append(parts.pop())
    cube((x+face*.09,y,z),(.04,.035,.54),8)
    cube((x+face*.09,y,z),(.04,.42,.035),8)

def box_flowers(x,y,z):
    cube((x,y,z),(.69,.22,.15),8)
    for i in range(7):
        xx=x-.28+i*.095; cube((xx,y,z+.12),(.055,.11,.13),4);cube((xx,y-.01,z+.20),(.07,.08,.07),13 if i%2 else 12)

# Pine: layered 12-sided branch crowns and visible bark; three overlapping taper tiers.
cylinder((0,0,.55),.19,1.1,5)
for z,r,h in [(1.05,1.02,1.35),(1.65,.87,1.30),(2.22,.72,1.24),(2.75,.55,1.17),(3.23,.38,1.05)]:
    cone((0,0,z),r,h,4)
    for k in range(7):
        a=2*math.pi*(k/7+.04*(int(z*10)%3))
        cone((r*.73*math.cos(a),r*.73*math.sin(a),z-h*.19),r*.23,h*.42,4)
pine=finish('pine_tree')

# Alpine cottage, complete facades. Local front is -Y.
cube((0,0,.28),(2.5,2.0,.56),3);cube((0,0,1.45),(2.36,1.9,1.85),1)
for x in (-1.12,0,1.12):cube((x,-.97,1.47),(.13,.10,1.85),0)
for z in (.60,1.52,2.30):cube((0,-.98,z),(2.38,.11,.12),0)
for x in (-.78,.78):window(x,-1.04,1.92,.43,.43);box_flowers(x,-1.12,1.58)
cube((0,-1.035,1.04),(.49,.12,.85),8);cube((0,-1.11,1.04),(.36,.03,.75),0)
for x in (-.77,.77):window(x,-1.04,.99,.42,.46)
for y in (-.70,.70):
    for x in (-1.22,1.22):cube((x,y,1.48),(.12,.12,1.85),0)
for y in (-.62,.62):
    for x in (-1.22,1.22):side_window(x,y,1.80,1 if x>0 else -1)
for x in (-.72,.72):window(x,1.00,1.55,.43,.50,face=1)
for x in (-1.12,0,1.12):cube((x,.97,1.47),(.13,.10,1.85),0)
for z in (.60,1.52,2.30):cube((0,.98,z),(2.38,.11,.12),0)
gable(2.36,2.36,1.9,.70)
roof(0,0,2.36,2.9,2.5,.80)
cube((.70,.45,2.95),(.32,.32,.75),3);cube((.70,.45,3.34),(.42,.42,.10),8)
house=finish('standard_house')
parts=glows;house_glow=finish('house_glow');glows=[]

# Clock tower: static shell, clock and balcony; hand meshes have dial-center pivots.
cube((0,0,.32),(2.9,2.35,.64),3);cube((0,0,2.0),(2.65,2.1,2.75),1)
for x in (-1.23,1.23):cube((x,-1.08,2.0),(.16,.12,2.8),0)
for z in (.67,2.05,3.36):cube((0,-1.09,z),(2.7,.14,.15),0)
cube((0,-1.10,1.3),(.65,.13,1.20),8)
for x in (-.85,.85):window(x,-1.13,1.48,.36,.50)
# Balcony, four separate visible alcoves and railing.
cube((0,-1.45,2.46),(2.65,.75,.18),0)
cube((0,-1.82,2.80),(2.65,.10,.09),0)
for x in [-1.2,-.8,-.4,0,.4,.8,1.2]:cube((x,-1.82,2.63),(.07,.09,.38),0)
for x in (-.87,-.29,.29,.87):cube((x,-1.085,2.96),(.48,.07,.63),11)
# Upper dial and roof.
cube((0,0,3.93),(2.25,1.85,1.14),1)
cylinder((0,-.97,4.08),.52,.08,8,32,(math.pi/2,0,0));cylinder((0,-1.025,4.08),.46,.04,7,32,(math.pi/2,0,0))
for i in range(12):
    a=2*math.pi*i/12;x=.37*math.sin(a);z=4.08+.37*math.cos(a)
    o=cube((x,-1.06,z),(.045,.025,.09 if i%3==0 else .055),8);o.rotation_euler[1]=a
cube((0,-.98,4.70),(.53,.08,.32),11)
gable(4.82,2.25,1.85,.65)
roof(0,0,4.82,2.85,2.35,.82)
for x in (-1.05,1.05):cube((x,-.97,3.95),(.12,.12,1.3),0)
finish('clock_tower')
parts=glows;tower_glow=finish('tower_glow');glows=[]
# World Foundry actor origins are at the center of the dial; front is -Y.
for name,length,angle in [('hour_hand',.27,math.radians(304)),('minute_hand',.38,math.radians(48))]:
    o=cube((0,0,length/2),(.055,.03,length),8);o.rotation_euler[1]=angle
    hand=finish(name,(0,0,0));hand.location=(0,-1.10,4.08)
cube((0,0,.15),(.48,.08,.30),0);door=finish('bird_door',(-.24,0,0));door.location=(0,-1.04,4.55)

# Engine actors: independent geometry and shared named house mesh instances.
assets=[bpy.data.objects[n] for n in ('pine_tree','standard_house','clock_tower','hour_hand','minute_hand','bird_door','house_glow','tower_glow')]
for o in assets:
    o['wf_schema_path']=str(ROOT/'wfsource/source/oas/platform.oad');o['wf_Mobility']='Anchored';o['wf_Model Type']='Mesh';o['wf_Mass']=0.0;o['wf_Visibility Mailbox']=1;o['wf_Mesh Name']=o.name+'.iff';o['wf_original_mesh_name']=o.name+'.iff'
    if o.name.endswith('_glow'):o['wf_Visibility Mailbox']=200;o.hide_render=True
# Lay out assets in a review level. The tower components must move with the tower.
positions={'pine_tree':(-4.8,0,0),'standard_house':(3.7,0,0),'house_glow':(3.7,0,0),'clock_tower':(0,0,0),'tower_glow':(0,0,0)}
for n,loc in positions.items():bpy.data.objects[n].location=loc
for i,(loc,angle) in enumerate([((7.1,1.5,0),.35),((5.2,4.1,0),-.45)]):
    o=house.copy();o.data=house.data;o.name=f'house_instance_{i+1}';bpy.context.scene.collection.objects.link(o);o.location=loc;o.rotation_euler.z=angle;o['wf_Mesh Name']='standard_house.iff';o['wf_original_mesh_name']='standard_house.iff'
    glow=house_glow.copy();glow.data=house_glow.data;glow.name=f'house_glow_{i+1}';bpy.context.scene.collection.objects.link(glow);glow.location=loc;glow.rotation_euler.z=angle;glow['wf_Mesh Name']='house_glow.iff';glow['wf_original_mesh_name']='house_glow.iff'
# Lighting and camera for WF level.
sun=bpy.data.objects['SunLight'];sun.rotation_euler=(0,math.radians(40),math.radians(90));sun['wf_lightType']='Directional'
for ch,v in zip(('Red','Green','Blue'),(.80,.78,.72)):sun['wf_light'+ch]=v
amb=sun.copy();amb.name='AmbientLight';bpy.context.scene.collection.objects.link(amb);amb['wf_lightType']='Ambient'
for ch in ('Red','Green','Blue'):amb['wf_light'+ch]=.42
look=bpy.data.objects['LookAt'];look.location=(1.0,0,2)
wide=bpy.data.objects['cs_wide'];wide.location=(7,-12,8)
for axis in 'XYZ':wide['wf_Position '+axis]='Absolute'
wide['wf_Rotation']='Fixed'
for key in ('Follow','Target','Track Object'):wide['wf_'+key]='LookAt'
bpy.data.objects['Camera'].location=wide.location
bpy.data.objects['Matte']['wf_Matte Type']='Color';bpy.data.objects['Matte']['wf_Background Color']=0x0b1115
bpy.data.objects['Player'].location=(0,-3,1)
bpy.data.objects['Room'].location=(0,0,0);bpy.data.objects['Room']['wf_original_bbox']=(-60,-60,-10,60,60,40)
# Save editable project and an honest Blender preview before exporter mutates anything.
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=12
scene.render.resolution_x=1200;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Review_world');scene.world.color=(.035,.035,.035)
bpy.ops.object.light_add(type='AREA',location=(0,-10,15));light=bpy.context.object;light.name='Review_light';light.data.energy=1800;light.data.shape='DISK';light.data.size=10
bpy.ops.object.camera_add(location=(13,-23,13));cam=bpy.context.object;cam.name='Review_camera';cam.rotation_euler=(Vector((1,0,2))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=17;scene.camera=cam
(HERE/'actor-map.json').write_text(json.dumps({o.name:i+1 for i,o in enumerate(o for o in scene.objects if o.get('wf_schema_path'))},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'village_assets.blend'))
scene.render.filepath=str(HERE/'preview.png');bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(light,do_unlink=True);bpy.data.objects.remove(cam,do_unlink=True)
bpy.ops.wf.export_level(filepath=str(HERE/'cuckoo_village_assets.lev'))
print('ASSET_BUILD_OK')
