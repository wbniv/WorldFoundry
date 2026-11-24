"""Generate the standalone Metronome Forest clock."""
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
COLORS.update({'gold':(.85,.57,.22),'goldlight':(1.,.80,.40),'goldshade':(.43,.24,.07),'steel':(.65,.69,.68),'steelshade':(.25,.30,.32),'ivory':(.95,.87,.69),'base':(.12,.08,.06),'ruby':(.8,.12,.17),'bead':(.30,1.,.75),'wood':(.30,.16,.09),'dark':(.08,.06,.04),'backdrop':(.09,.07,.065)})
COLORS.update({'green':(.18,.80,.13),'neutral':(.70,.73,.72),'gunmetal':(.23,.26,.27),'bronze':(.42,.25,.10),'panel':(.07,.055,.045),'glow':(.9,.78,.50)})
COLORS.update({'gray_front':(.43,.47,.48),'gray_side':(.27,.30,.31),
               'gray_back':(.34,.37,.38),'gray_top':(.57,.60,.60)})
materials = {}
for key, rgb in COLORS.items():
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    mat.diffuse_color = (*rgb, 1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*rgb, 1)
    mat['wf_prelit'] = True
    mat['wf_double_sided'] = True
    materials[key] = mat

brass=materials['gold'];brass.diffuse_color=(1,1,1,1)
tex=brass.node_tree.nodes.new('ShaderNodeTexImage')
tex.image=bpy.data.images.load(str(HERE/'brass-source.png'))
_ = len(tex.image.pixels);tex.image.scale(128,128)
tex.image.filepath_raw=str(HERE/'brass-texture.tga');tex.image.file_format='TARGA';tex.image.save()
brass.node_tree.links.new(tex.outputs['Color'],brass.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])


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
        if 'gold' in keys:
            uv=data.uv_layers.new(name='UVMap')
            coords=[v.co for v in data.vertices]
            xmin=min(v.x for v in coords);xspan=max(.001,max(v.x for v in coords)-xmin)
            zmin=min(v.z for v in coords);zspan=max(.001,max(v.z for v in coords)-zmin)
            for poly in data.polygons:
                for loop in poly.loop_indices:
                    p=data.vertices[data.loops[loop].vertex_index].co
                    uv.data[loop].uv=((p.x-xmin)/xspan,1-(p.z-zmin)/zspan)
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


def case(mesh,x,y,z,metal):
    """Solid tapered body, broad and deep at the bottom like the reference."""
    bottom=[(x-.43,y-.32,z),(x+.43,y-.32,z),(x+.43,y+.32,z),(x-.43,y+.32,z)]
    top=[(x-.18,y-.12,z+1.45),(x+.18,y-.12,z+1.45),
         (x+.18,y+.12,z+1.45),(x-.18,y+.12,z+1.45)]
    mesh.face(list(reversed(bottom)),metal)
    mesh.face(top,'gray_top' if metal=='gunmetal' else metal)
    for i in range(4):
        j=(i+1)%4
        shade=('gray_front','gray_side','gray_back','gray_side')[i] if metal=='gunmetal' else metal
        mesh.face([bottom[i],bottom[j],top[j],top[i]],shade)


def pendulum(green):
    m=Mesh('pendulum')
    m.beam((0,0),(0,1.14),.045,-.025,.025,'neutral')
    m.sphere((0,-.035,.74),.12,'green' if green else 'black',segments=12,rings=6)
    m.sphere((0,-.035,0),.08,'black',segments=8,rings=4)
    return m


actor('Level','levelobj');actor('Room','room',bounds=(-50,-50,-25,50,50,40))
director=actor('Director','director')
actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(4.9,-7.7,11.44),fields={'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=(0,0,.8))
actor('cs_wide','camshot',pos=(4.9,-7.7,11.44),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':50.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':1.,'lightGreen':1.,'lightBlue':1.})
actor('Sun','light',fields={'lightType':'Directional','lightRed':.9,'lightGreen':.8,'lightBlue':.7})
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x15100d})
actor('MetronomeForestSettings','metronomeforestsettings',fields={'Editor Label':'Metronome Forest'})

