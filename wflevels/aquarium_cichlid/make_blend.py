"""Import the generated OBJ into an editable Blender source file."""
import bpy
from pathlib import Path
p=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
vertices=[];uvs=[];faces=[]
for line in (p/'cichlid.obj').read_text().splitlines():
 a=line.split()
 if not a:continue
 if a[0]=='v':vertices.append(tuple(map(float,a[1:4])))
 elif a[0]=='vt':uvs.append(tuple(map(float,a[1:3])))
 elif a[0]=='f':faces.append([int(x.split('/')[0])-1 for x in a[1:]])
mesh=bpy.data.meshes.new('cichlid');mesh.from_pydata(vertices,[],faces);mesh.update()
obj=bpy.data.objects.new('cichlid',mesh);bpy.context.collection.objects.link(obj)
uv=mesh.uv_layers.new(name='UVMap')
for poly in mesh.polygons:
 for loop in poly.loop_indices:uv.data[loop].uv=uvs[mesh.loops[loop].vertex_index]
mat=bpy.data.materials.new('cichlid');mat.use_nodes=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(p/'cobalt.png'));tex.image.filepath='//cobalt.png'
mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
mesh.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(p/'cichlid.blend'))
