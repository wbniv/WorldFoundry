"""Author the Mirror and Haze clock with existing World Foundry level facilities."""
import json, math, subprocess, sys
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
sys.path[:0]=[str(ROOT/'wftools'),str(ROOT/'wflevels/clock_common')]
import wf_blender, wf_core
from wf_blender.export_level import _seed_defaults
from clock_mesh import Mesh
OAS=ROOT/'wfsource/source/oas'
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()

COLORS={'black':(.024,.029,.035),'edge':(.16,.19,.21),'metal':(.35,.38,.40),'bright':(.65,.68,.68),
        'gold':(.65,.44,.18),'glass':(.20,.24,.27),'amber':(1.,.52,.055),'green':(.08,1.,.30),'red':(1.,.10,.08),
        'amberhaze':(.8,.28,.02),'greenhaze':(.04,.6,.12),'redhaze':(.65,.04,.025),'gauzehaze':(.13,.15,.17),
        'nightlight':(.85,.88,1.)}
materials={}
for key,rgb in COLORS.items():
    mat=bpy.data.materials.new(key);mat.use_nodes=True;mat.diffuse_color=(*rgb,1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*rgb,1)
    mat['wf_prelit']=True;mat['wf_double_sided']=True
    if key.endswith('haze'):mat['wf_opacity']=.07 if key=='gauzehaze' else .22
    materials[key]=mat

def actor(name,cls,mesh=None,pos=(0,0,0),fields=None,bounds=None):
    data=None
    if mesh is not None:
        data=bpy.data.meshes.new(name);data.from_pydata(mesh.vertices,[],mesh.faces)
        keys=list(dict.fromkeys(mesh.colors))
        for key in keys:data.materials.append(materials[key])
        for poly,key in zip(data.polygons,mesh.colors):poly.material_index=keys.index(key)
        data.update()
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

def rail(m,r,z,w,color,n=72):
    for i in range(n):
        a,b=math.tau*i/n,math.tau*(i+1)/n
        m.face([(d*math.sin(t),d*math.cos(t),z) for d,t in ((r-w,a),(r+w,a),(r+w,b),(r-w,b))],color)

def beam_mesh(name,z,width,color):
    m=Mesh(name)
    # Crossed, differently oriented sheets stay visible from elevated and low cameras.
    m.face([(-width/2,.28,z),(width/2,.28,z),(width/2,4.15,z),(-width/2,4.15,z)],color)
    m.face([(0,.28,z-width/2),(0,4.15,z-width/2),(0,4.15,z+width/2),(0,.28,z+width/2)],color)
    return m

actor('Level','levelobj');actor('Room','room',bounds=(-50,-50,-25,50,50,40))
director=actor('Director','director');actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(0,-6,11.5),fields={'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=(0,0,1.9))
actor('cs_wide','camshot',pos=(0,-6,11.5),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':40.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':.5,'lightGreen':.5,'lightBlue':.5})
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x030507})
actor('MirrorHazeSettings','mirrorhazesettings',fields={'Editor Label':'Mirror and Haze'})
actor('HazeProbe','target')

case=Mesh('case');case.column_z(0,0,-.50,.02,4.45,'black',sides=72)
for z,r,w in ((-.48,4.45,.08),(-.33,4.46,.035),(.065,4.42,.06),(.075,4.18,.025)):
    rail(case,r,z,w,'edge')
for i in range(60):
    a=math.tau*i/60;r0=3.68 if i%5==0 else 3.95;r1=4.11;w=.04 if i%5==0 else .012
    x0,y0=r0*math.sin(a),r0*math.cos(a);x1,y1=r1*math.sin(a),r1*math.cos(a);dx,dy=w*math.cos(a),-w*math.sin(a)
    case.face([(x0-dx,y0-dy,.085),(x1-dx,y1-dy,.085),(x1+dx,y1+dy,.085),(x0+dx,y0+dy,.085)],'bright' if i%5==0 else 'edge')
# Thin vertical rails imply a taut dark mesh without an opaque wall blocking the clock.
for i in range(72):
    a=math.tau*i/72;x,y=4.20*math.sin(a),4.20*math.cos(a)
    case.column_z(x,y,.18,3.62,.018,'edge',sides=6)
for z in (.15,3.62):rail(case,4.20,z,.035,'metal')
for i in range(12):
    a=math.tau*i/12;x,y=4.20*math.sin(a),4.20*math.cos(a)
    case.column_z(x,y,3.55,3.78,.055,'metal',sides=8)
    case.column_z(x,y,-.53,-.44,.055,'bright',sides=8)
for z,r in ((.08,.55),(.18,.42),(.30,.28),(3.8,.28),(3.9,.35)):
    case.column_z(0,0,z,z+.10,r,'metal',sides=24)
