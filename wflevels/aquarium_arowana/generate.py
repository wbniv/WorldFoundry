"""Build the independent bare Arowana tank through the established exporter."""
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

COMMON=Path(__file__).resolve().parent.parent/'aquarium_tanks'
HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent
sys.path.insert(0,str(COMMON))
from mesh import Mesh
import arowana
LEVEL='aquarium_arowana'
spec=importlib.util.spec_from_file_location('tank_config',HERE/'config.py')
C=importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
PROFILE=os.environ.get('TANK_PROFILE','remote')
assert PROFILE in ('keyboard','touch','remote')
COUNT=1
ROWS=[]
HX=C.DIMENSIONS_M[0]*C.WORLD_SCALE/2
HY=C.DIMENSIONS_M[1]*C.WORLD_SCALE/2
HEIGHT=WATER=C.DIMENSIONS_M[2]*C.WORLD_SCALE
WALL=.127
SAND=.20
LIMIT_X,LIMIT_Y=HX-3.61,HY-1.35
OAD=REPO/'wftools/wf_oad/tests/fixtures'
COLORS=dict(arowana.COLORS,frame=(.30,.55,.63),rim=(.53,.74,.79),
            stand=(.06,.09,.11),backdrop=(.018,.04,.065))
MATERIALS={}
def material(key):
    if key not in MATERIALS:
        mt = bpy.data.materials.new('tank-'+key)
        mt.use_nodes = True
        rgb = (*COLORS[key], 1)
        mt.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = rgb
        mt.diffuse_color = rgb
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
assert addon_utils.enable('wf_blender', default_set=False, persistent=False), 'wf_blender unavailable'
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
meshes,offsets=arowana.models()
data=[blender_mesh(m) for m in meshes]
player=bpy.data.objects['Player']
player.data=data[0].copy()
player.location=C.SPAWN
player['wf_Model Type']='Mesh'
player['wf_Mesh Name']='player_hull.iff'
player['wf_original_mesh_name']=player['wf_Mesh Name']
player['wf_Mobility']='Physics'
player['wf_Visibility Mailbox']=0
player['wf_Script Controls Input']='True'
box_fields(player,(-.20,-.15,-.15,.20,.15,.15))
for key,value in {'Mass':1,'Falling Acceleration':0,'Running Acceleration':0,
                  'Walking Acceleration':0,'Jumping Acceleration':0,'Running Deceleration':.05,
                  'Air Acceleration':0,'Horiz Air Drag':0,'Vert Air Drag':0,
                  'Max Air Speed':4,'Max Ground Speed':4,'Turn Rate':0,'Elasticity':0}.items():
    player['wf_'+key]=float(value)
parts=[]
for k in range(COUNT):
    pos=C.SPAWN if not k else ROWS[k-1][:3]
    scale=1 if not k else ROWS[k-1][8]
    group=[]
    for m,d,offset in zip(meshes,data,offsets):
        obj=actor(f'animal-{k:02d}-{m.name}',d,tuple(pos[i]+offset[i]*scale for i in range(3)),mesh_name=m.name)
        obj.scale=(scale,)*3
        group.append(obj)
    parts.append(group)

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
player['wf_Script'],bpy.data.objects['Director']['wf_Script'],ar_values=arowana.scripts(
    indices,[m.name for m in meshes],offsets,PROFILE,C)
mailboxes={n:v for n,v in ar_values.items() if 700<=v<800}
(HERE/'actor-map.json').write_text(json.dumps(dict(level=LEVEL,title=C.TITLE,kind=C.KIND,count=COUNT,
    profile=PROFILE,indices=indices,mailboxes=mailboxes,parts=[m.name for m in meshes],offsets=offsets,
    animal=C.KIND,spawn=C.SPAWN,bottom=C.BOTTOM,top=C.TOP,limits=[LIMIT_X,LIMIT_Y],rows=ROWS,
    betta_fins=None,feeding=None),indent=2)+'\n')
print(f'[{LEVEL}] {COUNT} animals; {len(objects)} actors; profile={PROFILE}')
bpy.ops.wf.export_level(filepath=str(HERE/(LEVEL+'.lev')))
