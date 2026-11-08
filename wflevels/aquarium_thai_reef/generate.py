"""Assemble a static reef preview with the existing WF Blender exporter.

Run inside the existing Blender image only, after making it available. This is
an unverified prototype: exporter/cooked output and camera framing require tests.
The source checkout is read-only; pass --out to a writable scratch directory.
"""
import argparse
import json
import sys
from pathlib import Path
from mathutils import Matrix, Vector

import bpy
import bmesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import (ANIME_HULL_TRIANGLES_MAX, ANIME_STATIC_TRIANGLES_MAX, KIT_VISIBLE_GROUPS_MAX,
                    KIT_VISIBLE_TRIANGLES_MAX, STATIC_GROUPS_MAX, STATIC_TRIANGLES_MAX)
p = argparse.ArgumentParser()
p.add_argument('--repo', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
p.add_argument('--level-id', default='aquarium_thai_reef')
p.add_argument('--style', choices=('realistic', 'anime'), default='realistic')
p.add_argument('--preview', type=Path, help='also render a Blender composition preview to this PNG')
p.add_argument('--remesh-rocks', action='store_true', help='voxel-union the blockout rock masses before export')
p.add_argument('--bake-light', action='store_true', help='bake static reef lighting and ambient occlusion')
p.add_argument('--verification-target', choices=('duster', 'clam', 'crab', 'shrimp', 'worms'),
               help='make a diagnostic view centered on one reaction')
p.add_argument('--verification-far', action='store_true', help='place the fish away from the diagnostic target')
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
repo = args.repo.resolve()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo / 'wflevels/aquarium_tanks'))
sys.path.insert(0, str(repo / 'wftools'))
from mesh import Mesh
from reef.atlas import write_atlas, FISH_DARK
from reef import uvmap
from reef.geometry import build_groups, triangles
from reef.scene import anchor_map, worm_mouths, worm_origin
from reef.fishes import boxfish, humbug
from reef import life, invertebrates, worm_rig, crab_rig, feather_rig, flora_rig, corals, kit
import species
import wf_blender
import wf_blender.operators as wf_operators
import wf_core

atlas_path = out / 'reef_atlas.tga'
write_atlas(atlas_path, style=args.style)
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()
bpy.ops.wf.import_level(filepath=str(repo / 'wflevels/snowgoons-blender/snowgoons-blender.lev'))
classes = {'director':'Director', 'camera':'Camera', 'levelobj':'LevelObj',
           'matte':'Matte', 'light':'SunLight', 'room':'Room',
           'camshot':'cs_wide', 'target':'LookAt', 'player':'Player'}
seen = set()
for obj in list(bpy.context.scene.objects):
    cls = Path(obj.get('wf_schema_path', '')).stem
    if cls not in classes or cls in seen:
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    seen.add(cls)
    obj.name = classes[cls]
    runtime_schema = repo / 'wfsource/source/oas' / f'{cls}.oad'
    if runtime_schema.is_file():
        obj['wf_schema_path'] = str(runtime_schema)
        wf_operators._seed_defaults(obj, wf_core.load_schema(str(runtime_schema)))
    obj.location = (0, -20, 1)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj['wf_Mass'] = 0.0
    obj['wf_Model Type'] = 'None'
    obj['wf_Script'] = ''
    obj['wf_original_bbox'] = (-.1, -.1, -.1, .1, .1, .1)
    obj['wf_had_authored_bbox'] = True
assert seen == set(classes), seen

mat = bpy.data.materials.new('reef-atlas')
mat.use_nodes = True
mat.diffuse_color = (1, 1, 1, 1)
image = bpy.data.images.load(str(atlas_path), check_existing=True)
node = mat.node_tree.nodes.new('ShaderNodeTexImage')
node.image = image
mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
# Atlas UVs come from reef/uvmap.py, the same pure-Python function the texel
# audit and the review renders use (static tiles world-projected; creature
# skins, worm crowns and zoanthid discs in their own cells).
def blender_mesh(mesh, smooth=False):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata(mesh.vertices, [], mesh.faces)
    data.materials.append(mat)
    data.update()
    uv = data.uv_layers.new(name='UVMap')
    for poly, face_uv in zip(data.polygons, uvmap.face_uvs(mesh)):
        for li, value in zip(poly.loop_indices, face_uv):
            uv.data[li].uv = value
    data.update()
    if smooth:
        for poly in data.polygons:
            poly.use_smooth = True
    return data


def add_outline(data, width):
    """Append a dark, reversed hull to an existing material/UV mesh."""
    data.calc_loop_triangles()
    before = len(data.loop_triangles)
    bm = bmesh.new()
    bm.from_mesh(data)
    bm.normal_update()
    duplicate = bmesh.ops.duplicate(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces))['geom']
    verts = [element for element in duplicate if isinstance(element, bmesh.types.BMVert)]
    faces = [element for element in duplicate if isinstance(element, bmesh.types.BMFace)]
    for vertex in verts:
        vertex.co += vertex.normal * width
    bmesh.ops.reverse_faces(bm, faces=faces)
    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        raise ValueError('anime outline requires the mesh UV layer')
    for face in faces:
        for loop in face.loops:
            loop[uv_layer].uv = (FISH_DARK[0] / 1024, FISH_DARK[1] / 1024)
    bm.to_mesh(data)
    bm.free()
    data.update()
    data.calc_loop_triangles()
    return len(data.loop_triangles) - before

groups = build_groups(Mesh)
# The rock-module kit (plan W5b, reef/kit.py). The Fixed layout is one arrangement of it:
# the hero modules are today's three rock masses, each with the dressing that grows on it,
# so the static scene below is today's geometry, split by host module and re-pivoted.
static = {'reef_shell': {'mesh': groups['reef_shell'], 'module': None, 'kind': 'shell'}}
for hero in kit.HEROES:
    static[hero['rock']] = {'mesh': groups[hero['rock']], 'module': hero['name'], 'kind': 'rock'}
