"""Build the Lighthouse clock's editable scene and standalone level."""
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
import model

OAS = ROOT/'wfsource/source/oas'
SCALE = 2.0  # Keep the lantern's fine triangles above the fixed-point area limit.
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()

COLORS = {
    'sea': (.12,.28,.40), 'rock': (.32,.34,.36), 'rockdark': (.14,.16,.18),
    'foam': (.32,.53,.60), 'foamlight': (.50,.68,.71), 'white': (.86,.84,.75), 'red': (.60,.10,.075),
    'redshade': (.39,.055,.045), 'stone': (.42,.41,.38), 'dark': (.075,.08,.10),
    'metal': (.30,.31,.29), 'gold': (.87,.57,.18), 'light': (1.,.78,.32),
    'lamp': (1.,.93,.61), 'beam': (1.,.72,.22), 'beam_edge': (1.,.83,.40),
    'reflection': (.77,.49,.13),
    'hull': (.34,.14,.075), 'wood': (.52,.32,.15), 'sail': (.86,.80,.65),
    'glass': (.70,.64,.40), 'cloud': (.19,.25,.31), 'nightglow': (.45,.75,1.0),
}
materials = {}
for key,rgb in COLORS.items():
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    mat.diffuse_color = (*rgb, 1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*rgb, 1)
    mat['wf_prelit'] = key in ('sea','light','lamp','beam','beam_edge','reflection','foam','foamlight','glass','nightglow')
    mat['wf_double_sided'] = True
    if key == 'beam':
        mat['wf_opacity'] = .22
    if key == 'beam_edge':
        mat['wf_opacity'] = .35
    if key == 'reflection':
        mat['wf_opacity'] = .18
    materials[key] = mat


def texture(key, source, size, tint=None):
    mat = materials[key]
    mat.diffuse_color = (1,1,1,1)
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    image = bpy.data.images.load(str(HERE/source))
    _ = len(image.pixels)
    image.scale(*size)
    if tint:
        pixels = list(image.pixels)
        for i in range(0,len(pixels),4):
            v = .25*pixels[i]+.55*pixels[i+1]+.20*pixels[i+2]
            pixels[i], pixels[i+1], pixels[i+2] = (v*tint[0],v*tint[1],v*tint[2])
        image.pixels[:] = pixels
    image.filepath_raw = str(HERE/(key+'-texture.tga'))
    image.file_format = 'TARGA'
    image.save()
    node.image = image
    mat.node_tree.links.new(node.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])


