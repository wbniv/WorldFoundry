"""Export Sea Stars through the existing Blender level and DFRM pipelines."""
import argparse
import json
import subprocess
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import config as cfg
import controller
import scene
import stars
p=argparse.ArgumentParser()
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--empty',action='store_true',help='early static performance gate')
p.add_argument('--preview',type=Path)
p.add_argument('--art-mode',choices=('full','scene','revisions','poses','brittle'),default='full')
p.add_argument('--art-dir',type=Path,help='save rigged Blender source and render the complete asset review')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
repo=a.repo.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(repo/'wflevels/aquarium_tanks'),str(repo/'wflevels/aquarium_thai_reef'),str(repo/'wftools')]
from mesh import Mesh
from reef.rockscape import rock_blob
import wf_blender
from wf_blender import dfrm_chunk
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()
bpy.ops.wf.import_level(filepath=str(repo/'wflevels/snowgoons-blender/snowgoons-blender.lev'))
classes={'director':'Director','camera':'Camera','levelobj':'LevelObj','matte':'Matte','light':'SunLight','room':'Room','camshot':'cs_wide','target':'LookAt','player':'Player'}
seen=set()
for obj in list(bpy.context.scene.objects):
    cls=Path(obj.get('wf_schema_path','')).stem
    if cls not in classes or cls in seen:
        bpy.data.objects.remove(obj,do_unlink=True);continue
    seen.add(cls);obj.name=classes[cls]
    obj['wf_schema_path']=str(repo/'wfsource/source/oas'/f'{cls}.oad')
    obj.location=(0,-20,1);obj.rotation_euler=(0,0,0);obj.scale=(1,1,1)
    obj['wf_Mass']=0.;obj['wf_Model Type']='None';obj['wf_Script']=''
    obj['wf_original_bbox']=(-.1,-.1,-.1,.1,.1,.1);obj['wf_had_authored_bbox']=True
