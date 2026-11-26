"""Generate the Moon Lantern standalone clock using existing level features."""
import json
import math
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

OAS = ROOT/'wfsource/source/oas'
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()

COLORS = {'stone':(.095,.12,.17),'stoneedge':(.16,.19,.25),'gold':(.68,.43,.16),
          'goldlight':(.92,.70,.35),'metal':(.26,.28,.31),'dark':(.027,.035,.055),
          'shadow':(.025,.035,.065),'shadow2':(.035,.045,.075),'ivory':(.88,.85,.72),
          'moonlit':(.88,.84,.68),'moonshade':(.14,.17,.23),'glass':(.75,.48,.20),
          'lantern':(1.,.70,.25),'tick':(.82,.77,.62),'nightglow':(1.,.37,.08)}
materials={}
for key,rgb in COLORS.items():
    mat=bpy.data.materials.new(key);mat.use_nodes=True;mat.diffuse_color=(*rgb,1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*rgb,1)
    mat['wf_prelit']=key in ('shadow','shadow2','moonlit','moonshade','lantern','glass','tick','nightglow')
    mat['wf_double_sided']=True
    materials[key]=mat

# Existing brass artwork gives the metal subtle surface variation.  The dark
# dial texture is authored for this level, with fine mineral veins.
for key, filename in (('gold', ROOT/'wflevels/triple_axis_tourbillon/brass-source.png'),
                      ('stone', HERE/'marble-source.png'),
                      ('moonlit', HERE/'moonlit-source.png'),
                      ('moonshade', HERE/'moonshade-source.png')):
    mat=materials[key];mat.diffuse_color=(1,1,1,1)
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(filename));_ = len(tex.image.pixels);tex.image.scale(128,128)
    tex.image.filepath_raw=str(HERE/(key+'-texture.tga'));tex.image.file_format='TARGA';tex.image.save()
    mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])


def actor(name,cls,mesh=None,pos=(0,0,0),fields=None,bounds=None):
    data=None
    if mesh is not None:
        data=bpy.data.meshes.new(name);data.from_pydata(mesh.vertices,[],mesh.faces)
        keys=list(dict.fromkeys(mesh.colors))
        for key in keys:data.materials.append(materials[key])
        for poly,key in zip(data.polygons,mesh.colors):poly.material_index=keys.index(key)
        data.update()
        if any(k in keys for k in ('gold','stone','moonlit','moonshade')):
            uv=data.uv_layers.new(name='UVMap')
            for poly in data.polygons:
                for loop in poly.loop_indices:
                    p=data.vertices[data.loops[loop].vertex_index].co
                    uv.data[loop].uv=((p.x+.70)/1.40,(p.z+.70)/1.40) if name.startswith('Moon') else ((p.x+4.8)/9.6,(p.y+4.8)/9.6)
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);obj.location=pos
    schema=OAS/(cls+'.oad');obj['wf_schema_path']=str(schema);_seed_defaults(obj,wf_core.load_schema(str(schema)))
    values={'Mobility':'Anchored','Mass':0.,'Model Type':'Mesh' if data else 'None',
            'Visibility Mailbox':1 if data else 0,'Script':'','Script Controls Input':'False',
            'Moves Between Rooms':'False','Number Of Local Mailboxes':0}
    values.update(fields or {})
    for key,value in values.items():obj['wf_'+key]=value
    if data:obj['wf_Mesh Name']=name+'.iff';obj['wf_original_mesh_name']=name+'.iff'
    if bounds or not data:obj['wf_original_bbox']=tuple(bounds or (-.05,-.05,-.05,.05,.05,.05));obj['wf_had_authored_bbox']=True
    return obj


def ring(mesh,r0,r1,z,color,n=72):
    for i in range(n):
        a,b=math.tau*i/n,math.tau*(i+1)/n
        mesh.face([(r*math.sin(t),r*math.cos(t),z) for r,t in ((r0,a),(r1,a),(r1,b),(r0,b))],color)

def rail(mesh,r,z,tube,color,n=72,sides=8):
    def pt(i,j):
        a=math.tau*i/n;b=math.tau*j/sides
        return ((r+tube*math.cos(b))*math.sin(a),(r+tube*math.cos(b))*math.cos(a),z+tube*math.sin(b))
    for i in range(n):
        for j in range(sides):mesh.face([pt(i,j),pt(i+1,j),pt(i+1,j+1),pt(i,j+1)],color)


