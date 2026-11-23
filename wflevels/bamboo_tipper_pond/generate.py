"""Generate a live miniature railway clock using only existing level features."""
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT/'wftools'), str(ROOT/'wflevels/clock_common'), str(HERE)]
import wf_blender
import wf_core
from wf_blender.export_level import _seed_defaults
from clock_mesh import Mesh
import model

OAS = ROOT/'wfsource/source/oas'
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()

COLORS = {
    'grass': (.12,.29,.16), 'rim': (.20,.095,.045), 'rim_gold': (.64,.39,.12),
    'ballast': (.22,.24,.23), 'sleeper': (.31,.19,.10), 'rail': (.75,.68,.49),
    'red': (.66,.10,.085), 'red_trim': (.94,.37,.13), 'teal': (.055,.35,.36),
    'cream': (.90,.82,.59), 'roof': (.19,.18,.18), 'black': (.045,.055,.06),
    'window': (1.0,.73,.25), 'station': (.66,.55,.38), 'station_roof': (.42,.15,.11),
    'tree': (.055,.22,.12), 'tree_light': (.09,.32,.16), 'trunk': (.23,.12,.055),
    'white': (.90,.93,.88), 'express': (.72,.80,.78), 'express_trim': (.13,.42,.62),
}
COLORS.update({'water':(.65,.85,.75), 'bamboo':(.90,.86,.44), 'fishwhite':(1.,.98,.90), 'fishred':(1.,.23,.12), 'koi_skin':(1.,1.,1.), 'moss':(.43,.66,.29), 'stone':(.72,.72,.62), 'dialstone':(.82,.80,.70), 'lantern':(1.,.84,.43), 'dark':(.32,.23,.12), 'stream':(.85,1.,1.), 'ripple':(.40,.61,.54), 'tree_light':(.18,.43,.14),'sky':(.55,.72,.63),'scene':(1.,1.,1.)})
materials = {}
for key, rgb in COLORS.items():
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    mat.diffuse_color = (*rgb, 1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*rgb, 1)
    mat['wf_prelit'] = True
    mat['wf_double_sided'] = True
    materials[key] = mat


def actor(name, cls, mesh=None, pos=(0,0,0), fields=None, bounds=None):
    data = None
    if mesh is not None:
        data = bpy.data.meshes.new(name)
        data.from_pydata(mesh.vertices, [], mesh.faces)
        keys = list(dict.fromkeys(mesh.colors))
        for key in keys:
            data.materials.append(materials[key])
        for poly, key in zip(data.polygons, mesh.colors):
            poly.material_index = keys.index(key)
        data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS/(cls+'.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    values = {'Mobility':'Anchored', 'Mass':0.0, 'Model Type':'Mesh' if data else 'None',
              'Visibility Mailbox':1 if data else 0, 'Script':'', 'Script Controls Input':'False',
              'Moves Between Rooms':'False', 'Number Of Local Mailboxes':0}
    values.update(fields or {})
    for key, value in values.items():
        obj['wf_'+key] = value
    if data:
        obj['wf_Mesh Name'] = name+'.iff'
        obj['wf_original_mesh_name'] = name+'.iff'
    if bounds or not data:
        obj['wf_original_bbox'] = tuple(bounds or (-.05,-.05,-.05,.05,.05,.05))
        obj['wf_had_authored_bbox'] = True
    return obj


def texture(key, source, size):
    mat=materials[key];mat.diffuse_color=(1,1,1,1);mat['wf_prelit']=True
    node=mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image=bpy.data.images.load(str(HERE/source));_=len(node.image.pixels)
    node.image.scale(*size);node.image.filepath_raw=str(HERE/(key+'-texture.tga'))
    node.image.file_format='TARGA';node.image.save()
    mat.node_tree.links.new(node.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])


def texture_uv(obj,mesh=None):
    data=obj.data; uv=data.uv_layers.new(name='UVMap')
    for poly in data.polygons:
        key=data.materials[poly.material_index].name
        for loop in poly.loop_indices:
            p=data.vertices[data.loops[loop].vertex_index].co
            if key=='water': uv.data[loop].uv=((p.x+6)/12,1-(p.y+6)/12)
            elif key=='moss':
                verts=[data.vertices[data.loops[n].vertex_index].co for n in poly.loop_indices]
                lowx=min(v.x for v in verts);lowy=min(v.y for v in verts)
                uv.data[loop].uv=(min(1,(p.x-lowx)/5),1-min(1,(p.y-lowy)/5))
            elif key in ('stone','dialstone'): uv.data[loop].uv=getattr(mesh,'stone_uv',{}).get(data.loops[loop].vertex_index,((p.x+9)/18,1-(p.y+9)/18))
            elif key=='scene': uv.data[loop].uv=((p.x+80)/160,1-(p.z+15)/55)
            elif key=='koi_skin': uv.data[loop].uv=((p.x+.75)/1.5,1-(p.y+.35)/.70)
            else: uv.data[loop].uv=((p.x+3)/6,1-(p.z+3)/6)


