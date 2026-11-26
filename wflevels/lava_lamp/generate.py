"""Author the lava lamp clock in Blender: a 1963-style Astro on a sideboard, wax that moves, the time in the base.

docs/plans/2026-11-26-lava-lamp.md. Run by build.sh in the Blender container:

    blender --background --python-exit-code 1 --python wflevels/lava_lamp/generate.py

Everything is authored in metres, then scaled 48x (lamp.SCALE: the smallest triangle keeps a sound normal). The
wax is one blob mesh with six shape keys (morph_rise, morph_fall, morph_squash, morph_neck, morph_wobble_a,
morph_wobble_b), shared by the eight blobs and the four merged meshes, and a pool mesh with four; the exporter writes
them as an MRPH chunk and the Morph deformer (E1) poses and tints them. The liquid, glass, wall glow and table light
carry an MRPH chunk with no targets: the director recolours them through the same deformer (D8). The director is
forth.py's script.
"""
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import bmesh
import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT / 'wftools'), str(HERE)]
import wf_blender  # noqa: E402
import wf_core  # noqa: E402
from wf_blender.export_level import _seed_defaults  # noqa: E402
import forth  # noqa: E402
import lamp as L  # noqa: E402
import shapes  # noqa: E402

OAS = ROOT / 'wfsource/source/oas'
SETTINGS_OAD = OAS / 'lavalampsettings.oad'
S = L.SCALE
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()


