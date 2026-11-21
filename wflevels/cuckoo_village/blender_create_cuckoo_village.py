#!/usr/bin/env python3
"""Build the Cuckoo Village level, Classic mode (plan docs/plans/2026-11-21-cuckoo-village.md).

The tree, house, tower, hands and bird door are the models of the asset prototype
(wflevels/cuckoo_village_assets/generate.py, owned by another session; the model code is
reproduced here so this level builds on its own). This script adds the village around them, four
figures and a bird, then poses every moving actor from timeline.py at the reference time and
writes the director script. Run through build.sh in the Blender container.

+Z is up, building fronts face -Y. Writes cuckoo_village.lev and actor-map.json.
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'wftools'))
sys.path.insert(0, str(HERE))
import wf_blender            # noqa: E402
import wf_blender.operators as wf_ops   # noqa: E402
import wf_core               # noqa: E402
import forth                 # noqa: E402
import timeline as tl        # noqa: E402

TAG = '[cuckoo-village]'
REFERENCE = 10 * 3600 + 8 * 60 + 22.0       # the pose the level starts from: 10:08
random.seed(48)
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()
bpy.ops.wf.import_level(filepath=str(ROOT / 'wflevels/snowgoons-blender/snowgoons-blender.lev'))
classes = {'director': 'Director', 'camera': 'Camera', 'levelobj': 'LevelObj', 'matte': 'Matte', 'light': 'SunLight',
           'room': 'Room', 'camshot': 'cs_wide', 'target': 'LookAt', 'player': 'Player'}
seen = set()
for o in list(bpy.context.scene.objects):
    cls = Path(o.get('wf_schema_path', '')).stem
    if cls not in classes or cls in seen:
        bpy.data.objects.remove(o, do_unlink=True)
        continue
    seen.add(cls)
    o.name = classes[cls]
    schema = ROOT / 'wfsource/source/oas' / f'{cls}.oad'
    if schema.is_file():
        o['wf_schema_path'] = str(schema)
        wf_ops._seed_defaults(o, wf_core.load_schema(str(schema)))
    o.location = (0, -20, 1)
    o.rotation_euler = (0, 0, 0)
    o.scale = (1, 1, 1)
    o.hide_render = True
    o['wf_Mass'] = 0.0
    o['wf_Model Type'] = 'None'
    o['wf_Script'] = ''
    o['wf_original_bbox'] = (-.1, -.1, -.1, .1, .1, .1)
    o['wf_had_authored_bbox'] = True
assert seen == set(classes), seen
bpy.data.objects['Room']['wf_Adjacent Room 1'] = ''
bpy.data.objects['Player']['wf_Tool A'] = ''

mat = bpy.data.materials.new('village_atlas')
mat.use_nodes = True
img = bpy.data.images.load(str(HERE / 'village_atlas.tga'), check_existing=True)
img.filepath = '//village_atlas.tga'
node = mat.node_tree.nodes.new('ShaderNodeTexImage')
node.image = img
uvnode = mat.node_tree.nodes.new('ShaderNodeUVMap')
uvnode.uv_map = 'UVMap'
mapping = mat.node_tree.nodes.new('ShaderNodeMapping')
mapping.inputs['Scale'].default_value = (1, -1, 1)
mapping.inputs['Location'].default_value = (0, 1, 0)
mat.node_tree.links.new(uvnode.outputs['UV'], mapping.inputs['Vector'])
mat.node_tree.links.new(mapping.outputs['Vector'], node.inputs['Vector'])
mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
parts = []
glows = []


def uv(obj, tile):
    """Map each polygon into one atlas tile, inset to avoid bleeding."""
    mesh = obj.data
    mesh.materials.clear()
    mesh.materials.append(mat)
    layer = mesh.uv_layers.active or mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        normal = poly.normal
        axis = max(range(3), key=lambda i: abs(normal[i]))
        axes = [i for i in range(3) if i != axis]
        coords = [[mesh.vertices[mesh.loops[li].vertex_index].co[i] for i in axes] for li in poly.loop_indices]
        mins = [min(c[i] for c in coords) for i in range(2)]
        spans = [max(max(c[i] for c in coords) - mins[i], 1e-6) for i in range(2)]
        for li, c in zip(poly.loop_indices, coords):
            layer.data[li].uv = ((tile % 4 + .03 + .94 * (c[0] - mins[0]) / spans[0]) / 4,
                                 (tile // 4 + .03 + .94 * (c[1] - mins[1]) / spans[1]) / 4)
    parts.append(obj)
    return obj


def cube(loc, scale, tile, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return uv(o, tile)


def cylinder(loc, r, depth, tile, vertices=12, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return uv(o, tile)


def cone(loc, r, depth, tile, vertices=12, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=r, radius2=.02, depth=depth, location=loc, rotation=rot)
    o = bpy.context.object
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return uv(o, tile)


def sphere(loc, scale, tile, segments=8, rings=6):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1, location=loc)
    o = bpy.context.object
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return uv(o, tile)


def beam(a, b, width, depth, tile):
    a, b = Vector(a), Vector(b)
    o = cube((a + b) / 2, (width, depth, (b - a).length), tile)
    o.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
    return o


def roof(cx, cy, z, w, d, h):
    for sign in (-1, 1):
        inner = (cx, z + h)
        outer = (cx + sign * w / 2, z)
        v = [(inner[0], cy - d / 2, inner[1]), (outer[0], cy - d / 2, outer[1]), (outer[0], cy + d / 2, outer[1]), (inner[0], cy + d / 2, inner[1])]
        v += [(x, y, zz - .10) for x, y, zz in v]
        faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)] if sign < 0 else [(3, 2, 1, 0), (4, 5, 6, 7), (1, 5, 4, 0), (2, 6, 5, 1), (3, 7, 6, 2), (0, 4, 7, 3)]
        mesh = bpy.data.meshes.new('roof')
        mesh.from_pydata(v, [], faces)
        mesh.update()
        o = bpy.data.objects.new('roof', mesh)
        bpy.context.scene.collection.objects.link(o)
        uv(o, 2)
    beam((cx, cy - d / 2, z + h), (cx, cy + d / 2, z + h), .13, .13, 0)


def gable(z, w, d, h):
    vertices = [(-w / 2, -d / 2, z), (w / 2, -d / 2, z), (0, -d / 2, z + h), (-w / 2, d / 2, z), (w / 2, d / 2, z), (0, d / 2, z + h)]
    faces = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    data = bpy.data.meshes.new('gable')
    data.from_pydata(vertices, [], faces)
    data.update()
    o = bpy.data.objects.new('gable', data)
    bpy.context.scene.collection.objects.link(o)
    uv(o, 1)


def finish(name, origin=(0, 0, 0)):
    global parts
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    o.data.name = name
    bpy.context.scene.cursor.location = origin
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    parts = []
    return o


def window(x, y, z, w=.48, h=.56, face=-1):
    cube((x, y, z), (w + .12, .09, h + .12), 0)
    cube((x, y + face * .055, z), (w, .035, h), 11)
    cube((x, y + face * .077, z), (w - .025, .008, h - .025), 6)
    glows.append(parts.pop())
    cube((x, y + face * .08, z), (.035, .04, h), 8)
    cube((x, y + face * .08, z), (w, .04, .035), 8)
    for side in (-1, 1):
        cube((x + side * (w / 2 + .14), y, z), (.20, .10, h + .08), 9)
        for dz in (-.16, 0, .16):
            cube((x + side * (w / 2 + .14), y + face * .06, z + dz), (.18, .02, .025), 0)


def side_window(x, y, z, face):
    cube((x, y, z), (.10, .56, .68), 0)
    cube((x + face * .06, y, z), (.035, .42, .54), 11)
    cube((x + face * .08, y, z), (.008, .395, .515), 6)
    glows.append(parts.pop())
    cube((x + face * .09, y, z), (.04, .035, .54), 8)
    cube((x + face * .09, y, z), (.04, .42, .035), 8)


def box_flowers(x, y, z):
    cube((x, y, z), (.69, .22, .15), 8)
    for i in range(7):
        xx = x - .28 + i * .095
        cube((xx, y, z + .12), (.055, .11, .13), 4)
        cube((xx, y - .01, z + .20), (.07, .08, .07), 13 if i % 2 else 12)


# ---------------------------------------------------------------------------------------------
# Models from the asset prototype: pine, house (+ glow), clock tower (+ glow), hands, bird door
# ---------------------------------------------------------------------------------------------
cylinder((0, 0, .55), .19, 1.1, 5)
for z, r, h in [(1.05, 1.02, 1.35), (1.65, .87, 1.30), (2.22, .72, 1.24), (2.75, .55, 1.17), (3.23, .38, 1.05)]:
    cone((0, 0, z), r, h, 4)
    for k in range(7):
        a = 2 * math.pi * (k / 7 + .04 * (int(z * 10) % 3))
        cone((r * .73 * math.cos(a), r * .73 * math.sin(a), z - h * .19), r * .23, h * .42, 4)
pine = finish('pine_tree')

cube((0, 0, .28), (2.5, 2.0, .56), 3)
cube((0, 0, 1.45), (2.36, 1.9, 1.85), 1)
for x in (-1.12, 0, 1.12):
    cube((x, -.97, 1.47), (.13, .10, 1.85), 0)
for z in (.60, 1.52, 2.30):
    cube((0, -.98, z), (2.38, .11, .12), 0)
for x in (-.78, .78):
    window(x, -1.04, 1.92, .43, .43)
    box_flowers(x, -1.12, 1.58)
cube((0, -1.035, 1.04), (.49, .12, .85), 8)
cube((0, -1.11, 1.04), (.36, .03, .75), 0)
for x in (-.77, .77):
    window(x, -1.04, .99, .42, .46)
for y in (-.70, .70):
    for x in (-1.22, 1.22):
        cube((x, y, 1.48), (.12, .12, 1.85), 0)
for y in (-.62, .62):
    for x in (-1.22, 1.22):
        side_window(x, y, 1.80, 1 if x > 0 else -1)
for x in (-.72, .72):
    window(x, 1.00, 1.55, .43, .50, face=1)
for x in (-1.12, 0, 1.12):
    cube((x, .97, 1.47), (.13, .10, 1.85), 0)
for z in (.60, 1.52, 2.30):
    cube((0, .98, z), (2.38, .11, .12), 0)
gable(2.36, 2.36, 1.9, .70)
roof(0, 0, 2.36, 2.9, 2.5, .80)
cube((.70, .45, 2.95), (.32, .32, .75), 3)
cube((.70, .45, 3.34), (.42, .42, .10), 8)
house = finish('standard_house')
parts = glows
house_glow = finish('house_glow')
glows = []

cube((0, 0, .32), (2.9, 2.35, .64), 3)
cube((0, 0, 2.0), (2.65, 2.1, 2.75), 1)
for x in (-1.23, 1.23):
    cube((x, -1.08, 2.0), (.16, .12, 2.8), 0)
for z in (.67, 2.05, 3.36):
    cube((0, -1.09, z), (2.7, .14, .15), 0)
cube((0, -1.10, 1.3), (.65, .13, 1.20), 8)
for x in (-.85, .85):
    window(x, -1.13, 1.48, .36, .50)
cube((0, -1.45, 2.46), (2.65, .75, .18), 0)
cube((0, -1.82, 2.80), (2.65, .10, .09), 0)
for x in [-1.2, -.8, -.4, 0, .4, .8, 1.2]:
    cube((x, -1.82, 2.63), (.07, .09, .38), 0)
for x in (-.87, -.29, .29, .87):
    cube((x, -1.085, 2.96), (.48, .07, .63), 11)
cube((0, 0, 3.93), (2.25, 1.85, 1.14), 1)
cylinder((0, -.97, 4.08), .52, .08, 8, 32, (math.pi / 2, 0, 0))
cylinder((0, -1.025, 4.08), .46, .04, 7, 32, (math.pi / 2, 0, 0))
for i in range(12):
    a = 2 * math.pi * i / 12
    x = .37 * math.sin(a)
    z = 4.08 + .37 * math.cos(a)
    o = cube((x, -1.06, z), (.045, .025, .09 if i % 3 == 0 else .055), 8)
    o.rotation_euler[1] = a
cube((0, -.98, 4.70), (.53, .08, .32), 11)
gable(4.82, 2.25, 1.85, .65)
roof(0, 0, 4.82, 2.85, 2.35, .82)
for x in (-1.05, 1.05):
    cube((x, -.97, 3.95), (.12, .12, 1.3), 0)
finish('clock_tower')
parts = glows
tower_glow = finish('tower_glow')
glows = []
for name, length in [('hour_hand', .27), ('minute_hand', .38)]:
    o = cube((0, 0, length / 2), (.055, .03, length), 8)
    hand = finish(name, (0, 0, 0))
cube((0, 0, .15), (.48, .08, .30), 0)
door = finish('bird_door', (-.24, 0, 0))

# ---------------------------------------------------------------------------------------------
# New in this level: broadleaf garden tree, garden bed, four figures, the bird
# ---------------------------------------------------------------------------------------------
cylinder((0, 0, .45), .12, .9, 5, 8)
sphere((0, 0, 1.35), (.75, .75, .62), 4)
sphere((.35, .1, 1.1), (.5, .5, .42), 4)
sphere((-.3, -.1, 1.15), (.48, .48, .4), 4)
garden_tree = finish('garden_tree')

cube((0, 0, .06), (1.6, .8, .12), 5)
for i in range(6):
    xx = -.6 + i * .24
    cube((xx, 0, .17), (.05, .08, .16), 4)
    cube((xx, -.01, .27), (.12, .12, .1), (12, 13, 6, 12, 13, 6)[i])
garden_bed = finish('garden_bed')


def toy_figure(name, robe, hat, trim):
    """A small toy: skirt, torso, head, hat and two arms. Origin at the feet, front toward -Y."""
    cylinder((0, 0, .14), .115, .28, robe, 10)
    cylinder((0, 0, .375), .095, .22, trim, 10)
    sphere((0, 0, .545), (.07, .07, .07), 7)
    cube((.115, 0, .37), (.04, .05, .18), robe)
    cube((-.115, 0, .37), (.04, .05, .18), robe)
    if hat == 0:                       # tall pointed cap
        cone((0, 0, .66), .075, .20, hat_tile(name))
    elif hat == 1:                     # wide flat hat
        cylinder((0, 0, .615), .13, .02, hat_tile(name), 12)
        cylinder((0, 0, .65), .06, .06, hat_tile(name), 10)
    elif hat == 2:                     # round cap
        sphere((0, 0, .60), (.08, .08, .05), hat_tile(name))
    else:                              # crown
        for k in range(5):
            a = 2 * math.pi * k / 5
            cone((.06 * math.cos(a), .06 * math.sin(a), .64), .02, .07, hat_tile(name), 6)
        cylinder((0, 0, .60), .065, .03, hat_tile(name), 10)
    return finish(name, (0, 0, 0))


HAT_TILE = {'figure_1': 13, 'figure_2': 14, 'figure_3': 9, 'figure_4': 6}


def hat_tile(name):
    return HAT_TILE[name]


figures = [toy_figure('figure_1', 13, 0, 8),    # red robe, tall cap
           toy_figure('figure_2', 14, 1, 7),    # blue robe, wide hat
           toy_figure('figure_3', 9, 2, 5),     # green robe, round cap
           toy_figure('figure_4', 6, 3, 12)]    # gold robe, crown

sphere((0, 0, .09), (.065, .10, .075), 6)
sphere((0, -.07, .17), (.045, .045, .05), 6)
cone((0, -.12, .17), .02, .05, 13, 6, (math.pi / 2, 0, 0))
cube((0, .09, .09), (.04, .08, .03), 12, (-.35, 0, 0))
cuckoo = finish('bird', (0, 0, 0))

# ---------------------------------------------------------------------------------------------
# Static village: base, grass, ring road, spokes, cobbled square, fountain, fences
# ---------------------------------------------------------------------------------------------
BASE_X, BASE_Y = 22.0, 18.0
cube((0, 0, -.45), (BASE_X * 2 + 1.6, BASE_Y * 2 + 1.6, .9), 8)          # dark wood plinth
cube((0, 0, -.02), (BASE_X * 2, BASE_Y * 2, .08), 9)                      # grass

RING_A, RING_B, RING_W = 10.5, 8.0, 2.0
SEGMENTS = 36
for k in range(SEGMENTS):
    a0, a1 = 2 * math.pi * k / SEGMENTS, 2 * math.pi * (k + 1) / SEGMENTS
    p0 = Vector((RING_A * math.cos(a0), RING_B * math.sin(a0), 0))
    p1 = Vector((RING_A * math.cos(a1), RING_B * math.sin(a1), 0))
    mid = (p0 + p1) / 2
    seg = p1 - p0
    cube((mid.x, mid.y, .035), (seg.length * 1.06, RING_W, .05), 3, (0, 0, math.atan2(seg.y, seg.x)))
for sx, sy, sw, sl in [(0, -1, RING_W, 1), (0, 1, RING_W, 1)]:           # spokes along the axes, square to ring
    for lo, hi in [(5.0, RING_B - .3)]:
        cube((0, sy * (lo + hi) / 2, .035), (RING_W, hi - lo, .05), 3)
for sx in (-1, 1):
    cube((sx * (5.0 + RING_A - .3) / 2, 0, .035), (RING_A - 5.3, RING_W, .05), 3)
SQUARE_R, CELL = 5.4, 1.35
nx = int(SQUARE_R / CELL) + 1
for ix in range(-nx, nx + 1):
    for iy in range(-nx, nx + 1):
        cx, cy = ix * CELL, iy * CELL
        if math.hypot(cx, cy) <= SQUARE_R - .2:
            cube((cx, cy, .045), (CELL * .98, CELL * .98, .07), 3)
# fountain at the front right of the square, off the tower's view axis
FX, FY = 3.2, -4.0
cylinder((FX, FY, .30), 1.15, .5, 3, 16)
cylinder((FX, FY, .56), 1.0, .06, 14, 16)
cylinder((FX, FY, .85), .14, .6, 3, 8)
cylinder((FX, FY, 1.18), .45, .1, 3, 12)
cone((FX, FY, 1.40), .12, .3, 14, 8)
# low fences along the plinth edge and around the road
for sgn in (-1, 1):
    for k in range(-20, 21):
        cube((k * 1.05, sgn * (BASE_Y - .4), .35), (.12, .12, .7), 5)
        if abs(k * .85) < BASE_Y - .5:
            cube((sgn * (BASE_X - .4), k * .85, .35), (.12, .12, .7), 5)
    cube((0, sgn * (BASE_Y - .4), .5), (BASE_X * 2 - .6, .08, .09), 5)
    cube((0, sgn * (BASE_Y - .4), .25), (BASE_X * 2 - .6, .08, .09), 5)
    cube((sgn * (BASE_X - .4), 0, .5), (.08, BASE_Y * 2 - .6, .09), 5)
    cube((sgn * (BASE_X - .4), 0, .25), (.08, BASE_Y * 2 - .6, .09), 5)
ground = finish('village_ground')

# ---------------------------------------------------------------------------------------------
# Actor properties, layout and instances
# ---------------------------------------------------------------------------------------------
GLOW_CELL0 = 200
singles = ['pine_tree', 'standard_house', 'house_glow', 'clock_tower', 'tower_glow', 'hour_hand', 'minute_hand', 'bird_door',
           'garden_tree', 'garden_bed', 'bird', 'figure_1', 'figure_2', 'figure_3', 'figure_4', 'village_ground']
assets = [bpy.data.objects[n] for n in singles]
for o in assets:
    o['wf_schema_path'] = str(ROOT / 'wfsource/source/oas/platform.oad')
    o['wf_Mobility'] = 'Anchored'
    o['wf_Model Type'] = 'Mesh'
    o['wf_Mass'] = 0.0
    o['wf_Visibility Mailbox'] = 1
    o['wf_Mesh Name'] = o.name + '.iff'
    o['wf_original_mesh_name'] = o.name + '.iff'
    assert len(o.name + '.iff') <= 30, o.name
for n in ('house_glow', 'tower_glow'):
    bpy.data.objects[n].hide_render = True


def duplicate(src, name, loc, rot_z=0.0, scale=1.0):
    o = src.copy()
    o.data = src.data
    o.name = name
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (0, 0, rot_z)
    o.scale = (scale, scale, scale)
    o['wf_Mesh Name'] = src['wf_Mesh Name']
    o['wf_original_mesh_name'] = src['wf_original_mesh_name']
    return o


def place(o, loc, rot_z=0.0, scale=1.0):
    o.location = loc
    o.rotation_euler = (0, 0, rot_z)
    o.scale = (scale, scale, scale)


# tower and its parts
tower = bpy.data.objects['clock_tower']
place(tower, (0, 0, 0))
place(bpy.data.objects['tower_glow'], (0, 0, 0))
bpy.data.objects['tower_glow']['wf_Visibility Mailbox'] = GLOW_CELL0 + tl.HOUSES
bpy.data.objects['village_ground'].location = (0, 0, 0)
poses = tl.all_poses(REFERENCE)
for name in ('hour_hand', 'minute_hand', 'bird_door', 'bird', 'figure_1', 'figure_2', 'figure_3', 'figure_4'):
    p = poses[name]
    o = bpy.data.objects[name]
    o.location = p[:3]
    o.rotation_euler = (p[3] * math.tau, p[4] * math.tau, p[5] * math.tau)

# twelve houses on an ellipse, fronts toward the middle; the arc in front of the tower stays open
rng = random.Random(7)
HA, HB = 14.5, 11.5
phis = [math.radians(-55 + 290 * k / 11.0) for k in range(12)]
for k, phi in enumerate(phis):
    jp = phi + math.radians(rng.uniform(-2.5, 2.5))
    loc = (HA * math.cos(jp) + rng.uniform(-.5, .5), HB * math.sin(jp) + rng.uniform(-.5, .5), 0)
    rot = jp - math.pi / 2 + math.radians(rng.uniform(-5, 5))
    sc = rng.uniform(.95, 1.08)
    if k == 0:
        h, g = bpy.data.objects['standard_house'], bpy.data.objects['house_glow']
        place(h, loc, rot, sc)
        place(g, loc, rot, sc)
    else:
        h = duplicate(bpy.data.objects['standard_house'], f'house_{k + 1:02d}', loc, rot, sc)
        g = duplicate(bpy.data.objects['house_glow'], f'house_glow_{k + 1:02d}', loc, rot, sc)
    g['wf_Visibility Mailbox'] = GLOW_CELL0 + k
    g.hide_render = True

# pines on a wider ring, and broadleaf garden trees around the square
pine_src = bpy.data.objects['pine_tree']
for k in range(14):
    ang = 2 * math.pi * (k + rng.uniform(-.25, .25)) / 14
    loc = (19.2 * math.cos(ang) + rng.uniform(-.8, .8), 15.6 * math.sin(ang) + rng.uniform(-.8, .8), 0)
    sc = rng.uniform(.8, 1.25)
    if k == 0:
        place(pine_src, loc, rng.uniform(0, math.tau), sc)
    else:
        duplicate(pine_src, f'pine_{k + 1:02d}', loc, rng.uniform(0, math.tau), sc)
tree_src = bpy.data.objects['garden_tree']
tree_spots = [(-6.4, -3.4), (6.6, 2.2), (-6.8, 3.0), (6.2, -2.2), (-3.0, 6.4), (3.4, 6.6), (-9.6, -5.5)]
for k, (x, y) in enumerate(tree_spots):
    if k == 0:
        place(tree_src, (x, y, 0), rng.uniform(0, math.tau), rng.uniform(.9, 1.2))
    else:
        duplicate(tree_src, f'garden_tree_{k + 1:02d}', (x, y, 0), rng.uniform(0, math.tau), rng.uniform(.9, 1.2))
bed_src = bpy.data.objects['garden_bed']
bed_spots = [(-9.8, -1.5, 0.3), (9.9, -3.0, -0.2), (-8.5, 6.0, 0.9), (8.8, 5.6, -0.7), (-2.4, -10.4, 0.0), (2.6, -10.6, 0.0)]
for k, (x, y, r) in enumerate(bed_spots):
    if k == 0:
        place(bed_src, (x, y, 0), r)
    else:
        duplicate(bed_src, f'garden_bed_{k + 1:02d}', (x, y, 0), r)

# light, camera, background
sun = bpy.data.objects['SunLight']
sun.rotation_euler = (0, math.radians(40), math.radians(90))
sun['wf_lightType'] = 'Directional'
for ch, v in zip(('Red', 'Green', 'Blue'), (.80, .78, .72)):
    sun['wf_light' + ch] = v
amb = sun.copy()
amb.name = 'AmbientLight'
bpy.context.scene.collection.objects.link(amb)
amb['wf_lightType'] = 'Ambient'
for ch in ('Red', 'Green', 'Blue'):
    amb['wf_light' + ch] = .42
look = bpy.data.objects['LookAt']
look.location = poses['LookAt'][:3]
wide = bpy.data.objects['cs_wide']
wide.location = poses['cs_wide'][:3]
for axis in 'XYZ':
    wide['wf_Position ' + axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow', 'Target', 'Track Object'):
    wide['wf_' + key] = 'LookAt'
bpy.data.objects['Camera'].location = wide.location
# The template's distance fog (start 20, complete 30) would grey out the village's far side: push it past the scene
cam_obj = bpy.data.objects['Camera']
fog_keys = [k for k in cam_obj.keys() if 'Start Distance' in k or 'Complete Distance' in k or 'FoggingStart' in k or 'FoggingComplete' in k]
assert len(fog_keys) == 2, f'camera fog properties not found: {list(cam_obj.keys())}'
for k in fog_keys:
    cam_obj[k] = 90.0 if 'Start' in k else 140.0
bpy.data.objects['Matte']['wf_Matte Type'] = 'Color'
bpy.data.objects['Matte']['wf_Background Color'] = 0x0b1115
bpy.data.objects['Player'].location = (0, -3, 1)
bpy.data.objects['Room'].location = (0, 0, 0)
bpy.data.objects['Room']['wf_original_bbox'] = (-60, -60, -10, 60, 60, 40)

scene = bpy.context.scene
objects = [o for o in scene.objects if o.get('wf_schema_path')]
indices = {o.name: i + 1 for i, o in enumerate(objects)}
for a, b in zip(['figure_1', 'figure_2', 'figure_3'], ['figure_2', 'figure_3', 'figure_4']):
    assert indices[b] - indices[a] == 1, 'the four figures must be contiguous'
bpy.data.objects['Director']['wf_Script'] = forth.director_script(indices)
(HERE / 'actor-map.json').write_text(json.dumps(dict(indices=indices, reference=REFERENCE), indent=1) + '\n')
print(f'{TAG} {len(objects)} actors')
bpy.ops.wf.export_level(filepath=str(HERE / 'cuckoo_village.lev'))
print(f'{TAG} done')
