"""Generate editable discus Blender mesh. Run under Blender in background."""
import bpy, os, json, sys
from pathlib import Path
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P))
from discus_geometry import mesh_data, uv as discus_uv  # the shared mesh source (also the Aquarium tank's)
variant=os.environ.get('DISCUS_PALETTE','wild-brown')
if variant not in json.loads((P/'palettes.json').read_text()):raise ValueError('unknown palette: '+variant)
bpy.ops.wm.read_factory_settings(use_empty=True)
verts,faces=mesh_data()
mesh=bpy.data.meshes.new('discus');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('discus',mesh);bpy.context.collection.objects.link(obj)
uv=mesh.uv_layers.new(name='UVMap')
for poly in mesh.polygons:
 for loop in poly.loop_indices:
  x,y,z=mesh.vertices[mesh.loops[loop].vertex_index].co
  # WF convention: V measured down from texture top.
  uv.data[loop].uv=discus_uv(x,z)
mat=bpy.data.materials.new('discus_turquoise');mat.use_nodes=True;mat['wf_prelit']=True;mat['wf_double_sided']=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(P/(variant+'.tga')));tex.image.filepath='//'+variant+'.tga'
uvnode=mat.node_tree.nodes.new('ShaderNodeUVMap');mapping=mat.node_tree.nodes.new('ShaderNodeMapping');mapping.inputs['Scale'].default_value=(1,-1,1);mapping.inputs['Location'].default_value=(0,1,0)
mat.node_tree.links.new(uvnode.outputs['UV'],mapping.inputs['Vector']);mat.node_tree.links.new(mapping.outputs['Vector'],tex.inputs['Vector']);mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color']);mesh.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(P/'discus.blend'))
print('DISCUS',len(verts),'vertices',len(faces),'faces')