def actor(name, cls, mesh=None, pos=(0,0,0), fields=None, bounds=None):
    data = None
    if mesh is not None:
        data = bpy.data.meshes.new(name)
        data.from_pydata(mesh.vertices, [], mesh.faces)
        keys = list(dict.fromkeys(mesh.colors))
        for key in keys: data.materials.append(materials[key])
        for poly,key in zip(data.polygons,mesh.colors): poly.material_index = keys.index(key)
        data.update()
        if 'sea' in keys or 'rock' in keys:
            uv = data.uv_layers.new(name='UVMap')
            for poly in data.polygons:
                key = data.materials[poly.material_index].name
                for loop in poly.loop_indices:
                    v = data.vertices[data.loops[loop].vertex_index].co
                    if key == 'sea': uv.data[loop].uv = ((v.x+8.2)/16.4, 1-(-v.z+8.2)/16.4)
                    elif key == 'rock': uv.data[loop].uv = getattr(mesh,'rock_uv',{}).get(data.loops[loop].vertex_index,((v.x+8)/16,1-(v.y+8)/16))
    obj = bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS/(cls+'.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj,wf_core.load_schema(str(schema)))
    values = {'Mobility':'Anchored','Mass':0.,'Model Type':'Mesh' if data else 'None',
              'Visibility Mailbox':1 if data else 0,'Script':'','Script Controls Input':'False',
              'Moves Between Rooms':'False','Number Of Local Mailboxes':0}
    values.update(fields or {})
    for key,value in values.items(): obj['wf_'+key] = value
    if data:
        obj['wf_Mesh Name'] = name+'.iff'
        obj['wf_original_mesh_name'] = name+'.iff'
    if bounds or not data:
        obj['wf_original_bbox'] = tuple(bounds or (-.05,-.05,-.05,.05,.05,.05))
        obj['wf_had_authored_bbox'] = True
    return obj


def frustum(mesh,z0,z1,r0,r1,color,sides=32):
    for i in range(sides):
        a,b = math.tau*i/sides,math.tau*(i+1)/sides
        mesh.face([(r*math.cos(t),r*math.sin(t),z) for r,t,z in ((r0,a,z0),(r0,b,z0),(r1,b,z1),(r1,a,z1))],color)
    mesh.face([(r1*math.cos(math.tau*i/sides),r1*math.sin(math.tau*i/sides),z1) for i in range(sides)],color)


def annulus(mesh,cx,cy,r0,r1,z,color,sides=40):
    for i in range(sides):
        a,b = math.tau*i/sides,math.tau*(i+1)/sides
        mesh.face([(cx+r*math.cos(t),cy+r*math.sin(t),z) for r,t in ((r0,a),(r1,a),(r1,b),(r0,b))],color)


def foam(mesh,cx,cy,radius,seed,z=-.03):
    """Broken, uneven surf instead of a perfect bright circle."""
    n = 48
    for i in range(n):
        if math.sin(i*2.7+seed*1.3) < -.55:
            continue
        a,b = math.tau*i/n, math.tau*(i+1)/n
        r0 = radius+.025*math.sin(i*1.3+seed)
        r1 = radius+.025*math.sin((i+1)*1.3+seed)
        width = .018+.025*(.5+.5*math.sin(i*2.1+seed))
        mesh.face([(cx+r*math.cos(t),cy+r*math.sin(t),z)
                   for r,t in ((r0,a),(r0+width,a),(r1+width,b),(r1,b))],'foam')


def rock(mesh,cx,cy,cz,sx,sy,sz,seed):
    """Layered, fractured rock with per-rock UVs spanning the full texture."""
    if not hasattr(mesh,'rock_uv'): mesh.rock_uv = {}
    sides = 24
    radii = (.65,.94,1.,.91,.75,.56,.32)
    def point(level,i):
        a = math.tau*i/sides
        ridge = (1 + .19*math.sin(a*5+seed*1.7) + .11*math.sin(a*9-seed*.7+level*1.3)
                 + .07*math.sin(a*13+level*3.1+seed))
        r = radii[level]*ridge
        height = -0.65 + level*(1.65/(len(radii)-1))
        height += .09*math.sin(a*4+seed*.6+level) + .055*math.sin(a*9+seed)
        return (cx+sx*r*math.cos(a),cy+sy*r*math.sin(a),cz+sz*height)
    for level in range(len(radii)-1):
        for i in range(sides):
            start = len(mesh.vertices)
            mesh.face([point(level,i),point(level,i+1),point(level+1,i+1),point(level+1,i)],'rock')
            u0,u1 = i/sides,(i+1)/sides
            v0,v1 = 1-level/(len(radii)-1),1-(level+1)/(len(radii)-1)
            for j,uv in enumerate(((u0,v0),(u1,v0),(u1,v1),(u0,v1))): mesh.rock_uv[start+j] = uv
    for i in range(sides):
        start = len(mesh.vertices)
        mesh.face([point(len(radii)-1,i),point(len(radii)-1,i+1),(cx,cy,cz+sz)],'rock')
        for j,uv in enumerate(((i/sides,0),((i+1)/sides,0),((i+.5)/sides,.05))): mesh.rock_uv[start+j] = uv


texture('sea','water-source.png',(128,128),(.19,.38,.62))
texture('rock','stone-source.png',(512,512),(.52,.55,.58))
actor('Level','levelobj')
actor('Room','room',bounds=(-60,-60,-30,60,60,50))
director = actor('Director','director')
actor('Player','player',pos=(0,20,0))
actor('Camera','camera',pos=model.CAMERA_STILL[:3],fields={'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=model.CAMERA_STILL[3:])
actor('cs_wide','camshot',pos=model.CAMERA_STILL[:3],fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':50.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':.50,'lightGreen':.52,'lightBlue':.62})
sun = actor('Moonlight','light',fields={'lightType':'Directional','lightRed':.75,'lightGreen':.80,'lightBlue':1.})
sun.rotation_euler = (0,math.radians(45),math.radians(90))
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x080f1c})
actor('LighthouseSettings','lighthousesettings',fields={'Editor Label':'Lighthouse'})

# The local XZ disc is rotated flat. The existing fish deformer displaces its
# local Y, which becomes world Z, making a gentle travelling surface wave.
water = Mesh('water')
for ring in range(16):
    r0,r1 = 8.2*ring/16,8.2*(ring+1)/16
    for i in range(64):
        a,b = math.tau*i/64,math.tau*(i+1)/64
        def vertex(r,t): return (r*math.cos(t),-.06,-r*math.sin(t))
        if ring == 0:
            water.face([vertex(0,a),vertex(r1,a),vertex(r1,b)],'sea')
        else:
            water.face([vertex(r0,a),vertex(r1,a),vertex(r1,b),vertex(r0,b)],'sea')