for piece_name, (hero_name, kind, piece) in kit.dressing_pieces(groups, Mesh, uvmap.face_uvs).items():
    static[piece_name] = {'mesh': piece, 'module': hero_name, 'kind': kind}
for filler in kit.FILLERS:
    static[filler['rock']] = {'mesh': kit.filler_mesh(Mesh, filler), 'module': filler['name'], 'kind': 'filler'}
FIXED_STATIC = [name for name, piece in static.items() if piece['kind'] != 'filler']
actual_triangles = {}
actual_hull_triangles = {}
outline_specs = []
oad = repo / 'wfsource/source/oas/platform.oad'
for name, piece in static.items():
    mesh, kind = piece['mesh'], piece['kind']
    rocky = kind in ('rock', 'filler')
    obj = bpy.data.objects.new(name, blender_mesh(mesh, smooth=rocky))
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = str(oad)
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1 if piece['module'] is None else kit.module_cell(piece['module'])
    obj['wf_Mesh Name'] = name + '.iff'
    obj['wf_original_mesh_name'] = name + '.iff'
    if args.remesh_rocks and rocky:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        # The anime pass has a tighter static-geometry budget. A coarser rock
        # union preserves the same placements while leaving room for life.
        # Fillers (shown only by the Random layout) are coarser still.
        if kind == 'filler':
            obj.data.remesh_voxel_size = .22 if args.style == 'anime' else .13
        else:
            obj.data.remesh_voxel_size = .17 if args.style == 'anime' else .10
        bpy.ops.object.voxel_remesh()
        obj.select_set(False)
        uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
        for loop in obj.data.loops:
            x, y, z = obj.data.vertices[loop.vertex_index].co
            u = (.04 + .92 * ((x * .37 + y * .11) % 1)) / 4
            v = (1 + .04 + .92 * ((z * .37 + y * .11) % 1)) / 4
            uv.data[loop.index].uv = (u, v)
        for poly in obj.data.polygons:
            poly.use_smooth = True
        obj.data.update()
    # Re-pivot every hero piece onto its module's foot after the world-space remesh and UVs,
    # so the world geometry (and the Fixed look) is unchanged. Fillers are authored locally.
    if piece['module'] in kit.MODULES[:len(kit.HEROES)]:
        pivot = kit.hero_pivot(piece['module'])
        obj.data.transform(Matrix.Translation(Vector(pivot) * -1))
        obj.data.update()
        obj.location = pivot
    elif kind == 'filler':
        obj.location = kit.filler_park(kit.MODULES.index(piece['module']) - len(kit.HEROES))
    obj.data.calc_loop_triangles()
    actual_triangles[name] = len(obj.data.loop_triangles)
    if args.style == 'anime' and kind in ('rock', 'filler', 'hard'):
        # Hard-coral dressing contains many overlapping narrow coral branches. A
        # rock-sized expansion pushes their back-facing hulls through adjacent
        # branches, producing black speckles across their visible surfaces.
        outline_specs.append((name, obj, .004 if kind == 'hard' else .035))

# Simple rock proxies provide collision without making the visual meshes (or
# the boxfish itself) static physics bodies. One pivot-centred box per kit module
# (plan W5b): Jolt never rotates a static body, and a box centred on the pivot is
# unchanged by the two allowed headings (0 and 1/2 revolution). The heroes' boxes
# are today's RockColliderLeft/Right exactly; the arch's covers the lintel only,
# so its cave stays open. Filler colliders wait, parked with their hidden rock.
from reef.geometry import _box
collider_names = {}
for index, module in enumerate(kit.MODULES):
    hero = next((h for h in kit.HEROES if h['name'] == module), None)
    if hero:
        name, (lo, hi), location = hero['collider_name'], hero['collider'], hero['pivot']
    else:
        filler_mesh = static['reef_' + module]['mesh']
        top = max(v[2] for v in filler_mesh.vertices)
        half_x = .85 * (max(v[0] for v in filler_mesh.vertices) - min(v[0] for v in filler_mesh.vertices)) / 2
        half_y = .85 * (max(v[1] for v in filler_mesh.vertices) - min(v[1] for v in filler_mesh.vertices)) / 2
        name = 'RockCollider' + module.capitalize()
        lo, hi = (-half_x, -half_y, 0.0), (half_x, half_y, round(.8 * top, 3))
        location = kit.filler_park(index - len(kit.HEROES))
    proxy = Mesh(name.lower())
    _box(proxy, lo, hi, 'rock')
    obj = bpy.data.objects.new(name, blender_mesh(proxy))
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj['wf_schema_path'] = str(repo / 'wfsource/source/oas/statplat.oad')
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 0
    obj['wf_Mesh Name'] = proxy.name + '.iff'
    obj['wf_original_mesh_name'] = proxy.name + '.iff'
    collider_names[module] = (name, [round(v, 4) for v in lo], [round(v, 4) for v in hi])

# A hidden hull satisfies Level::reset's Player requirement and drives the fish.
hull = Mesh('player_hull')
_box(hull, (-.05,-.05,-.05), (.05,.05,.05), 'rock')
player = bpy.data.objects['Player']
player.data = blender_mesh(hull)
targets = {'duster': anchor_map()['feather_duster'],
           'clam': anchor_map()['giant_clam'],
           'crab': anchor_map()['guard_crab'], 'shrimp': anchor_map()['cleaner_station'],
           'worms': worm_origin()}
verification = targets.get(args.verification_target)
player.location = ((verification[0] + (.3 if not args.verification_far else 3),
                    verification[1], max(.9, verification[2] + .35))
                   if verification else anchor_map()['boxfish_spawn'])