assert seen==set(classes),seen
stars.write_atlas(out/'stars_atlas.tga')
mat=bpy.data.materials.new('sea-stars-atlas');mat.use_nodes=True
image=bpy.data.images.load(str(out/'stars_atlas.tga'))
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.8
mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
def mesh_data(mesh,kind=None):
    data=bpy.data.meshes.new(mesh.name);data.from_pydata(mesh.vertices,[],mesh.faces)
    data.materials.append(mat);data.update();uv=data.uv_layers.new(name='UVMap')
    for poly,face,color in zip(data.polygons,mesh.faces,mesh.colors):
        points=[mesh.vertices[i] for i in face]
        values=stars.uv_face(kind,color,points) if kind else scene.uv(color,points)
        for li,value in zip(poly.loop_indices,values): uv.data[li].uv=value
        poly.use_smooth=bool(kind) or mesh.name=='sea_rocks'
    bm=bmesh.new();bm.from_mesh(data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    bm.to_mesh(data);bm.free();data.update()
    data.calc_loop_triangles()
    return data

def actor(name,mesh,pos,kind=None,schema='platform'):
    obj=bpy.data.objects.new(name,mesh_data(mesh,kind));bpy.context.scene.collection.objects.link(obj)
    obj.location=pos;obj['wf_schema_path']=str(repo/'wfsource/source/oas'/f'{schema}.oad')
    obj['wf_Model Type']='Mesh';obj['wf_Mobility']='Anchored';obj['wf_Mass']=0.
    obj['wf_Visibility Mailbox']=1;obj['wf_Mesh Name']=mesh.name+'.iff';obj['wf_original_mesh_name']=mesh.name+'.iff'
    return obj
static=scene.build(Mesh,rock_blob)
for name,mesh in static.items():actor(name,mesh,(0,0,0))
# Invisible authored rock proxies. Player motion uses their expanded export-time bounds.
for i,(x,y,rx,ry,h) in enumerate(cfg.ROCKS):
    proxy=Mesh('sea_rock_proxy'+str(i));scene.box(proxy,(-rx,-ry,0),(rx,ry,h),'rock')
    obj=actor('RockProxy'+str(i),proxy,(x,y,.775),schema='statplat');obj['wf_Visibility Mailbox']=0
hull=Mesh('sea_player_hull');scene.box(hull,(-.04,-.04,-.02),(.04,.04,.02),'rock')
player=bpy.data.objects['Player'];player.data=mesh_data(hull);player.location=(0,-1,.8)
player['wf_Model Type']='Mesh';player['wf_Mesh Name']=hull.name+'.iff';player['wf_original_mesh_name']=hull.name+'.iff'
player['wf_Mobility']='Physics';player['wf_Visibility Mailbox']=0;player['wf_Script Controls Input']='True'
player['wf_Mass']=1.;player['wf_Falling Acceleration']=0.;player['wf_original_bbox']=(-.04,-.04,-.02,.04,.04,.02)
for key,value in {'Running Acceleration':0,'Walking Acceleration':0,'Jumping Acceleration':0,'Running Deceleration':0,
                  'Air Acceleration':0,'Horiz Air Drag':0,'Vert Air Drag':0,'Max Air Speed':4,'Max Ground Speed':4,'Turn Rate':0,'Elasticity':0}.items():player['wf_'+key]=float(value)
animals=[('BlueStar','linckia',(0,-1,.8)),*cfg.RESIDENTS]
meshes={kind:stars.mesh(Mesh,kind) for kind in cfg.SPECIES}
if not a.empty:
    for name,kind,pos in animals:actor(name,meshes[kind],pos,kind)
sun=bpy.data.objects['SunLight'];sun.rotation_euler=(0,.6981317,1.5707963);sun['wf_lightType']='Directional'
for channel,value in zip(('Red','Green','Blue'),(.64,.69,.75)):sun['wf_light'+channel]=value
ambient=sun.copy();ambient.name='AmbientLight';bpy.context.scene.collection.objects.link(ambient);ambient['wf_lightType']='Ambient'
for channel,value in zip(('Red','Green','Blue'),(.43,.47,.52)):ambient['wf_light'+channel]=value
bpy.data.objects['LookAt'].location=(0,0,2.35)
wide=bpy.data.objects['cs_wide'];wide.location=(0,-8.5,4.1)
for axis in 'XYZ':wide['wf_Position '+axis]='Absolute'
wide['wf_Rotation']='Fixed'
for key in ('Follow','Target','Track Object'):wide['wf_'+key]='LookAt'
cam=bpy.data.objects['Camera'];cam.location=wide.location;cam['wf_Mass']=1.
cam['wf_FoggingColor']=0x102b40;cam['wf_FoggingStartDistance']=9;cam['wf_FoggingCompleteDistance']=45
for key,value in {'WaterAbsorbR':.016,'WaterAbsorbG':.009,'WaterAbsorbB':.004,'CausticStrength':.22,'CausticScale':5,'ToonBands':0}.items():cam['wf_'+key]=value
bpy.data.objects['Matte']['wf_Matte Type']='Color';bpy.data.objects['Matte']['wf_Background Color']=0x09141e
room=bpy.data.objects['Room'];room.location=(0,0,0);room['wf_original_bbox']=(-25,-30,-6,25,10,18);room['wf_had_authored_bbox']=True
# One SeaStarsSettings object carries the nine live settings (docs/plans/2026-11-20-sea-stars-settings.md),
# placed the way aquarium_tanks/generate.py places PlantedTankSettings. The director reads it with property@.
settings=bpy.data.objects.new('SeaStarsSettings',None)
bpy.context.scene.collection.objects.link(settings)
settings['wf_schema_path']=str(repo/'wfsource/source/oas/seastarssettings.oad')
settings['wf_Model Type']='None';settings['wf_Mass']=0.0
settings['wf_original_bbox']=(-.1,-.1,-.1,.1,.1,.1);settings['wf_had_authored_bbox']=True
catalog=json.loads(subprocess.check_output([str(repo/'wftools/wf_attr_edit/target/release/catalog'),settings['wf_schema_path']],text=True))
settings_fields={f['key']:f['index'] for f in catalog['fields'] if f['width']}
assert all(label in settings_fields for label in controller.FIELD_LABELS.values()),settings_fields
objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices={o.name:i+1 for i,o in enumerate(objects)}
player['wf_Script']=controller.player()+'\nst-tick\n'
bpy.data.objects['Director']['wf_Script']=controller.director(indices,settings_fields) if not a.empty else f'{indices["cs_wide"]} INDEXOF_CAMSHOT write-mailbox\n'
triangles={n:sum(len(f)-2 for f in m.faces) for n,m in static.items()}
assert len(static)<=cfg.STATIC_GROUPS_MAX and sum(triangles.values())<=cfg.STATIC_TRIANGLES_MAX
(out/'actor-map.json').write_text(json.dumps(dict(level='aquarium_sea_stars',actors=indices,indices=indices,static_triangles=triangles,
    animated_triangles={} if a.empty else {n:sum(len(f)-2 for f in meshes[k].faces) for n,k,_ in animals},
    residents=[dict(name=n,kind=k,position=pos) for n,k,pos in cfg.RESIDENTS],mailboxes=controller.CELLS,empty=a.empty),indent=2)+'\n')
bpy.ops.wf.export_level(filepath=str(out/'aquarium_sea_stars.lev'))
if not a.empty:
    for kind in cfg.SPECIES:stars.bind(out/('star_'+kind+'.iff'),kind,dfrm_chunk)
if a.preview:
    # Blender samples images bottom-up; WF atlas coordinates are top-down.
    for obj in bpy.context.scene.objects:
        if obj.get('wf_Visibility Mailbox') == 0 or obj.get('wf_Model Type') == 'None': obj.hide_render=True
        if obj.type == 'MESH' and obj.data.uv_layers.active:
            for uv in obj.data.uv_layers.active.data: uv.uv.y = 1 - uv.uv.y
    cd=bpy.data.cameras.new('Preview');camera=bpy.data.objects.new('Preview',cd);bpy.context.scene.collection.objects.link(camera)
    camera.location=(0,-17,10);camera.rotation_euler=(Vector((0,0,1.1))-camera.location).to_track_quat('-Z','Y').to_euler();cd.lens=45
    bpy.context.scene.camera=camera
    ld=bpy.data.lights.new('PreviewLight','AREA');ld.energy=2600;ld.shape='DISK';ld.size=8
    light=bpy.data.objects.new('PreviewLight',ld);bpy.context.scene.collection.objects.link(light);light.location=(-3,-4,9)
    light.rotation_euler=(Vector((0,0,0))-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.scene.world=bpy.data.worlds.new('PreviewWorld');bpy.context.scene.world.color=(.18,.23,.27)
    sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.samples=24
    sc.render.resolution_x=1440;sc.render.resolution_y=900;sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG';sc.render.filepath=str(a.preview);bpy.ops.render.render(write_still=True)

if a.art_dir:
    from art import build_review
    build_review(repo,out,a.art_dir.resolve(),mode=a.art_mode)
