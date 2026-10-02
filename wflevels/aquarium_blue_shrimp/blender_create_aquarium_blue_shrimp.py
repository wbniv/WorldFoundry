#!/usr/bin/env python3
"""Build the independent Blue Shrimp tank; never writes the existing aquarium.

SHRIMP_COUNT=1..24 includes the player. SHRIMP_PROFILE=keyboard|touch.
Build: bash wflevels/aquarium_blue_shrimp/build.sh
"""
import json
import math
import os
from pathlib import Path
import random
import sys

import addon_utils
import bpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import constants as C
from geometry import Mesh, PALETTE, PARTS, OFFSETS, shrimp_meshes

PROFILE = os.environ.get('SHRIMP_PROFILE', 'keyboard')
assert PROFILE in ('keyboard', 'touch')
COUNT = int(os.environ.get('SHRIMP_COUNT', '24'))
ROWS = C.residents(COUNT-1)
OAD = REPO / 'wftools/wf_oad/tests/fixtures'
TAG = '[blue-shrimp]'
COLORS = dict(PALETTE, sand=(.76, .73, .57), sand_hi=(.85, .80, .64),
              sand_lo=(.65, .64, .49), frame=(.42, .70, .74),
              rim=(.64, .84, .84), rock=(.16, .22, .24), rock_hi=(.23, .32, .33),
              wood=(.25, .17, .105), wood_hi=(.37, .26, .14),
              moss=(.20, .38, .16), moss_hi=(.33, .49, .18),
              leaf=(.18, .39, .24), leaf_hi=(.32, .56, .29),
              stem=(.16, .30, .18), stand=(.08, .10, .10), backdrop=(.025, .055, .075))
MATERIALS = {}


def material(key):
    if key not in MATERIALS:
        mt = bpy.data.materials.new('shrimp-'+key)
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

# Player and all visual parts precede the enclosing shell in physics setup.
models = shrimp_meshes()
data = [blender_mesh(m) for m in models]
player = bpy.data.objects['Player']
player.data = data[0].copy()
player.location = C.SPAWN
player['wf_Model Type'] = 'Mesh'
player['wf_Mesh Name'] = 'shrimp_hull.iff'
player['wf_original_mesh_name'] = 'shrimp_hull.iff'
player['wf_Mobility'] = 'Physics'
player['wf_Visibility Mailbox'] = 0
player['wf_Script Controls Input'] = 'True'
box_fields(player, (-.20,-.125,-.15,.20,.125,.15))
for key, value in {'Mass':1, 'Falling Acceleration':0, 'Running Acceleration':0,
                   'Walking Acceleration':0, 'Jumping Acceleration':0, 'Running Deceleration':.05,
                   'Air Acceleration':0, 'Horiz Air Drag':0,
                   'Vert Air Drag':0, 'Max Air Speed':4, 'Max Ground Speed':4,
                   'Turn Rate':0, 'Elasticity':0}.items():
    player['wf_'+key] = float(value)

ALL_PARTS = []
for k in range(COUNT):
    row = ROWS[k-1] if k else dict(home=(C.SPAWN[0], C.SPAWN[1], C.SAND), size=1, yaw=0)
    parts = []
    for part, mesh, offset in zip(PARTS, data, OFFSETS):
        p = actor(f'shrimp-{k:02d}-{part}', mesh,
                  tuple(row['home'][i]+offset[i]*row['size'] for i in range(3)),
                  mesh_name='shrimp_'+part.replace('-', '_'))
        p.scale = (row['size'],)*3
        parts.append(p)
    ALL_PARTS.append(parts)

# Water is colored inner wall geometry and fog. No opaque front pane.
static_box('tank-base', (-C.HX,-C.HY,0), (C.HX,C.HY,C.WALL), 'frame')
for j in range(12):
    f = j/11
    key = f'water-{j}'
    COLORS[key] = (.055+.07*f, .19+.17*f, .23+.17*f)
    low, high = C.SAND+(C.WATER-C.SAND)*j/12, C.SAND+(C.WATER-C.SAND)*(j+1)/12
    static_box(f'water-back-{j}', (-C.HX+C.WALL,C.HY-C.WALL,low), (C.HX-C.WALL,C.HY,high), key)