player['wf_Model Type'] = 'Mesh'
player['wf_Mesh Name'] = 'player_hull.iff'
player['wf_original_mesh_name'] = 'player_hull.iff'
player['wf_Mobility'] = 'Physics'
player['wf_Visibility Mailbox'] = 0
player['wf_Script Controls Input'] = 'True'
player['wf_Mass'] = 1.0
player['wf_Falling Acceleration'] = 0.0
player['wf_original_bbox'] = (-.05,-.05,-.05,.05,.05,.05)
for key, value in {'Running Acceleration':0, 'Walking Acceleration':0,
                   'Jumping Acceleration':0, 'Running Deceleration':.05,
                   'Air Acceleration':0, 'Horiz Air Drag':0, 'Vert Air Drag':0,
                   'Max Air Speed':4, 'Max Ground Speed':4, 'Turn Rate':0,
                   'Elasticity':0}.items():
    player['wf_'+key] = float(value)

# Fish have independent anchored render actors; the physics Player remains an
# invisible control hull, as in the other standalone aquarium tanks.
animated_triangles = {}
for name, mesh, pos in (
    ('BoxfishVisual', boxfish(Mesh), anchor_map()['boxfish_spawn']),
    ('HumbugOne', humbug(Mesh), anchor_map()['humbug_pair']),
    ('HumbugTwo', humbug(Mesh), tuple(a+b for a,b in zip(anchor_map()['humbug_pair'], (.5,.1,-.2)))),
):
    animated_triangles[name] = triangles(mesh)
    obj = bpy.data.objects.new(name, blender_mesh(mesh))
    if args.style == 'anime':
        outline_specs.append((name, obj, .012))
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    obj['wf_schema_path'] = str(oad)
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Mesh Name'] = mesh.name + '.iff'
    obj['wf_original_mesh_name'] = mesh.name + '.iff'

# Moving forms remain separate from the static reef so the director can pose
# them without re-uploading the large static life group.
worm_crown_origin = worm_origin()
for name, builder, pos in (
    ('SeaFan', life._sea_fan, anchor_map()['sea_fan_left']),
    ('FeatherStar', life._feather_star, anchor_map()['feather_star']),
    ('Nudibranch', life._nudibranch, anchor_map()['nudibranch']),
    ('WormCrowns', lambda mesh, _: life.worm_crowns(mesh, worm_crown_origin), worm_crown_origin),
    ('FeatherDusters', life.feather_dusters, anchor_map()['feather_duster']),
    ('FlowerpotCoral', corals.flowerpot, anchor_map()['flowerpot']),
    ('LeatherCoral', corals.leather_coral, anchor_map()['leather_coral']),
    ('GiantClam', life._clam, anchor_map()['giant_clam']),
    ('GuardCrab', invertebrates.guard_crab, anchor_map()['guard_crab']),
    ('ShrimpOne', invertebrates.banded_shrimp, anchor_map()['cleaner_station']),
    ('ShrimpTwo', invertebrates.banded_shrimp, tuple(a+b for a,b in zip(anchor_map()['cleaner_station'], (.35,.12,0)))),
    ('HermitCrab', invertebrates.hermit_crab, anchor_map()['hermit_crab']),
):
    mesh = Mesh(name.lower())
    builder(mesh, (0, 0, 0))
    animated_triangles[name] = triangles(mesh)
    obj = bpy.data.objects.new(name, blender_mesh(mesh))
    if args.style == 'anime' and name in ('GuardCrab', 'ShrimpOne', 'ShrimpTwo'):
        outline_specs.append((name, obj, .006))
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    obj['wf_schema_path'] = str(oad)
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Mesh Name'] = mesh.name + '.iff'
    obj['wf_original_mesh_name'] = mesh.name + '.iff'

# Attached life belongs to the hero module it grows on (plan W5b): it shows and hides with
# that module, and W5c places it at the module pivot plus this offset. The fish swim freely.
ATTACHED = ('SeaFan', 'FeatherStar', 'Nudibranch', 'WormCrowns', 'FeatherDusters', 'FlowerpotCoral',
            'LeatherCoral', 'GiantClam', 'GuardCrab', 'ShrimpOne', 'ShrimpTwo', 'HermitCrab')
attached = {}
for name in ATTACHED:
    obj = bpy.data.objects[name]
    position = tuple(obj.location)
    host = kit.host_of_point(position)
    pivot = kit.hero_pivot(host)
    obj['wf_Visibility Mailbox'] = kit.module_cell(host)
    attached[name] = {'module': host, 'offset': [round(position[i] - pivot[i], 5) for i in range(3)]}

# Colony clumps (plan W5b): small static pieces W5c places on site-table points, rotating
# local +z onto the site normal. One shared mesh per kind; each clump has its own cell and
# waits, hidden and parked, until W5c shows it. They are not baked (lit like the animals).
clumps = []
for kind, count in kit.CLUMPS:
    clump = kit.clump_mesh(Mesh, kind)
    data = blender_mesh(clump)
    for k in range(count):
        serial = len(clumps)
        name = f'KitClump{kind.capitalize()}{k + 1}'
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = kit.clump_park(serial)
        obj['wf_schema_path'] = str(oad)
        obj['wf_Mobility'] = 'Anchored'
        obj['wf_Model Type'] = 'Mesh'
        obj['wf_Mass'] = 0.0
        obj['wf_Visibility Mailbox'] = kit.CLUMP_CELL_BASE + serial
        obj['wf_Mesh Name'] = clump.name + '.iff'
        obj['wf_original_mesh_name'] = clump.name + '.iff'
        clumps.append({'actor': name, 'kind': kind, 'cell': kit.CLUMP_CELL_BASE + serial,
                       'triangles': triangles(clump), 'mesh': clump.name + '.iff'})

sun = bpy.data.objects['SunLight']
sun.rotation_euler = (0, .6981317, 1.5707963)
sun['wf_lightType'] = 'Directional'
for channel, value in zip(('Red','Green','Blue'),(.65,.69,.74)):
    sun['wf_light'+channel] = value
ambient = sun.copy()
ambient.name = 'AmbientLight'
bpy.context.scene.collection.objects.link(ambient)
ambient['wf_lightType'] = 'Ambient'
for channel, value in zip(('Red','Green','Blue'),(.43,.48,.56)):
    ambient['wf_light'+channel] = value