case.column_z(0,0,.34,3.80,.19,'metal',sides=24)
for i in range(12):
    a=math.tau*i/12; x,y=.19*math.sin(a),.19*math.cos(a)
    case.column_z(x,y,.36,3.80,.025,'bright' if i%3==0 else 'edge',sides=6)
actor('Instrument','platform',case)
night_ring=Mesh('night_ring')
rail(night_ring,4.20,3.82,.065,'nightlight')
actor('NightRing','platform',night_ring,fields={'Visibility Mailbox':780})

gauze=Mesh('gauze')
for i in range(72):
    a,b=math.tau*i/72,math.tau*(i+1)/72
    gauze.face([(4.16*math.sin(t),4.16*math.cos(t),z) for t,z in ((a,.18),(b,.18),(b,3.58),(a,3.58))],'gauzehaze')
actor('Gauze','platform',gauze)

for name,z,width,color in (('Hour',1.25,.25,'amber'),('Minute',2.20,.13,'green'),('Second',3.15,.055,'red')):
    assembly=Mesh(name+'Mirror')
    assembly.column_z(0,0,z-.15,z+.15,.28,'edge',sides=20)
    for dz in (-.20,.20):assembly.column_z(0,0,z+dz-.035,z+dz+.035,.31,'bright',sides=20)
    assembly.box((-.39,.17,z-.23),(.39,.37,z+.23),'edge')
    assembly.box((-.33,.37,z-.19),(.33,.42,z+.19),'metal')
    assembly.box((-.25,.42,z-.13),(.25,.445,z+.13),color)
    for x in (-.30,.30):
        for dz in (-.16,.16):assembly.sphere((x,.45,z+dz),.045,'gold',segments=8,rings=4)
    for x in (-.46,.46):
        assembly.column_z(x,.22,z-.20,z+.20,.09,'gold',sides=12)
        for k in range(8):
            a=math.tau*k/8
            assembly.column_z(x+.095*math.sin(a),.22+.095*math.cos(a),z-.16,z+.16,.03,'metal',sides=6)
    for x in (-.26,.26):
        assembly.column_z(x,.28,z-.23,z+.23,.045,'gold',sides=8)
    actor(name+'Mirror','platform',assembly)
    actor(name+'Beam','platform',beam_mesh(name+'Beam',z,width,color))
    actor(name+'Haze','platform',beam_mesh(name+'Haze',z,width*3.2,color+'haze'),fields={'Visibility Mailbox':840})

bpy.context.view_layer.update();objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'mirrorhazesettings.oad')],text=True))
fields={f['key']:f['index'] for f in catalog['fields']};drift=fields['Camera drift'];haze=fields['Haze']
lines=[r'\ Mirror and Haze: wall-clock hands with sub-second seconds motion.',
 ': mh-sub INDEXOF_WALL_SECOND read-mailbox 701 read-mailbox <> if INDEXOF_WALL_SECOND read-mailbox 701 write-mailbox 0 700 write-mailbox else 700 read-mailbox INDEXOF_DELTA_TIME read-mailbox 0 max .1 min + .98 min 700 write-mailbox then ;',
 ': mh-s INDEXOF_WALL_SECOND read-mailbox 700 read-mailbox + 60 / ;',
 ': mh-m INDEXOF_WALL_MINUTE read-mailbox mh-s + 60 / ;',
 ': mh-h INDEXOF_WALL_HOUR read-mailbox 12 mod mh-m + 12 / ;',
 ': mh-tick mh-sub',
 ' INDEXOF_WALL_HOUR read-mailbox dup 6 < swap 18 >= | 780 write-mailbox',
 f' {idx["MirrorHazeSettings"]} {haze} property@ if 0 <> else drop 1 then 840 write-mailbox',
 f' 840 read-mailbox INDEXOF_X_POS {idx["HazeProbe"]} write-actor-mailbox']
for name,phase in (('Hour','mh-h'),('Minute','mh-m'),('Second','mh-s')):
    for suffix in ('Mirror','Beam','Haze'):
        lines.append(f' {phase} negate INDEXOF_ROTATION_C {idx[name+suffix]} write-actor-mailbox')
        lines.append(f' 0 0 {idx[name+suffix]} fish-deform')
lines += [f' {idx["MirrorHazeSettings"]} {drift} property@ if 0 <> else drop 0 then if 0 else INDEXOF_TIME read-mailbox 90 / sin-rev 1.1 * then INDEXOF_X_POS {idx["cs_wide"]} write-actor-mailbox',
          f' {idx["MirrorHazeSettings"]} {drift} property@ if 0 <> else drop 0 then if 11.5 else INDEXOF_TIME read-mailbox 120 / sin-rev .8 * 11.5 + then INDEXOF_Z_POS {idx["cs_wide"]} write-actor-mailbox',
          ';','mh-tick']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'mirror_haze.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'mirror_haze.lev'))
