"""Exercise the actual Blender exporter with a shared-position color seam."""
import struct
import sys
from pathlib import Path
import bpy

root, out, core_dir = (Path(p) for p in sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, str(core_dir))
sys.path.insert(0, str(root/'wftools/wf_blender'))
import export_level

mesh = bpy.data.meshes.new('baked-color-test')
mesh.from_pydata([(0,0,0), (1,0,0), (0,1,0), (1,1,0)], [], [(0,1,2), (1,3,2)])
uv = mesh.uv_layers.new(name='UVMap')
for loop in uv.data:
    loop.uv = (0, 0)
colors = mesh.color_attributes.new(name='ReefBake', type='BYTE_COLOR', domain='CORNER')
for polygon in mesh.polygons:
    for loop in polygon.loop_indices:
        colors.data[loop].color = (1,0,0,1) if polygon.index == 0 else (0,1,0,1)
obj = bpy.data.objects.new('baked-color-test', mesh)
mat = bpy.data.materials.new('baked-color-test')
mat.use_nodes = True
mat['wf_prelit'] = True
mat['wf_baked_vertex_color'] = True
mesh.materials.append(mat)

def chunks(path):
    data = path.read_bytes()
    result, pos = {}, 8
    while pos < len(data):
        tag, size = struct.unpack_from('<4sI', data, pos)
        result[tag] = data[pos+8:pos+8+size]
        pos += 8 + ((size+3) & ~3)
    return result

obj['wf_baked_vertex_color'] = 'ReefBake'
export_level._write_mesh_iff(obj, str(out/'colored.iff'))
parts = chunks(out/'colored.iff')
verts = [struct.unpack_from('<iiIiii', parts[b'VRTX'], i) for i in range(0, len(parts[b'VRTX']), 24)]
assert len(verts) == 6, verts
assert {v[2] for v in verts} == {0xff0000, 0x00ff00}, verts
assert struct.unpack_from('<i', parts[b'MATL'])[0] & (1|4|32) == (1|4|32)

del obj['wf_baked_vertex_color']
try:
    export_level._write_mesh_iff(obj, str(out/'missing.iff'))
    raise AssertionError('baked material accepted a missing color layer')
except ValueError as exc:
    assert 'requires a vertex color layer' in str(exc)
mat['wf_baked_vertex_color'] = False
mat['wf_prelit'] = False
export_level._write_mesh_iff(obj, str(out/'default.iff'))
parts = chunks(out/'default.iff')
verts = [struct.unpack_from('<iiIiii', parts[b'VRTX'], i) for i in range(0, len(parts[b'VRTX']), 24)]
assert len(verts) == 4
assert {v[2] for v in verts} == {0xffffff}