bpy.data.objects['LookAt'].location = (0, 0, 2.75)
wide = bpy.data.objects['cs_wide']
wide.location = (0, -7.5, 2.75)
if verification:
    bpy.data.objects['LookAt'].location = verification
    wide.location = (verification[0], verification[1] - 3.0, verification[2] + .4)
for axis in 'XYZ': wide['wf_Position '+axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow','Target','Track Object'): wide['wf_'+key] = 'LookAt'
look_close = bpy.data.objects['LookAt'].copy()
look_close.name = 'LookClose'
look_close.location = (0, 0, 2.3)
bpy.context.scene.collection.objects.link(look_close)
close = wide.copy()
close.name = 'cs_close'
close.location = (0, -6.5, 2.3)
for key in ('Follow', 'Target', 'Track Object'):
    close['wf_'+key] = 'LookClose'
bpy.context.scene.collection.objects.link(close)
cam = bpy.data.objects['Camera']
cam.location = wide.location
cam['wf_Mass'] = 1.0
cam['wf_FoggingColor'] = 0x102b40
cam['wf_FoggingStartDistance'] = 9
cam['wf_FoggingCompleteDistance'] = 45
if args.style == 'realistic':
    # The aquarium is only 1.2 m across; use a gentle absorption over its
    # scaled camera distance so the sand and coral retain their warm colours.
    cam['wf_WaterAbsorbR'] = .016
    cam['wf_WaterAbsorbG'] = .009
    cam['wf_WaterAbsorbB'] = .004
    # S2 is gated on a matched Chromecast HD cost measurement.
    cam['wf_CausticStrength'] = 0.0
    cam['wf_CausticScale'] = 5.0
    cam['wf_ToonBands'] = 0
else:
    cam['wf_WaterAbsorbR'] = 0.0
    cam['wf_WaterAbsorbG'] = 0.0
    cam['wf_WaterAbsorbB'] = 0.0
    cam['wf_CausticStrength'] = 0.0
    cam['wf_CausticScale'] = 0.0
    cam['wf_ToonBands'] = 3
bpy.data.objects['Matte']['wf_Matte Type'] = 'Color'
bpy.data.objects['Matte']['wf_Background Color'] = 0x09141e
room = bpy.data.objects['Room']
room.location = (0,0,0)
room['wf_original_bbox'] = (-25,-30,-6,25,10,18)
room['wf_had_authored_bbox'] = True
objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name:i+1 for i,o in enumerate(objects)}
mailboxes = {n:600+i for i,n in enumerate(['init','phase','heading','prev','mode','dart','cooldown','dx','dy','dz',
    'vx','vy','vz','target','x','y','z','yaw','scale','sy','cy','actor','ox','oy','oz','camera','clock','pulse'])}
header = ''.join(f': tk-{name} {number} ;\n' for name,number in mailboxes.items())
for name, number in {'player':indices['Player'], 'touch':0, 'jelly':0, 'limit-x':5.3,
                     'limit-y':2.3, 'bottom':.9, 'top':5.0, 'speed':1.2,
                     'focus-z':2.3, 'cam-close':indices['cs_close'], 'cam-wide':indices['cs_wide']}.items():
    header += f': tk-{name} {number} ;\n'
header += species.header('betta')
core = (repo/'wflevels/aquarium_tanks/controller.fth').read_text().replace(
    '\\ SPECIES_CONTROLLER', species.controller('betta'))
player['wf_Script'] = header + core + '\ntk-player-tick\n'
def rotate(index, a='0', b='0', c='0'):
    """Forth that sets an actor's whole rotation, in revolutions.

    Writing all three axes keeps each actor's orientation explicit. (Until
    2026-11-08 the engine also required it: rotation writes from scripts went
    into one Euler shared by every actor and applied only on a C write, so a
    lone A or B write leaked into the next actor. The engine now applies each
    axis to its own actor.) Arguments are Forth expressions.
    """
    return (f' {a} INDEXOF_ROTATION_A {index} write-actor-mailbox'
            f' {b} INDEXOF_ROTATION_B {index} write-actor-mailbox'
            f' {c} INDEXOF_ROTATION_C {index} write-actor-mailbox\n')

visual = indices['BoxfishVisual']
tick = ': reef-tick\n'
for axis in 'XYZ':
    tick += f' INDEXOF_{axis}_POS tk-player read-actor-mailbox INDEXOF_{axis}_POS {visual} write-actor-mailbox\n'
    tick += f' INDEXOF_{axis}_POS tk-player read-actor-mailbox tk-{axis.lower()} tk!\n'
tick += (rotate(visual, c='tk-heading tk@') +
         f' 648 tk@ 0 = if tk-x tk@ dup * tk-y tk@ dup * + '
         f'tk-z tk@ tk-focus-z - dup * + 5 > if 1 648 tk! then then\n'
         f' 648 tk@ if tk-camera-tick else {indices["cs_wide"]} INDEXOF_CAMSHOT tk! then ;\nreef-tick\n')
if verification:
    tick = tick[:tick.index(' 648 tk@ if tk-camera-tick')] + f' {indices["cs_wide"]} INDEXOF_CAMSHOT tk! ;\nreef-tick\n'
fish_x, fish_y, fish_z = anchor_map()['humbug_pair']
shoal = ': reef-shoal\n 640 tk@ tk-dt@ .12 * + tk-frac 640 tk!\n'
shoal += (f' INDEXOF_X_POS tk-player read-actor-mailbox {fish_x} - dup * '
          f'INDEXOF_Z_POS tk-player read-actor-mailbox {fish_z} - dup * + 1.44 < 641 tk!\n')
shoal += (' 641 tk@ if 2.5 740 tk! else 740 tk@ tk-dt@ - 0 max 740 tk! then\n'
          ' 740 tk@ 0 > if 741 tk@ tk-dt@ 2 * + 1 min '
          'else 741 tk@ tk-dt@ - 0 max then 741 tk!\n')
