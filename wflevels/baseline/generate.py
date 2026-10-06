"""Construct baseline actors explicitly, from an empty Blender scene.

Blender: --python generate.py -- --output <new.blend> --preset default
Export a reviewed file: --python generate.py -- --export <reviewed.blend>
"""
import argparse
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'wftools'))
sys.path.insert(0, str(HERE))
import wf_blender
import wf_core
from wf_blender.export_level import export_scene_to_lev, _seed_defaults
from prepare_assets import LABELS

C = json.loads((HERE / 'baseline.json').read_text())
MATERIALS = {}
COLLECTIONS = {}

def material(name, colour, texture=None):
    if name not in MATERIALS:
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*colour, 1)
        m.use_nodes = True
        m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*colour, 1)
        if texture:
            m['wf_prelit'] = True
            node = m.node_tree.nodes.new('ShaderNodeTexImage')
            node.image = bpy.data.images.load(str(HERE / texture), check_existing=True)
            m.node_tree.links.new(node.outputs['Color'], m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        MATERIALS[name] = m
    return MATERIALS[name]

def collection(name):
    if name not in COLLECTIONS:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
        COLLECTIONS[name] = col
    return COLLECTIONS[name]

def actor(name, cls, group='CORE', mesh=None, pos=(0,0,0), fields=None, bounds=None):
    obj = bpy.data.objects.new(name, mesh)
    collection(group).objects.link(obj)
    obj.location = pos
    schema = ROOT / 'wfsource/source/oas' / (cls + '.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    defaults = {'Mobility':'Anchored', 'Mass':0.0, 'Model Type':'Mesh' if mesh else 'None',
                'Visibility Mailbox':1 if mesh else 0, 'Script':'', 'Script Controls Input':'False',
                'Moves Between Rooms':'False', 'Number Of Local Mailboxes':0}
    defaults.update(fields or {})
    for key, value in defaults.items():
        obj['wf_' + key] = value
    obj['wf_baseline_collection'] = group
    obj['wf_original_mesh_name'] = (name.lower() + '.iff') if mesh else ''
    if mesh:
        obj['wf_Mesh Name'] = obj['wf_original_mesh_name']
    if bounds:
        obj['wf_original_bbox'] = tuple(bounds)
        obj['wf_had_authored_bbox'] = True
    elif not mesh:
        obj['wf_original_bbox'] = (-.05,-.05,-.05,.05,.05,.05)
        obj['wf_had_authored_bbox'] = True
    return obj

class Geometry:
    def __init__(self, name):
        self.name, self.vertices, self.faces, self.mats, self.uvs = name, [], [], [], []
    def face(self, vertices, mat, uv=None):
        start = len(self.vertices)
        self.vertices.extend(vertices)
        self.faces.append(tuple(range(start, start + len(vertices))))
        self.mats.append(mat)
        self.uvs.append(uv or [(0,0)] * len(vertices))
    def box(self, lo, hi, mat):
        a,b,c=lo; x,y,z=hi
        v=[(a,b,c),(x,b,c),(x,y,c),(a,y,c),(a,b,z),(x,b,z),(x,y,z),(a,y,z)]
        for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            self.face([v[i] for i in f],mat)
    def mesh(self):
        data = bpy.data.meshes.new(self.name)
        data.from_pydata(self.vertices, [], self.faces)
        unique = list(dict.fromkeys(self.mats))
        for m in unique: data.materials.append(m)
        uv = data.uv_layers.new(name='UVMap')
        for p, m, coords in zip(data.polygons,self.mats,self.uvs):
            p.material_index = unique.index(m)
            for li, xy in zip(p.loop_indices, coords): uv.data[li].uv = xy
        data.update()
        return data

def label(g, text, x,y,z, width=1.8, vertical=False):
    i=LABELS.index(text); u=(i%4)/4; v=(i//4)/8
    mat=material('labels',(1,1,1),'labels.tga')
    height=width/4
    vertices=[(x,y,z),(x+width,y,z),(x+width,y,z+height),(x,y,z+height)] if vertical else [(x,y,z),(x+width,y,z),(x+width,y+height,z),(x,y+height,z)]
    g.face(vertices,mat,[(u,v+.125),(u+.25,v+.125),(u+.25,v),(u,v)])

def arrow(g, axis, mat):
    # Each tip is exactly the positive unit basis vector; no diagonal arrow.
    def point(t,a,b):
        v=[a,b,t] if axis==2 else [a,t,b] if axis==1 else [t,a,b]
        return tuple(v)
    lo=[-.025]*3;hi=[.025]*3;lo[axis]=0;hi[axis]=.8
    g.box(lo,hi,mat)
    ring=[point(.8,-.09,-.09),point(.8,.09,-.09),point(.8,.09,.09),point(.8,-.09,.09)]
    tip=point(1,0,0)
    # Correct orientation with centroid/normal, independent of axis permutation.
    from mathutils import Vector
    centre=Vector(point(.84,0,0))
    for v in [[ring[3],ring[2],ring[1],ring[0]]] + [[ring[i],ring[(i+1)%4],tip] for i in range(4)]:
        a,b,c=map(Vector,v[:3]); n=(b-a).cross(c-a)
        if n.dot(sum((Vector(q) for q in v),Vector())/len(v)-centre)<0: v.reverse()
        g.face(v,mat)
    lo=[-.015]*3;hi=[.015]*3;lo[axis]=-.25;hi[axis]=-.05
    g.box(lo,hi,mat)

def build(preset):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    wf_blender.register()
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene.unit_settings.scale_length=1
    mb=C['mailboxes']
    actor('Level','levelobj',fields={'Number Of Mailboxes':mb['count'],'Number Of Scratch Mailboxes':mb['scratch'],'Number Of Temporary Objects':16})
    actor('Room','room',bounds=C['room_bounds'])
    director=actor('Director','director')
    player_geo=Geometry('player')
    mat=material('player',(.85,.86,.79))
    # Simple round-ended visual, with its actual axis-aligned box in orange.
    rings=[(-.9,.03),(-.8,.22),(-.6,.3),(.6,.3),(.8,.22),(.9,.03)]
    for (z,r),(zz,rr) in zip(rings,rings[1:]):
        for i in range(12):
            a=math.tau*i/12;b=math.tau*(i+1)/12
            player_geo.face([(r*math.cos(a),r*math.sin(a),z),(r*math.cos(b),r*math.sin(b),z),(rr*math.cos(b),rr*math.sin(b),zz),(rr*math.cos(a),rr*math.sin(a),zz)],mat)
    for z,r,reverse in [(*rings[0],True),(*rings[-1],False)]:
        v=[(r*math.cos(math.tau*i/12),r*math.sin(math.tau*i/12),z) for i in range(12)]
        player_geo.face(list(reversed(v)) if reverse else v,mat)
    orange=material('hull',(.98,.63,.24))
    for a in [-.3,.3]:
        for b in [-.3,.3]: player_geo.box((a-.012,b-.012,-.9),(a+.012,b+.012,.9),orange)
    for z in [-.9,.9]:
        for a in [-.3,.3]:
            player_geo.box((-.3,a-.012,z-.012),(.3,a+.012,z+.012),orange)
            player_geo.box((a-.012,-.3,z-.012),(a+.012,.3,z+.012),orange)
    phys=C['physics']
    player=actor('Player','player',mesh=player_geo.mesh(),pos=C['spawn'],bounds=C['player_bounds'],fields={
        'Mobility':'Physics','Mass':phys['mass'],'Script Controls Input':'True','Step Size':.2,
        'Running Acceleration':phys['acceleration'],'Running Deceleration':phys['deceleration'],
        'Max Ground Speed':phys['max_speed'],'Max Air Speed':phys['max_speed'],
        'Jumping Acceleration':phys['jump'],'Falling Acceleration':phys['gravity'],
        'Horizontal Elasticity':0.0,'Vertical Elasticity':0.0,'Surface Friction':.9,'Turn Rate':3.0})
    player.rotation_euler.z=C['spawn_heading']*math.tau
    cam=C['camera']
    actor('Camera','camera',pos=(0,-12,4.92),fields={'Mobility':'Camera','Mass':1.0,'FoggingStartDistance':320.0,'FoggingCompleteDistance':350.0,'FoggingColor':0x172028})
    actor('CameraOrigin','target')
    actor('TargetFollow','target',pos=(0,0,.6))
    actor('TargetFirst','target',pos=(10,0,.65))
    for name,offset in [('Follow',cam['offset']),('FirstPerson',(-.15,0,.65))]:
        actor(name,'camshot',pos=offset,fields={'Follow':'CameraOrigin','Target':'TargetFollow' if name=='Follow' else 'TargetFirst','Track Object':'Player',
            'Rotation':'Track','Position X':'Relative','Position Y':'Relative','Position Z':'Relative',
            'Hither':cam['hither'],'Yon':cam['yon'],'FOV':cam['fov'],'Pan Time In Seconds':0.0})
    for name,kind,rgb in [('Directional','Directional',(.65,.65,.65)),('Ambient','Ambient',(.35,.35,.35))]:
        obj=actor(name,'light',fields=dict(lightType=kind,lightRed=rgb[0],lightGreen=rgb[1],lightBlue=rgb[2]))
        obj.rotation_euler=(.5,.7,.3)
    actor('Background','matte',fields={'Model Type':'None','Matte Type':'Color','Background Color':0x172028})
    floor=Geometry('floor'); size=C['floor_size'];half=size/2;step=C['grid_major']
    assert size % step == 0 and half % step == 0
    grid=material('grid',(1,1,1),'grid.tga')
    for x in range(int(-half),int(half),step):
        for y in range(int(-half),int(half),step):
            floor.face([(x,y,0),(x+step,y,0),(x+step,y+step,0),(x,y+step,0)],grid,[(0,0),(1,0),(1,1),(0,1)])
    slab=material('slab',(.12,.16,.20))
    # Sides/bottom only: no duplicate coplanar floor surface.
    lo=(-half,-half,-C['floor_depth']);hi=(half,half,0)
    a,b,c=lo;x,y,z=hi
    floor.face([(a,b,c),(a,y,c),(x,y,c),(x,b,c)],slab)
    for v in [[(a,b,c),(x,b,c),(x,b,z),(a,b,z)],[(x,b,c),(x,y,c),(x,y,z),(x,b,z)],[(x,y,c),(a,y,c),(a,y,z),(x,y,z)],[(a,y,c),(a,b,c),(a,b,z),(a,y,z)]]:floor.face(v,slab)
    actor('Floor','statplat','GROUND',floor.mesh(),bounds=(*lo,*hi))
    axes=Geometry('axes')
    for axis,rgb in enumerate([(.937,.325,.314),(.4,.733,.416),(.259,.647,.961)]):arrow(axes,axis,material('axis'+str(axis),rgb))
    actor('OriginAxes','platform','DEBUG_DEFAULT',axes.mesh(),fields={'Mass':0.0})
    cube=Geometry('unit_cube');cube.box((-.5,-.5,-.5),(.5,.5,.5),material('cube',(.55,.64,.69)))
    actor('UnitCube','statplat','DEBUG_DEFAULT',cube.mesh(),pos=(5,0,.5),bounds=(-.5,-.5,-.5,.5,.5,.5))
    guides=Geometry('guides')
    white=material('marks',(.8,.85,.85))
    for i in range(11):guides.box((i,-2.05,.005),(i+.025,-1.7,.025),white)
    guides.box((0,-2.05,.005),(10,-2.025,.025),white)
    # Spawn ring and +Y facing arrow: visual-only platform actor, zero mass.
    for i in range(32):
        a=math.tau*i/32;b=math.tau*(i+1)/32
        guides.face([(r*math.cos(t),-5+r*math.sin(t),.015) for r,t in [(.65,a),(.75,a),(.75,b),(.65,b)]],white)
    guides.face([(-.12,-4.6,.02),(.12,-4.6,.02),(0,-4.2,.02)],white)
    actor('SpawnRuler','platform','DEBUG_DEFAULT',guides.mesh(),fields={'Mass':0.0})
    labels=Geometry('coordinates')
    for text,x,y,z,w,vertical in [('X (1,0,0)',1.1,0,.035,1.8,False),('Y (0,1,0)',0,1.1,.035,1.8,False),('Z (0,0,1)',.1,0,1.08,1.8,True),('(0,0,0)',-1.9,-.6,.035,1.8,False),('SPAWN +Y',-1,-6,.035,2,False),('1 x 1 x 1',4.1,-.75,.035,1.8,False),('10 units',4,-2.65,.035,2,False)]:label(labels,text,x,y,z,w,vertical)
    for n in range(-100,101,10):
        for x,y in [(n-.9,-99),(n-.9,98),( -99,n-.22),(97,n-.22)]:label(labels,str(n),max(-99.7,min(97.9,x)),max(-99.7,min(99.2,y)),.025)
    actor('CoordinateLabels','platform','DEBUG_DEFAULT',labels.mesh(),fields={'Mass':0.0})
    from fixtures import add_fixtures
    add_fixtures(preset, actor, Geometry, material, label)
    # Stable schema instances can be catalogued without native actor-class changes.
    for name in ['SampleSettings','SampleSettings2']:
        actor(name,'target','CONFIG',pos=(2,-4,1))
    objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
    ids={o.name:i+1 for i,o in enumerate(objects)}
    header='\\ Explicit generated baseline actor constants\n'+''.join(f': base-{n.lower()} {ids[n]} ;\n' for n in ['Player','Follow','FirstPerson'])
    header+=''.join(f': base-{n.replace("_","-")} {v} ;\n' for n,v in mb.items() if n not in ['count','scratch'])
    header+=''.join(f': base-spawn-{a} {v} ;\n' for a,v in zip('xyz',C['spawn']))
    header+=f': base-spawn-heading {C["spawn_heading"]} ;\n'
    player['wf_Script']=header+(HERE/'scripts/player.fth').read_text()
    director['wf_Script']=header+(HERE/'scripts/baseline.fth').read_text()
    bpy.context.scene['baseline_preset']=preset
    bpy.context.scene['baseline_config']=json.dumps(C)
    bpy.context.scene['baseline_actor_map']=json.dumps(ids)
    # A separate Blender inspection camera is never exported as an actor.
    data=bpy.data.cameras.new('AuthoringView');view=bpy.data.objects.new('AuthoringView',data)
    collection('AUTHORING_ONLY').objects.link(view);view.location=(14,-22,17)
    view.rotation_euler=(Vector((0,0,0))-view.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.scene.camera=view;data.clip_end=400
    return ids

def export(path):
    # Exporter does not filter hidden collections. Explicitly detach fixture schemas
    # for collections whose export policy says they are excluded.
    detached={}
    for obj in bpy.context.scene.objects:
        if obj.get('wf_baseline_excluded') and obj.get('wf_schema_path'):
            detached[obj.name]=obj['wf_schema_path'];del obj['wf_schema_path']
    try:
        ok,msg=export_scene_to_lev(bpy.context,str(HERE/'baseline.lev'))
        if not ok:raise RuntimeError(msg)
        ids={o.name:i+1 for i,o in enumerate(o for o in bpy.context.scene.objects if o.get('wf_schema_path'))}
        (HERE/'actor-map.json').write_text(json.dumps({'indices':ids,'preset':bpy.context.scene.get('baseline_preset','default')},indent=2)+'\n')
        inventory=[dict(name=o.name,collection=o.get('wf_baseline_collection'),schema=Path(o['wf_schema_path']).name,position=list(o.location),bounds=list(o.get('wf_original_bbox',[])),properties={k[3:]:v for k,v in o.items() if k.startswith('wf_') and isinstance(v,(str,int,float))}) for o in bpy.context.scene.objects if o.get('wf_schema_path')]
        (HERE/'build').mkdir(exist_ok=True)
        (HERE/'build/scene-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
        print(msg)
    finally:
        for name,schema in detached.items():bpy.data.objects[name]['wf_schema_path']=schema

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);ap.add_argument('--export',type=Path);ap.add_argument('--overwrite',action='store_true');ap.add_argument('--preset',choices=C['presets'],default='default')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    if args.export:
        wf_blender.register();bpy.ops.wm.open_mainfile(filepath=str(args.export.resolve()));export(args.export)
    else:
        out=(args.output or HERE/'build/baseline-generated.blend').resolve()
        if out.exists() and not args.overwrite:raise RuntimeError('Refusing to overwrite an existing Blender file; use --overwrite explicitly')
        out.parent.mkdir(parents=True,exist_ok=True);build(args.preset)
        bpy.ops.wm.save_as_mainfile(filepath=str(out))
        # Make schema/texture references portable relative to the saved file.
        for obj in bpy.context.scene.objects:
            if obj.get('wf_schema_path'):obj['wf_schema_path']=bpy.path.relpath(obj['wf_schema_path'])
        for image in bpy.data.images:
            if image.filepath:image.filepath=bpy.path.relpath(image.filepath)
        bpy.ops.wm.save_as_mainfile(filepath=str(out))
        print('Generated editable scene:',out)
