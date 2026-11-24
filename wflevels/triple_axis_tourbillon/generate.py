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
COLORS.update({'gold':(.85,.57,.22),'goldlight':(1.,.80,.40),'goldshade':(.43,.24,.07),'steel':(.65,.69,.68),'steelshade':(.25,.30,.32),'ivory':(.95,.87,.69),'base':(.12,.08,.06),'ruby':(.8,.12,.17),'bead':(.30,1.,.75),'wood':(.30,.16,.09),'dark':(.08,.06,.04),'backdrop':(.09,.07,.065)})
COLORS['night_glow']=(1.,.78,.32)
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


def torus(mesh,r,tube,plane,colour,n=72,m=8):
    def point(a,b):
        u=math.tau*a/n;v=math.tau*b/m
        x=(r+tube*math.cos(v))*math.cos(u);y=(r+tube*math.cos(v))*math.sin(u);z=tube*math.sin(v)
        return (x,z,y) if plane=='xz' else ((z,x,y) if plane=='yz' else (x,y,z))
    for i in range(n):
        for j in range(m):
            shade=colour
            if j in (3,4) and colour in ('gold','goldlight'):shade='goldshade'
            if j in (3,4) and colour=='steel':shade='steelshade'
            mesh.face([point(i,j),point(i+1,j),point(i+1,j+1),point(i,j+1)],shade)


def beveled_base(mesh,half_x,half_y,z0,z1,cut,colour):
    ring=[(-half_x+cut,-half_y),(half_x-cut,-half_y),(half_x,-half_y+cut),(half_x,half_y-cut),
          (half_x-cut,half_y),(-half_x+cut,half_y),(-half_x,half_y-cut),(-half_x,-half_y+cut)]
    mesh.face([(x,y,z0) for x,y in reversed(ring)],colour)
    mesh.face([(x,y,z1) for x,y in ring],colour)
    for i in range(len(ring)):
        x,y=ring[i];u,v=ring[(i+1)%len(ring)]
        mesh.face([(x,y,z0),(u,v,z0),(u,v,z1),(x,y,z1)],colour)


def cage_web(mesh,r,plane,colour):
    """Two continuous rails connected by narrow ribs leave true open slots."""
    for edge in (r-.13,r+.13): torus(mesh,edge,.035,plane,colour)
    for i in range(24):
        a=math.tau*i/24; radial=(math.cos(a),math.sin(a)); tangent=(-radial[1],radial[0])
        def pt(rad,tan,depth):
            x=rad*radial[0]+tan*tangent[0];y=rad*radial[1]+tan*tangent[1]
            return (x,depth,y) if plane=='xz' else ((depth,x,y) if plane=='yz' else (x,y,depth))
        for depth in (-.065,.065):
            mesh.face([pt(r-.13,-.045,depth),pt(r+.13,-.045,depth),pt(r+.13,.045,depth),pt(r-.13,.045,depth)],colour)
        for tan in (-.045,.045):
            mesh.face([pt(r-.13,tan,-.065),pt(r+.13,tan,-.065),pt(r+.13,tan,.065),pt(r-.13,tan,.065)],colour)


def gear(mesh,r,z,colour,teeth=24):
    # Open wheel: a toothed rim and a small hub connected by narrow spokes.
    for radius,tube in ((r-.08,.045),(r*.22,.035)):
        first=len(mesh.vertices);torus(mesh,radius,tube,'xy',colour)
        for j in range(first,len(mesh.vertices)):
            x,y,h=mesh.vertices[j];mesh.vertices[j]=(x,y,h+z+.04)
    for i in range(8):
        a=math.tau*i/8;dx,dy=math.cos(a),math.sin(a);nx,ny=-dy*.035,dx*.035
        inner=r*.18;outer=r-.10
        for height in (z,z+.08):
            mesh.face([(inner*dx+nx,inner*dy+ny,height),(outer*dx+nx,outer*dy+ny,height),
                       (outer*dx-nx,outer*dy-ny,height),(inner*dx-nx,inner*dy-ny,height)],colour)
    for i in range(teeth):
        a=math.tau*i/teeth;x=r*math.cos(a);y=r*math.sin(a)
        mesh.box((x-.055,y-.055,z),(x+.055,y+.055,z+.08),colour)


