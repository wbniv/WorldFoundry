"""Render the actual single-mesh authoring asset and reference poses in Blender.
blender -b --python render_anemone_asset.py -- OUTPUT
"""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from anemone_model import write_textures,write_manifest,pose_vertex
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=True)
write_textures(out);model,metadata=write_manifest(out)
bpy.ops.wm.read_factory_settings(use_empty=True)
data=bpy.data.meshes.new('anemone');data.from_pydata(model.vertices,[],model.faces);data.update()
uv=data.uv_layers.new(name='UVMap')
for poly in data.polygons:
 poly.use_smooth=True
 for loop in poly.loop_indices:uv.data[loop].uv=model.uvs[data.loops[loop].vertex_index]
mat=bpy.data.materials.new('anemone tissue');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.58
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(out/'anemone_tissue.tga'))
mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color']);data.materials.append(mat)
obj=bpy.data.objects.new('Anemone · one visual mesh',data);bpy.context.collection.objects.link(obj)
obj.shape_key_add(name='Basis')
for name,phase,withdraw in [('flow-left',.25,0),('flow-right',.75,0),('withdrawn',0,1)]:
 key=obj.shape_key_add(name=name)
 for i,(p,rig) in enumerate(zip(model.vertices,model.rig)):
  key.data[i].co=pose_vertex(p,rig,phase=phase,withdraw=withdraw)
 key.value=0
# A connected rock shelf with an indentation around the foot.
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=12,location=(0,0,-.13))
rock=bpy.context.object;rock.name='Rock attachment surface';rock.scale=(1.6,1.1,.21)
rockmat=bpy.data.materials.new('weathered rock');rockmat.use_nodes=True;rockmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.16,.19,.17,1);rockmat.diffuse_color=(.16,.19,.17,1);rock.data.materials.append(rockmat)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Water backdrop');scene.world.color=(.025,.055,.065)
for name,pos,power in [('Key',(1,-2,3),380),('Fill',(-2,1,2),250)]:
 d=bpy.data.lights.new(name,'AREA');d.energy=power;d.size=3
 light=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(light);light.location=pos
 light.rotation_euler=(Vector((0,0,.5))-light.location).to_track_quat('-Z','Y').to_euler()
d=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',d);bpy.context.collection.objects.link(cam)
cam.location=(2.1,-3.4,2.0);cam.rotation_euler=(Vector((0,0,.58))-cam.location).to_track_quat('-Z','Y').to_euler()
d.type='ORTHO';d.ortho_scale=2.9;scene.camera=cam;scene.view_settings.view_transform='AgX'
scene.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'anemone.blend'))
for name in ['rest','flow-left','flow-right','withdrawn']:
 for key in obj.data.shape_keys.key_blocks:key.value=int(key.name==name)
 scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
print('Authoring preview complete; not runtime evidence')
