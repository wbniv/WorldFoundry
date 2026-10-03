"""Round-trip actual Jelly materials and reject malformed OPAC chunks."""
from pathlib import Path
import struct
import tempfile
import bpy
import addon_utils

ROOT = Path(__file__).resolve().parents[2]
LEVEL = ROOT/'wflevels/aquarium_blue_shrimp'
addon_utils.enable('wf_blender', default_set=False, persistent=False)
from wf_blender.export_level import (_load_mesh_iff, _make_blender_material,
                                     _write_mesh_iff, _write_iff_chunk, _read_iff_chunks)

with tempfile.TemporaryDirectory(prefix='shrimp-opacity-') as tmp:
    for path in sorted(LEVEL.glob('jelly_*.iff')):
        verts, faces, uvs, slots, materials = _load_mesh_iff(str(path))
        mesh = bpy.data.meshes.new(path.stem)
        mesh.from_pydata(verts, [], faces)
        uv = mesh.uv_layers.new(name='UVMap')
        for poly in mesh.polygons:
            poly.material_index = slots[poly.index]
            for loop in poly.loop_indices:
                uv.data[loop].uv = uvs[mesh.loops[loop].vertex_index]
        for info in materials:
            mesh.materials.append(_make_blender_material(path.stem, info,
                str(LEVEL/'blue_jelly.tga') if info['tex'] else None))
        obj = bpy.data.objects.new(path.stem, mesh)
        bpy.context.scene.collection.objects.link(obj)
        out = Path(tmp)/path.name
        assert _write_mesh_iff(obj, str(out))
        roundtrip = _load_mesh_iff(str(out))[-1]
        assert [m.get('opacity',1) for m in materials] == [m.get('opacity',1) for m in roundtrip]
    assert all('opacity' not in m for m in _load_mesh_iff(str(LEVEL/'shrimp_body.iff'))[-1])
    source = (LEVEL/'jelly_body.iff').read_bytes()
    chunks = _read_iff_chunks(source[8:])
    count = len(chunks['MATL'])//264
    invalid = [b'', struct.pack('<II',2,count)+bytes(count*4),
               struct.pack('<II',1,count+1)+bytes(count*4),
               struct.pack('<II',1,count)+struct.pack('<I',65537)*count]
    for payload in invalid:
        chunks['OPAC'] = payload
        out = Path(tmp)/'invalid.iff'
        out.write_bytes(_write_iff_chunk('MODL', b''.join(_write_iff_chunk(k,v) for k,v in chunks.items())))
        try:
            _load_mesh_iff(str(out))
        except ValueError:
            pass
        else:
            raise AssertionError('Malformed OPAC accepted')
print('PASS: five Jelly opacity round trips, legacy opaque default, four malformed metadata cases')