for name, offset, phase in (('HumbugOne', 0, 0), ('HumbugTwo', .5, .25)):
    idx = indices[name]
    shoal += (f' {fish_x+offset} 640 tk@ {phase} + tk-sin .22 * + INDEXOF_X_POS {idx} write-actor-mailbox\n'
              f' {fish_z - (0 if not offset else .2)} 741 tk@ .48 * - '
              f'INDEXOF_Z_POS {idx} write-actor-mailbox\n')
shoal += ';\n'
worm_tick = (': reef-worm ( x y z index -- ) 1063 tk! 1062 tk! 1061 tk! 1060 tk!\n'
             ' INDEXOF_X_POS tk-player read-actor-mailbox 1060 tk@ - dup *\n'
             ' INDEXOF_Y_POS tk-player read-actor-mailbox 1061 tk@ - dup * +\n'
             ' INDEXOF_Z_POS tk-player read-actor-mailbox 1062 tk@ - dup * + .64 <\n'
             ' if 1063 tk@ 7 * 15 mod .35 * 3 + 1000 1063 tk@ + tk!\n'
             '    1020 1063 tk@ + tk@ tk-dt@ 6.533333 * - .02 max\n'
             ' else 1000 1063 tk@ + tk@ tk-dt@ - 0 max 1000 1063 tk@ + tk!\n'
             '    1020 1063 tk@ + tk@ 1000 1063 tk@ + tk@ 0 <=\n'
             '    if tk-dt@ .653333 * + 1 min then\n'
             ' then 1020 1063 tk@ + tk!\n'
             ' 1020 1063 tk@ + tk@ 1195 1063 tk@ 4 * + tk! ;\n')
from reef.placement import NUDIBRANCH_PATH as nudi_path
life_tick = (': reef-life\n' + rotate(indices["SeaFan"], a='640 tk@ tk-sin .012 *')
             + rotate(indices["FeatherStar"], c='640 tk@ .17 + tk-sin .018 *') +
             f' 751 tk@ tk-dt@ .03 * + tk-frac 751 tk!\n'
             # The slug crawls back and forth along the sand at the foot of the
             # left rock (reef.placement.NUDIBRANCH_PATH), on the sand without
             # bobbing, and turns to face its direction of travel (front = -x).
             f' {nudi_path["x"]} 751 tk@ tk-sin {nudi_path["amplitude"]} * + '
             f'INDEXOF_X_POS {indices["Nudibranch"]} write-actor-mailbox\n'
             f' {anchor_map()["nudibranch"][2]} INDEXOF_Z_POS {indices["Nudibranch"]} write-actor-mailbox\n'
             # Headings are in revolutions: half a turn faces +x.
             + rotate(indices["Nudibranch"], c='751 tk@ .25 + tk-sin 0 > if .5 else 0 then'))
# ReefSettings (plan W5a), owned by the Director: Layout, Rocks, Colonies,
# Seed (fields 1-4). Polled once a second into 860-863 so a settings-panel
# change is seen without a reload; W5c lays out the reef from them.
life_tick += (f' 864 tk@ tk-dt@ - dup 864 tk! 0 <= if 1 864 tk!'
              f' {indices["Director"]} 1 property@ if else drop 0 then 860 tk!'
              f' {indices["Director"]} 2 property@ if else drop 3 then 861 tk!'
              f' {indices["Director"]} 3 property@ if else drop 1 then 862 tk!'
              f' {indices["Director"]} 4 property-int-bytes@ if drop 65536 * swap 256 * + +'
              f' else drop drop drop drop 0 then 863 tk! then\n')
life_tick += ' 1064 tk@ 0 = if\n' + ''.join(f' 1 {1020+i} tk!\n' for i in range(15)) + ' 1 1064 tk! then\n'
for i, worm in enumerate(worm_mouths()):
    x, y, z = worm['mouth']
    life_tick += f' {x:.6f} {y:.6f} {z:.6f} {i} reef-worm\n'
life_tick += f' 1027 tk@ 642 tk! 1155 15 {indices["WormCrowns"]} dfrm-pose-curves 1099 tk!\n'
duster_x, duster_y, duster_z = anchor_map()['feather_duster']
life_tick += ' 788 tk@ 0 = if 1 784 tk! 1 785 tk! 1 786 tk! 1 787 tk! 1 788 tk! then\n'
for worm in range(4):
    x, y, z = duster_x + (worm-1.5)*.42, duster_y, duster_z + (worm % 2)*.12
    timer, scale, control = 780+worm, 784+worm, 1255+40+worm*4
    life_tick += (f' INDEXOF_X_POS tk-player read-actor-mailbox {x} - dup * '
                  f'INDEXOF_Y_POS tk-player read-actor-mailbox {y} - dup * + '
                  f'INDEXOF_Z_POS tk-player read-actor-mailbox {z} - dup * + .64 < '
                  f'if {3+worm} {timer} tk! {scale} tk@ tk-dt@ 4.9 * - .02 max '
                  f'else {timer} tk@ tk-dt@ - 0 max {timer} tk! '
                  f'{scale} tk@ {timer} tk@ 0 <= if tk-dt@ .4 * + 1 min then then '
                  f'dup {scale} tk! {control} tk!\n')
life_tick += f' 1255 4 {indices["FeatherDusters"]} dfrm-pose-curves 1099 tk!\n'
life_tick += (' 790 tk@ tk-dt@ .008 * + tk-frac 790 tk!\n'
              ' 789 tk@ tk-dt@ 790 tk@ tk-sin .5 * .5 + .06 * .075 + * + tk-frac 789 tk!\n')
for curve in range(12):
    control = 1391+40+curve*4
    life_tick += f' 1 {control} tk! 789 tk@ {curve*.09} + tk-sin 7 * {control+3} tk!\n'
life_tick += f' 1391 12 {indices["FlowerpotCoral"]} dfrm-pose-curves 1099 tk!\n'
life_tick += (f' 640 tk@ tk-sin .075 * .925 + 1519 tk! '
              f'1 1523 tk! 640 tk@ tk-sin 4 * 1522 tk! '
              f'1479 2 {indices["LeatherCoral"]} dfrm-pose-curves 1099 tk!\n')
