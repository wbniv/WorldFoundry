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


def annulus(mesh, radius, width, height, colour, segments=96):
    for i in range(segments):
        a,b = math.tau*i/segments, math.tau*(i+1)/segments
        mesh.face([(r*math.cos(t),r*math.sin(t),height)
                   for r,t in ((radius-width/2,a),(radius+width/2,a),
                               (radius+width/2,b),(radius-width/2,b))], colour)


def sleeper(mesh, radius, theta):
    c,s = math.cos(theta), math.sin(theta)
    mesh.face([(r*c-t*s,r*s+t*c,.087) for r,t in
               ((radius-.32,-.055),(radius+.32,-.055),(radius+.32,.055),(radius-.32,.055))], 'sleeper')


def tree(mesh, x, y, size):
    mesh.column_z(x,y,.03,.28*size,.075*size,'trunk',sides=6)
    for base,rad,colour in ((.19,.36,'tree'),(.46,.27,'tree_light'),(.70,.18,'tree')):
        z=.03+base*size
        pts=[(x+rad*size*math.cos(math.tau*i/7),y+rad*size*math.sin(math.tau*i/7),z) for i in range(7)]
        tip=(x,y,z+.50*size)
        for i in range(7):
            mesh.face([pts[i],pts[(i+1)%7],tip],colour)


def station(mesh, lights, x, y):
    mesh.box((x-.33,y-.27,.04),(x+.33,y+.27,.46),'station')
    # Dark panes remain visible by day; illuminated panes overlay them at night.
    mesh.box((x-.25,y-.282,.19),(x-.07,y-.274,.37),'black')
    mesh.box((x+.07,y-.282,.19),(x+.25,y-.274,.37),'black')
    lights.box((x-.25,y-.286,.19),(x-.07,y-.283,.37),'window')
    lights.box((x+.07,y-.286,.19),(x+.25,y-.283,.37),'window')
    mesh.box((x-.39,y-.33,.46),(x+.39,y+.33,.50),'station_roof')
    corners=[(x-.39,y-.33,.5),(x+.39,y-.33,.5),(x+.39,y+.33,.5),(x-.39,y+.33,.5)]
    top=(x,y,.80)
    for i in range(4):
        mesh.face([corners[i],corners[(i+1)%4],top],'station_roof')
    mesh.column_z(x+.48,y-.30,.04,.63,.025,'rim_gold',sides=6)
    lights.sphere((x+.48,y-.30,.65),.07,'window',segments=8,rings=4)


def train_mesh(name, kind):
    m=Mesh(name)
    if kind in ('hour_engine','minute_engine'):
        main,trim = ('red','red_trim') if kind=='hour_engine' else ('teal','rim_gold')
        m.box((-.23,-.50,.16),(.23,.48,.30),'black')
        m.box((-.20,-.38,.30),(.20,.32,.56),main)
        m.box((-.19,-.42,.52),(.19,-.09,.84),main)
        m.box((-.24,-.47,.83),(.24,-.04,.90),'roof')
        m.box((-.205,-.39,.63),(-.201,-.17,.76),'window')
        m.box((.201,-.39,.63),(.205,-.17,.76),'window')
        m.column_z(0,.20,.53,.79,.08,'black',sides=8)
        m.column_z(0,.20,.76,.82,.11,trim,sides=8)
        m.box((-.23,.37,.30),(.23,.45,.36),trim)
        m.sphere((0,.49,.43),.09,'window',segments=8,rings=4)
    elif kind=='car':
        m.box((-.21,-.45,.16),(.21,.45,.28),'black')
        m.box((-.20,-.40,.28),(.20,.40,.66),'cream')
        m.box((-.23,-.43,.66),(.23,.43,.74),'roof')
        for y in (-.27,-.09,.09,.27):
            m.box((-.205,y-.055,.42),(-.201,y+.055,.58),'window')
            m.box((.201,y-.055,.42),(.205,y+.055,.58),'window')
    else:
        m.box((-.22,-.61,.16),(.22,.38,.28),'black')
        m.box((-.21,-.58,.28),(.21,.38,.55),'express')
        m.box((-.19,-.50,.54),(.19,.28,.65),'express_trim')
        m.face([(-.21,.38,.28),(.21,.38,.28),(0,.74,.28)],'express')
        m.face([(-.21,.38,.55),(0,.74,.28),(.21,.38,.55)],'express')
        m.face([(-.21,.38,.28),(0,.74,.28),(-.21,.38,.55)],'express_trim')
        m.face([(.21,.38,.28),(.21,.38,.55),(0,.74,.28)],'express_trim')
        for y in (-.42,-.20,.02,.24):
            m.box((-.215,y-.06,.40),(-.211,y+.06,.52),'window')
            m.box((.211,y-.06,.40),(.215,y+.06,.52),'window')
    for x in (-.22,.22):
        for y in (-.30,.25):
            m.sphere((x,y,.16),.12,'black',segments=8,rings=4)
    return m


