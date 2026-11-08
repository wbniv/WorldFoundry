"""Review renders of the reef's rock-module kit (plan 2026-11-08 W5b), from the COOKED levels.

Usage (in the Blender container, from the repo root):
  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background \
    --python docs/diagnostics/reef-w5b-kit-2026-11-08/render-kit.py -- OUTDIR MODE LEVELDIR [PREFIX]

MODE
  fixed    every actor the Fixed layout shows (visibility 1 or a hero module's cell), at its
           cooked position: wide (the engine's cs_wide camera) and three-quarter views
  kit      each kit module alone, in a row, with its site-table points (red) and normals
  arrange  static arrangements with 2, 3 and 5 rocks (heroes first), headings 0 or 1/2
           revolution, attached life at pivot + offset, a few colony clumps on filler sites

Meshes, UVs and baked vertex colours come from the cooked .iff files and positions from the
.lev, so this shows what the level ships (CPU Cycles, matte; not the engine's lighting).
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
OUT, MODE, LEVEL = Path(argv[0]).resolve(), argv[1], Path(argv[2]).resolve()
PREFIX = argv[3] if len(argv) > 3 else MODE
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
amap = json.loads((LEVEL / 'actor-map.json').read_text())
modules = {m['name']: m for m in amap.get('kit', {}).get('modules', [])}   # absent before W5b
HERO_CELLS = {m['cell'] for m in modules.values() if m['role'] == 'hero'}


def shot(view, location, target, lens):
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.filepath = str(OUT / f'{PREFIX}-{view}.png')
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath)


def marker(p, n):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.045, location=p, segments=10, ring_count=6)
    bpy.context.active_object.data.materials.append(red)
    end = [p[i] + .3 * n[i] for i in range(3)]
    mid = [(p[i] + end[i]) / 2 for i in range(3)]
    bpy.ops.mesh.primitive_cylinder_add(radius=.012, depth=.3, location=mid, vertices=6)
    rod = bpy.context.active_object
    rod.rotation_euler = Vector(n).to_track_quat('Z', 'Y').to_euler()
    rod.data.materials.append(red)


def is_fixed_visible(info):
    return info['class'] != 'statplat' and info['mesh'] and info['mesh'] != 'player_hull.iff' and \
        (info['vis'] == 1 or info['vis'] in HERO_CELLS)


def module_pieces(module):
    m = modules[module]
    return m['pieces'] + m['attached']


def put_module(module, pivot, heading):
    """Place a module's pieces at pivot with heading (0 or 0.5 revolution)."""
    m = modules[module]
    origin = m['pivot'] if m['role'] == 'hero' else m['park']
    c, s = math.cos(heading * math.tau), math.sin(heading * math.tau)
    for piece in module_pieces(module):
        info = actors[piece]
        local = [info['pos'][i] - origin[i] for i in range(3)]
        rotated = (c * local[0] - s * local[1], s * local[0] + c * local[1], local[2])
        place(info['mesh'], tuple(pivot[i] + rotated[i] for i in range(3)), heading, piece)


if MODE == 'fixed':
    for name, info in actors.items():
        if is_fixed_visible(info):
            place(info['mesh'], info['pos'], 0.0, name)
    shot('wide', (0, -7.5, 2.75), (0, 0, 2.75), 17.6)
    shot('three-quarter', (-6.6, -6.2, 3.6), (-1.0, -.2, 1.6), 30)
elif MODE == 'kit':
    shell = actors['reef_shell']
    sand_z = .72
    for k, module in enumerate(modules):
        pivot = (-10.0 + 4.0 * k, 0.0, sand_z)
        put_module(module, pivot, 0.0)
        for site in modules[module]['sites']:
            marker([pivot[i] + site['p'][i] for i in range(3)], site['n'])
    floor = bpy.data.meshes.new('floor')
    floor.from_pydata([(-14, -4, sand_z), (14, -4, sand_z), (14, 4, sand_z), (-14, 4, sand_z)], [], [(0, 1, 2, 3)])
    sand_mat = bpy.data.materials.new('sand')
    sand_mat.use_nodes = True
    s_bsdf = next(n for n in sand_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    s_bsdf.inputs['Base Color'].default_value = (.62, .58, .48, 1)
    s_bsdf.inputs['Roughness'].default_value = 1.0
    floor.materials.append(sand_mat)
    bpy.context.scene.collection.objects.link(bpy.data.objects.new('floor', floor))
    shot('row', (0.0, -26.0, 6.0), (0.0, 0.0, 1.4), 30)
    for k, module in enumerate(modules):
        x = -10.0 + 4.0 * k
        shot(module, (x + .2, -5.4, 2.6), (x, 0.0, 1.3), 30)
else:
    place(actors['reef_shell']['mesh'], actors['reef_shell']['pos'], 0.0, 'reef_shell')
    for name in ('BoxfishVisual', 'HumbugOne', 'HumbugTwo'):
        place(actors[name]['mesh'], actors[name]['pos'], 0.0, name)
    sand = .72
    ARRANGEMENTS = {   # rocks: [(module, x, y, heading)]
        2: [('left', -2.3, .5, 0.0), ('arch', 2.2, .45, 0.5)],
        3: [('right', -3.3, .5, 0.5), ('arch', .1, .55, 0.0), ('left', 3.35, .45, 0.5)],
        5: [('left', -4.0, .55, 0.0), ('ledge', -1.55, -.1, 0.0), ('arch', .55, .6, 0.5),
            ('tall', 2.55, .2, 0.0), ('right', 4.45, .55, 0.0)],
    }
    count = int(argv[4]) if len(argv) > 4 else 3
    clump_names = [c['actor'] for c in amap['kit']['clumps']]
    used = 0
    for module, x, y, heading in ARRANGEMENTS[count]:
        put_module(module, (x, y, sand), heading)
        if modules[module]['role'] == 'filler':
            c, s = math.cos(heading * math.tau), math.sin(heading * math.tau)
            for site in modules[module]['sites'][:4]:
                if used >= len(clump_names):
                    break
                p, n = site['p'], site['n']
                world = (x + c * p[0] - s * p[1], y + s * p[0] + c * p[1], sand + p[2])
                obj = place(actors[clump_names[used]]['mesh'], world, 0.0, clump_names[used])
                obj.rotation_euler = Vector((c * n[0] - s * n[1], s * n[0] + c * n[1], n[2])).to_track_quat('Z', 'Y').to_euler()
                used += 1
    shot('wide', (0, -7.5, 2.75), (0, 0, 2.75), 17.6)