for curve in range(10):
    control = 1311 + 40 + 4 * curve
    life_tick += f' 1 {control} tk! 640 tk@ {curve * .08} + tk-sin 12 * {control + 3} tk!\n'
life_tick += f' 1311 10 {indices["FeatherStar"]} dfrm-pose-curves 1099 tk!\n'
clam_x = anchor_map()['giant_clam'][0]
life_tick += (f' INDEXOF_X_POS tk-player read-actor-mailbox {clam_x} - dup * '
              f' INDEXOF_Y_POS tk-player read-actor-mailbox -1.15 - dup * + 1 < '
              f' INDEXOF_Z_POS tk-player read-actor-mailbox .82 > & '
              f' if 4 746 tk! else 746 tk@ tk-dt@ - 0 max 746 tk! then\n'
              f' 746 tk@ 0 > if 745 tk@ tk-dt@ 3 * + 1 min '
              f'else 745 tk@ tk-dt@ - 0 max then 745 tk!\n'
              f' 1 440 tk! 1 444 tk! 1 745 tk@ .65 * - 448 tk! '
              f' 745 tk@ 22 * 443 tk! 745 tk@ 22 * 447 tk!\n'
              f' 400 3 {indices["GiantClam"]} dfrm-pose-curves 1099 tk!\n')
station = anchor_map()['cleaner_station']
crab_x, crab_y, crab_z = anchor_map()['guard_crab']
life_tick += (f' INDEXOF_X_POS tk-player read-actor-mailbox {crab_x} - dup * '
              f'INDEXOF_Y_POS tk-player read-actor-mailbox {crab_y} - dup * + '
              f'INDEXOF_Z_POS tk-player read-actor-mailbox {crab_z} - dup * + 1 < '
              f'if 2 643 tk! else 643 tk@ tk-dt@ - 0 max 643 tk! then '
              + rotate(indices["GuardCrab"], a='643 tk@ 0 > if .16 else 0 then'))
for curve in range(10):
    base = 1531 + 40 + 4 * curve
    life_tick += f' 1 {base} tk!\n'
    if curve in (4, 9):
        life_tick += f' 643 tk@ 0 > if 42 else 0 then {base + 3} tk!\n'
    else:
        life_tick += f' 640 tk@ {curve * .125} + tk-sin 18 * {base + 3} tk!\n'
life_tick += f' 1531 10 {indices["GuardCrab"]} dfrm-pose-curves 1099 tk!\n'
for curve in range(6):
    control = 1611 + 40 + 4 * curve
    life_tick += f' 1 {control} tk! 640 tk@ {curve * .17} + tk-sin 16 * {control + 3} tk!\n'
life_tick += f' 1611 6 {indices["HermitCrab"]} dfrm-pose-curves 1099 tk!\n'
for shrimp, block, phase in (('ShrimpOne', 1675, 0), ('ShrimpTwo', 1739, .3)):
    for curve in range(6):
        control = block + 40 + 4 * curve
        amplitude = 12 if curve % 3 == 1 else 20
        life_tick += (f' 1 {control} tk! 640 tk@ {phase + curve * .13} + tk-sin '
                      f'{amplitude} * {control + 3} tk!\n')
    life_tick += f' {block} 6 {indices[shrimp]} dfrm-pose-curves 1099 tk!\n'
for curve in range(5):
    control = 1803 + 40 + 4 * curve
    life_tick += f' 1 {control} tk! 640 tk@ {curve * .19} + tk-sin 20 * {control + 3} tk!\n'
life_tick += f' 1803 5 {indices["BoxfishVisual"]} dfrm-pose-curves 1099 tk!\n'
life_tick += (f' 647 tk@ 0 = if {station[0]} 645 tk! {station[0]+.35} 646 tk! '
              f'{station[1]} 747 tk! {station[1]+.12} 748 tk! '
              f'{station[2]} 749 tk! {station[2]} 750 tk! 1 647 tk! then\n'
              f' INDEXOF_X_POS tk-player read-actor-mailbox {station[0]} - dup * '
              f'INDEXOF_Z_POS tk-player read-actor-mailbox {station[2]} - dup * + 1 < '
              f'INDEXOF_XSPEED tk-player read-actor-mailbox abs .1 < & '
              f'INDEXOF_YSPEED tk-player read-actor-mailbox abs .1 < & '
              f'INDEXOF_ZSPEED tk-player read-actor-mailbox abs .1 < & '
              f'if 644 tk@ tk-dt@ + 3 min 644 tk! else 0 644 tk! then\n')
life_tick += (' 644 tk@ 2 >= 744 tk@ 0 = & if 5 743 tk! 1 744 tk! then\n'
              ' 644 tk@ 0 = if 0 744 tk! then\n'
              ' 743 tk@ tk-dt@ - 0 max 743 tk!\n')