static_box('back-air', (-C.HX,C.HY-C.WALL,C.WATER), (C.HX,C.HY,C.HEIGHT), 'backdrop')
for side in (-1, 1):
    low, high = (-C.HX, -C.HX+C.WALL) if side < 0 else (C.HX-C.WALL, C.HX)
    static_box(f'tank-end-{side}', (low,-C.HY,0), (high,C.HY,C.HEIGHT), 'frame')
static_box('front-collider', (-C.HX,-C.HY-C.WALL,0), (C.HX,-C.HY,C.HEIGHT), 'frame', False)
rim = Mesh('tank_rim')
for lo, hi in [((-C.HX-.05,-C.HY-.05,C.HEIGHT),(C.HX+.05,-C.HY+.08,C.HEIGHT+.1)),
               ((-C.HX-.05,C.HY-.08,C.HEIGHT),(C.HX+.05,C.HY+.05,C.HEIGHT+.1)),
               ((-C.HX-.05,-C.HY,C.HEIGHT),(-C.HX+.08,C.HY,C.HEIGHT+.1)),
               ((C.HX-.08,-C.HY,C.HEIGHT),(C.HX+.05,C.HY,C.HEIGHT+.1))]:
    cube(rim, lo, hi, 'rim')
actor('tank-rim', rim, kind='statplat')

sand = Mesh('sand')
cube(sand, (-C.HX+C.WALL,-C.HY+C.WALL,C.WALL), (C.HX-C.WALL,C.HY-C.WALL,C.SAND-.003), 'sand_lo')
rng = random.Random(32)
for x in range(48):
    for y in range(8):
        x0 = -C.HX+C.WALL+x*(2*(C.HX-C.WALL)/48)
        y0 = -C.HY+C.WALL+y*(2*(C.HY-C.WALL)/8)
        sand.face([(x0,y0,C.SAND),(x0+.2487083,y0,C.SAND),
                   (x0+.2487083,y0+.381,C.SAND),(x0,y0+.381,C.SAND)],
                  rng.choice(['sand','sand','sand_hi','sand_lo']))
actor('sand', sand, kind='statplat')

for k, (x,y,rx,ry,h) in enumerate(C.ROCKS):
    rock = Mesh('rock')
    # A faceted convex boulder with a flat top for an authored grazing perch.
    lower = [(rx*math.cos(math.tau*i/9),ry*math.sin(math.tau*i/9),0) for i in range(9)]
    upper = [(rx*.55*math.cos(math.tau*i/9),ry*.55*math.sin(math.tau*i/9),h) for i in range(9)]
    rock.face(upper, 'rock_hi')
    rock.face(list(reversed(lower)), 'rock')
    for i in range(9):
        rock.face([lower[i],lower[(i+1)%9],upper[(i+1)%9],upper[i]], 'rock' if i%3 else 'rock_hi')
    obj = actor(f'rock-{k}', rock, (x,y,C.SAND), kind='statplat')
    # Base is at local z=0; no centered prop placed halfway inside the sand.

wood = Mesh('branching_wood')
wood.tube(C.WOOD, .16, 'wood', 7)
wood.tube([C.WOOD[1],(-.3,.85,1.65),(-.7,.92,2.05)], .08, 'wood_hi', 6)
wood.tube([C.WOOD[2],(1.2,.82,1.55),(2.0,.85,1.5)], .065, 'wood', 6)
actor('branching-wood', wood, kind='statplat')

# Leaf clusters have real thickness and open gaps, not a painted backdrop.
plants = Mesh('plants')
for x in (-5.3,-4.7,-3.9,-.9,.2,2.8,3.4,4.7,5.25):
    for branch in range(3):
        px, py = x+rng.uniform(-.22,.22), rng.uniform(.9,1.2)
        height = rng.uniform(.9,2.9)
        plants.tube([(px,py,C.SAND),(px+.12,py+.03,C.SAND+height)], .015, 'stem')
        for j in range(5):
            z = C.SAND+(j+1)*height/6
            side = -1 if j%2 else 1
            plants.ellipsoid((px+side*.15,py,z), (.25,.065,.075),
                             'leaf_hi' if j%3==0 else 'leaf', 6, 4)
