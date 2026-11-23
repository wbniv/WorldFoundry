"""Generate an editable asset scene and export a World Foundry test level.

Run with Blender from the repository root; see README.md. +Z is up, front is -Y.
"""
import json, math, random, sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'wftools'))
import wf_blender
import wf_blender.operators as wf_ops
import wf_core

random.seed(48)
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()
bpy.ops.wf.import_level(filepath=str(ROOT/'wflevels/snowgoons-blender/snowgoons-blender.lev'))
classes={'director':'Director','camera':'Camera','levelobj':'LevelObj','matte':'Matte','light':'SunLight','room':'Room','camshot':'cs_wide','target':'LookAt','player':'Player'}
seen=set()
for o in list(bpy.context.scene.objects):
    cls=Path(o.get('wf_schema_path','')).stem
    if cls not in classes or cls in seen:
        bpy.data.objects.remove(o,do_unlink=True); continue
    seen.add(cls); o.name=classes[cls]
    schema=ROOT/'wfsource/source/oas'/f'{cls}.oad'
    if schema.is_file():
        o['wf_schema_path']=str(schema); wf_ops._seed_defaults(o,wf_core.load_schema(str(schema)))
    o.location=(0,-20,1); o.rotation_euler=(0,0,0); o.scale=(1,1,1)
    o.hide_render=True; o['wf_Mass']=0.0; o['wf_Model Type']='None'; o['wf_Script']=''; o['wf_original_bbox']=(-.1,-.1,-.1,.1,.1,.1);o['wf_had_authored_bbox']=True
assert seen==set(classes),seen
bpy.data.objects['Room']['wf_Adjacent Room 1']=''
bpy.data.objects['Player']['wf_Tool A']=''

with bpy.data.libraries.load(str(HERE/'discus.blend'), link=False) as (source,target):
    target.objects=['discus']
obj=target.objects[0];bpy.context.collection.objects.link(obj)
obj['wf_Script']='\n'.join(line for line in (HERE/'swim.fth').read_text().splitlines() if not line.lstrip().startswith(chr(92)));obj['wf_schema_path']=str(ROOT/'wfsource/source/oas/platform.oad');obj['wf_Mobility']='Anchored';obj['wf_Model Type']='Mesh';obj['wf_Mass']=0.0;obj['wf_Visibility Mailbox']=1;obj['wf_Mesh Name']='discus.iff';obj['wf_original_mesh_name']='discus.iff'
# Enlarge the 0.2 m model for a visible, fixed orthographic-like review.
obj.scale=(10,10,10);bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);obj.select_set(False)
sun=bpy.data.objects['SunLight'];sun['wf_lightType']='Ambient'
for ch in ('Red','Green','Blue'):sun['wf_light'+ch]=1.0
look=bpy.data.objects['LookAt'];look.location=(0,0,0)
wide=bpy.data.objects['cs_wide'];wide.location=(.8,-2.8,.4)
for axis in 'XYZ':wide['wf_Position '+axis]='Absolute'
wide['wf_Rotation']='Fixed'
for key in ('Follow','Target','Track Object'):wide['wf_'+key]='LookAt'
bpy.data.objects['Camera'].location=wide.location
bpy.data.objects['Matte']['wf_Matte Type']='Color';bpy.data.objects['Matte']['wf_Background Color']=0x0b1115
bpy.data.objects['Player'].location=(0,-3,0)
bpy.data.objects['Room'].location=(0,0,0);bpy.data.objects['Room']['wf_original_bbox']=(-60,-60,-10,60,60,40)
bpy.ops.wf.export_level(filepath=str(HERE/'discus_asset.lev'))
print('DISCUS_EXPORT_OK')
