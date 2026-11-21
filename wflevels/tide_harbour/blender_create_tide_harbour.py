#!/usr/bin/env python3
"""Build the Tide Harbour level (plan docs/plans/2026-11-21-tide-harbour-clock.md, Phase 2).

Built from the baseline toolkit's way (plan Q10, wflevels/baseline/generate.py): an empty scene, every
actor created from its current OAD with the schema's defaults seeded and the level's values set
explicitly, no Snowgoons import. Every moving piece is an actor the director poses from the date and
the time; the sky, banks, pier, houses, tower and dial are static. The dial's Thai and Roman numerals
are drawn from fonts here: the Thai digits from Noto Sans Thai, which the Blender package ships in
its datafiles (checked: it is in the container image, so docker/Dockerfile.blender needs no change).

Run through build.sh, in the Blender container. Writes wflevels/tide_harbour/tide_harbour.lev, the
per-mesh .iff files and actor-map.json.
"""
import json
import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / 'wftools'))
sys.path.insert(0, str(HERE))
import wf_blender  # noqa: E402
import wf_core  # noqa: E402
from wf_blender.export_level import export_scene_to_lev, _seed_defaults  # noqa: E402

import forth  # noqa: E402
import parts  # noqa: E402
import timeline as tl  # noqa: E402