def movement_gear(mesh,cx,cy,cz,r,colour,teeth):
    """Open toothed wheel on the movement's front plane, with hub and spokes."""
    for radius,tube in ((r,.028),(r*.56,.018)):
        first=len(mesh.vertices);torus(mesh,radius,tube,'xz',colour)
        for j in range(first,len(mesh.vertices)):
            x,y,z=mesh.vertices[j];mesh.vertices[j]=(x+cx,y+cy,z+cz)
    for i in range(teeth):
        a=math.tau*i/teeth
        mesh.beam((cx+(r-.015)*math.cos(a),cz+(r-.015)*math.sin(a)),
                  (cx+(r+.08)*math.cos(a),cz+(r+.08)*math.sin(a)),.045,cy-.025,cy+.025,colour)
    for i in range(8):
        a=math.tau*i/8
        mesh.beam((cx,cz),(cx+r*.90*math.cos(a),cz+r*.90*math.sin(a)),.035,cy-.025,cy+.025,colour)
    # Open metal rings around the inner plate provide visible perforations.
    for i in range(6):
        a=math.tau*i/6;first=len(mesh.vertices)
        torus(mesh,r*.065,.012,'xz',colour,n=12,m=4)
        for j in range(first,len(mesh.vertices)):
            x,y,z=mesh.vertices[j]
            mesh.vertices[j]=(x+cx+r*.31*math.cos(a),y+cy-.04,z+cz+r*.31*math.sin(a))
    mesh.sphere((cx,cy,cz),.13,'goldshade',segments=12,rings=6)
    mesh.sphere((cx,cy-.04,cz),.09,'ruby',segments=12,rings=6)


def inner_ring(mesh,r,angle_x,angle_y,colour):
    """An auxiliary open ring in the balance assembly at its own tilt."""
    first=len(mesh.vertices);torus(mesh,r,.026,'xy',colour)
    sx,cx=math.sin(angle_x),math.cos(angle_x)
    sy,cy=math.sin(angle_y),math.cos(angle_y)
    for i in range(first,len(mesh.vertices)):
        x,y,z=mesh.vertices[i]
        y,z=y*cx-z*sx,y*sx+z*cx
        mesh.vertices[i]=(x*cy+z*sy,y,-x*sy+z*cy)


actor('Level','levelobj');actor('Room','room',bounds=(-40,-40,-20,40,40,30))
director=actor('Director','director')
actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(0,-11,6),fields={'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=(0,0,3.3))
actor('cs_wide','camshot',pos=(0,-11,6),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':50.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':1.,'lightGreen':1.,'lightBlue':1.})
actor('Sun','light',fields={'lightType':'Directional','lightRed':1.,'lightGreen':.9,'lightBlue':.75})
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x21180f})
actor('TourbillonSettings','tourbillonsettings',fields={'Editor Label':'Triple-axis Tourbillon'})

base=Mesh('pedestal');beveled_base(base,3.9,3.0,0,.48,.35,'base')
beveled_base(base,3.86,2.96,.47,.54,.35,'gold')
beveled_base(base,3.78,2.88,.53,.63,.35,'base')
for x in (-2.8,2.8):
    base.beam((x,.57),(x*.98,4.15),.25,-.13,.13,'gold')
    base.sphere((x,0,4.15),.22,'goldlight',segments=12,rings=6)
for x in (-2,2):
    for y in (-1.8,1.8):base.sphere((x,y,.65),.10,'goldlight',segments=10,rings=5)
gear(base,1.25,.61,'gold',36)
gear(base,.86,.69,'steel',28)
gear(base,.51,.77,'goldlight',20)
actor('Pedestal','platform',base)
night_lamps=Mesh('night_lamps')
for x in (-2.8,2.8):
    night_lamps.sphere((x,-.22,4.15),.13,'night_glow',segments=12,rings=6)
actor('NightLamps','platform',night_lamps,fields={'Visibility Mailbox':780})