for name, anchor, offset, phase, amplitude in (
    ('GuardCrab', 'guard_crab', 0, 0, .025),
    ('ShrimpOne', 'cleaner_station', 0, .25, .06),
    ('ShrimpTwo', 'cleaner_station', .35, .5, .06),
    ('HermitCrab', 'hermit_crab', 0, .75, .12),
):
    if name.startswith('Shrimp'):
        cell = 645 if name == 'ShrimpOne' else 646
        ycell = 747 if name == 'ShrimpOne' else 748
        zcell = 749 if name == 'ShrimpOne' else 750
        yoffset = 0 if name == 'ShrimpOne' else .12
        life_tick += (f' 743 tk@ 0 > if INDEXOF_X_POS tk-player read-actor-mailbox {offset-.175} + '
                      f'else {anchor_map()[anchor][0] + offset} 640 tk@ {phase} + tk-sin {amplitude} * + then '
                      f'{cell} tk-v {cell} tk@ INDEXOF_X_POS {indices[name]} write-actor-mailbox\n')
        life_tick += (f' 743 tk@ 0 > if INDEXOF_Y_POS tk-player read-actor-mailbox {yoffset-.06} + '
                      f'else {station[1] + yoffset} then {ycell} tk-v '
                      f'{ycell} tk@ INDEXOF_Y_POS {indices[name]} write-actor-mailbox\n'
                      # Body centers sit above the boxfish, with the shrimp legs
                      # reaching its back instead of their bodies intersecting it.
                      f' 743 tk@ 0 > if INDEXOF_Z_POS tk-player read-actor-mailbox .24 + '
                      f'else {station[2]} then {zcell} tk-v '
                      f'{zcell} tk@ INDEXOF_Z_POS {indices[name]} write-actor-mailbox\n')
    elif name == 'GuardCrab':
        # Traverse a small loop around the host head, including a climb and descent.
        life_tick += (f' {anchor_map()[anchor][0]} 640 tk@ tk-sin .12 * + '
                      f'INDEXOF_X_POS {indices[name]} write-actor-mailbox\n'
                      f' {anchor_map()[anchor][2]} 640 tk@ .25 + tk-sin .12 * + '
                      f'INDEXOF_Z_POS {indices[name]} write-actor-mailbox\n')
    else:
        life_tick += (f' {anchor_map()[anchor][0] + offset} 640 tk@ {phase} + tk-sin {amplitude} * + '
                      f'INDEXOF_X_POS {indices[name]} write-actor-mailbox\n')
life_tick += ';\n'
# Kit visibility (plan W5b): every kit piece is hidden until its cell is set. Until W5c's
# layout exists, the Director shows the Fixed arrangement (the three hero modules) once at
# entry; fillers and colony clumps stay hidden and parked.
kit_init = (f': reef-kit-init {kit.KIT_INIT_GUARD} tk@ 0 = if'
            + ''.join(f' 1 {kit.module_cell(h["name"])} tk!' for h in kit.HEROES)
            + f' 1 {kit.KIT_INIT_GUARD} tk! then ;\n')
tick = tick.replace(': reef-tick\n', shoal + worm_tick + life_tick + kit_init + ': reef-tick\n reef-kit-init reef-shoal reef-life\n')
bpy.data.objects['Director']['wf_Script'] = header + core + tick
if args.bake_light:
    from reef.bake import bake_static
    fillers = [bpy.data.objects[f['rock']] for f in kit.FILLERS]
    # Fixed scene first, with the parked fillers out of the way below the sand and frame.
    bake_static([bpy.data.objects[name] for name in FIXED_STATIC if name != 'reef_shell'], mat, args.style)
    # Fillers have no fixed neighbourhood: bake each alone, far from the reef, then park it.
    parked = [tuple(obj.location) for obj in fillers]
    for k, obj in enumerate(fillers):
        obj.location = (40.0 + 10.0 * k, 0.0, 0.0)
    bake_static(fillers, mat, args.style)
    for obj, location in zip(fillers, parked):
        obj.location = location
# Bake the visible surfaces before adding their reversed outline shells, so
# the shells do not occlude the surfaces during Cycles' light and AO passes.
for name, obj, width in outline_specs:
    actual_hull_triangles[name] = add_outline(obj.data, width)
# Static budgets (plan W5b) count what can be visible at once, not every loaded group:
# the Fixed arrangement, and the worst Random set = the three heroes with their dressing,
# the two largest fillers (D6: at most 5 rocks, heroes first) and every colony clump.
triangle_limit = ANIME_STATIC_TRIANGLES_MAX if args.style == 'anime' else STATIC_TRIANGLES_MAX
fixed_triangles = sum(actual_triangles[name] for name in FIXED_STATIC)
largest_fillers = sorted((f['rock'] for f in kit.FILLERS), key=lambda n: -actual_triangles[n])[:2]
worst_static = FIXED_STATIC + largest_fillers
worst_triangles = (sum(actual_triangles[name] for name in worst_static)
                   + sum(c['triangles'] for c in clumps))
# Outline hulls visible at once: the worst static set's plus every animal's (the fish and
# crabs always show), which is what ANIME_HULL_TRIANGLES_MAX has always bounded.
animal_hull = sum(actual_hull_triangles.get(name, 0) for name in animated_triangles)
worst_hull = sum(actual_hull_triangles.get(name, 0) for name in worst_static) + animal_hull
kit_budget = {'fixed': {'groups': len(FIXED_STATIC), 'triangles': fixed_triangles,
                        'hull_triangles': sum(actual_hull_triangles.get(n, 0) for n in FIXED_STATIC) + animal_hull},
              'worst_visible': {'groups': len(worst_static) + len(clumps), 'triangles': worst_triangles,
                                'hull_triangles': worst_hull, 'pieces': worst_static + [c['actor'] for c in clumps]}}
triangle_total = fixed_triangles
if len(FIXED_STATIC) > STATIC_GROUPS_MAX or fixed_triangles > triangle_limit:
    raise ValueError(f'Fixed reef exceeds budget: {len(FIXED_STATIC)} groups, {fixed_triangles} triangles')
if worst_triangles > KIT_VISIBLE_TRIANGLES_MAX[args.style] or len(worst_static) + len(clumps) > KIT_VISIBLE_GROUPS_MAX:
    raise ValueError(f'worst visible kit set exceeds budget: {kit_budget["worst_visible"]}')
if worst_hull > ANIME_HULL_TRIANGLES_MAX:
    raise ValueError(f'anime outlines exceed budget: {worst_hull} triangles visible at once')
if len(animated_triangles) > 16:
    raise ValueError(f'reef exceeds animated actor budget: {len(animated_triangles)}')