TAG = '[tide-harbour]'
OAS = REPO / 'wfsource/source/oas'
REFERENCE = tl.parse_when('2026-11-21T12:00:00')     # the pose the level is built in: noon, so the authored colours are the day's
THAI_FONT = Path('/usr/lib/blender/datafiles/fonts/NotoSansThai-VariableFont_wdth,wght.woff2')
THAI = ['๑๒', '๑', '๒', '๓', '๔', '๕', '๖', '๗', '๘', '๙', '๑๐', '๑๑']     # 12 at the top, then clockwise
ROMAN = ['XII', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI']
LIGHT_B, LIGHT_C = 45.0, 90.0          # degrees: the light travels toward +y and down at 45, so tops and camera-facing fronts light alike
DIRECTIONAL, AMBIENT = 0.78, 0.45      # top = front = 0.45 + 0.78 sin 45 = 1.0; sides 0.45
MATERIALS = {}


def material(key):
    if key not in MATERIALS:
        mt = bpy.data.materials.new('th-' + key)
        mt.use_nodes = True
        # the exporter truncates (int(c * 255)), so author the byte's centre: the level's colour is then exactly the
        # byte the director writes by day, and SetMaterialColor sees no change (the mesh stays baked)
        rgb = tuple((tl.byte(c) + 0.5) / 255.0 for c in parts.day_colour(key)) + (1.0,)
        bsdf = next(n for n in mt.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        bsdf.inputs['Base Color'].default_value = rgb
        mt.diffuse_color = rgb
        MATERIALS[key] = mt
    return MATERIALS[key]


def blender_mesh(mesh):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata(mesh.vertices, [], mesh.faces)
    keys = mesh.material_keys()
    for key in keys:
        data.materials.append(material(key))
    for poly, key in zip(data.polygons, mesh.colors):
        poly.material_index = keys.index(key)
    data.update()
    return data


def actor(name, cls, data=None, pos=(0.0, 0.0, 0.0), fields=None, bounds=None):
    """One actor from its OAD: schema defaults seeded, then this level's values (the baseline's recipe)."""
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS / (cls + '.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    values = {'Mobility': 'Anchored', 'Mass': 0.0, 'Model Type': 'Mesh' if data else 'None',
              'Visibility Mailbox': 1 if data else 0, 'Script': '', 'Script Controls Input': 'False',
              'Moves Between Rooms': 'False', 'Number Of Local Mailboxes': 0}
    values.update(fields or {})
    for key, value in values.items():
        obj['wf_' + key] = value
    if data:
        filename = name + '.iff'
        assert len(filename) <= 30, filename
        obj['wf_Mesh Name'] = filename
        obj['wf_original_mesh_name'] = filename
    box = bounds or ((-.05, -.05, -.05, .05, .05, .05) if not data else None)
    if box:
        obj['wf_original_bbox'] = tuple(box)
        obj['wf_had_authored_bbox'] = True
    return obj


def mesh_actor(mesh, cls='platform', pose=None, visibility=1):
    obj = actor(mesh.name, cls, blender_mesh(mesh), fields={'Visibility Mailbox': visibility})
    if pose is not None:
        obj.location = (pose.x, pose.y, pose.z)
        obj.rotation_euler = (pose.a * math.tau, pose.b * math.tau, pose.c * math.tau)
        obj.scale = (pose.sx, pose.sy, pose.sz)
    return obj


def numerals(name, texts, font, height):
    """The twelve numerals on the dial as one mesh facing -y, each centred on its hour, the tallest `height` high."""
    glyphs = []
    for k, text in enumerate(texts):
        curve = bpy.data.curves.new(f'{name}_{k}', type='FONT')
        curve.body = text
        if font is not None:
            curve.font = font
        curve.size = 1.0
        curve.align_x = 'CENTER'
        curve.align_y = 'CENTER'
        curve.offset = 0.035                      # embolden: the digits must read across a room (D8)
        curve.resolution_u = 3                    # few faces: the outlines are a metre high and seen from 40 m
        obj = bpy.data.objects.new(f'{name}_{k}', curve)
        bpy.context.scene.collection.objects.link(obj)
        glyphs.append(obj)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    shapes = []
    for obj in glyphs:
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
        verts = [tuple(v.co) for v in me.vertices]
        faces = [tuple(p.vertices) for p in me.polygons]
        assert faces, f'{obj.name}: the font gave no outline for {obj.data.body!r}'
        shapes.append((verts, faces))
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(me)
    tallest = max(max(v[1] for v in verts) - min(v[1] for v in verts) for verts, _f in shapes)
    s = height / tallest
    radius = tl.DIAL_R * 0.72
    cx, y, cz = tl.DIAL
    m = parts.Mesh(name)
    for k, (verts, faces) in enumerate(shapes):
        a = k / 12.0 * math.tau
        ox, oz = cx + radius * math.sin(a), cz + radius * math.cos(a)
        mx = (max(v[0] for v in verts) + min(v[0] for v in verts)) / 2
        my = (max(v[1] for v in verts) + min(v[1] for v in verts)) / 2
        base = len(m.vertices)
        # (x, y, 0) on the text plane, normal +z, becomes (x, -0.05, y): a quarter turn about x, so the normal is -y
        m.vertices.extend((ox + (vx - mx) * s, y - 0.05, oz + (vy - my) * s) for vx, vy, _vz in verts)
        for f in faces:
            m.faces.append(tuple(base + i for i in f))
            m.colors.append('ink')
    from clock_mesh import face_normal
    assert all(face_normal([m.vertices[i] for i in f])[1] < 0 for f in m.faces), f'{name}: a numeral face looks away from the camera'
    return m


bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 1

day, sod = REFERENCE
poses = tl.all_poses(day, sod)

# the core, explicitly (wflevels/baseline/docs/scene-contract.md)
actor('Level', 'levelobj')
actor('Room', 'room', bounds=tl.ROOM)
director = actor('Director', 'director')
actor('Player', 'player', pos=(-15.0, -9.5, tl.DECK_Z + 1.0))
lx, ly, lz = tl.LOOK_AT
cam = poses['cs_wide']
actor('Camera', 'camera', pos=(cam.x, cam.y, cam.z), fields={
    'Mobility': 'Camera', 'Moves Between Rooms': 'True',
    # fog explicitly (the guides): none inside the scene; it starts past the farthest sky corner
    'FoggingColor': 0x101828, 'FoggingStartDistance': 900.0, 'FoggingCompleteDistance': 1000.0})
actor('LookAt', 'target', pos=(lx, ly, lz))
actor('cs_wide', 'camshot', pos=(cam.x, cam.y, cam.z), fields={
    'Follow': 'LookAt', 'Target': 'LookAt', 'Track Object': 'LookAt', 'Rotation': 'Fixed',
    'Position X': 'Absolute', 'Position Y': 'Absolute', 'Position Z': 'Absolute',
    'Hither': 1.0, 'Yon': 600.0, 'FOV': 50.0, 'Pan Time In Seconds': 0.0})
for name, kind, rgb in (('SunLight', 'Directional', (DIRECTIONAL,) * 3), ('AmbientLight', 'Ambient', (AMBIENT,) * 3)):
    light = actor(name, 'light', fields=dict(lightType=kind, lightRed=rgb[0], lightGreen=rgb[1], lightBlue=rgb[2]))
    # Measured 2026-11-21 (Tide Harbour spike, finding 2): a directional light travels along (cos B cos C, cos B sin C, -sin B)
    light.rotation_euler = (0.0, math.radians(LIGHT_B), math.radians(LIGHT_C))
actor('Background', 'matte', fields={'Matte Type': 'Color', 'Background Color': 0x101828})

# static scenery, then the toggled statics, then the moving actors (each group contiguous)
for mesh in parts.static_meshes():
    mesh_actor(mesh, 'statplat')
for mesh in parts.toggled_static_meshes():
    mesh_actor(mesh, 'platform', visibility=tl.VIS[parts.VISIBLE_STATICS[mesh.name]])
assert THAI_FONT.is_file(), f'{THAI_FONT}: the Thai font is missing from this Blender (it ships in the blender package)'
thai = bpy.data.fonts.load(str(THAI_FONT))
mesh_actor(numerals('numerals_thai', THAI, thai, 0.95), 'platform', visibility=tl.VIS['numerals_thai'])
mesh_actor(numerals('numerals_roman', ROMAN, None, 0.70), 'platform', visibility=tl.VIS['numerals_roman'])
for name, mesh in parts.all_meshes().items():
    group = parts.visibility_group(name)
    mesh_actor(mesh, 'platform', poses[name], visibility=tl.VIS[group] if group else 1)

objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name: i + 1 for i, o in enumerate(objects)}
for prefix, count in (('bar_', tl.N_BARS), ('lantern_', len(tl.LANTERNS)), ('glint_', len(tl.GLINTS))):
    names = [f'{prefix}{k:02d}' if prefix == 'bar_' else f'{prefix}{k}' for k in range(count)]
    for a, b in zip(names, names[1:]):
        assert indices[b] - indices[a] == 1, f'{a} and {b} must be contiguous: the director loops over them'
director['wf_Script'] = forth.director_script(indices)

(HERE / 'actor-map.json').write_text(json.dumps(dict(indices=indices, reference=list(REFERENCE)), indent=1) + '\n')
posed = len(parts.all_meshes()) + 2
print(f'{TAG} {len(objects)} actors ({posed} posed by the director, budget 150)')
ok, msg = export_scene_to_lev(bpy.context, str(HERE / 'tide_harbour.lev'))
assert ok, msg
print(f'{TAG} {msg}')
print(f'{TAG} done')