actor('plants', plants)
moss = Mesh('moss')
for center in [(-2.65,.30,C.SAND+.88), (.60,.75,1.66), (-4.9,.5,C.SAND+.06), (4.7,.5,C.SAND+.06)]:
    for k in range(9):
        x,y,z = center
        moss.ellipsoid((x+rng.uniform(-.24,.24),y+rng.uniform(-.13,.13),z+rng.uniform(0,.045)),
                       (.11,.09,.055), 'moss_hi' if k%3==0 else 'moss', 6, 4)
actor('moss-patches', moss)
static_box('stand', (-C.HX-.15,-C.HY-.15,-2.5),(C.HX+.15,C.HY+.15,-.025),'stand')
static_box('room-backdrop', (-20,3,-5),(20,3.1,15),'backdrop')

sun = bpy.data.objects['SunLight']
sun.rotation_euler = (0,math.radians(40),math.radians(90))
sun['wf_lightType'] = 'Directional'
for ch, v in zip(('Red','Green','Blue'), (.64,.70,.72)):
    sun['wf_light'+ch] = v
amb = sun.copy()
amb.name = 'AmbientLight'
bpy.context.scene.collection.objects.link(amb)
amb['wf_lightType'] = 'Ambient'
for ch,v in zip(('Red','Green','Blue'), (.42,.48,.56)):
    amb['wf_light'+ch] = v

look = bpy.data.objects['LookAt']
look.location = (0,0,2.25)
wide = bpy.data.objects['cs_wide']
wide.location = C.CAMERA
for axis in 'XYZ':
    wide['wf_Position '+axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow','Target','Track Object'):
    wide['wf_'+key] = 'LookAt'
close_look = look.copy()
close_look.name = 'LookClose'
close_look.location = C.CLOSE_LOOK
bpy.context.scene.collection.objects.link(close_look)
close = wide.copy()
close.name = 'cs_grazing'
close.location = C.CLOSE_CAMERA
for key in ('Follow','Target','Track Object'):
    close['wf_'+key] = 'LookClose'
bpy.context.scene.collection.objects.link(close)
cam = bpy.data.objects['Camera']
cam.location = C.CAMERA
cam['wf_Mass'] = 1
cam['wf_FoggingColor'] = 0x164454
cam['wf_FoggingStartDistance'] = 8
cam['wf_FoggingCompleteDistance'] = 45
bpy.data.objects['Matte']['wf_Matte Type'] = 'Color'
bpy.data.objects['Matte']['wf_Background Color'] = 0x09141e
room = bpy.data.objects['Room']
room.location = (0,0,0)
box_fields(room, (-25,-30,-6,25,10,18))

objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name:i+1 for i,o in enumerate(objects)}
assert indices['Player'] < indices['tank-base']
def number(x):
    return f'{x:.7f}'.rstrip('0').rstrip('.') if x else '0'
def word(name,value):
    return f': sh-{name} {number(value)} ;\n'

header = '\\ generated indices and constants, Blue Shrimp\n'
for name, address in C.MAILBOX.items():
    header += word(name,address)
for name,value in {'player':indices['Player'],'touch':int(PROFILE=='touch'),
                   'limit-x':C.LIMIT_X,'limit-y':C.LIMIT_Y,'lift':C.HULL_LIFT,
                   'sand':C.SAND,'top':C.WATER-.5,'count':len(ROWS),
                   'stride':C.STRIDE,'table-base':C.TABLE,'heads':1400,
                   'cam-wide':indices['cs_wide'],'cam-close':indices['cs_grazing']}.items():
    header += word(name,value)