for name,r,plane,colour in (('OuterCage',3.0,'xz','gold'),('MiddleCage',2.25,'xy','steel'),('InnerCage',1.55,'xy','goldlight')):
    cage=Mesh(name);cage_web(cage,r,plane,colour)
    for i in range(8):
        a=math.tau*i/8
        pos=(r*math.cos(a),0,r*math.sin(a)) if plane=='xz' else (r*math.cos(a),r*math.sin(a),0)
        # A dark recessed bezel surrounds each coloured jewel.
        cage.sphere(pos,.15,'goldshade' if plane=='xz' else 'steelshade',segments=12,rings=6)
        jewel=(pos[0],pos[1]-.09,pos[2]) if plane=='xz' else (pos[0],pos[1],pos[2]+.09)
        cage.sphere(jewel,.105,'ruby' if i%2 else 'goldlight',segments=12,rings=6)
        if i%2==0:
            if plane=='xz':
                cage.beam((r*.78*math.cos(a),r*.78*math.sin(a)),(r*.98*math.cos(a),r*.98*math.sin(a)),.08,-.05,.05,colour)
            else:
                x,y=r*.84*math.cos(a),r*.84*math.sin(a)
                cage.box((x-.055,y-.055,-.06),(x+.055,y+.055,.06),colour)
    if plane=='xz':
        cage.beam((-r*.72,-r*.62),(-r*.48,-r*.38),.09,-.08,.08,colour)
        cage.beam((r*.72,-r*.62),(r*.48,-r*.38),.09,-.08,.08,colour)
    else:
        cage.box((-r*.92,-.045,-.035),(-r*.46,.045,.035),colour)
        cage.box((r*.46,-.045,-.035),(r*.92,.045,.035),colour)
    actor(name,'platform',cage,pos=(0,0,4.15))

balance=Mesh('balance');torus(balance,.95,.055,'xz','gold')
torus(balance,.68,.025,'xz','steel');torus(balance,.46,.025,'xz','goldlight')
inner_ring(balance,.84,.62,.52,'steel')
inner_ring(balance,.70,-.65,.90,'gold')
inner_ring(balance,.54,1.05,-.42,'steel')
movement_gear(balance,-.32,-.17,-.22,.40,'gold',20)
movement_gear(balance,.38,-.20,.16,.28,'steel',16)
movement_gear(balance,.02,-.22,.48,.18,'goldlight',12)
movement_gear(balance,.34,-.27,-.43,.23,'goldlight',18)
movement_gear(balance,-.54,-.31,.30,.20,'steel',16)
movement_gear(balance,.03,-.34,-.63,.15,'gold',14)
movement_gear(balance,.61,-.36,.46,.13,'gold',12)
for i in range(100):
    a=i*math.tau*3/100;b=(i+1)*math.tau*3/100
    r0=.10+.0035*i;r1=.10+.0035*(i+1)
    balance.beam((r0*math.cos(a),r0*math.sin(a)),(r1*math.cos(b),r1*math.sin(b)),.012,-.10,-.08,'steel')
for angle in (0,math.pi/3,2*math.pi/3):
    x,z=.88*math.cos(angle),.88*math.sin(angle)
    balance.beam((-x,-z),(x,z),.055,-.04,.04,'steel')
balance.sphere((0,0,0),.16,'ruby',segments=12,rings=6)
actor('Balance','platform',balance,pos=(0,0,4.15))
bead=Mesh('bead');bead.sphere((0,0,0),.20,'bead',segments=16,rings=8)
actor('SecondBead','platform',bead,pos=(3,0,4.15))

dial=Mesh('dial');dial.disc_y(0,0,1.08,0,'gold',sides=48);dial.disc_y(0,0,.96,-.02,'ivory',sides=48)
for i in range(12):
    a=math.tau*i/12;x,z=.78*math.sin(a),.78*math.cos(a)
    dial.beam((x,z),(.89*math.sin(a),.89*math.cos(a)),.045,-.06,-.04,'gold')
actor('Dial','platform',dial,pos=(0,-3.02,1.25))
for name,length,width,colour in (('HourHand',.51,.07,'dark'),('MinuteHand',.78,.045,'dark')):
    hand=Mesh(name);hand.beam((0,-.10),(0,length),width,-.01,.01,colour);hand.sphere((0,0,0),.075,'gold',segments=8,rings=4)
    actor(name,'platform',hand,pos=(0,-3.10,1.25))

