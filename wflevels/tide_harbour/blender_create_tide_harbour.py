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
import subprocess
import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / 'wftools'))
sys.path.insert(0, str(HERE))
import wf_blender  # noqa: E402
import wf_core  # noqa: E402
from wf_blender.export_level import export_scene_to_lev, _seed_defaults  # noqa: E402

import forth  # noqa: E402
import panel as pn  # noqa: E402
import panel_parts as pp  # noqa: E402
import parts  # noqa: E402
import timeline as tl  # noqa: E402

TAG = '[tide-harbour]'
OAS = REPO / 'wfsource/source/oas'
REFERENCE = tl.parse_when('2026-11-21T12:00:00')     # the pose the level is built in: noon, so the authored colours are the day's
STOP_SIZE, STOP_GAP = 0.016, 0.006      # the full stop after ม and กม: a square on the baseline, in metres
THAI_FONT = HERE / 'fonts' / 'NotoSansThai-Bold.ttf'      # static and bold: no `offset` embolden, which tears the thin Thai features (fonts/README.md)
THAI = ['๑๒', '๑', '๒', '๓', '๔', '๕', '๖', '๗', '๘', '๙', '๑๐', '๑๑']     # 12 at the top, then clockwise
ROMAN = ['XII', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI']
PANEL_DIGITS = '0123456789'                          # the river panel uses Arabic digits; Thai text keeps its own font
DRUM_DIGITS = {'h10': 3, 'h1': 10, 'm10': 6, 't1': 10, 't01': 10}     # how many digits a drum can show: hours tens 0-2, minute tens 0-5
LIGHT_B, LIGHT_C = 45.0, 90.0          # degrees: the light travels toward +y and down at 45, so tops and camera-facing fronts light alike
DIRECTIONAL, AMBIENT = 0.64, 0.55      # top = front = 0.55 + 0.64 sin 45 = 1.0; sides 0.55
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


def outlines(name, texts, font):
    """Each text's outline as triangles in the xy plane (size 1.0, facing +z): [(verts, faces)]."""
    glyphs = []
    for k, text in enumerate(texts):
        curve = bpy.data.curves.new(f'{name}_{k}', type='FONT')
        curve.body = text
        if font is not None:
            curve.font = font
        curve.size = 1.0
        curve.align_x = 'CENTER'
        curve.align_y = 'CENTER'
        # embolden: the digits must read across a room (D8). Thai text is already bold and is NOT offset: an offset curve self-intersects
        # on the thin loops of ๕ ๗ ๘ and the fill tears (bitten digits on cast1, 2026-11-22)
        curve.offset = 0.0 if (font is not None and Path(font.filepath).name == THAI_FONT.name) else 0.02
        curve.resolution_u = 3                    # few faces: the outlines are a metre high and seen from 40 m
        obj = bpy.data.objects.new(f'{name}_{k}', curve)
        bpy.context.scene.collection.objects.link(obj)
        glyphs.append(obj)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    shapes = []
    for obj in glyphs:
        me = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
        # triangulate here: a glyph's fill has concave n-gons, which the exporter's fan triangulation breaks
        # (the first build's numerals lost pieces of ๓ and ๙)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='EAR_CLIP')     # BEAUTY puts triangles outside a concave outline: bitten digits
        verts = [tuple(v.co) for v in bm.verts]
        bm.verts.index_update()
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        assert faces, f'{obj.name}: the font gave no outline for {obj.data.body!r}'
        shapes.append((verts, faces))
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(me)
    return shapes


def numerals(name, texts, font, height, max_width):
    """The twelve numerals on the dial as one mesh facing -y, each centred on its hour: one height for all (the
    tallest glyph `height` high), and any numeral wider than `max_width` scaled down to fit between its neighbours."""
    shapes = outlines(name, texts, font)
    tallest = max(max(v[1] for v in verts) - min(v[1] for v in verts) for verts, _f in shapes)
    s = height / tallest
    radius = tl.DIAL_R * 0.70
    cx, y, cz = tl.DIAL
    m = parts.Mesh(name)
    for k, (verts, faces) in enumerate(shapes):
        a = k / 12.0 * math.tau
        ox, oz = cx + radius * math.sin(a), cz + radius * math.cos(a)
        mx = (max(v[0] for v in verts) + min(v[0] for v in verts)) / 2
        my = (max(v[1] for v in verts) + min(v[1] for v in verts)) / 2
        k_s = min(s, max_width / (max(v[0] for v in verts) - min(v[0] for v in verts)))
        base = len(m.vertices)
        # (x, y, 0) on the text plane, normal +z, becomes (x, -0.05, y): a quarter turn about x, so the normal is -y
        m.vertices.extend((ox + (vx - mx) * k_s, y - 0.05, oz + (vy - my) * k_s) for vx, vy, _vz in verts)
        for f in faces:
            m.faces.append(tuple(base + i for i in f))
            m.colors.append('ink')
    from clock_mesh import face_normal
    assert all(face_normal([m.vertices[i] for i in f])[1] < 0 for f in m.faces), f'{name}: a numeral face looks away from the camera'
    return m


def panel_glyphs(meshes, font):
    """The river panel's glyphs, added to the meshes panel_parts draws: Arabic digits on the drums, the Thai unit label and
    the minute units' zero in the band's mask, the column's numerals, the scale bar's label and the map's place names.
    Every glyph is a flat outline facing -y, centred (or aligned) on its place in the part's own coordinates."""
    texts = ['ม', 'กรุงเทพฯ', 'ปากน้ำ', 'อ่าวไทย', 'กม']
    shapes = dict(zip(PANEL_DIGITS, outlines('pg_digits', PANEL_DIGITS, None)))
    shapes.update(zip(texts, outlines('pg_thai', texts, font)))
    # Preserve the original Thai-label scale independently of the new digit font.
    thai_metrics = outlines('pg_thai_metrics', '๐๑๒๓๔๕๖๗๘๙', font)
    em = pn.GLYPH_H / max(max(v[1] for v in verts) - min(v[1] for v in verts) for verts, _faces in thai_metrics)
    digit_em = pn.GLYPH_H / max(max(v[1] for v in shapes[d][0]) - min(v[1] for v in shapes[d][0]) for d in PANEL_DIGITS)
    # Fit the widest digit once, so narrow digits retain the same height and weight.
    widest_digit = max(max(v[0] for v in shapes[d][0]) - min(v[0] for v in shapes[d][0]) for d in PANEL_DIGITS)
    digit_em = min(digit_em, pn.WIN_W * 0.9 / widest_digit)
    added = []

    def put(mesh, text, x, z, scale=1.0, align='c', color='p_text', max_width=None, slot=None):
        verts, faces = shapes[text]
        k = (digit_em if text in PANEL_DIGITS else em) * scale
        x0, x1 = min(v[0] for v in verts), max(v[0] for v in verts)
        if max_width is not None:
            k = min(k, max_width / (x1 - x0))
        dx = {'c': -(x0 + x1) / 2, 'l': -x0, 'r': -x1}[align]
        my = (max(v[1] for v in verts) + min(v[1] for v in verts)) / 2
        base = len(mesh.vertices)
        flat = [(x + (vx + dx) * k, z + (vy - my) * k) for vx, vy, _vz in verts]
        # on a drum the glyph is carried to its ring slot (panel_parts.on_ring); anywhere else it is flat on the panel
        mesh.vertices.extend(pp.on_ring(px, pz, slot) if slot is not None else (px, 0.0, pz) for px, pz in flat)
        for f in faces:
            mesh.faces.append(tuple(base + i for i in f))
            mesh.colors.append(color)
        added.append((mesh.name, text))
        return max(x for x, _z in flat), z + (min(v[1] for v in verts) - my) * k          # the glyph's right edge and its baseline

    def stop(mesh, x_right, z_base, color='p_text'):
        """A full stop after a glyph: Noto Sans Thai has none (it would come out as the font's missing-glyph box), so it is a
        small square on the baseline, as the decimal point is."""
        pp._quad(mesh, x_right + STOP_GAP, z_base, x_right + STOP_GAP + STOP_SIZE, z_base + STOP_SIZE, color)

    for row in (0, 1):
        for name, count in DRUM_DIGITS.items():
            for k in range(count):
                put(meshes[f'panel_drum_{row}_{name}'], PANEL_DIGITS[k], 0.0, 0.0, max_width=pn.WIN_W * 0.9, slot=k)
        v = pn.row_v(row)
        xr, zb = put(meshes['panel_band_mask'], 'ม', pn.row_u('unit') - (STOP_GAP + STOP_SIZE) / 2, v, 0.55, max_width=0.095 - STOP_GAP - STOP_SIZE)
        stop(meshes['panel_band_mask'], xr, zb)
        put(meshes['panel_band_mask'], PANEL_DIGITS[0], pn.row_u('m1'), v, max_width=pn.WIN_W * 0.9)
    body = meshes['panel_col_body']
    for metres in (1, 2, 3):
        put(body, PANEL_DIGITS[metres], pn.COL_X - 0.026 - 0.075, pn.level_v(float(metres)), 0.42, color='p_ink')
    mid = pn.SCALE_X1 - pn.SCALE_KM * pn.M_PER_KM / 2.0                           # the scale bar's label, centred above it
    half = pn.SCALE_KM * pn.M_PER_KM / 2.0 - 0.004                                   # each half of the label stays within its half of the bar
    put(body, PANEL_DIGITS[int(pn.SCALE_KM)], mid - 0.004, pn.SCALE_V + 0.06, 0.32, 'r', 'p_ink', max_width=half * 0.6)
    xr, zb = put(body, 'กม', mid + 0.004, pn.SCALE_V + 0.06, 0.32, 'l', 'p_ink', max_width=half - STOP_GAP - STOP_SIZE)
    stop(body, xr, zb, 'p_ink')
    # The map's credit is not on the panel: the ODbL attribution lives in the settings form's read-only "About the map" row
    # (tideharboursettings.oas), added in the same change that took the line off the panel.
    river = meshes['panel_map']
    doc = json.loads(pp.CENTRELINE.read_text())
    hx, hz = pp.map_xy(doc['station_HD']['lon'], doc['station_HD']['lat'])
    mx, mz = pp.river_points()[0]
    put(river, 'กรุงเทพฯ', hx + pp.STATION_DX + 0.055, hz + 0.02, 0.42, 'l', 'p_ink')               # the tower's name, to its right, over the land
    lz = mz + 0.045                                                           # the mouth's name, left of the water at its height: glyphs and water share a plane
    west = min([x for poly in pp.outline()['polygons'] for x, z in (pp.map_xy(lo, la) for lo, la in poly['pts']) if abs(z - lz) < 0.05] or [mx - 0.07])
    put(river, 'ปากน้ำ', west - 0.02, lz, 0.40, 'r', 'p_ink')
    put(river, 'อ่าวไทย', mx - 0.25, mz - 0.20, 0.50, 'c', 'p_ink')                  # the gulf, below the ripples
    return added


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
# The settings object (plan D13): one TideHarbourSettings, no model and no mass, on the pier deck; the director reads
# its fields with property@ at the field indices the catalog tool reports (written into the script and actor-map.json).
settings = actor(tl.SETTINGS_ACTOR, 'tideharboursettings', pos=(-15.0, -9.5, tl.DECK_Z + 0.5),
                 fields={'Editor Label': 'Tide Harbour', 'Visibility Mailbox': 0})
catalog = json.loads(subprocess.check_output([str(REPO / 'wftools/wf_attr_edit/target/release/catalog'),
                                              settings['wf_schema_path']], text=True))
by_key = {f['key']: f for f in catalog['fields']}
fields = {label: by_key[label]['index'] for label in tl.FIELD_LABELS.values()}
assert all(by_key[label]['live'] for label in fields), 'every settings field must be live'

# static scenery, then the toggled statics, then the moving actors (each group contiguous)
for mesh in parts.static_meshes():
    mesh_actor(mesh, 'statplat')
for mesh in parts.toggled_static_meshes():
    mesh_actor(mesh, 'platform', visibility=tl.VIS[parts.VISIBLE_STATICS[mesh.name]])
assert THAI_FONT.is_file(), f'{THAI_FONT}: the Thai font is missing from the repo (wflevels/tide_harbour/fonts)'
thai = bpy.data.fonts.load(str(THAI_FONT))
mesh_actor(numerals('numerals_thai', THAI, thai, 1.0, 1.0), 'platform', visibility=tl.VIS['numerals_thai'])
mesh_actor(numerals('numerals_roman', ROMAN, None, 0.75, 1.4), 'platform', visibility=tl.VIS['numerals_roman'])
moving = parts.all_meshes()
glyphs = panel_glyphs(moving, thai)
print(f'{TAG} {len(glyphs)} panel glyphs')
for name, mesh in moving.items():
    group = parts.visibility_group(name)
    mesh_actor(mesh, 'platform', poses[name], visibility=tl.VIS[group] if group else 1)

# The exporter reads matrix_world, which Blender only recomputes on a depsgraph update: without this every actor
# placed after the last update exports at the origin (found by scripts/check-tide-harbour.py, 2026-11-21).
bpy.context.view_layer.update()
objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name: i + 1 for i, o in enumerate(objects)}
for prefix, count in (('bar_', tl.N_BARS), ('lantern_', len(tl.LANTERNS)), ('glint_', len(tl.GLINTS)), ('krathong_', tl.KRATHONG_MAX)):
    names = [f'{prefix}{k:02d}' if prefix == 'bar_' else f'{prefix}{k}' for k in range(count)]
    for a, b in zip(names, names[1:]):
        assert indices[b] - indices[a] == 1, f'{a} and {b} must be contiguous: the director loops over them'
director['wf_Script'] = forth.director_script(indices, fields)

(HERE / 'actor-map.json').write_text(json.dumps(dict(indices=indices, reference=list(REFERENCE), settings_fields=fields), indent=1) + '\n')
posed = len(parts.all_meshes()) + 2
print(f'{TAG} {len(objects)} actors ({posed} posed by the director, budget 150)')
ok, msg = export_scene_to_lev(bpy.context, str(HERE / 'tide_harbour.lev'))
assert ok, msg
print(f'{TAG} {msg}')
print(f'{TAG} done')