def phase_moon(phase):
    m=Mesh('moon');n=32;rows=16;light=(math.sin(math.tau*phase),math.cos(math.tau*phase),0)
    def point(i,j):
        a=math.tau*i/n;b=math.pi*j/rows
        return (.70*math.sin(b)*math.cos(a),.70*math.sin(b)*math.sin(a),.70*math.cos(b))
    for j in range(rows):
        for i in range(n):
            pts=[point(i,j),point(i,j+1),point(i+1,j+1),point(i+1,j)]
            pts=list(dict.fromkeys(tuple(round(v,8) for v in p) for p in pts))
            if len(pts)<3:continue
            center=[sum(p[k] for p in pts)/len(pts) for k in range(3)]
            m.face(pts,'moonlit' if center[0]*light[0]+center[1]*light[1]>0 else 'moonshade')
    return m


actor('Level','levelobj');actor('Room','room',bounds=(-50,-50,-25,50,50,40))
director=actor('Director','director');actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(0,-10,8),fields={'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=(0,0,1.5))
actor('cs_wide','camshot',pos=(0,-10,8),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':30.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':.5,'lightGreen':.5,'lightBlue':.56})
sun=actor('Key','light',fields={'lightType':'Directional','lightRed':1.,'lightGreen':.88,'lightBlue':.70});sun.rotation_euler=(0,math.radians(40),math.radians(90))
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x080e1a})
actor('MoonLanternSettings','moonlanternsettings',fields={'Editor Label':'Moon Lantern'})
actor('PhaseProbe','target')

dial=Mesh('dial');dial.column_z(0,0,-.55,.05,4.7,'stone',sides=72)
for z,r in ((-.53,4.70),(-.43,4.73),(.015,4.72)):
    rail(dial,r,z,.045,'gold',n=72)
ring(dial,4.48,4.63,.07,'gold');ring(dial,4.18,4.22,.075,'goldlight')
for i in range(60):
    a=math.tau*i/60;r0=3.70 if i%5==0 else 4.0;r1=4.13;w=.035 if i%5==0 else .012
    x0,y0=r0*math.sin(a),r0*math.cos(a);x1,y1=r1*math.sin(a),r1*math.cos(a)
    dx,dy=w*math.cos(a),-w*math.sin(a)
    dial.face([(x0-dx,y0-dy,.08),(x1-dx,y1-dy,.08),(x1+dx,y1+dy,.08),(x0+dx,y0+dy,.08)],'tick')
dial.column_z(0,0,.08,.21,.48,'gold',sides=32);dial.column_z(0,0,.21,3.9,.16,'metal',sides=24)
for z,r in ((.23,.32),(.30,.24),(2.95,.22),(3.05,.20)):
    dial.column_z(0,0,z,z+.08,r,'gold',sides=24)
dial.column_z(0,0,3.9,4.05,.26,'gold',sides=24);dial.sphere((0,0,4.1),.17,'goldlight',segments=16,rings=8)
for z,r in ((4.65,2.65),(3.65,3.65)):
    rail(dial,r,z,.045,'goldlight')
    for i in range(12):
        a=math.tau*i/12;dial.sphere((r*math.sin(a),r*math.cos(a),z),.055,'gold',segments=8,rings=4)
for x in (-2.8,2.8):
    dial.box((x-.30,-3.0,-.95),(x+.30,-2.38,-.52),'metal')
    dial.box((x-.36,-3.07,-.98),(x+.36,-2.33,-.88),'gold')
for side in (-1,1):
    # Swept, faceted brackets attach the larger orbit to the case.
    path=[(side*4.28,.08),(side*4.16,.55),(side*3.93,1.20),
          (side*3.70,1.90),(side*3.60,2.65),(side*3.65,3.65)]
    for p,q in zip(path,path[1:]):dial.beam(p,q,.16,-.09,.09,'gold')
    # The small orbit is supported by curved arms rising from the post.
    path=[(side*.16,2.92),(side*.42,3.54),(side*.95,4.00),
          (side*1.65,4.35),(side*2.65,4.65)]
    for p,q in zip(path,path[1:]):dial.beam(p,q,.10,-.07,.07,'metal')
actor('Dial','platform',dial)

for name,length,width,z,color in (('HourShadow',2.3,.115,.095,'shadow'),('MinuteShadow',3.45,.075,.10,'shadow2')):
    m=Mesh(name);m.face([(-width,0,z),(width,0,z),(width*.45,length,z),(-width*.45,length,z)],color)
    actor(name,'platform',m)

lantern=Mesh('lantern');lantern.column_z(0,0,-.34,-.26,.25,'gold',sides=16)
lantern.column_z(0,0,-.40,-.34,.19,'metal',sides=16)
lantern.column_z(0,0,-.26,.27,.21,'glass',sides=16)
for i in range(8):
    a=math.tau*i/8;lantern.column_z(.22*math.sin(a),.22*math.cos(a),-.26,.29,.025,'goldlight',sides=8)
