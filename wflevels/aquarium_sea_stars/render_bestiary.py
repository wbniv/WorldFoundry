"""Render three neutral orthographic views per Sea Stars species from the saved master."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from config import SPECIES
import brittle
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
blend=HERE/'sea_stars_assets.blend'
bpy.ops.wm.open_mainfile(filepath=str(blend))
sc=bpy.context.scene
for obj in sc.objects:
    if obj.type=='MESH':obj.hide_render=True
sc.render.engine='CYCLES';sc.cycles.samples=12;sc.cycles.use_denoising=True
sc.render.threads_mode='FIXED';sc.render.threads=4
sc.render.resolution_x=600;sc.render.resolution_y=440;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG'
sc.world.use_nodes=True
sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.40,.43,.42,1)
sc.world.node_tree.nodes['Background'].inputs[1].default_value=.65
camera=sc.camera;camera.data.type='ORTHO'
objects={'linckia':'BlueStar','chip':'ChipOne','fromia':'FromiaOne','sand':'SandOne','brittle':'Brittle','cushion':'Cushion'}
manifest={'source_blend':'wflevels/aquarium_sea_stars/sea_stars_assets.blend','source_sha256':hashlib.sha256(blend.read_bytes()).hexdigest(),'species':[],'representation':'Neutral views of the authored 3D models and materials; runtime acceptance remains pending.'}
for kind,name in objects.items():
    obj=bpy.data.objects[name];obj.hide_render=False;obj.hide_set(False)
    obj.location=(0,0,0);obj.rotation_euler=(0,0,0);obj.scale=(1,1,1)
    for modifier in obj.modifiers:
        if modifier.type=='ARMATURE':
            rig=modifier.object;rig.location=(0,0,0);rig.rotation_euler=(0,0,0)
            rig.animation_data.action=None
            for bone in rig.pose.bones:bone.rotation_euler=(0,0,0)
            if kind=='brittle':brittle.apply_pose(rig)
    camera.data.ortho_scale=SPECIES[kind]['radius']*2.40*(600/440)
    images={}
    for view,pos in (('dorsal',(0,0,4)),('side',(0,-4,.12)),('oral',(0,0,-4))):
        camera.location=pos;camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
        path=out/f'{kind}-{view}.png';sc.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        images[view]={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    obj.hide_render=True
    manifest['species'].append({'kind':kind,'object':name,'scientific':SPECIES[kind]['scientific'],'images':images})
    print('Bestiary views ready:',kind,flush=True)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