def ellipse(mesh,centre,scale,colour):
    first=len(mesh.vertices);mesh.sphere(centre,1,colour,segments=12,rings=6)
    cx,cy,cz=centre
    for i in range(first,len(mesh.vertices)):
        x,y,z=mesh.vertices[i]
        if colour in ('stone','dialstone'):
            if not hasattr(mesh,'stone_uv'): mesh.stone_uv={}
            mesh.stone_uv[i]=((x-cx+1)/2,1-(y-cy+1)/2)
            irregular=1+.12*math.sin(7*x+11*y+5*z+cx*3)
        else: irregular=1
        mesh.vertices[i]=(cx+(x-cx)*scale[0]*irregular,cy+(y-cy)*scale[1]*irregular,cz+(z-cz)*scale[2]*irregular)


def ring(mesh,inside,outside,z,colour):
    for i in range(96):
        a,b=math.tau*i/96,math.tau*(i+1)/96
        mesh.face([(r*math.sin(t),r*math.cos(t),z) for r,t in ((inside,a),(outside,a),(outside,b),(inside,b))],colour)


def hollow_tube(mesh,length,radius,colour):
    # A half-open bamboo trough along X; the surface and nodes are real geometry.
    for i in range(12):
        a=-math.pi*i/12;b=-math.pi*(i+1)/12
        mesh.face([(x,radius*math.cos(t),radius*math.sin(t)) for x,t in ((-length/2,a),(length/2,a),(length/2,b),(-length/2,b))],colour)
        mesh.face([(x,(radius-.035)*math.cos(t),(radius-.035)*math.sin(t)) for x,t in ((-length/2,b),(length/2,b),(length/2,a),(-length/2,a))],'dark')
    for x in (-length/2+.04,0,length/2-.08):
        for i in range(12):
            a=-math.pi*i/12;b=-math.pi*(i+1)/12
            mesh.face([(v,(radius+.006)*math.cos(t),(radius+.006)*math.sin(t)) for v,t in ((x-.025,a),(x+.025,a),(x+.025,b),(x-.025,b))],'dark')


def cylinder_x(mesh,x0,x1,y,z,r,colour):
    for i in range(12):
        a,b=math.tau*i/12,math.tau*(i+1)/12
        mesh.face([(x,y+r*math.cos(t),z+r*math.sin(t)) for x,t in ((x0,a),(x1,a),(x1,b),(x0,b))],colour)
    for x in (x0,x1):
        mesh.face([(x,y+r*math.cos(math.tau*i/12),z+r*math.sin(math.tau*i/12)) for i in range(12)],colour)


texture('water','water-source.png',(128,128))
texture('bamboo','bamboo-source.png',(64,64))
texture('moss','moss-source.png',(128,128))
texture('stone','stone-grain-source.png',(64,64))
texture('dialstone','stone-grain-source.png',(64,64))
texture('scene','garden-source.png',(128,64))
texture('koi_skin','koi-source.png',(64,64))
actor('Level','levelobj')
actor('Room','room',bounds=(-40,-40,-20,40,40,30))
director=actor('Director','director')
actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(0,-8,8.5),fields={'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=(.7,0,0))
actor('cs_wide','camshot',pos=(0,-8,8.5),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':50.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':1.,'lightGreen':1.,'lightBlue':1.})
sun=actor('Sun','light',fields={'lightType':'Directional','lightRed':1.,'lightGreen':.95,'lightBlue':.85})
sun.rotation_euler=(0,0,math.pi)
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x20342c})
actor('BambooPondSettings','bamboopondsettings',fields={'Editor Label':'Bamboo Tipper and Pond'})

background=Mesh('background');background.quad_y(-80,-15,80,40,18,'scene')
texture_uv(actor('GardenBackdrop','platform',background))

garden=Mesh('garden')
for ix in range(-6,6):
    for iy in range(-6,6):
        x,y=ix*5,iy*5
        garden.face([(x-.01,y-.01,-.14),(x+5.01,y-.01,-.14),(x+5.01,y+5.01,-.14),(x-.01,y+5.01,-.14)],'moss')
random.seed(39)
for i in range(12):
    a=math.tau*i/12
    ellipse(garden,(4.20*math.sin(a),4.20*math.cos(a),.055),(.37,.37,.14),'dialstone')