lantern.column_z(0,0,.27,.34,.26,'gold',sides=16);lantern.sphere((0,0,.40),.09,'goldlight',segments=10,rings=5)
for z in (-.20,.02,.23):rail(lantern,.23,z,.035,'goldlight',n=16,sides=6)
lantern.sphere((0,0,0),.14,'lantern',segments=12,rings=6)
lantern.vertices=[tuple(v*1.35 for v in p) for p in lantern.vertices]
actor('Lantern','platform',lantern,pos=(0,-3.65,3.65))
night_lantern=Mesh('night_lantern')
night_lantern.sphere((0,0,0),.31,'nightglow',segments=16,rings=8)
actor('NightLantern','platform',night_lantern,pos=(0,-3.65,3.65),fields={'Visibility Mailbox':780})
for i in range(32):actor('Moon'+str(i),'platform',phase_moon(i/32),pos=(0,-2.65,4.65),fields={'Visibility Mailbox':800+i})

bpy.context.view_layer.update();objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'moonlanternsettings.oad')],text=True))
drift=next(f['index'] for f in catalog['fields'] if f['key']=='Camera drift')
lines=[r'\ Moon Lantern: local time and approximate UTC lunar elongation.',
 ': ml-h INDEXOF_WALL_HOUR read-mailbox 12 mod 12 / INDEXOF_WALL_MINUTE read-mailbox 720 / + INDEXOF_WALL_SECOND read-mailbox 43200 / + ;',
 ': ml-m INDEXOF_WALL_MINUTE read-mailbox 60 / INDEXOF_WALL_SECOND read-mailbox 3600 / + ;',
 ': ml-d INDEXOF_WALL_DAY read-mailbox INDEXOF_WALL_HOUR read-mailbox 24 / + INDEXOF_WALL_MINUTE read-mailbox 1440 / + INDEXOF_WALL_SECOND read-mailbox 86400 / + INDEXOF_WALL_UTC_OFFSET read-mailbox 1440 / - .5 - ;',
 ': ml-frac dup floor - dup 1 >= if 1 - then ;',  # the engine floor; a tiny negative rounds to 1, which wraps to 0 as the old loop did
 ': ml-moon 218.316 ml-d 13.176396 * + ml-d 13.064993 * 134.963 + 360 / sin-rev 6.289 * + ;',
 ': ml-sun 280.460 ml-d .9856474 * + ml-d .9856003 * 357.528 + 360 / sin-rev 1.915 * + ;',
 ': ml-tick',
 ' INDEXOF_WALL_HOUR read-mailbox dup 6 < swap 18 >= | 780 write-mailbox',
 ' ml-moon ml-sun - 360 / ml-frac 650 write-mailbox',
 f' 650 read-mailbox INDEXOF_X_POS {idx["PhaseProbe"]} write-actor-mailbox',
 f' ml-h negate INDEXOF_ROTATION_C {idx["HourShadow"]} write-actor-mailbox',
 f' ml-m negate INDEXOF_ROTATION_C {idx["MinuteShadow"]} write-actor-mailbox',
 f' ml-m .5 + sin-rev 3.65 * INDEXOF_X_POS {idx["Lantern"]} write-actor-mailbox',
 f' ml-m .5 + cos-rev 3.65 * INDEXOF_Y_POS {idx["Lantern"]} write-actor-mailbox']
lines += [f' ml-m .5 + sin-rev 3.65 * INDEXOF_X_POS {idx["NightLantern"]} write-actor-mailbox',
          f' ml-m .5 + cos-rev 3.65 * INDEXOF_Y_POS {idx["NightLantern"]} write-actor-mailbox']
for i in range(32):
    name='Moon'+str(i)
    lines += [f' 650 read-mailbox {i/32:.7f} >= 650 read-mailbox {(i+1)/32:.7f} < & {800+i} write-mailbox',
              f' ml-h .5 + sin-rev 2.65 * INDEXOF_X_POS {idx[name]} write-actor-mailbox',
              f' ml-h .5 + cos-rev 2.65 * INDEXOF_Y_POS {idx[name]} write-actor-mailbox',
              f' 0 0 {idx[name]} fish-deform']
for name in ('HourShadow','MinuteShadow','Lantern'):lines.append(f' 0 0 {idx[name]} fish-deform')
lines += [f' {idx["MoonLanternSettings"]} {drift} property@ if 0 <> else drop 0 then if 0 else INDEXOF_TIME read-mailbox 60 / sin-rev 1.4 * then INDEXOF_X_POS {idx["cs_wide"]} write-actor-mailbox',
          ';','ml-tick']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'moon_lantern.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'moon_lantern.lev'))