# Actor lookup slots are distinct from pose scratch and resident state.
for j, part in enumerate(PARTS):
    header += f': sh-actor-{part} {650+j} read-mailbox ;\n'
header += ': sh-player-actors\n'+''.join(f'  {indices[o.name]} {650+j} write-mailbox\n' for j,o in enumerate(ALL_PARTS[0]))+';\n'
header += ': sh-resident-actors\n'+''.join(f'  {j} sh-cell {650+j} write-mailbox\n' for j in range(5))+';\n'
header += ': sh-pose-parts\n'
for j, (part, off) in enumerate(zip(PARTS,OFFSETS)):
    a = 'sh-walk' if part=='legs-near' else 'sh-walk negate' if part=='legs-far' else '0'
    b = 'sh-tail-bend' if part=='tail' else '0'
    yaw = 'sh-yaw sh@ sh-phase sh@ sh-sin .012 * +' if part=='antennae' else 'sh-yaw sh@'
    header += '  '+' '.join(number(v) for v in off)+f' {a} {b} {yaw} sh-actor-{part} sh-part\n'
header += ';\n'
setup = ': sh-setup\n'
for k,row in enumerate(ROWS):
    values = [*(indices[o.name] for o in ALL_PARTS[k+1]), *row['home'], *row['excursion'],
              row['period'],row['phase'],row['size'],row['yaw'],row['home'][0],row['home'][1],0]
    assert len(values)==C.STRIDE
    for j,value in enumerate(values):
        setup += f'  {number(value)} {C.TABLE+k*C.STRIDE+j} write-mailbox\n'
    setup += f'  {number(row["yaw"])} {1400+k} write-mailbox\n'
    for obj in ALL_PARTS[k+1]:
        for axis in 'XYZ':
            setup += f'  {number(row["size"])} INDEXOF_{axis}_SCALE {indices[obj.name]} write-actor-mailbox\n'
setup += ';\n'
support = ': sh-rock-support\n'
for x,y,rx,ry,h in C.ROCKS:
    support += f'''  INDEXOF_X_POS sh@ {number(x)} - abs {number(rx*.43)} <
  INDEXOF_Y_POS sh@ {number(y)} - abs {number(ry*.43)} < &
  INDEXOF_Z_POS sh@ {number(C.SAND+h+C.HULL_LIFT-.05)} >= &
  if {number(C.SAND+h)} sh-support sh! then
'''
support += ';\n'
# Dependencies: functions referring to generated pose helpers are defined
# after the core library; split at sh-pose, so constants never reference later words.
library = (HERE/'shrimp.fth').read_text()
prefix, suffix = library.split(': sh-pose\n', 1)
# sh-player-tick references rock-support; generated support uses only header and sh@.
basic_end = prefix.index(': sh-support-height')
prefix = prefix[:basic_end]+support+prefix[basic_end:]
pose_helpers = header[header.index(': sh-pose-parts'):]
header = header[:header.index(': sh-pose-parts')]
# resident-actors needs sh-cell, declared late; move it beside sh-table/sh-cell.
start = header.index(': sh-resident-actors')
resident_helper = header[start:]
header = header[:start]
suffix = suffix.replace(': sh-route\n', resident_helper+': sh-route\n')
script = header+prefix+pose_helpers+': sh-pose\n'+suffix.replace(': sh-director-tick\n', setup+': sh-director-tick\n')
player['wf_Script'] = header+prefix[:prefix.index(': sh-place')]+ '\nsh-player-tick\n'
bpy.data.objects['Director']['wf_Script'] = script+'\nsh-director-tick\n'

(HERE/'actor-map.json').write_text(json.dumps(dict(indices=indices,count=COUNT,profile=PROFILE,
                                                   rows=ROWS,mailboxes=C.MAILBOX),indent=2)+'\n')
print(f'{TAG} {COUNT} shrimp, {len(objects)} actors; profile={PROFILE}')
print(f'{TAG} independent outputs: {HERE/C.LEVEL}.lev')
bpy.ops.wf.export_level(filepath=str(HERE/(C.LEVEL+'.lev')))
print(f'{TAG} done')