for i in range(30):
    a=random.random()*math.tau;r=random.uniform(5.8,8)
    x,y=r*math.sin(a),r*math.cos(a)
    if x>4 and abs(y)<2: continue
    ellipse(garden,(x,y,-.03),(random.uniform(.12,.38),random.uniform(.12,.35),random.uniform(.08,.20)),'stone')
for i in range(28):
    a=random.random()*math.tau;r=random.uniform(5.25,7.7)
    x,y=r*math.sin(a),r*math.cos(a)
    if x>4 and abs(y)<2: continue
    for blade in range(7):
        q=math.tau*blade/7;reach=random.uniform(.45,.95);height=random.uniform(.65,1.25)
        tip=(x+reach*math.cos(q),y+reach*math.sin(q),height)
        left=(x+.08*math.cos(q+1),y+.08*math.sin(q+1),-.02)
        right=(x+.08*math.cos(q-1),y+.08*math.sin(q-1),-.02)
        garden.face([left,right,tip],'tree_light')
        for part in range(1,5):
            t=part/5;cx=x+reach*math.cos(q)*t;cy=y+reach*math.sin(q)*t;cz=height*t
            width=.25*(1-t)
            for side in (-1,1):
                garden.face([(cx,cy,cz),(cx+side*width*math.sin(q),cy-side*width*math.cos(q),cz+.035),(cx+.09*math.cos(q),cy+.09*math.sin(q),cz+.07)],'tree_light')
texture_uv(actor('Garden','platform',garden),garden)
grove=Mesh('bamboo-grove')
for i in range(15):
    x=-8+i*1.15+random.uniform(-.55,.55); y=7.4+random.uniform(-.2,1.7); height=random.uniform(3.4,5.6)
    grove.column_z(x,y,-.1,height,.075,'bamboo',sides=10)
    for n in range(1,7):
        z=height*n/7
        grove.column_z(x,y,z,z+.055,.09,'dark',sides=10)
    for n in range(4):
        z=height*(.50+n*.11);side=-1 if (n+i)%2 else 1
        for j in range(4):
            reach=.38+j*.10
            grove.face([(x+side*.06,y,z),(x+side*reach,y-.04,z+.18+j*.05),(x+side*(reach-.10),y+.06,z+.10+j*.05)],'tree_light')
texture_uv(actor('BambooGrove','platform',grove))
pond=Mesh('pond');pond.column_z(0,0,-.13,-.04,4.7,'water',sides=96)
texture_uv(actor('PondWater','platform',pond))

lantern=Mesh('lantern');lantern.box((-.30,-.30,0),(.30,.30,.13),'dark')
lantern.box((-.24,-.24,.13),(.24,.24,.56),'lantern')
for x in (-.25,.21):
    for y in (-.25,.21): lantern.box((x,y,.12),(x+.04,y+.04,.63),'dark')
lantern.box((-.33,-.33,.57),(.33,.33,.64),'dark')
actor('FloatingLantern','platform',lantern,pos=(0,3.55,0))

koi=Mesh('koi');ellipse(koi,(0,0,.13),(.30,.72,.20),'koi_skin')
koi.face([(-.08,-.52,.13),(-.44,-1,.08),(0,-.82,.13),(.44,-1,.08),(.08,-.52,.13)],'fishwhite')
for s in (-1,1):
    koi.face([(s*.18,-.02,.10),(s*.52,-.35,.08),(s*.24,-.30,.17)],'fishwhite')
    ellipse(koi,(s*.20,.50,.18),(.035,.035,.035),'black')
# The Aquarium's fish-deform primitive expects a fish whose nose points along +X.
koi.vertices=[(y,-x,z) for x,y,z in koi.vertices]
texture_uv(actor('Koi','platform',koi,pos=(0,2.85,0)))

for name in ('KoiRipples','LanternRipples'):
    ripple=Mesh(name)
    for r in (.50,.75,1.0): ring(ripple,r,r+.015,.025,'ripple')
    actor(name,'platform',ripple,fields={'Visibility Mailbox':870})

support=Mesh('tipper-support')
for y in (-.45,.45): support.column_z(5.55,y,-.05,1.45,.11,'bamboo',sides=12)
support.column_z(6.75,0,-.05,2.7,.16,'bamboo',sides=12)
cylinder_x(support,6.05,6.70,0,2.55,.11,'bamboo')
ellipse(support,(5.55,0,.05),(.45,.40,.18),'stone')
texture_uv(actor('BambooSupport','platform',support))
tube=Mesh('tipper');hollow_tube(tube,2.6,.32,'bamboo')
texture_uv(actor('Tipper','platform',tube,pos=(5.55,0,1.40)))
fillmesh=Mesh('fill');fillmesh.box((-1.02,-.22,-.26),(1.02,.22,-.23),'water')
texture_uv(actor('TubeWater','platform',fillmesh,pos=(5.55,0,1.4)))
stream=Mesh('stream');stream.column_z(6.05,0,1.45,2.48,.035,'stream',sides=6)
actor('SpoutWater','platform',stream)