actor('Level','levelobj')
actor('Room','room',bounds=(-40,-40,-20,40,40,30))
director=actor('Director','director')
actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(0,-10.6,14.2),fields={'Mobility':'Camera','Moves Between Rooms':'True',
      'FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=(0,0,0))
actor('cs_wide','camshot',pos=(0,-10.6,14.2),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt',
      'Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute',
      'Hither':1.,'Yon':200.,'FOV':50.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':1.,'lightGreen':1.,'lightBlue':1.})
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x101828})
actor('TrainLoopsSettings','trainloopssettings',fields={'Editor Label':'Train Loops'})

table=Mesh('table')
table.column_z(0,0,-.44,-.12,8.3,'rim',sides=72)
table.column_z(0,0,-.13,-.07,8.32,'rim_gold',sides=72)
table.column_z(0,0,-.08,.02,8.15,'grass',sides=72)
actor('Table','platform',table)

tracks=Mesh('tracks')
for radius in model.RADII.values():
    annulus(tracks,radius,.70,.04,'ballast')
    for i in range(72):
        sleeper(tracks,radius,math.tau*i/72)
    for delta in (-.23,.23):
        annulus(tracks,radius+delta,.055,.105,'rail')
actor('Tracks','platform',tracks)

scenery=Mesh('scenery')
lights=Mesh('station-lights')
for i in range(12):
    angle=math.tau*i/12
    station(scenery,lights,7.14*math.sin(angle),7.14*math.cos(angle))
random.seed(29)
for i in range(34):
    radius=random.choice((1.5,2.0,3.70,5.15,6.57))
    angle=math.tau*(i+.33)/34
    # Keep the approach to each outer station clear.
    if radius==6.57 and abs((angle/(math.tau/12)+.5)%1-.5)<.18:
        continue
    tree(scenery,radius*math.sin(angle),radius*math.cos(angle),random.uniform(.55,.95))
actor('StationsAndTrees','platform',scenery)
actor('StationLights','platform',lights,fields={'Visibility Mailbox':701})

# Switch all twelve station labels together at noon and midnight.
digits = ((-.4,.85,.4,1),(.33,.05,.48,.9),(.33,-.9,.48,-.05),(-.4,-1,.4,-.85),
          (-.48,-.9,-.33,-.05),(-.48,.05,-.33,.9),(-.4,-.08,.4,.08))
masks=(63,6,91,79,102,109,125,7,127,111)
plaques=Mesh('station-plaques')
morning=Mesh('station-am')
afternoon=Mesh('station-pm')
for i in range(12):
    angle=math.tau*i/12
    x,y=6.67*math.sin(angle),6.67*math.cos(angle)
    plaques.box((x-.36,y-.05,.08),(x+.36,y+.05,.88),'roof')
    for markers,text in ((morning,f'{i:02d}'), (afternoon,f'{i+12:02d}')):
        for j,ch in enumerate(text):
            shift=(j-(len(text)-1)/2)*.25
            for k,(x0,z0,x1,z1) in enumerate(digits):
                if masks[int(ch)] & (1<<k):
                    markers.quad_y(x+shift+x0*.23,.48+z0*.23,x+shift+x1*.23,.48+z1*.23,y-.055,'white')
