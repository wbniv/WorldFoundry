"""Build one independent Aquarium tank through the established Blender exporter."""
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import addon_utils
import bpy

COMMON=Path(__file__).resolve().parent
REPO=COMMON.parent.parent
sys.path.insert(0,str(COMMON))
from mesh import Mesh
import species
from models import COLORS as ANIMAL_COLORS, JELLY_OPACITY, models
from urchin import COLORS as URCHIN_COLORS, urchin, tube_foot
from planting import COLORS as PLANT_COLORS, planting
from temple import COLORS as TEMPLE_COLORS, pavilion
LEVEL=sys.argv[sys.argv.index('--')+1]
assert LEVEL in ('aquarium_betta','aquarium_jellyfish','aquarium_lionfish','aquarium_plants','aquarium_arowana')
HERE=REPO/'wflevels'/LEVEL
spec=importlib.util.spec_from_file_location('tank_config',HERE/'config.py')
C=importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
PROFILE=os.environ.get('TANK_PROFILE','keyboard')
assert PROFILE in ('keyboard','touch','remote')
COUNT=int(os.environ.get('TANK_COUNT',str(C.COUNT)))
assert (COUNT==C.COUNT if C.KIND=='plants' else 1<=COUNT<=C.COUNT)
ROWS=C.RESIDENTS[:COUNT-1]
FEEDING=C.KIND=='lionfish' and os.environ.get('LIONFISH_FEEDING','1')!='0'
LION_RIG=C.KIND=='lionfish' and os.environ.get('LIONFISH_REALISM','1')!='0'
BETTA_FINS=C.KIND=='betta' and os.environ.get('BETTA_FINS','1')!='0'
if BETTA_FINS:
    sys.path.insert(0,str(HERE))
    from detailed_model import COLORS as BETTA_COLORS, detailed_models
HX,HY,HEIGHT,WALL,SAND,WATER=6.096,1.651,5.334,.127,.635,4.826
LIMIT_X,LIMIT_Y=4.70,(.88 if C.KIND=='plants' else .34 if C.KIND=='jellyfish' else .27)
OAD=REPO/'wftools/wf_oad/tests/fixtures'
COLORS=dict(ANIMAL_COLORS,sand=(.75,.70,.55),frame=(.30,.55,.63),rim=(.53,.74,.79),
            rock=(.25,.29,.29),rock_hi=(.38,.43,.40),leaf=(.18,.39,.24),
            leaf_hi=(.38,.59,.29),stem=(.15,.30,.16),stand=(.06,.09,.11),backdrop=(.018,.04,.065))
COLORS.update(TEMPLE_COLORS)
COLORS.update(PLANT_COLORS)
COLORS.update(URCHIN_COLORS)
if BETTA_FINS:COLORS.update(BETTA_COLORS)
if C.KIND=='arowana':
    import arowana
    COLORS.update(arowana.COLORS)
    HX=C.DIMENSIONS_M[0]*C.WORLD_SCALE/2
    HY=C.DIMENSIONS_M[1]*C.WORLD_SCALE/2
    HEIGHT=WATER=C.DIMENSIONS_M[2]*C.WORLD_SCALE
    WALL=.127
    SAND=.20
    LIMIT_X,LIMIT_Y=HX-3.61,HY-1.35