sea = actor('Sea','platform',water)
sea.rotation_euler = (math.pi/2,0,0)
night_glow = Mesh('night_sea_glow')
annulus(night_glow,0,0,8.05,8.16,.025,'nightglow',sides=72)
actor('NightSeaGlow','platform',night_glow,fields={'Visibility Mailbox':780})

island = Mesh('island')
rock(island,0,0,.14,1.8,1.55,.58,1)
for i in range(16):
    a = math.tau*i/16
    r = 1.25+.18*math.sin(i*2.8)
    rock(island,r*math.sin(a),r*math.cos(a),.18,.51,.38,.42,i+2)
    rock(island,(r+.28)*math.sin(a+.06),(r+.28)*math.cos(a+.06),.12,.25,.23,.23,i+81)
foam(island,0,0,1.90,12)
actor('Island','platform',island)

# Twelve distinct dial rocks and narrow foam rings at the waterline.
marks = Mesh('marks')
for i in range(12):
    x,y = model.point(model.RING_RADIUS,i/12)
    rock(marks,x,y,.10,.48,.41,.54,20+i)
    for j in range(4):
        angle = math.tau*j/4 + i*.37
        dx,dy = .32*math.cos(angle),.32*math.sin(angle)
        rock(marks,x+dx,y+dy,.07,.23,.20,.27,52+i*4+j)
    foam(marks,x,y,.61,i)
actor('TwelveRocks','platform',marks)

# Subtle broken surf oscillates locally around the stationary piles. The
# original fixed foam remains visible when Water motion is switched off.
for i in range(12):
    x,y = model.point(model.RING_RADIUS,i/12)
    surf = Mesh('surf')
    foam(surf,0,0,.66,i+37,z=.08)
    actor('Surf'+str(i),'platform',surf,pos=(x,y,0),fields={'Visibility Mailbox':871})
isurf = Mesh('island surf')
foam(isurf,0,0,1.95,77,z=.08)
actor('IslandSurf','platform',isurf,fields={'Visibility Mailbox':871})

# Sparse short broken crests drift over open water, away from the hour rocks.
glint_positions = []
for i in range(16):
    a = i*2.39996323
    r = 2.6+(i%4)*.72
    x,y = r*math.cos(a),r*math.sin(a)
    glint_positions.append((x,y))
    glint = Mesh('glint')
    for j in range(3):
        x0 = -.47+j*.33
        x1 = x0+.25+.04*math.sin(i+j)
        y0 = .10*math.sin(i*1.7+j*2.1)
        glint.face([(x0,y0,.10),(x1,y0+.035,.10),(x1,y0+.100,.10),(x0,y0+.065,.10)],'foam')
    actor('Glint'+str(i),'platform',glint,pos=(x,y,0),fields={'Visibility Mailbox':871})

tower = Mesh('tower')
frustum(tower,.55,.80,1.12,1.08,'stone')
for i in range(5):
    z0,z1 = .80+i*1.02,.80+(i+1)*1.02
    r0,r1 = 1.04-.07*i,1.04-.07*(i+1)
    frustum(tower,z0,z1,r0,r1,'white' if i%2==0 else 'red')
frustum(tower,5.90,6.08,.77,.83,'stone')
frustum(tower,6.08,6.18,1.12,1.12,'metal')
frustum(tower,6.18,6.23,1.15,1.15,'gold')
for i in range(16):
    a = math.tau*i/16
    x,y = 1.04*math.cos(a),1.04*math.sin(a)
    tower.column_z(x,y,6.23,6.75,.025,'metal',sides=8)
annulus(tower,0,0,1.01,1.05,6.72,'gold',sides=32)
frustum(tower,6.22,7.22,.67,.67,'glass',sides=16)
for i in range(8):
    a = math.tau*i/8
    tower.column_z(.69*math.cos(a),.69*math.sin(a),6.22,7.22,.045,'metal',sides=8)
frustum(tower,7.22,7.35,.78,.78,'metal')
frustum(tower,7.35,7.88,.78,.12,'dark')
tower.sphere((0,0,7.95),.12,'gold',segments=12,rings=6)
tower.column_z(0,0,8.02,8.35,.025,'metal',sides=8)
actor('Tower','platform',tower)

lamp = Mesh('lamp')
lamp.sphere((0,0,6.71),.32,'lamp',segments=16,rings=8)
actor('Lamp','platform',lamp)