stand=Mesh('stand')
stand.box((-8,-3.35,-.22),(8,3.35,-.04),'base')
stand.box((-8,-3.37,-.12),(8,-3.33,-.03),'goldshade')
for x in (-6.8, 6.8):
    stand.box((x-.11,-3.28,-.03),(x+.11,-3.06,.40),'dark')
    stand.box((x-.25,-3.32,.38),(x+.25,-3.02,.45),'goldshade')
actor('FlatDisplay','platform',stand)
night_lamps=Mesh('night_lamps')
for x in (-6.8, 6.8):
    night_lamps.sphere((x,-3.17,.62),.25,'glow',segments=12,rings=6)
actor('NightLamps','platform',night_lamps,fields={'Visibility Mailbox':780})

for col in range(12):
    x=(col-5.5)*1.30
    for is_brass in (True,False):
        body=Mesh('column')
        for row in range(5): case(body,x,-2.6+row*1.3,0,'gold' if is_brass else 'gunmetal')
        actor(('Brass' if is_brass else 'Gray')+str(col),'platform',body,fields={'Visibility Mailbox':800+col*2+(0 if is_brass else 1)})
    for row in range(5):
        i=col*5+row;position=(x,-2.6+row*1.3-.37,.23)
        for green in (True,False):
            actor(('Green' if green else 'Plain')+str(i),'platform',pendulum(green),pos=position,fields={'Visibility Mailbox':900+i*2+(0 if green else 1)})

bpy.context.view_layer.update();objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'metronomeforestsettings.oad')],text=True))
fields={f['key']:f for f in catalog['fields']};drift=fields['Camera drift']['index']
lines=[r'\ Silent pendulum-wave clock: 60 distinct whole cycles per minute.',
       ': mf-hour INDEXOF_WALL_HOUR read-mailbox 12 mod dup 0 = if drop 12 then ;']
def spline_word(component):
    def polynomial(segment):
        a,b,c,d=model.spline_coefficients(segment,component);local=f'{segment} - ' if segment else ''
        return f'{local}dup dup {a:.7f} * {b:.7f} + * {c:.7f} + * {d:.7f} +'
    branches=' '.join(f'dup {i+1} < if {polynomial(i)} else' for i in range(5))
    return f': mf-c{component} INDEXOF_WALL_SECOND read-mailbox 10 / {branches} {polynomial(5)} '+'then '*5+';'
lines.extend(spline_word(i) for i in range(6))
lines.append(': mf-tick')
lines.append(' INDEXOF_WALL_HOUR read-mailbox dup 6 < swap 18 >= | 780 write-mailbox')
for col in range(12):
    lines.append(f' mf-hour {col} > dup {800+col*2} write-mailbox 0 = {801+col*2} write-mailbox')
    for variant in ('Brass','Gray'):
        lines.append(f' 0 0 {idx[variant+str(col)]} fish-deform')
for i in range(60):
    lines.append(f' INDEXOF_WALL_MINUTE read-mailbox {i} > dup {900+i*2} write-mailbox 0 = {901+i*2} write-mailbox')
    for variant in ('Green','Plain'):
        name=variant+str(i)
        lines.append(f' INDEXOF_WALL_SECOND read-mailbox {60+i} * 60 / sin-rev .07 * INDEXOF_ROTATION_B {idx[name]} write-actor-mailbox')
        lines.append(f' 0 0 {idx[name]} fish-deform')
lines.append(f' {idx["MetronomeForestSettings"]} {drift} property@ if 0 <> else drop 0 then if')
axes=('INDEXOF_X_POS','INDEXOF_Y_POS','INDEXOF_Z_POS')
for j in range(6):
    name='cs_wide' if j<3 else 'LookAt'
    lines.append(f' {model.CAMERA_STILL[j]:.7f} {axes[j%3]} {idx[name]} write-actor-mailbox')
lines.append(' else')
for j in range(6):
    name='cs_wide' if j<3 else 'LookAt'
    lines.append(f' mf-c{j} {axes[j%3]} {idx[name]} write-actor-mailbox')
lines+=[' then',';','mf-tick']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'metronome_forest.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'metronome_forest.lev'))
