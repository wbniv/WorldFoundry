"""Export the Tulpenkade model, clock director and actor map in one pass."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OAS = ROOT/'wfsource/source/oas'
sys.path[:0] = [str(ROOT/'wftools'), str(HERE)]
from town import build
from director import script, ROUTE
from materials import SIZE, pixels, uv_material
import wf_blender
import wf_core
from wf_blender.export_level import _seed_defaults

bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()
image=bpy.data.images.new('quay.tga',width=SIZE,height=SIZE,alpha=False)
image.pixels.foreach_set(pixels())
image.filepath_raw=str(HERE/'quay.tga')
image.file_format='TARGA_RAW'
image.save()
material=bpy.data.materials.new('Tulpenkade')
material.use_nodes=True
tex=material.node_tree.nodes.new('ShaderNodeTexImage')
tex.image=image
shader=material.node_tree.nodes.get('Principled BSDF')
material.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
material['wf_double_sided']=True


def actor(name, cls, at=(0,0,0), data=None, bounds=None, **fields):
    obj=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location=at
    schema=OAS/(cls+'.oad')
    obj['wf_schema_path']=str(schema)
    _seed_defaults(obj,wf_core.load_schema(str(schema)))
    values={'Mobility':'Anchored','Model Type':'Mesh' if data else 'None','Mass':0.,
            'Visibility Mailbox':1,'Moves Between Rooms':'False','Script':'',
            'Number Of Local Mailboxes':0,'Script Controls Input':'False'}
    for k,v in {**values,**fields}.items():
        obj['wf_'+k]=v
    if data:
        obj['wf_Mesh Name']=obj['wf_original_mesh_name']=name+'.iff'
    else:
        obj['wf_original_bbox']=bounds or (-.05,-.05,-.05,.05,.05,.05)
        obj['wf_had_authored_bbox']=True
    return obj


actor('Level','levelobj')
actor('Room','room',bounds=(-32,-32,-4,32,32,25))
director=actor('Director','director')
actor('Player','player',(0,2,.7),**{'Visibility Mailbox':0})
eye=ROUTE[0][:3]
actor('Camera','camera',eye,**{'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':100.,'FoggingCompleteDistance':150.})
actor('LookAt','target',ROUTE[0][3:])
actor('cs_wide','camshot',eye,**{'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed',
      'Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':.12,'Yon':95.,'FOV':52.,'Pan Time In Seconds':0.})
actor('Ambient','light',lightType='Ambient',lightRed=.64,lightGreen=.63,lightBlue=.62)
sun=actor('Sun','light',lightType='Directional',lightRed=.78,lightGreen=.76,lightBlue=.69)
sun.rotation_euler=(0,math.radians(40),math.radians(72))
actor('Sky','matte',**{'Matte Type':'Color','Background Color':0x869d9d})
holder=actor('DutchCuckooVillageSettings','dutchcuckoovillagesettings',**{'Editor Label':'Dutch Cuckoo Village'})
from clearance import check
models=build().models
check(models)
for name,(m,at,cell) in models.items():
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(m.vertices,[],m.faces)
    mesh.update()
    mesh.materials.append(material)
    uv=mesh.uv_layers.new(name='UVMap')
    for poly,color in zip(mesh.polygons,m.colors):
        # Project along the dominant normal to retain detail on roofs and façades.
        axes=sorted(range(3),key=lambda j:abs(poly.normal[j]))[:2]
        axes.sort()
        coords=[tuple(m.vertices[mesh.loops[i].vertex_index][j] for j in axes) for i in poly.loop_indices]
        low=tuple(map(min,zip(*coords)))
        high=tuple(map(max,zip(*coords)))
        for i,p in zip(poly.loop_indices,coords):
            u,v=((p[j]-low[j])/max(.0001,high[j]-low[j]) for j in (0,1))
            atlas_u,atlas_v=uv_material(color,u,v)
            # textile writes rows in image order; the runtime addresses row zero at the top.
            uv.data[i].uv=(atlas_u,1-atlas_v)
    actor(name,'platform',at,mesh,**{'Visibility Mailbox':cell})
indices={obj.name:i for i,obj in enumerate(bpy.context.scene.objects,1)}
figs=[indices['tower_figure_'+str(i)] for i in range(1,5)]
assert figs==list(range(figs[0],figs[0]+4))
catalog=json.loads(subprocess.check_output([ROOT/'wftools/wf_attr_edit/target/release/catalog',holder['wf_schema_path']],text=True))
fields={f['key']:f['index'] for f in catalog['fields'] if f['width']}
director['wf_Script']=script(indices,fields)
(HERE/'actor-map.json').write_text(json.dumps({'indices':indices},indent=2)+'\n')
bpy.ops.wf.export_level(filepath=str(HERE/'dutch_cuckoo_village.lev'))

# A Blender reference makes material and camera comparisons with the engine repeatable.
if os.environ.get('TULPENKADE_REVIEW'):
    from mathutils import Vector
    from director import STILL
    scene=bpy.context.scene
    for o in scene.objects:
        if o.type=='MESH':
            for loop in o.data.uv_layers.active.data:
                loop.uv.y=1-loop.uv.y
        if o.get('wf_Visibility Mailbox',1)!=1:
            o.hide_render=True
    scene.render.engine='CYCLES'
    scene.cycles.samples=5
    scene.world=bpy.data.worlds.new('Overcast sky')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.52,.64,.67,1)
    data=bpy.data.lights.new('Daylight','SUN')
    data.energy=2.4
    light=bpy.data.objects.new('Daylight',data)
    scene.collection.objects.link(light)
    light.rotation_euler=(math.radians(34),math.radians(-25),math.radians(-12))
    data=bpy.data.cameras.new('Aerial')
    data.lens=26
    camera=bpy.data.objects.new('Review camera',data)
    scene.collection.objects.link(camera)
    scene.camera=camera
    camera.location=STILL[:3]
    camera.rotation_euler=(Vector(STILL[3:])-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x,scene.render.resolution_y=960,540
    scene.render.resolution_percentage=100
    scene.render.filepath=os.environ['TULPENKADE_REVIEW']
    bpy.ops.render.render(write_still=True)