# Individual front-facing windows: dark setting always present, lit inset toggled.
window_frames = Mesh('frames')
for i in range(11):
    z = 1.05+i*.415
    r = 1.04-(z-.80)*.07/1.02
    window_frames.cylinder_y(0,z,.115,-r-.045,-r-.015,'dark',sides=12)
    glass = Mesh('window')
    glass.cylinder_y(0,0,.085,-.008,.008,'light',sides=12)
    actor('Window'+str(i),'platform',glass,pos=(0,-r-.06,z),fields={'Visibility Mailbox':800+i})
actor('WindowFrames','platform',window_frames)

# Beam points north at :00. A translucent volume and water highlight rotate as one.
beam = Mesh('beam')
beam.face([(-.10,0,6.72),(.10,0,6.72),(.72,7.1,.18),(-.72,7.1,.18)],'beam')
beam.face([(-.035,0,6.70),(.035,0,6.70),(.20,7.1,.185),(-.20,7.1,.185)],'beam_edge')
# Broken glints on the sea keep the beam direction readable even edge-on.
for i in range(28):
    y0 = 1.6+i*.19
    y1 = y0+.10+.05*(.5+.5*math.sin(i*2.1))
    offset = .16*math.sin(i*2.3)
    w0 = .025+.02*(.5+.5*math.sin(i*1.7))
    w1 = w0*.8
    beam.face([(offset-w0,y0,.13),(offset+w0,y0,.13),
               (offset+w1,y1,.13),(offset-w1,y1,.13)],'reflection')
actor('Beam','platform',beam)

boat = Mesh('boat')
boat.face([(-.65,-.22,.20),(.63,-.22,.20),(.47,-.15,.03),(-.48,-.15,.03)],'hull')
boat.face([(-.65,.22,.20),(-.48,.15,.03),(.47,.15,.03),(.63,.22,.20)],'hull')
boat.face([(-.65,-.22,.20),(-.65,.22,.20),(.63,.22,.20),(.63,-.22,.20)],'wood')
boat.column_z(0,0,.20,1.50,.025,'dark',sides=8)
boat.face([(.02,0,1.42),(.02,0,.29),(.63,0,.35)],'sail')
boat.face([(-.04,.01,1.31),(-.04,.01,.34),(-.48,.01,.35)],'sail')
actor('Boat','platform',boat,pos=(0,model.BOAT_RADIUS,0))

# Local +X is the boat's heading. These broken strokes form a small aft V.
wake = Mesh('wake')
for side in (-1,1):
    for j in range(4):
        x0 = -.30-j*.34
        x1 = x0-.23
        y0,y1 = side*(-x0)*.23,side*(-x1)*.23
        wake.face([(x0,y0-.025,.10),(x1,y1-.025,.10),
                   (x1,y1+.025,.10),(x0,y0+.025,.10)],'foamlight')
actor('Wake','platform',wake,pos=(0,model.BOAT_RADIUS,0),fields={'Visibility Mailbox':871})

bpy.context.view_layer.update()
objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx = {o.name:i+1 for i,o in enumerate(objects)}
catalog = json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'lighthousesettings.oad')],text=True))
fields = {f['key']:f for f in catalog['fields']}
drift,water_motion = fields['Camera drift']['index'],fields['Water motion']['index']

def spline_word(component):
    def polynomial(segment):
        a,b,c,d = model.spline_coefficients(segment,component)
        local = f'{segment} - ' if segment else ''
        return f'{local}dup dup {a:.7f} * {b:.7f} + * {c:.7f} + * {d:.7f} +'
    branches = ' '.join(f'dup {i+1} < if {polynomial(i)} else' for i in range(5))
    return f': lh-c{component} INDEXOF_WALL_SECOND read-mailbox 10 / {branches} {polynomial(5)} '+'then '*5+';'

lines = [r'\ Lighthouse: seconds beam, minutes boat, counted local hours.',
         ': lh-boat INDEXOF_WALL_MINUTE read-mailbox 60 / INDEXOF_WALL_SECOND read-mailbox 3600 / + ;',
         ': lh-beam INDEXOF_WALL_SECOND read-mailbox 60 / ;',
         ': lh-wave-step 870 read-mailbox if 700 read-mailbox INDEXOF_DELTA_TIME read-mailbox 0 max .1 min 12 / + dup 1 >= if 1 - then 700 write-mailbox then ;']
