"""Run in Blender with the saved master open, validating delivered source assets."""
import json
from pathlib import Path
import bpy
bpy.data.orphans_purge(do_recursive=True)
sc=bpy.context.scene
required={'BlueStar':20,'ChipOne':20,'FromiaOne':20,'SandOne':20,'Brittle':80,'Cushion':0}
report={'status':'PASS','source':bpy.data.filepath,'species':{},'packed_textures':[],
        'actions':sorted(a.name for a in bpy.data.actions),
        'scope':'Source-asset verification only; gameplay/device acceptance pending.'}
for name,count in required.items():
    obj=bpy.data.objects[name]
    assert obj.type=='MESH' and len(obj.data.polygons)>0
    mods=[m for m in obj.modifiers if m.type=='ARMATURE']
    if count:
        assert len(mods)==1 and len(mods[0].object.data.bones)==count,name
        assert len(obj.vertex_groups)==count,name
    else:assert not mods,name
    assert obj.get('scientific_name'),name
    report['species'][name]={'scientific':obj['scientific_name'],'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),'bones':count}
for image in bpy.data.images:
    if image.source=='FILE':
        assert image.packed_file is not None,image.name
        assert tuple(image.size)==(512,512),image.size
        report['packed_textures'].append(image.name)
assert report['packed_textures']
assert {'linckia_glide','linckia_lead','linckia_corner','linckia_reach','brittle_row','brittle_hide','cushion_puff'}<=set(report['actions'])
skeleton=next(m.object for m in bpy.data.objects['BlueStar'].modifiers if m.type=='ARMATURE')
for clip in ('linckia_lead','linckia_corner','linckia_reach'):
    skeleton.animation_data.action=bpy.data.actions[clip];sc.frame_set(31)
    assert all(sum(v*v for v in skeleton.pose.bones[f'arm{i+1}.1'].rotation_euler)<1e-10 for i in range(5)),clip
skeleton.animation_data.action=None
for bone in skeleton.pose.bones:bone.rotation_euler=(0,0,0)
sc.frame_set(1)
brittle=bpy.data.objects['Brittle']
rig=next(m.object for m in brittle.modifiers if m.type=='ARMATURE')
assert rig.animation_data.action and rig.animation_data.action.name=='brittle_hide'
bpy.context.view_layer.update()
evaluated=brittle.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
assert max((a.co-b.co).length for a,b in zip(evaluated.vertices,brittle.data.vertices))>.25,'Brittle resting pose is still radial'
report['brittle_curled_rest_pose']=True
for name in ('sea_shell','sea_rocks','sea_grass','sea_ledge'):assert bpy.data.objects.get(name)
for name in ('BlueStar','ChipOne','FromiaOne','SandOne','Brittle','Cushion'):
    assert not bpy.data.objects[name].hide_render,name
for obj in sc.objects:
    if obj.get('wf_Visibility Mailbox')==0 or obj.get('wf_Model Type')=='None':obj.hide_set(True)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
out=Path(bpy.data.filepath).parents[2]/'docs/reference/sea-stars-art/verification.json'
out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