MATERIALS={}
def material(key):
    if key not in MATERIALS:
        mt = bpy.data.materials.new('tank-'+key)
        mt.use_nodes = True
        rgb = (*COLORS[key], 1)
        mt.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = rgb
        mt.diffuse_color = rgb
        if C.KIND == 'jellyfish' and key in JELLY_OPACITY:
            opacity = JELLY_OPACITY[key]
            mt['wf_opacity'] = opacity
            mt.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value = opacity
            mt.surface_render_method = 'DITHERED'
        if C.KIND=='plants' and key.startswith('plant_'):
            mt['wf_prelit']=True
            if os.environ.get('PLANTED_TANK_DETAIL','runtime')=='runtime':
                tex=mt.node_tree.nodes.new('ShaderNodeTexImage')
                tex.image=bpy.data.images.load(str(HERE/'leaf_surfaces.tga'),check_existing=True)
                mt.node_tree.links.new(tex.outputs['Color'],mt.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        if LION_RIG and key in ('body','fin'):
            mt['wf_texture_palette']=True
            mt['wf_palette_texture']='lionfish_'+('body' if key=='body' else 'fins')+'.tga'
            tex=mt.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image=bpy.data.images.load(str(HERE/mt['wf_palette_texture']),check_existing=True)
            mt.node_tree.links.new(tex.outputs['Color'],mt.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
            if key=='fin':mt['wf_opacity']=.55;mt['wf_double_sided']=True
        if key.startswith(('betta_mem' ,'betta_ray','betta_margin')):mt['wf_prelit']=True
        MATERIALS[key] = mt
    return MATERIALS[key]


def blender_mesh(mesh):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata(mesh.vertices, [], mesh.faces)
    keys = list(dict.fromkeys(mesh.colors))
    for key in keys:
        data.materials.append(material(key))
    for poly, key in zip(data.polygons, mesh.colors):
        poly.material_index = keys.index(key)
    data.update()
    if hasattr(mesh,'uvs'):
        uv=data.uv_layers.new(name='FinWeights')
        for poly in data.polygons:
            for li in poly.loop_indices:uv.data[li].uv=mesh.uvs[data.loops[li].vertex_index]
    if LION_RIG and hasattr(mesh,'regions'):
        lionfish_model.rig_attributes(data,mesh)
    return data


def schema(obj, name):
    obj['wf_schema_path'] = str(OAD / (name+'.oad'))


def box_fields(obj, box):
    obj['wf_original_bbox'] = tuple(box)
    obj['wf_had_authored_bbox'] = True


def actor(name, mesh, pos=(0, 0, 0), kind='platform', visible=True, mesh_name=None):
    obj = bpy.data.objects.new(name, blender_mesh(mesh) if isinstance(mesh, Mesh) else mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema(obj, kind)
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = int(visible)
    filename = (mesh_name or name.replace('-', '_'))+'.iff'
    assert len(filename) <= 30, filename
    obj['wf_Mesh Name'] = filename
    obj['wf_original_mesh_name'] = filename
    return obj


def cube(mesh, lo, hi, key):
    a, b, c = lo
    x, y, z = hi
    v = [(a,b,c),(x,b,c),(x,y,c),(a,y,c),(a,b,z),(x,b,z),(x,y,z),(a,y,z)]
    for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
        mesh.face([v[i] for i in f], key)


def static_box(name, lo, hi, key, visible=True):
    m = Mesh(name)
    cube(m, lo, hi, key)
    return actor(name, m, kind='statplat', visible=visible)


bpy.ops.wm.read_factory_settings(use_empty=True)
# Use this checkout's exporter, including its optional lionfish rig metadata.
sys.path.insert(0,str(REPO/'wftools'))
import wf_blender
wf_blender.register()
bpy.ops.wf.import_level(filepath=str(REPO/'wflevels/snowgoons-blender/snowgoons-blender.lev'))
classes = {'director':'Director','camera':'Camera','levelobj':'LevelObj','matte':'Matte',
           'light':'SunLight','room':'Room','camshot':'cs_wide','target':'LookAt','player':'Player'}
seen = set()
for obj in list(bpy.context.scene.objects):
    cls = Path(obj.get('wf_schema_path', '')).stem
    if cls not in classes or cls in seen:
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    seen.add(cls)
    obj.name = classes[cls]
    obj.location = (0, -20, 1)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj['wf_Mass'] = 0.0
    obj['wf_Model Type'] = 'None'
    obj['wf_Script'] = ''
    box_fields(obj, (-.1,-.1,-.1,.1,.1,.1))
assert seen == set(classes), seen

# Player uses one small invisible neutral hull; visual pieces are anchored/no bodies.
meshes,offsets=arowana.models() if C.KIND=='arowana' else ([],[]) if C.KIND=='plants' else models(C.KIND)
if BETTA_FINS:meshes,offsets=detailed_models()
if FEEDING:
    from lionfish_mouth import feeding_models
    meshes,offsets=feeding_models()
if LION_RIG:
    import lionfish_model
    lionfish_model.write_textures(HERE)
    COLORS.update(body=(1,1,1),fin=(1,1,1),eye=(.009,.015,.017),mouth=(.009,.015,.017))
    meshes,offsets=[lionfish_model.geometry()],[(0,0,0)]
data=[blender_mesh(m) for m in meshes]
player=bpy.data.objects['Player']
if C.KIND=='plants':
    player.data=blender_mesh(urchin())
else:
    player.data=blender_mesh(models('betta')[0][0]) if BETTA_FINS else data[0].copy()
player.location=C.SPAWN
player['wf_Model Type']='Mesh'
player['wf_Mesh Name']='sea_urchin.iff' if C.KIND=='plants' else 'player_hull.iff'
player['wf_original_mesh_name']=player['wf_Mesh Name']
player['wf_Mobility']='Physics'
player['wf_Visibility Mailbox']=int(C.KIND=='plants')
player['wf_Script Controls Input']='True'
box_fields(player,(-.20,-.15,-.15,.20,.15,.15))
for key,value in {'Mass':1,'Falling Acceleration':0,'Running Acceleration':0,
                  'Walking Acceleration':0,'Jumping Acceleration':0,'Running Deceleration':.05,
                  'Air Acceleration':0,'Horiz Air Drag':0,'Vert Air Drag':0,
                  'Max Air Speed':4,'Max Ground Speed':4,'Turn Rate':0,'Elasticity':0}.items():
    player['wf_'+key]=float(value)
parts=[]
for k in range(0 if C.KIND=='plants' else COUNT):
    pos=C.SPAWN if not k else ROWS[k-1][:3]
    scale=1 if not k else ROWS[k-1][8]
    group=[]
    for m,d,offset in zip(meshes,data,offsets):
        obj=actor(f'animal-{k:02d}-{m.name}',d,tuple(pos[i]+offset[i]*scale for i in range(3)),mesh_name=m.name)
        obj.scale=(scale,)*3
        if LION_RIG:obj['wf_lion_rig']=True
        group.append(obj)
    parts.append(group)

urchin_feet=[]
if C.KIND=='plants':
    foot_data=blender_mesh(tube_foot())
    for k in range(8):
        angle=math.tau*k/8
        offset=(.25*math.cos(angle),.25*math.sin(angle))
        obj=actor(f'urchin-foot-{k}',foot_data,(C.SPAWN[0]+offset[0],C.SPAWN[1]+offset[1],C.SPAWN[2]),mesh_name='urchin_tube_foot')
        urchin_feet.append((obj,offset))

if FEEDING:
    import goldfish
    prey_mesh=goldfish.blender_mesh(bpy,HERE)
    for k in range(3):
        prey=actor(f'goldfish-{k}',prey_mesh,(0,0,3.65),mesh_name='goldfish')
        prey['wf_Visibility Mailbox']=goldfish.BASE+goldfish.STRIDE*k

# The shell has no front pane; opaque inner walls suggest water.
static_box('tank-base',(-HX,-HY,0),(HX,HY,WALL),'frame')
water=Mesh('water_back')
for j in range(10):
    f=j/9
    COLORS[f'water{j}']=(.025+.035*f,.075+.14*f,.12+.19*f) if C.KIND=='jellyfish' else (.045+.05*f,.14+.16*f,.18+.17*f)
    cube(water,(-HX+WALL,HY-WALL,SAND+(WATER-SAND)*j/10),(HX-WALL,HY,SAND+(WATER-SAND)*(j+1)/10),f'water{j}')
actor('water-back',water,kind='statplat')
static_box('back-air',(-HX,HY-WALL,WATER),(HX,HY,HEIGHT),'backdrop')
for side in [-1,1]:
    lo,hi=(-HX,-HX+WALL) if side<0 else (HX-WALL,HX)
    static_box(f'tank-end-{side}',(lo,-HY,0),(hi,HY,HEIGHT),'frame')
static_box('front-collider',(-HX,-HY-WALL,0),(HX,-HY,HEIGHT),'frame',False)
rim=Mesh('rim')
for lo,hi in [((-HX,-HY,HEIGHT),(HX,-HY+.08,HEIGHT+.1)),((-HX,HY-.08,HEIGHT),(HX,HY,HEIGHT+.1)),
              ((-HX,-HY,HEIGHT),(-HX+.08,HY,HEIGHT+.1)),((HX-.08,-HY,HEIGHT),(HX,HY,HEIGHT+.1))]:
    cube(rim,lo,hi,'rim')
actor('rim',rim)
static_box('floor',(-HX+WALL,-HY+WALL,WALL),(HX-WALL,HY-WALL,SAND),'backdrop' if C.KIND in ('jellyfish','arowana') else 'sand')
if C.KIND=='plants':
    for mesh in planting(SAND):
        obj=actor(mesh.name,mesh)
        box_fields(obj,(-5.95,-1.45,SAND,5.95,1.45,WATER))
elif C.KIND=='betta':
    plants=Mesh('broad_leaves')
    for k,x in enumerate([-5.25,-1.65,2.9,4.0,5.0]):
        for j in range(3):
            h=1.2+((k*7+j*3)%7)*.28
            px=x+(j-1)*.25; py=.75+(j%2)*.3
            plants.tube([(px,py,SAND),(px+.1,py,SAND+h)],.025,'stem',5)
            # Broad solid leaves have thickness and diagonal veins.
            for z,side in [(SAND+h*.45,-1),(SAND+h*.78,1)]:
                base=(px,py,z)
                tip=(px+side*.68,py-.18,z+.65)
                left=(px+side*.16,py-.32,z+.38)
                right=(px+side*.49,py+.18,z+.30)
                plants.face([base,left,tip,right],'leaf_hi' if j%2 else 'leaf')
                plants.face([right,tip,left,base],'leaf')
                plants.tube([base,tip],.016,'stem',4)
    actor('broad-leaf-plants',plants)
    actor('siam-pavilion',pavilion(),(-3.60,1.13,SAND))
elif C.KIND=='jellyfish':
    # Rounded backdrop framing is visual; controls use conservative box bounds.
    curves=Mesh('curved_backdrop')
    for side in [-1,1]:
        pts=[(side*(5.3-.75*math.sin(math.pi*j/12)),1.25,SAND+(WATER-SAND)*j/12) for j in range(13)]
        curves.tube(pts,.09,'frame',6)
    actor('rounded-display',curves)
else:
    for k,(x,y,rx,ry,h) in enumerate(C.ROCKS):
        rock=Mesh('rock')
        low=[(rx*math.cos(math.tau*i/8),ry*math.sin(math.tau*i/8),0) for i in range(8)]
        high=[(rx*.50*math.cos(math.tau*i/8),ry*.50*math.sin(math.tau*i/8),h) for i in range(8)]
        rock.face(high,'rock_hi');rock.face(list(reversed(low)),'rock')
        for i in range(8):
            rock.face([low[i],low[(i+1)%8],high[(i+1)%8],high[i]],'rock' if i%2 else 'rock_hi')
        actor(f'low-rock-{k}',rock,(x,y,SAND),kind='statplat')
static_box('stand',(-HX-.15,-HY-.15,-2.5),(HX+.15,HY+.15,-.025),'stand')
back_y=HY+1 if C.KIND=='arowana' else 3
static_box('room-backdrop',(-30,back_y,-5),(30,back_y+.1,20),'backdrop')
sun=bpy.data.objects['SunLight']
sun.rotation_euler=(0,math.radians(40),math.radians(90))
sun['wf_lightType']='Directional'
for ch,v in zip(('Red','Green','Blue'),(.65,.69,.74)):sun['wf_light'+ch]=v
amb=sun.copy();amb.name='AmbientLight';bpy.context.scene.collection.objects.link(amb)
amb['wf_lightType']='Ambient'
for ch,v in zip(('Red','Green','Blue'),(.43,.48,.56)):amb['wf_light'+ch]=v
look=bpy.data.objects['LookAt'];look.location=C.CLOSE_LOOK if C.KIND=='arowana' else (0,0,2.5)
wide=bpy.data.objects['cs_wide'];wide.location=C.WIDE_CAMERA if C.KIND=='arowana' else (0,-12,2.5)
for axis in 'XYZ':wide['wf_Position '+axis]='Absolute'
wide['wf_Rotation']='Fixed'
for key in ('Follow','Target','Track Object'):wide['wf_'+key]='LookAt'
close_look=look.copy();close_look.name='LookClose';close_look.location=C.CLOSE_LOOK
bpy.context.scene.collection.objects.link(close_look)
close=wide.copy();close.name='cs_close';close.location=C.CLOSE_CAMERA
for key in ('Follow','Target','Track Object'):close['wf_'+key]='LookClose'
bpy.context.scene.collection.objects.link(close)
cam=bpy.data.objects['Camera'];cam.location=wide.location;cam['wf_Mass']=1
cam['wf_FoggingColor']=0x102b40;cam['wf_FoggingStartDistance']=9;cam['wf_FoggingCompleteDistance']=45
bpy.data.objects['Matte']['wf_Matte Type']='Color';bpy.data.objects['Matte']['wf_Background Color']=0x09141e
room=bpy.data.objects['Room'];room.location=(0,0,0);box_fields(room,(-60,-70,-6,60,30,40) if C.KIND=='arowana' else (-25,-30,-6,25,10,18))

objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices={o.name:i+1 for i,o in enumerate(objects)}
mailboxes={n:600+i for i,n in enumerate(['init','phase','heading','prev','mode','dart','cooldown','dx','dy','dz',
                                      'vx','vy','vz','target','x','y','z','yaw','scale','sy','cy',
                                      'actor','ox','oy','oz','camera','clock','pulse'])}
def num(v):return f'{v:.7f}'.rstrip('0').rstrip('.') if v else '0'
def word(n,v):return f': tk-{n} {num(v)} ;\n'
header='\\ Generated standalone tank constants and actor indices\n'
for n,v in mailboxes.items():header+=word(n,v)
for n,v in {'player':indices['Player'],'touch':int(PROFILE=='touch'),'jelly':int(C.KIND=='jellyfish'),
            'limit-x':LIMIT_X,'limit-y':LIMIT_Y,'bottom':C.BOTTOM,'top':C.TOP,'speed':C.SPEED,
            'focus-z':C.CLOSE_LOOK[2],'cam-close':indices['cs_close'],'cam-wide':indices['cs_wide']}.items():header+=word(n,v)
if C.KIND!='plants':header+=species.header(C.KIND)
core=(COMMON/'controller.fth').read_text().replace('\\ SPECIES_CONTROLLER',species.controller(C.KIND))
if BETTA_FINS:
    header+=': bf-drive 660 ; : bf-turn 661 ; : bf-last-yaw 662 ; : bf-swim-phase 663 ; : bf-pect-phase 664 ; : bf-sweep 665 ; : bf-spread 666 ;\n'
    core=core.replace('1.9 *','1.15 *')
feeding=''
if FEEDING:
    header+=goldfish.constants(indices,int(os.environ.get('LIONFISH_INITIAL_GOLDFISH','0')),
                              os.environ.get('LIONFISH_AUTOEAT','1')!='0')
    feeding=(COMMON/'lionfish_feeding.fth').read_text()
    feeding=(COMMON/'lionfish_suction.fth').read_text()+'\n'+feeding
    obstacles=': gf-obstacles\n'
    for x,y,rx,ry,h in C.ROCKS:
        obstacles+=' '+' '.join(num(v) for v in (x-rx,x+rx,y-ry,y+ry,SAND,SAND+h))+' gf-rock\n'
    obstacles+=';\n'
    header+=word('rock-top',max(SAND+r[4] for r in C.ROCKS)).replace('tk-rock-top','gf-rock-top')
    feeding=feeding.replace('\\ GENERATED_OBSTACLES',obstacles)
    # Compile the replacement BEFORE tk-player-tick binds its tk-input call.
    input_word=re.search(r': tk-input\b.*?;',feeding,re.S).group()
    core=re.sub(r': tk-input\b.*?;',lambda m:input_word,core,flags=re.S)
    feeding=feeding.replace(input_word,'')
pose=': tk-pose\n tk-yaw tk@ tk-sin tk-sy tk! tk-yaw tk@ tk-cos tk-cy tk! tk-root\n'
if FEEDING:pose=pose.replace(': tk-pose\n',': tk-pose\n 5 profile-begin\n')
for j,(m,off) in enumerate(zip(meshes,offsets)):
    # Actor lookup in 650..653, assigned for each animal before posing.
    a='0';b='0';c='tk-yaw tk@'
    if C.KIND=='betta' and not BETTA_FINS:
        if j==1:c+=' tk-gait .045 * +'
        if j==2:a='tk-gait .018 *'
        if j==3:a='tk-gait .018 * negate'
    elif C.KIND=='lionfish':
        if j==1:c+=' tk-gait tk-pose-drive tk@ .016 * .004 + * +'
        if j in (2,3):a='tk-gait tk-pose-drive tk@ .012 * .008 + *'+(' negate' if j==3 else '')
        if FEEDING and j in (4,5):
            b='gf-bite tk@ '+('-.025' if j==4 else '.09')+' *'
    elif C.KIND!='jellyfish' and not BETTA_FINS:
        if j==1:a='tk-phase tk@ .12 - tk-sin .018 *';b='tk-phase tk@ .17 - tk-cos .012 *'
        if j==2:a='tk-gait .008 *'
    position=' '.join(num(v) for v in off)
    if FEEDING and j in (4,5):position=f'{num(off[0])} gf-bite tk@ .08 * + 0 {num(off[2])}'
    pose+=' '+position+f' {a} {b} {c} {650+j} tk@ tk-part\n'
    for axis in 'XYZ':
        expr='tk-scale tk@'
        if j==0 and C.KIND=='lionfish' and not LION_RIG and axis=='Y':
            expr+=' tk-gait .022 * 1 + *'
        pose+=f' {expr} INDEXOF_{axis}_SCALE {650+j} tk@ write-actor-mailbox\n'
if C.KIND=='jellyfish':pose+=' j-rig\n'
if LION_RIG:
    # Palette selected via the same stable helper for every animal/spawn.
    palette=': lf-palette\n'
    for k in range(COUNT):
        dark,light=lionfish_model.packed_palette(0,k)
        palette+=f' 650 tk@ {indices[parts[k][0].name]} = if {dark} {light} exit then\n'
    dark,light=lionfish_model.packed_palette(0,0)
    palette+=f' {dark} {light} ;\n'
    pose=palette+pose
    pose+=' tk-phase tk@ tk-pose-drive tk@ tk-pose-roll tk@ .012 / -1 max 1 min gf-bite tk@ lf-palette 650 tk@ lion-pose\n'
pose+=(' 5 profile-end\n' if FEEDING else '')+';\n'
if BETTA_FINS:
    fin_motion=(HERE/'fin_motion.fth').read_text()
    pose=pose.replace(': tk-pose\n',fin_motion+'\n: tk-pose\n bf-motion\n')
    pose=pose[:-2]+' bf-fins\n;\n'
setup=': tk-setup\n'
for k,row in enumerate(ROWS):
    for j,v in enumerate(row):setup+=f' {num(v)} {800+k*12+j} tk!\n'
if C.KIND=='jellyfish':
    for k,row in enumerate(ROWS):
        values=(*row[:2],min(row[2],C.TOP),row[7],4+k*.35,0,0,0,row[8],0,0)
        for j,v in enumerate(values):setup+=f' {num(v)} {1200+k*16+j} tk!\n'
setup+=';\n'
tick=': tk-director-tick\n tk-init tk@ 0 = if tk-setup '+('gf-setup ' if FEEDING else '')+'1 tk-init tk! then\n'
# Bounded route phases, no growing clock or per-frame wrap loops over elapsed hours.
for k,row in enumerate(ROWS):
    base=800+k*12
    if FEEDING:
        for j,obj in enumerate(parts[k+1]):tick+=f' {indices[obj.name]} {650+j} tk!\n'
        continue
    if C.KIND=='jellyfish':
        tick+=f' {1200+k*16} j-base tk! j-resident\n'
    else:
        tick+=f' {base+7} tk@ tk-dt@ {base+6} tk@ / + tk-frac dup {base+7} tk! tk-phase tk!\n'
        tick+=f' {base} tk@ {base+3} tk@ tk-phase tk@ tk-sin * + tk-x tk!\n {base+1} tk@ tk-y tk!\n {base+2} tk@ tk-phase tk@ tk-sin .10 * + tk-z tk!\n'
    if C.KIND!='jellyfish':tick+=f' {base+8} tk@ tk-scale tk! {base+9} tk@ tk-yaw tk!\n'
    for j,obj in enumerate(parts[k+1]):tick+=f' {indices[obj.name]} {650+j} tk!\n'
    tick+=' tk-pose\n'
    if C.KIND=='jellyfish':tick+=' j-lag-pitch tk@ 9 j-store j-lag-roll tk@ 10 j-store\n'
if FEEDING:tick+=' gf-tick gf-bite-player tk@ gf-bite tk!\n'
tick+=' INDEXOF_X_POS tk-player read-actor-mailbox tk-x tk!\n INDEXOF_Y_POS tk-player read-actor-mailbox tk-y tk!\n INDEXOF_Z_POS tk-player read-actor-mailbox tk-z tk!\n tk-heading tk@ tk-yaw tk! tk-pitch tk@ tk-pose-pitch tk! tk-roll tk@ tk-pose-roll tk! tk-drive tk@ tk-speed / 1 min tk-pose-drive tk! 1 tk-scale tk!\n'
tick+=' tk-pulse tk@ tk-dt@ '+('.65' if C.KIND=='jellyfish' else 'tk-drive tk@ tk-speed / 1.2 * .35 +')+' * + tk-frac dup tk-pulse tk! tk-phase tk!\n'
if C.KIND=='jellyfish':
    tick+=' j-player-phase tk@ j-phase tk! j-player-vx tk@ tk-vx tk! j-player-vy tk@ tk-vy tk! j-player-vz tk@ tk-vz tk! j-player-lag-pitch tk@ j-lag-pitch tk! j-player-lag-roll tk@ j-lag-roll tk!\n'
for j,obj in enumerate(parts[0] if parts else []):tick+=f' {indices[obj.name]} {650+j} tk!\n'
tick+=' tk-pose tk-camera-tick '+('j-lag-pitch tk@ j-player-lag-pitch tk! j-lag-roll tk@ j-player-lag-roll tk! ' if C.KIND=='jellyfish' else '')+';\n'
if C.KIND=='plants':
    header+=word('look-close',indices['LookClose'])
    plant_core=(COMMON/'plants_controller.fth').read_text()
    core=plant_core
    if os.environ.get('PLANTED_TANK_DETAIL','runtime')=='runtime':
        core=core.replace("  JOYSTICK_BUTTON_A tk-edge tk-neutral tk@ not & if 1 tk-camera tk@ - tk-camera tk! then", "  \\ Camera taps and settings holds are handled by the native plant settings.")
    pose=setup=''
    header+=': uf-phase 740 ; : uf-init 741 ; : uf-last-x 742 ; : uf-last-y 743 ; : uf-dx 744 ; : uf-dy 745 ; : uf-u 746 ;\n'
    tick=": tk-director-tick\n tk-camera-tick\n INDEXOF_X_POS tk-player read-actor-mailbox tk-x tk! INDEXOF_Y_POS tk-player read-actor-mailbox tk-y tk!\n"
    tick+=' uf-init tk@ 0 = if tk-x tk@ uf-last-x tk! tk-y tk@ uf-last-y tk! 1 uf-init tk! then\n'
    tick+=' tk-x tk@ uf-last-x tk@ - uf-dx tk! tk-y tk@ uf-last-y tk@ - uf-dy tk!\n'
    tick+=' uf-phase tk@ uf-dx tk@ abs uf-dy tk@ abs + .06 / + dup 1 >= if 1 - then uf-phase tk!\n'
    for k,(obj,offset) in enumerate(urchin_feet):
        # Alternating contact/swing groups, advancing only with displacement.
        tick+=f' uf-phase tk@ {num((k%2)*.5)} + dup 1 >= if 1 - then uf-u tk!\n'
        for axis,n in [('X',0),('Y',1)]:
            tick+=f' tk-{axis.lower()} tk@ {num(offset[n])} + uf-u tk@ .5 - .035 * {num(math.cos(math.tau*k/8) if n==0 else math.sin(math.tau*k/8))} * + INDEXOF_{axis}_POS {indices[obj.name]} write-actor-mailbox\n'
        tick+=f' {num(C.BOTTOM)} uf-u tk@ .5 > if uf-u tk@ .5 - 2 * dup 1 swap - * .048 * + then INDEXOF_Z_POS {indices[obj.name]} write-actor-mailbox\n'
    if os.environ.get('PLANTED_TANK_DETAIL','runtime')=='runtime':
        header+=': pg-init 747 ; : pg-water 748 ;\n'
        bindings=' '.join(f'{k} {indices[f"plant_chunk_{k:02d}"]} plant-register' for k in range(8))
        tick+=f' pg-init tk@ 0 = if {bindings} 1 pg-init tk! then\n'
        tick+=' pg-water tk@ tk-dt@ + pg-water tk! INDEXOF_DELTA_TIME tk@ pg-water tk@ plant-step\n'
    tick+=' tk-x tk@ uf-last-x tk! tk-y tk@ uf-last-y tk! ;\n'

player['wf_Script']=header+core+'\ntk-player-tick\n'
bpy.data.objects['Director']['wf_Script']=header+core+pose+setup+feeding+tick+'\ntk-director-tick\n'
if C.KIND=='arowana':
    player['wf_Script'],bpy.data.objects['Director']['wf_Script'],ar_values=arowana.scripts(indices,[m.name for m in meshes],offsets,PROFILE,C)
    mailboxes={n:v for n,v in ar_values.items() if 700<=v<800}
(HERE/'actor-map.json').write_text(json.dumps(dict(level=LEVEL,title=C.TITLE,kind=C.KIND,count=COUNT,
    profile=PROFILE,indices=indices,mailboxes=mailboxes,parts=[m.name for m in meshes],offsets=offsets,
    movement=({'states':species.STATES,'kind':'pulse-and-drift' if C.KIND=='jellyfish' else 'steer-and-swim', 'jelly_states':species.JELLY if C.KIND=='jellyfish' else None} if C.KIND in ('betta','lionfish','jellyfish') else None),
    lionfish_rig=({'parts':1,'regions':lionfish_model.REGIONS,'triangles':sum(len(f)-2 for f in meshes[0].faces),
                  'palette_seed':0,'palettes':[lionfish_model.palette_for(0,k) for k in range(COUNT)],
                  'shared_textures':['lionfish_body.tga','lionfish_fins.tga'],'fin_opacity':.55} if LION_RIG else None),
    animal=('sea_urchin' if C.KIND=='plants' else C.KIND),spawn=C.SPAWN,bottom=C.BOTTOM,top=C.TOP,limits=[LIMIT_X,LIMIT_Y],rows=ROWS,
    betta_fins=({'groups':8,'actor_lookup':[650,657],'motion_mailboxes':[660,666],
                 'weights':'solid UV.x across fin; UV.y root-to-tip','physics_bodies_added':0,
                 'triangles':{m.name:sum(len(f)-2 for f in m.faces) for m in meshes}} if BETTA_FINS else None),
    feeding=({'slots':3,'base':1000,'stride':16,'release':930,'eat':931,'count':933,'target':932,
              'player_eaten':934,'resident_eaten':935,'resident_state':1100,'behavior_state':1108,
              'sensory_memory_base':1050,'sensory_memory_stride':8,
              'strike_base':1200,'strike_stride':16,'strike_duration':.26,'capture_target_time':.10,'capture_rule':'swept mouth entry and prey fit; transport completes consumption',
              'flow_scratch':[1300,1347],
              'observation_time':.65,'sight_range':5.5,'sight_memory':.8,
              'slot_fields':['active','generation','x','y','z','yaw','vx','vy','vz','phase','age',
                             'resident_awareness','alarm','escape_remaining','escape_cooldown','strike_owner'],
              'visibility':'slot active flag'} if FEEDING else None)),indent=2)+'\n')
print(f'[{LEVEL}] {COUNT} animals; {len(objects)} actors; profile={PROFILE}')
bpy.ops.wf.export_level(filepath=str(HERE/(LEVEL+'.lev')))