# Keep small valid faces. Record actual degeneracy separately, including faces
# that collapse after the exporter's 16.16 coordinate conversion. The export
# may still canonicalize coincident vertices; identify affected source faces
# instead of silently treating every small face as invalid.
triangle_diagnostics = {}
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH' or not obj.data.polygons:
        continue
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.faces.index_update()
    small, zero_area, quantized_degenerate = [], [], []
    for face in bm.faces:
        area = face.calc_area()
        points = [tuple(int(c * 65536) for c in vertex.co) for vertex in face.verts]
        a, b, c = points
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(c[i] - a[i] for i in range(3))
        cross = (u[1]*v[2] - u[2]*v[1], u[2]*v[0] - u[0]*v[2],
                 u[0]*v[1] - u[1]*v[0])
        if area == 0:
            zero_area.append(face.index)
        elif cross == (0, 0, 0):
            quantized_degenerate.append(face.index)
        elif area < .00008:
            small.append(face.index)
    if small or zero_area or quantized_degenerate:
        triangle_diagnostics[obj.name] = {'small_valid_faces': small,
            'zero_area_faces': zero_area, 'quantized_degenerate_faces': quantized_degenerate}
        print(f'{obj.name}: retaining {len(small)} small valid faces; '
              f'{len(zero_area)} zero-area, {len(quantized_degenerate)} quantization-degenerate')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
(out / 'triangle-diagnostics.json').write_text(json.dumps(triangle_diagnostics, indent=2)+'\n')
kit_map = {'modules': [], 'clumps': clumps, 'attached': attached, 'init_guard': kit.KIT_INIT_GUARD,
           'fixed_layout': {h['name']: list(h['pivot']) for h in kit.HEROES}, 'park_z': kit.PARK_Z}
for index, module in enumerate(kit.MODULES):
    pieces = [name for name, piece in static.items() if piece['module'] == module]
    hero = index < len(kit.HEROES)
    kit_map['modules'].append({
        'name': module, 'role': 'hero' if hero else 'filler', 'cell': kit.module_cell(module),
        'rock': 'reef_' + module, 'pieces': pieces, 'piece_actors': [indices[n] for n in pieces],
        'collider': collider_names[module][0], 'collider_actor': indices[collider_names[module][0]],
        'collider_box': {'lo': collider_names[module][1], 'hi': collider_names[module][2]},
        'pivot': list(kit.hero_pivot(module)) if hero else None,
        'park': None if hero else list(kit.filler_park(index - len(kit.HEROES))),
        'attached': [n for n, a in attached.items() if a['module'] == module],
        'sites': [{'p': list(s['p']), 'n': list(s['n'])} for s in kit.site_table(module)],
        'triangles': sum(actual_triangles[n] for n in pieces)})
for clump in clumps:
    clump['actor_index'] = indices[clump['actor']]
(out / 'actor-map.json').write_text(json.dumps({'level':args.level_id, 'actors':indices, 'indices':indices,
    'triangles':actual_triangles, 'triangle_total':triangle_total, 'kit':kit_map, 'kit_budget':kit_budget,
    'animated_triangles':animated_triangles, 'hull_triangles':actual_hull_triangles, 'anchors':anchor_map(),
    'rock_union':args.remesh_rocks, 'unverified':True}, indent=2)+'\n')
bpy.ops.wf.export_level(filepath=str(out / f'{args.level_id}.lev'))
# Level settings object (plan W5a): both styles carry the same ReefSettings.
import shutil
for settings_file in ('settings.oas', 'settings-bindings.json'):
    source = repo / 'wflevels/aquarium_thai_reef' / settings_file
    if source.resolve() != (out / settings_file).resolve():
        shutil.copyfile(source, out / settings_file)
from wf_blender import dfrm_chunk
worm_rig.bind_exported_mesh(out / 'wormcrowns.iff', Mesh, dfrm_chunk)
feather_rig.bind_exported_mesh(out / 'featherstar.iff', Mesh, dfrm_chunk)
crab_rig.bind_exported_mesh(out / 'guardcrab.iff', Mesh, dfrm_chunk)
crab_rig.bind_exported_mesh(out / 'hermitcrab.iff', Mesh, dfrm_chunk, species='hermit')
for shrimp in ('shrimpone', 'shrimptwo'):
    crab_rig.bind_exported_mesh(out / f'{shrimp}.iff', Mesh, dfrm_chunk, species='shrimp')
crab_rig.bind_exported_mesh(out / 'reef_boxfish.iff', Mesh, dfrm_chunk, species='boxfish')
crab_rig.bind_exported_mesh(out / 'giantclam.iff', Mesh, dfrm_chunk, species='clam')
for name, kind in (('featherdusters', 'dusters'), ('flowerpotcoral', 'flowerpot'), ('leathercoral', 'leather')):
    flora_rig.bind_exported_mesh(out / f'{name}.iff', Mesh, dfrm_chunk, kind)

if args.preview:
    # A presentation-only camera and lights let the procedural scene be
    # inspected in the pinned headless Blender container. They are not actors
    # in the exported level.
    camera_data = bpy.data.cameras.new('ReefPreviewCamera')
    camera = bpy.data.objects.new('ReefPreviewCamera', camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (0, -19, 3.05)
    target = Vector((0, 0, 2.55))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.lens = 43
    bpy.context.scene.camera = camera
    for name, position, energy, size, color in (
        ('ReefPreviewKey', (-4, -7, 9), 2400, 7, (0.72, 0.86, 1.0)),
        ('ReefPreviewFill', (6, -2, 6), 1100, 6, (0.28, 0.69, 1.0)),
    ):
        light_data = bpy.data.lights.new(name, 'AREA')
        light_data.energy = energy
        light_data.shape = 'DISK'
        light_data.size = size
        light_data.color = color
        light = bpy.data.objects.new(name, light_data)
        bpy.context.scene.collection.objects.link(light)
        light.location = position
        light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    scene = bpy.context.scene
    for preview_object in scene.objects:
        if preview_object.get('wf_schema_path') and not preview_object.name.startswith('reef_'):
            preview_object.hide_render = True
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = 'WORLD'
    scene.render.resolution_x = 720
    scene.render.resolution_y = 450
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(args.preview.resolve())
    scene.world = bpy.data.worlds.new('ReefPreviewWorld')
    scene.world.color = (0.025, 0.08, 0.12)
    bpy.ops.render.render(write_still=True)