lines.extend(spline_word(i) for i in range(6))
lines.append(': lh-tick')
lines.append(' INDEXOF_WALL_HOUR read-mailbox dup 6 < swap 18 >= | 780 write-mailbox')
for i in range(11): lines.append(f' INDEXOF_WALL_HOUR read-mailbox 12 mod {i} > {800+i} write-mailbox')
lines += [f' {idx["LighthouseSettings"]} {water_motion} property@ if 0 <> else drop 1 then 870 write-mailbox',
          ' 870 read-mailbox 871 write-mailbox',
          ' lh-wave-step',
          f' lh-beam negate INDEXOF_ROTATION_C {idx["Beam"]} write-actor-mailbox',
          f' lh-boat sin-rev {model.BOAT_RADIUS*SCALE:g} * INDEXOF_X_POS {idx["Boat"]} write-actor-mailbox',
          f' lh-boat cos-rev {model.BOAT_RADIUS*SCALE:g} * INDEXOF_Y_POS {idx["Boat"]} write-actor-mailbox',
          f' lh-boat negate INDEXOF_ROTATION_C {idx["Boat"]} write-actor-mailbox',
          f' 870 read-mailbox if 700 read-mailbox sin-rev .045 * {SCALE:g} * else 0 then INDEXOF_Z_POS {idx["Boat"]} write-actor-mailbox',
          f' 870 read-mailbox if 700 read-mailbox sin-rev .003 * else 0 then INDEXOF_ROTATION_A {idx["Boat"]} write-actor-mailbox',
          f' 870 read-mailbox if 700 read-mailbox .17 + sin-rev .002 * else 0 then INDEXOF_ROTATION_B {idx["Boat"]} write-actor-mailbox',
          f' lh-boat sin-rev {model.BOAT_RADIUS*SCALE:g} * INDEXOF_X_POS {idx["Wake"]} write-actor-mailbox',
          f' lh-boat cos-rev {model.BOAT_RADIUS*SCALE:g} * INDEXOF_Y_POS {idx["Wake"]} write-actor-mailbox',
          f' lh-boat negate INDEXOF_ROTATION_C {idx["Wake"]} write-actor-mailbox',
          f' 700 read-mailbox 870 read-mailbox if .008 else 0 then {idx["Sea"]} fish-deform']
for i in range(12):
    lines.append(f' 700 read-mailbox {i*.137:.5f} + sin-rev .015 * INDEXOF_ROTATION_C {idx["Surf"+str(i)]} write-actor-mailbox')
lines.append(f' 700 read-mailbox sin-rev .008 * INDEXOF_ROTATION_C {idx["IslandSurf"]} write-actor-mailbox')
for i,(x,y) in enumerate(glint_positions):
    name='Glint'+str(i)
    lines += [f' {x*SCALE:.5f} 700 read-mailbox {i*.113:.5f} + sin-rev {.12*SCALE:g} * + INDEXOF_X_POS {idx[name]} write-actor-mailbox',
              f' {y*SCALE:.5f} 700 read-mailbox {i*.113:.5f} + cos-rev {.08*SCALE:g} * + INDEXOF_Y_POS {idx[name]} write-actor-mailbox']
for name in ('Beam','Boat','Wake','IslandSurf') + tuple('Surf'+str(i) for i in range(12)) + tuple('Glint'+str(i) for i in range(len(glint_positions))):
    lines.append(f' 0 0 {idx[name]} fish-deform')
lines.append(f' {idx["LighthouseSettings"]} {drift} property@ if 0 <> else drop 0 then if')
axes = ('INDEXOF_X_POS','INDEXOF_Y_POS','INDEXOF_Z_POS')
for j in range(6):
    name = 'cs_wide' if j<3 else 'LookAt'
    lines.append(f' {model.CAMERA_STILL[j]*SCALE:.7f} {axes[j%3]} {idx[name]} write-actor-mailbox')
lines.append(' else')
for j in range(6):
    name = 'cs_wide' if j<3 else 'LookAt'
    lines.append(f' lh-c{j} {SCALE:g} * {axes[j%3]} {idx[name]} write-actor-mailbox')
lines += [' then',';','lh-tick']
director['wf_Script'] = '\n'.join(lines)
for obj in objects:
    obj.location *= SCALE
    if obj.type == 'MESH':
        for vertex in obj.data.vertices: vertex.co *= SCALE
    if obj.get('wf_had_authored_bbox'):
        obj['wf_original_bbox'] = tuple(v*SCALE for v in obj['wf_original_bbox'])
    if obj.name == 'cs_wide':
        obj['wf_Hither'] = 2.
        obj['wf_Yon'] = 400.
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'lighthouse.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'lighthouse.lev'))