# ---------------------------------------------------------------- materials
def material(name, rgb=(1, 1, 1), baked=True, double=False, opacity=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    mat.diffuse_color = (*rgb, 1)
    mat['wf_prelit'] = True
    mat['wf_baked_vertex_color'] = baked
    mat['wf_double_sided'] = double
    if opacity < 1:
        mat['wf_opacity'] = opacity
    return mat


MATS = {
    'wax': material('wax'),
    'gold': material('gold'),
    'liquid': material('liquid', double=True),
    'glass': material('glass', double=True),
    'bulb': material('bulb', double=True, opacity=0.45),
    'room': material('room', double=True),
    'hole': material('hole', double=True),
}


# ---------------------------------------------------------------- actors
def actor(name, cls, data=None, pos=(0, 0, 0), fields=None, bounds=None):
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS / (cls + '.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    values = {'Mobility': 'Anchored', 'Mass': 0., 'Model Type': 'Mesh' if data else 'None',
              'Visibility Mailbox': 1 if data else 0, 'Script': '', 'Script Controls Input': 'False',
              'Moves Between Rooms': 'False', 'Number Of Local Mailboxes': 0}
    values.update(fields or {})
    for key, value in values.items():
        obj['wf_' + key] = value
    if bounds or not data:
        obj['wf_original_bbox'] = tuple(bounds or (-.05, -.05, -.05, .05, .05, .05))
        obj['wf_had_authored_bbox'] = True
    return obj


def mesh(name, verts, faces, shades, mat='room', keys=None, morph=False, mats=None):
    """A mesh with one shade (vertex colour, 0..1 RGB per vertex) layer and optional morph_ shape keys."""
    data = bpy.data.meshes.new(name)
    data.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    names = mats or [mat]
    for m in names:
        data.materials.append(MATS[m])
    data.update()
    layer = data.color_attributes.new('shade', 'BYTE_COLOR', 'CORNER')
    for loop in data.loops:
        c = shades[loop.vertex_index]
        # sRGB bytes as given: the shade is the colour byte / 255 the engine multiplies (color is linear)
        layer.data[loop.index].color_srgb = (*[max(0., min(1., v)) for v in c], 1.)
    if keys:
        obj = bpy.data.objects.new('_tmp_' + name, data)
        obj.shape_key_add(name='Basis')
        for kname, kverts in keys.items():
            key = obj.shape_key_add(name='morph_' + kname, from_mix=False)
            for i, v in enumerate(kverts):
                key.data[i].co = v
        bpy.data.objects.remove(obj)
    data['wf_morph'] = bool(morph or keys)
    return data


def finish(obj, data):
    obj['wf_baked_vertex_color'] = 'shade'
    if data.get('wf_morph'):
        obj['wf_morph'] = True
    obj['wf_Mesh Name'] = data.name + '.iff'
    obj['wf_original_mesh_name'] = data.name + '.iff'
    return obj


# ---------------------------------------------------------------- geometry helpers
def revolve(profile, segments, a0=0.0, a1=2 * math.pi, closed=True):
    """A surface of revolution about Z: profile = [(r, z)], from angle a0 to a1 (azimuth 0 faces the camera, -Y)."""
    verts, faces = [], []
    n = segments if closed else segments + 1
    for (r, z) in profile:
        for k in range(n):
            a = a0 + (a1 - a0) * k / segments
            verts.append((r * math.sin(a), -r * math.cos(a), z))
    for j in range(len(profile) - 1):
        for k in range(segments):
            k1 = (k + 1) % n if closed else k + 1
            a, b = j * n + k, j * n + k1
            c, d = (j + 1) * n + k1, (j + 1) * n + k
            faces.append((a, b, c, d))
    return verts, faces, n


def scaled(vs, s=S):
    return [(x * s, y * s, z * s) for (x, y, z) in vs]


# ---------------------------------------------------------------- the wax
def uv_sphere(seg=32, rings=20):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    verts = [tuple(v.co) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return verts, faces


def blob_mesh():
    """The unit wax blob (radius 1, centred: a sphere may rest on its middle) and its six morph targets."""
    verts, faces = uv_sphere()
    keys = {name: [fn(v) for v in verts] for name, fn in shapes.BLOB_TARGETS.items()}
    shades = [shapes.blob_shade(v) for v in verts]
    return mesh('blob', verts, faces, shades, mat='wax', keys=keys)


def pool_mesh():
    """The wax pool on the coil: a lens filling the globe's foot, base at z = 0 (it rests on the glass)."""
    R = L.globe_r(0.03) * L.GLOBE_H * 0.97
    H = L.GLOBE_H                       # heights below are fractions of the globe
    rings, seg = 8, 40
    profile = [(R * (1 - (j / rings) ** 1.0), 0.0) for j in range(rings + 1)]
    verts, faces = [], []
    verts.append((0, 0, 0))
    for j in range(1, rings + 1):
        r = R * (1 - j / (rings + 1))
        for k in range(seg):
            a = 2 * math.pi * k / seg
            verts.append((r * math.sin(a), -r * math.cos(a), 0))
    # rings ordered from outer (j=1) to inner (j=rings); the dome rises toward the middle
    base = [(x, y, H * (0.004 + 0.030 * (1 - (math.hypot(x, y) / R) ** 2))) for (x, y, _z) in verts]
    for j in range(rings - 1):
        for k in range(seg):
            a, b = 1 + j * seg + k, 1 + j * seg + (k + 1) % seg
            c, d = 1 + (j + 1) * seg + (k + 1) % seg, 1 + (j + 1) * seg + k
            faces.append((a, b, c, d))
    inner = 1 + (rings - 1) * seg
    for k in range(seg):
        faces.append((inner + k, inner + (k + 1) % seg, 0))
    # the underside: a flat disc under the outer ring
    under0 = len(base)
    base.append((0, 0, 0))
    for k in range(seg):
        x, y, _ = verts[1 + k]
        base.append((x, y, 0))
    for k in range(seg):
        faces.append((under0 + 1 + (k + 1) % seg, under0 + 1 + k, under0))
    for k in range(seg):
        faces.append((1 + k, under0 + 1 + k, under0 + 1 + (k + 1) % seg, 1 + (k + 1) % seg))

    def target(fn):
        return [(x, y, fn(math.hypot(x, y) / R, z)) if i < under0 else (x, y, z) for i, (x, y, z) in enumerate(base)]
    keys = {
        'mound': target(lambda d, z: z + H * 0.035 * max(0., 1 - d * d)),
        'tower': target(lambda d, z: z + H * 0.11 * math.exp(-(d * 3.2) ** 2)),
        'neck': target(lambda d, z: z + H * 0.05 * math.exp(-(d * 5.0) ** 2)),
        'dip': target(lambda d, z: z - H * 0.025 * max(0., 1 - d * d)),
    }
    shades = [(0.85 + 0.15 * (1 - math.hypot(x, y) / R),) * 3 for (x, y, _z) in base]
    keys = {k: scaled(v) for k, v in keys.items()}
    return mesh('pool', scaled(base), faces, shades, mat='wax', keys=keys)


# ---------------------------------------------------------------- the lamp
def gold_shade(a, h, top=1.0):
    """Gold lit by the lamp itself: warmer and brighter toward the globe, a highlight strip left of centre."""
    face = max(0.0, math.cos(a))
    strip = math.exp(-((a + 0.45) / 0.22) ** 2)
    v = (0.28 + 0.55 * face + 0.45 * strip) * (0.55 + 0.45 * h) * top
    return (min(1, v * 1.0), min(1, v * 0.74), min(1, v * 0.30))


def lamp_body():
    seg = 64
    parts_v, parts_f, shades = [], [], []

    def add(verts, faces, sh):
        o = len(parts_v)
        parts_v.extend(verts)
        parts_f.extend(tuple(i + o for i in f) for f in faces)
        shades.extend(sh)
    # base cone: lowest vertex at z = 0 (the mesh rests on the sideboard)
    prof = [(L.BASE_R0, 0.0), (L.BASE_R0 * 0.995, 0.004), (L.BASE_R1 + 0.002, L.BASE_H - 0.004), (L.BASE_R1, L.BASE_H)]
    v, f, n = revolve(prof, seg)
    sh = []
    for j, (_r, z) in enumerate(prof):
        for k in range(n):
            a = 2 * math.pi * k / seg
            a = a if a <= math.pi else a - 2 * math.pi
            sh.append(gold_shade(a, z / L.BASE_H))
    add(v, f, sh)
    # the collar the globe sits in
    prof = [(L.BASE_R1, L.BASE_H), (L.BASE_R1 * 0.93, L.BASE_H + 0.006), (L.globe_r(0) * L.GLOBE_H * 1.02, L.GLOBE_Z0)]
    v, f, n = revolve(prof, seg)
    add(v, f, [gold_shade((2 * math.pi * (i % n) / seg + math.pi) % (2 * math.pi) - math.pi, 1.0, 1.1) for i in range(len(v))])
    # cap cone
    z0 = L.GLOBE_Z0 + L.GLOBE_H
    prof = [(L.globe_r(1.0) * L.GLOBE_H * 1.03, z0 - 0.004), (L.CAP_R0, z0 + 0.004), (L.CAP_R1, z0 + L.CAP_H), (0.0, z0 + L.CAP_H + 0.003)]
    v, f, n = revolve(prof, seg)
    sh = []
    for j, (_r, z) in enumerate(prof):
        for k in range(n):
            a = 2 * math.pi * k / seg
            a = a if a <= math.pi else a - 2 * math.pi
            sh.append(gold_shade(a, 1 - (z - z0) / L.CAP_H * 0.6, 0.9))
    add(v, f, sh)
    return mesh('lamp_body', scaled(parts_v), parts_f, shades, mat='gold')


def globe_profile(scale_r=1.0, rings=36, y0=0.0, y1=1.0):
    return [(L.globe_r(y0 + (y1 - y0) * j / rings) * L.GLOBE_H * scale_r, L.GLOBE_Z0 + L.GLOBE_H * (y0 + (y1 - y0) * j / rings))
            for j in range(rings + 1)]


def liquid_mesh():
    """The liquid behind the wax: the back half of the globe, prelit from the bulb (bright below, deep at the top)."""
    prof = globe_profile(0.98)
    v, f, n = revolve(prof, 32, math.pi / 2, 3 * math.pi / 2, closed=False)
    sh = []
    for j in range(len(prof)):
        y = j / (len(prof) - 1)
        for k in range(n):
            a = math.pi / 2 + math.pi * k / 32
            edge = abs(math.cos(a - math.pi))          # 1 at the back centre, 0 at the limb
            val = (0.30 + 0.75 * math.exp(-y / 0.18)) * (0.55 + 0.45 * edge) * (1.0 - 0.45 * y)
            sh.append((val, val, val))
    return mesh('liquid', scaled(v), f, sh, mat='liquid', morph=True)


def glass_mesh():
    """The globe's glass, faked opaque (the Risks answer to fill rate: a translucent sheet over the whole globe cost
    cast1 its refresh rate): two painted highlight strips and a darkened band at each edge, drawn only where the
    translucent sheet showed, in the shades it blended to. Tinted with the glass colour like the old sheet."""
    prof = globe_profile(1.03)
    verts, faces, sh = [], [], []

    def band(a0, a1, segs, shade):
        v, f, n = revolve(prof, segs, a0, a1, closed=False)
        o = len(verts)
        verts.extend(v)
        faces.extend(tuple(i + o for i in t) for t in f)
        for _j in range(len(prof)):
            for k in range(n):
                t = k / segs                      # 0..1 across the band
                val = shade(t)
                sh.append((val, val, val))
    def strip(peak, edge):
        return lambda t: edge + (peak - edge) * math.exp(-((t - 0.5) / 0.28) ** 2)
    band(-0.55 - 0.045, -0.55 + 0.045, 4, strip(1.0, 0.40))   # the broad highlight, left of centre
    band(0.35 - 0.022, 0.35 + 0.022, 2, strip(0.75, 0.40))     # the narrow one, right of centre
    band(-math.pi / 2, -1.30, 3, lambda t: 0.12 + 0.10 * t)   # edge darkening: darkest at the very edge
    band(1.30, math.pi / 2, 3, lambda t: 0.22 - 0.10 * t)
    return mesh('glass', scaled(verts), faces, sh, mat='glass', morph=True)


def bulb_glow_mesh():
    """Warm light over the bulb, at the bottom of the globe (not tinted)."""
    prof = globe_profile(0.99, rings=8, y0=0.0, y1=0.3)
    v, f, n = revolve(prof, 32, math.pi / 2, 3 * math.pi / 2, closed=False)
    sh = []
    for j in range(len(prof)):
        y = 0.3 * j / (len(prof) - 1)
        val = math.exp(-y / 0.09)
        sh.extend([(val, val * 0.86, val * 0.62)] * n)
    return mesh('bulb_glow', scaled(v), f, sh, mat='bulb')


def coil_mesh():
    """The wire coil at the globe's foot, mostly buried in the pool."""
    verts, faces, sh = [], [], []
    turns, seg, tube = 3, 72, 6
    R = L.globe_r(0.02) * L.GLOBE_H * 0.62
    for i in range(seg + 1):
        t = i / seg
        a = 2 * math.pi * turns * t
        cx, cy, cz = R * math.sin(a), -R * math.cos(a), L.GLOBE_Z0 + 0.001 + 0.004 * t
        for k in range(tube):
            b = 2 * math.pi * k / tube
            rr = 0.0012
            nx, ny = math.sin(a), -math.cos(a)
            verts.append((cx + rr * math.cos(b) * nx, cy + rr * math.cos(b) * ny, cz + rr * math.sin(b)))
            sh.append((0.5, 0.42, 0.35))
    for i in range(seg):
        for k in range(tube):
            a, b = i * tube + k, i * tube + (k + 1) % tube
            faces.append((a, b, b + tube, a + tube))
    return mesh('coil', scaled(verts), faces, sh, mat='gold')


# ---------------------------------------------------------------- the base display (D7)
FONT = {
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    '3': ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    '4': ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    '5': ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    '6': ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    '9': ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
}
COLS, ROWS = 29, 9
DIGIT_COL = (2, 8, 16, 22)          # each digit is 5 columns; the colon sits in column 14
COLON_COL, COLON_ROWS = 14, (2, 4)
GRID_Z0, GRID_Z1 = 0.036, 0.092     # rows run between these heights on the cone (metres)
GRID_SPAN = math.radians(62)        # half the azimuth span the columns cover


def cone_r(z):
    """The base cone's radius at height z, as lamp_body's profile draws it between its two bevels."""
    z0, z1 = 0.004, L.BASE_H - 0.004
    r0, r1 = L.BASE_R0 * 0.995, L.BASE_R1 + 0.002
    return r0 + (r1 - r0) * (z - z0) / (z1 - z0)


def hole(c, r, size=0.0024, lift=0.0006):
    """One hole: a small octagon on the cone's surface at column c, row r (row 0 at the top)."""
    a = -GRID_SPAN + 2 * GRID_SPAN * c / (COLS - 1)
    z = GRID_Z1 - (GRID_Z1 - GRID_Z0) * r / (ROWS - 1)
    rad = cone_r(z) + lift
    cx, cy = rad * math.sin(a), -rad * math.cos(a)
    tx, ty = math.cos(a), math.sin(a)                     # tangent along the cone, horizontal
    slope = cone_r(1.0) - cone_r(0.0)                   # the surface leans inward as it rises (dr/dz)
    up = (slope * math.sin(a), -slope * math.cos(a), 1.0)
    ul = math.sqrt(sum(u * u for u in up))
    up = tuple(u / ul for u in up)
    pts = [(cx, cy, z)]
    for k in range(8):
        t = 2 * math.pi * (k + 0.5) / 8
        s, u = math.cos(t) * size, math.sin(t) * size
        pts.append((cx + tx * s + up[0] * u, cy + ty * s + up[1] * u, z + up[2] * u))
    faces = [(0, 1 + (k + 1) % 8, 1 + k) for k in range(8)]
    return pts, faces


def holes_mesh(name, cells, colour, size=0.0024, lift=0.0006):
    verts, faces, sh = [], [], []
    for (c, r) in cells:
        p, f = hole(c, r, size, lift)
        o = len(verts)
        verts.extend(p)
        faces.extend(tuple(i + o for i in t) for t in f)
        sh.extend([colour] * len(p))
    return mesh(name, scaled(verts), faces, sh, mat='hole')


def glyph_cells(ch, col):
    return [(col + x, 1 + y) for y, row in enumerate(FONT[ch]) for x, bit in enumerate(row) if bit == '1']


LIT = (1.0, 0.93, 0.74)
DIM = (0.36, 0.26, 0.12)          # the faint starlight: every hole glows a little


# ---------------------------------------------------------------- the room
def room_meshes():
    W = 2.2
    wall_v = [(-W, 0.5, -0.05), (W, 0.5, -0.05), (W, 0.5, 1.4), (-W, 0.5, 1.4)]
    grid = 24
    verts, faces, sh = [], [], []
    for j in range(grid + 1):
        for i in range(grid + 1):
            x, z = -W + 2 * W * i / grid, -0.05 + 1.45 * j / grid
            verts.append((x, 0.5, z))
            d = math.hypot(x / 0.55, (z - 0.25) / 0.45)
            v = 0.06 + 0.85 * math.exp(-d * d)
            sh.append((v, v, v))
    for j in range(grid):
        for i in range(grid):
            a = j * (grid + 1) + i
            faces.append((a, a + 1, a + grid + 2, a + grid + 1))
    wall = mesh('wall_glow', scaled(verts), faces, sh, mat='room', morph=True)
    # sideboard: a dark top and front edge (static), and the light pool at the lamp's foot (tinted)
    top_v = [(-W, -0.6, 0.0), (W, -0.6, 0.0), (W, 0.5, 0.0), (-W, 0.5, 0.0),
             (-W, -0.6, -0.03), (W, -0.6, -0.03)]
    top_f = [(0, 1, 2, 3), (4, 5, 1, 0)]
    top_sh = [(0.10, 0.07, 0.06), (0.10, 0.07, 0.06), (0.05, 0.04, 0.04), (0.05, 0.04, 0.04),
              (0.05, 0.035, 0.03), (0.05, 0.035, 0.03)]
    board = mesh('sideboard', scaled(top_v), top_f, top_sh, mat='room')
    verts, faces, sh = [], [], []
    rings, seg = 10, 48
    verts.append((0, -0.02, 0.0008))
    sh.append((1, 1, 1))
    for j in range(1, rings + 1):
        r = 0.42 * j / rings
        for k in range(seg):
            a = 2 * math.pi * k / seg
            verts.append((r * math.sin(a) * 1.25, -0.02 - r * math.cos(a) * 0.7, 0.0008))
            v = math.exp(-(r / 0.19) ** 2)
            sh.append((v, v, v))
    for k in range(seg):
        faces.append((0, 1 + (k + 1) % seg, 1 + k))
    for j in range(rings - 1):
        for k in range(seg):
            a, b = 1 + j * seg + k, 1 + j * seg + (k + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    table = mesh('table_light', scaled(verts), faces, sh, mat='room', morph=True)
    return wall, board, table


# ---------------------------------------------------------------- the scene
actor('Level', 'levelobj')
actor('Room', 'room', bounds=(-150, -150, -40, 150, 150, 120))
director = actor('Director', 'director')
actor('Player', 'player', pos=(0, 30, 0))
# D3: the lamp fills 88 % of the frame height. The engine's view is always 60 degrees vertical (gfx/authored_view.hp;
# a camshot's FOV field is not read), so the camera stands at the distance that frames the lamp at 60 degrees.
LOOK_Z = L.LAMP_H * S * 0.5
EYE_Z = (L.GLOBE_Z0 + 0.5 * L.GLOBE_H) * S
CAM_Y = -(L.LAMP_H * S / 0.80) / 2 / math.tan(math.radians(30))   # 0.80 here frames it at about 88 % (perspective)
actor('Camera', 'camera', pos=(0, CAM_Y, EYE_Z),
      fields={'Mobility': 'Camera', 'Moves Between Rooms': 'True', 'FoggingStartDistance': 900., 'FoggingCompleteDistance': 1000.})
actor('LookAt', 'target', pos=(0, 0, LOOK_Z))
actor('cs_wide', 'camshot', pos=(0, CAM_Y, EYE_Z),
      fields={'Follow': 'LookAt', 'Target': 'LookAt', 'Track Object': 'LookAt', 'Rotation': 'Fixed', 'Position X': 'Absolute',
              'Position Y': 'Absolute', 'Position Z': 'Absolute', 'Hither': 2., 'Yon': 600., 'FOV': 60., 'Pan Time In Seconds': 0.})
actor('Ambient', 'light', fields={'lightType': 'Ambient', 'lightRed': .5, 'lightGreen': .5, 'lightBlue': .5})
actor('Background', 'matte', fields={'Matte Type': 'Color', 'Background Color': 0x07050b})
actor('LavaLampSettings', 'lavalampsettings', fields={'Editor Label': 'Lava lamp'})
# A 4K TV draws the lamp at 1080 rows and scales it up: at 2160 the fill rate missed every refresh (build record).
actor('RenderSettings', 'levelrendersettings', fields={'Editor Label': 'Rendering', 'Maximum surface height': 1080})

wall, board, table = room_meshes()
finish(actor('WallGlow', 'platform', wall), wall)
finish(actor('Sideboard', 'platform', board), board)
finish(actor('TableLight', 'platform', table), table)
body = lamp_body()
finish(actor('Lamp', 'platform', body), body)
coil = coil_mesh()
finish(actor('Coil', 'platform', coil), coil)
liquid = liquid_mesh()
finish(actor('Liquid', 'platform', liquid), liquid)
pool = pool_mesh()
finish(actor('Pool', 'platform', pool, pos=(0, 0, L.GZ0)), pool)
blob = blob_mesh()
for i in range(forth.N):
    finish(actor(f'Blob{i}', 'platform', blob, pos=(0, 0, L.GZ0 + 0.5 * L.G),
                 fields={'Visibility Mailbox': L.VIS_BLOB0 + i}), blob)
for k in range(L.N_MERGED):
    finish(actor(f'Merged{k}', 'platform', blob, pos=(0, 0, L.GZ0 + 0.5 * L.G),
                 fields={'Visibility Mailbox': L.VIS_MERGED0 + k}), blob)
bulb = bulb_glow_mesh()
finish(actor('BulbGlow', 'platform', bulb), bulb)
glass = glass_mesh()
# LAVA_DIAG=noglass: a diagnostic build with the glass sheet hidden (visibility mailbox 0, always false).
finish(actor('Glass', 'platform', glass,
             fields={'Visibility Mailbox': 0 if 'noglass' in os.environ.get('LAVA_DIAG', '') else 1}), glass)

every = [(c, r) for c in range(COLS) for r in range(ROWS)]
lit_any = set()
for p, col in enumerate(DIGIT_COL):
    for v in range(10):
        lit_any.update(glyph_cells(str(v), col))
holes = holes_mesh('holes', every, DIM, size=0.0019)
finish(actor('Holes', 'platform', holes), holes)
for p, col in enumerate(DIGIT_COL):
    for v in range(10):
        m = holes_mesh(f'digit{p}_{v}', glyph_cells(str(v), col), LIT, lift=0.0010)
        finish(actor(f'Digit{p}_{v}', 'platform', m, fields={'Visibility Mailbox': L.VIS_DIGIT0 + 10 * p + v}), m)
colon = holes_mesh('colon', [(COLON_COL, 1 + r) for r in COLON_ROWS] + [(COLON_COL, 7 - r) for r in COLON_ROWS[:0]], LIT, lift=0.0010)
finish(actor('Colon', 'platform', colon, fields={'Visibility Mailbox': L.VIS_COLON}), colon)
dash_cells = [cell for col in DIGIT_COL for cell in glyph_cells('-', col)]
dashes = holes_mesh('dashes', dash_cells, (0.55, 0.45, 0.30), lift=0.0010)
finish(actor('Dashes', 'platform', dashes, fields={'Visibility Mailbox': L.VIS_DASH}), dashes)

# ---------------------------------------------------------------- the director
bpy.context.view_layer.update()
objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx = {o.name: i + 1 for i, o in enumerate(objects)}
catalog = json.loads(subprocess.check_output([str(ROOT / 'wftools/wf_attr_edit/target/release/catalog'), str(SETTINGS_OAD)],
                                             text=True))
by_key = {f['key']: f['index'] for f in catalog['fields']}
fields = {name: by_key[name] for name in ('Camera drift', 'Lava color', 'Water color', 'Time display')}
director["wf_Script"] = forth.director_script(idx, fields, cam0=(0.0, EYE_Z))

# blob actors are moved by the director; their bounding boxes must hold every pose (unit sphere x scale 1)
for o in objects:
    if o.name.startswith(('Blob', 'Merged')):
        o['wf_original_bbox'] = (-2.5, -2.5, -2.5, 2.5, 2.5, 2.5)
        o['wf_had_authored_bbox'] = True

(HERE / 'actor-map.json').write_text(json.dumps({'indices': idx, 'fields': fields}, indent=2) + '\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'lava_lamp.blend'))
bpy.ops.wf.export_level(filepath=str(HERE / 'lava_lamp.lev'))