bpy.context.view_layer.update();objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'tourbillonsettings.oad')],text=True))
fields={f['key']:f for f in catalog['fields']};drift=fields['Camera drift']['index']
lines=[r'\ Triple-axis tourbillon: cage periods are 60 120 and 180 seconds.',
       ': tb-time INDEXOF_WALL_MINUTE read-mailbox 6 mod 60 * INDEXOF_WALL_SECOND read-mailbox + ;',
       ': tb-hour INDEXOF_WALL_HOUR read-mailbox 12 / INDEXOF_WALL_MINUTE read-mailbox 720 / + INDEXOF_WALL_SECOND read-mailbox 43200 / + ;',
       ': tb-minute INDEXOF_WALL_MINUTE read-mailbox 60 / INDEXOF_WALL_SECOND read-mailbox 3600 / + ;']
def spline_word(component):
    def polynomial(segment):
        a,b,c,d=model.spline_coefficients(segment,component)
        local=f'{segment} - ' if segment else ''
        return f'{local}dup dup {a:.7f} * {b:.7f} + * {c:.7f} + * {d:.7f} +'
    branches=' '.join(f'dup {i+1} < if {polynomial(i)} else' for i in range(5))
    return f': tb-c{component} INDEXOF_WALL_SECOND read-mailbox 10 / {branches} {polynomial(5)} '+'then '*5+';'
lines.extend(spline_word(i) for i in range(6))
lines += [': tb-tick',
       ' INDEXOF_WALL_HOUR read-mailbox dup 6 < swap 18 >= | 780 write-mailbox',
       f' tb-time 60 / INDEXOF_ROTATION_C {idx["OuterCage"]} write-actor-mailbox',
       # Euler order composes Z (outer), then Y (middle), then X (inner).
       f' tb-time 60 / INDEXOF_ROTATION_C {idx["MiddleCage"]} write-actor-mailbox',
       f' tb-time 120 / INDEXOF_ROTATION_B {idx["MiddleCage"]} write-actor-mailbox',
       f' tb-time 60 / INDEXOF_ROTATION_C {idx["InnerCage"]} write-actor-mailbox',
       f' tb-time 120 / INDEXOF_ROTATION_B {idx["InnerCage"]} write-actor-mailbox',
       f' tb-time 180 / INDEXOF_ROTATION_A {idx["InnerCage"]} write-actor-mailbox',
       f' tb-time 60 / INDEXOF_ROTATION_C {idx["Balance"]} write-actor-mailbox',
       f' tb-time 120 / INDEXOF_ROTATION_B {idx["Balance"]} write-actor-mailbox',
       f' tb-time 180 / INDEXOF_WALL_SECOND read-mailbox 2 / sin-rev .07 * + INDEXOF_ROTATION_A {idx["Balance"]} write-actor-mailbox',
       f' tb-time 60 / cos-rev 3 * INDEXOF_X_POS {idx["SecondBead"]} write-actor-mailbox',
       f' tb-time 60 / sin-rev 3 * INDEXOF_Y_POS {idx["SecondBead"]} write-actor-mailbox',
       f' tb-hour negate INDEXOF_ROTATION_B {idx["HourHand"]} write-actor-mailbox',
       f' tb-minute negate INDEXOF_ROTATION_B {idx["MinuteHand"]} write-actor-mailbox']
for name in ('OuterCage','MiddleCage','InnerCage','Balance','SecondBead','HourHand','MinuteHand'):
    lines.append(f' 0 0 {idx[name]} fish-deform')
lines.append(f' {idx["TourbillonSettings"]} {drift} property@ if 0 <> else drop 0 then if')
axes=('INDEXOF_X_POS','INDEXOF_Y_POS','INDEXOF_Z_POS')
for i in range(6):
    target='cs_wide' if i<3 else 'LookAt'
    lines.append(f' {model.CAMERA_STILL[i]:.7f} {axes[i%3]} {idx[target]} write-actor-mailbox')
lines.append(' else')
for i in range(6):
    target='cs_wide' if i<3 else 'LookAt'
    lines.append(f' tb-c{i} {axes[i%3]} {idx[target]} write-actor-mailbox')
lines += [' then',';','tb-tick']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'triple_axis_tourbillon.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'triple_axis_tourbillon.lev'))