bpy.context.view_layer.update()
objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'bamboopondsettings.oad')],text=True))
fields={f['key']:f for f in catalog['fields']};drift=fields['Camera drift']['index']
settings=idx['BambooPondSettings']
water_motion=fields['Water motion']['index'];ripples=fields['Ripples']['index'];koi_size=fields['Koi size']['index']
lines=[r'\ Bamboo pond: local time controls the two orbits and the silent tipper.',
       ': bp-hour INDEXOF_WALL_HOUR read-mailbox 12 / INDEXOF_WALL_MINUTE read-mailbox 720 / + INDEXOF_WALL_SECOND read-mailbox 43200 / + ;',
       ': bp-minute INDEXOF_WALL_MINUTE read-mailbox 60 / INDEXOF_WALL_SECOND read-mailbox 3600 / + ;',
       ': bp-tip INDEXOF_WALL_SECOND read-mailbox dup 1 < if .1 * else dup 2 < if drop .1 else dup 3 < if 3 swap - .1 * else drop 0 then then then ;',
       ': bp-fill INDEXOF_WALL_SECOND read-mailbox dup 3 < if drop 0 else 3 - 57 / then ;']
def spline_word(component):
    def polynomial(segment):
        a,b,c,d=model.spline_coefficients(segment,component)
        local=f'{segment} - ' if segment else ''
        return f'{local}dup dup {a:.7f} * {b:.7f} + * {c:.7f} + * {d:.7f} +'
    branches=' '.join(f'dup {i+1} < if {polynomial(i)} else' for i in range(5))
    return f': bp-c{component} INDEXOF_WALL_SECOND read-mailbox 10 / {branches} {polynomial(5)} '+'then '*5+';'
lines.extend(spline_word(i) for i in range(6))
lines.append(': bp-tick')
for name,phase,radius in (('FloatingLantern','bp-hour',3.55),('LanternRipples','bp-hour',3.55),('Koi','bp-minute',2.85),('KoiRipples','bp-minute',2.85)):
    lines += [f' {phase} sin-rev {radius} * INDEXOF_X_POS {idx[name]} write-actor-mailbox',
              f' {phase} cos-rev {radius} * INDEXOF_Y_POS {idx[name]} write-actor-mailbox']
lines.append(f' bp-minute negate INDEXOF_ROTATION_C {idx["Koi"]} write-actor-mailbox')
lines.append(f' {settings} {water_motion} property@ if 0 <> else drop 1 then if INDEXOF_WALL_SECOND read-mailbox 60 / sin-rev .02 * else 0 then INDEXOF_ROTATION_C {idx["PondWater"]} write-actor-mailbox')
lines.append(f' {settings} {ripples} property@ if 0 <> else drop 1 then 870 write-mailbox')
for axis in ('X','Y','Z'):
    lines.append(f' {settings} {koi_size} property@ if dup 0 = if drop .75 else 2 = if 1.35 else 1 then then else drop 1 then INDEXOF_{axis}_SCALE {idx["Koi"]} write-actor-mailbox')
for name in ('Tipper','TubeWater'):
    lines.append(f' bp-tip INDEXOF_ROTATION_B {idx[name]} write-actor-mailbox')
lines.append(f' bp-fill .12 * 1.39 + INDEXOF_Z_POS {idx["TubeWater"]} write-actor-mailbox')
for name in ('FloatingLantern','KoiRipples','LanternRipples','PondWater','Tipper','TubeWater'):
    lines.append(f' 0 0 {idx[name]} fish-deform')
lines.append(f' INDEXOF_WALL_SECOND read-mailbox 2 / .04 {idx["Koi"]} fish-deform')
lines.append(f' {idx["BambooPondSettings"]} {drift} property@ if 0 <> else drop 0 then if')
axes=('INDEXOF_X_POS','INDEXOF_Y_POS','INDEXOF_Z_POS')
for i in range(6):
    target='cs_wide' if i<3 else 'LookAt'
    lines.append(f' {model.CAMERA_STILL[i]:.7f} {axes[i%3]} {idx[target]} write-actor-mailbox')
lines.append(' else')
for i in range(6):
    target='cs_wide' if i<3 else 'LookAt'
    lines.append(f' bp-c{i} {axes[i%3]} {idx[target]} write-actor-mailbox')
lines += [' then',';','bp-tick']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'bamboo_tipper_pond.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'bamboo_tipper_pond.lev'))