actor('StationPlaques','platform',plaques)
actor('StationAM','platform',morning,fields={'Visibility Mailbox':700})
actor('StationPM','platform',afternoon,fields={'Visibility Mailbox':701})

vehicles=[('HourEngine','hour_engine','hour',0.0),('HourCar','car','hour',.34),
          ('MinuteEngine','minute_engine','minute',0.0),('MinuteCar1','car','minute',.225),
          ('MinuteCar2','car','minute',.45),('MinuteCar3','car','minute',.675),
          ('Express','express','express',0.0)]
for name, kind, loop, offset in vehicles:
    actor(name,'platform',train_mesh(name,kind),pos=(0,model.RADII[loop],0))

bpy.context.view_layer.update()
objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'trainloopssettings.oad')],text=True))
fields={f['key']:f for f in catalog['fields']}
drift=fields['Camera drift']['index']
lines=[r'\ Train Loops: phases read the same latched local time every frame.',
       ': tl-hour INDEXOF_WALL_HOUR read-mailbox 12 / INDEXOF_WALL_MINUTE read-mailbox 720 / + INDEXOF_WALL_SECOND read-mailbox 43200 / + ;',
       ': tl-minute INDEXOF_WALL_MINUTE read-mailbox 60 / INDEXOF_WALL_SECOND read-mailbox 3600 / + ;',
       ': tl-express INDEXOF_WALL_SECOND read-mailbox 60 / ;']

def spline_word(component):
    """Compile the same closed Catmull-Rom cubic used by the PC model."""
    def polynomial(segment):
        a,b,c,d = model.spline_coefficients(segment,component)
        local = f'{segment} - ' if segment else ''
        return f'{local}dup dup {a:.7f} * {b:.7f} + * {c:.7f} + * {d:.7f} +'
    branches = ' '.join(f'dup {i+1} < if {polynomial(i)} else' for i in range(5))
    return f': tl-c{component} INDEXOF_WALL_SECOND read-mailbox 10 / {branches} {polynomial(5)} ' + 'then '*5 + ';'

lines.extend(spline_word(component) for component in range(6))
lines.append(': tl-tick')
lines.append('  INDEXOF_WALL_HOUR read-mailbox 12 < dup 700 write-mailbox 0 = 701 write-mailbox')
for name in ('StationAM', 'StationPM', 'StationLights'):
    lines.append(f'  0 0 {idx[name]} fish-deform')
for name,kind,loop,offset in vehicles:
    phase=f'tl-{loop} {offset/math.tau:.10f} -'
    lines += [f'  {phase} sin-rev {model.RADII[loop]} * INDEXOF_X_POS {idx[name]} write-actor-mailbox',
              f'  {phase} cos-rev {model.RADII[loop]} * INDEXOF_Y_POS {idx[name]} write-actor-mailbox',
              f'  {phase} negate .25 - INDEXOF_ROTATION_C {idx[name]} write-actor-mailbox']
# Keep moving train meshes on the dynamic path so visibility and transforms
# remain correct when the renderer batches otherwise static geometry.
for name, _, _, _ in vehicles:
    lines.append(f'  0 0 {idx[name]} fish-deform')
lines.append(f'  {idx["TrainLoopsSettings"]} {drift} property@ if 0 <> else drop 0 then')
lines.append('  if')
axes = ('INDEXOF_X_POS', 'INDEXOF_Y_POS', 'INDEXOF_Z_POS')
for component in range(6):
    target = 'cs_wide' if component < 3 else 'LookAt'
    lines.append(f'    {model.CAMERA_STILL[component]:.7f} {axes[component%3]} {idx[target]} write-actor-mailbox')
lines.append('  else')
for component in range(6):
    target = 'cs_wide' if component < 3 else 'LookAt'
    lines.append(f'    tl-c{component} {axes[component%3]} {idx[target]} write-actor-mailbox')
lines += ['  then', ';\ntl-tick\n']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx,'camera_drift_field':drift,
    'vehicles':[{'name':name,'kind':kind,'loop':loop,'offset_radians':offset} for name,kind,loop,offset in vehicles]},indent=2)+'\n')
bpy.ops.wf.export_level(filepath=str(HERE/'train_loops.lev'))
