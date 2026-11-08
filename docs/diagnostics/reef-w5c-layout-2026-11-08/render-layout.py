"""Review renders of the reef's W5c layouts: cooked meshes placed where the Director puts them.

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/diagnostics/reef-w5c-layout-2026-11-08/render-layout.py -- OUTDIR LEVELDIR LAYOUTS.json [CASE ...]

LAYOUTS.json comes from layout-dump.py (the exported Director run in the zForth VM). An actor the
layout or the reactions wrote is placed at its dumped position and rotation (WF Euler a, b, c in
revolutions); any other actor keeps its cooked position. An actor shows when its visibility
mailbox is 1 or its cell is 1 in the dump. Wide camera = the engine's cs_wide. CPU Cycles, matte.
"""
import json
import math
import re
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
OUT, LEVEL, LAYOUTS = Path(argv[0]).resolve(), Path(argv[1]).resolve(), Path(argv[2]).resolve()
CASES = argv[3:]
OUT.mkdir(parents=True, exist_ok=True)
NAME = LEVEL.name


def lev_actors():
    text = (LEVEL / f'{NAME}.lev').read_text()
    out = {}
    for block in text.split("\t{ 'OBJ'")[1:]:
        name = re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)
        mesh = re.search(r'"Mesh Name" \} \{ \'STR\' "([^"]+)"', block)
        cls = re.search(r'"Class Name" \} \{ \'DATA\' "([^"]+)"', block).group(1)
        pos = re.search(r'"Position" \} \{ \'DATA\' (\S+)\(1\.15\.16\) (\S+)\(1\.15\.16\) (\S+)\(1\.15\.16\)', block)
        vis = re.search(r'"Visibility Mailbox" \} \{ \'DATA\' (\d+)l', block)
        out[name] = {'mesh': mesh.group(1) if mesh else None, 'class': cls,
                     'pos': tuple(float(pos.group(i)) for i in (1, 2, 3)) if pos else (0, 0, 0),
                     'vis': int(vis.group(1)) if vis else 1}
    return out


def read_iff(path):
    data = path.read_bytes()
    chunks, pos = {}, 8
    while pos + 8 <= len(data):
        tag, size = struct.unpack_from('<4sI', data, pos)
        chunks.setdefault(tag, data[pos + 8:pos + 8 + size])
        pos += 8 + ((size + 3) & ~3)
    verts = [struct.unpack_from('<iiIiii', chunks[b'VRTX'], i) for i in range(0, len(chunks[b'VRTX']), 24)]
    faces = [struct.unpack_from('<hhhh', chunks[b'FACE'], i)[:3] for i in range(0, len(chunks[b'FACE']), 8)]
    return verts, faces


_cache = {}


def mesh_data(file):
    if file not in _cache:
        verts, faces = read_iff(LEVEL / file)
        # Cooked faces can repeat an index after the exporter's welding; drop those, and build
        # per-corner UVs and colours with foreach_set (no per-loop Python access).
        faces = [f for f in faces if len(set(f)) == 3]
        data = bpy.data.meshes.new(file)
        data.from_pydata([(x / 65536, y / 65536, z / 65536) for _, _, _, x, y, z in verts], [], faces)
        corners = [i for f in faces for i in f]
        uv = data.uv_layers.new(name='UVMap')
        uv.data.foreach_set('uv', [c for i in corners for c in (verts[i][0] / 65536, 1 - verts[i][1] / 65536)])
        col = data.color_attributes.new(name='Col', type='FLOAT_COLOR', domain='CORNER')
        col.data.foreach_set('color', [c for i in corners for c in (((verts[i][2] >> 16) & 255) / 255,
                                                                    ((verts[i][2] >> 8) & 255) / 255,
                                                                    (verts[i][2] & 255) / 255, 1.0)])
        data.materials.append(MAT)
        data.update()
        _cache[file] = data
    return _cache[file]


def place(file, location, heading=0.0, name=None):
    obj = bpy.data.objects.new(name or file, mesh_data(file))
    obj.location = location
    obj.rotation_euler = (0, 0, heading * math.tau)
    bpy.context.scene.collection.objects.link(obj)
    return obj


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.seed = 20261108
scene.cycles.use_denoising = False
world = bpy.data.worlds.new('water')
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Color'].default_value = (0.05, 0.22, 0.38, 1)
bg.inputs['Strength'].default_value = 1.0
scene.world = world
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (.32, -.38, -.25)
scene.collection.objects.link(sun)
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam

MAT = bpy.data.materials.new('reef')
MAT.use_nodes = True
nodes, links = MAT.node_tree.nodes, MAT.node_tree.links
tex = nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(str(LEVEL / 'reef_atlas.tga'))
tex.interpolation = 'Closest'
attr = nodes.new('ShaderNodeVertexColor')
attr.layer_name = 'Col'
mix = nodes.new('ShaderNodeMix')
mix.data_type = 'RGBA'
mix.blend_type = 'MULTIPLY'
mix.inputs['Factor'].default_value = 1.0
links.new(tex.outputs['Color'], mix.inputs['A'])
links.new(attr.outputs['Color'], mix.inputs['B'])
bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 1.0
for key in ('Specular IOR Level', 'Specular'):
    if key in bsdf.inputs:
        bsdf.inputs[key].default_value = 0.0
red = bpy.data.materials.new('site')
red.use_nodes = True
r_bsdf = next(n for n in red.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
r_bsdf.inputs['Base Color'].default_value = (1, .05, .05, 1)
r_bsdf.inputs['Emission Color'].default_value = (1, .05, .05, 1)
r_bsdf.inputs['Emission Strength'].default_value = 2.0


actors = lev_actors()
index = {name: i + 1 for i, name in enumerate(actors)}
layouts = json.loads(LAYOUTS.read_text())


def wf_rotation(a, b, c):
    """Matrix34::ConstructEuler (row vectors) as a Blender rotation (column vectors)."""
    from mathutils import Matrix
    A, B, C = (v * math.tau for v in (a, b, c))
    sa, sb, sc, ca, cb, cc = math.sin(A), math.sin(B), math.sin(C), math.cos(A), math.cos(B), math.cos(C)
    rows = ((cb * cc, cb * sc, -sb),
            (sb * sa * cc - ca * sc, sb * sa * sc + ca * cc, cb * sa),
            (sb * ca * cc + sa * sc, sb * ca * sc - sa * cc, cb * ca))
    return Matrix([[rows[j][i] for j in range(3)] for i in range(3)]).to_4x4()


def shot(name, location, target, lens):
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.filepath = str(OUT / f'{name}.png')
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath)


from mathutils import Matrix
for case in CASES or list(layouts):
    for obj in [o for o in scene.objects if o.type == 'MESH']:
        bpy.data.objects.remove(obj, do_unlink=True)
    dump = layouts[case]
    cells = {int(k): v for k, v in dump['cells'].items()}
    for name, info in actors.items():
        if info['class'] == 'statplat' or not info['mesh'] or info['mesh'] == 'player_hull.iff':
            continue
        if not (info['vis'] == 1 or cells.get(info['vis'], 0) == 1):
            continue
        state = dump['actors'].get(str(index[name]))
        obj = place(info['mesh'], info['pos'], 0.0, name)
        if state and any(abs(v) > 1e-9 for v in state[:3]):
            obj.matrix_world = Matrix.Translation(state[:3]) @ wf_rotation(*state[3:6])
    shot(case, (0, -7.5, 2.75), (0, 0, 2.75), 17.6)
