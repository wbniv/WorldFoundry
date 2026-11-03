"""Assemble a static reef preview with the existing WF Blender exporter.

Run inside the existing Blender image only, after making it available. This is
an unverified prototype: exporter/cooked output and camera framing require tests.
The source checkout is read-only; pass --out to a writable scratch directory.
"""
import argparse
import json
import sys
from pathlib import Path
from mathutils import Vector

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import STATIC_GROUPS_MAX, STATIC_TRIANGLES_MAX
p = argparse.ArgumentParser()
p.add_argument('--repo', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
p.add_argument('--level-id', default='aquarium_thai_reef')
p.add_argument('--style', choices=('realistic', 'anime'), default='realistic')
p.add_argument('--preview', type=Path, help='also render a Blender composition preview to this PNG')
p.add_argument('--remesh-rocks', action='store_true', help='voxel-union the blockout rock masses before export')
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
repo = args.repo.resolve()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo / 'wflevels/aquarium_tanks'))
sys.path.insert(0, str(repo / 'wftools'))
from mesh import Mesh
from reef.atlas import write_atlas
from reef.geometry import build_groups, triangles
from reef.scene import anchor_map
from reef.fishes import boxfish, humbug
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
# Swatches correspond to the atlas tile order. UVs are world-projected and kept
# inside each tile; texturing and scale are provisional until rendered in-engine.
swatches = {'rock':4, 'porites':1, 'pocillopora':1, 'pocillopora_tip':1,
            'acropora':1, 'scroll':1, 'flowerpot':1, 'flowerpot_tip':1,
            'leather':1, 'fan':0, 'sponge':2, 'sponge_rim':2,
            'sponge_inner':2, 'sand':3, 'frame':4, 'coralline':0,
            'polyp':1, 'zoanthid':5, 'clam':6, 'fish':7}

def blender_mesh(mesh, smooth=False):
    data = bpy.data.meshes.new(mesh.name)
    data.from_pydata(mesh.vertices, [], mesh.faces)
    data.materials.append(mat)
    uv = data.uv_layers.new(name='UVMap')
    for poly, key in zip(data.polygons, mesh.colors):
        if key in ('fish_dark', 'fish_white'):
            u = (776 if key == 'fish_dark' else 792) / 1024
            v = 1 - 520 / 1024
            for li in poly.loop_indices:
                uv.data[li].uv = (u, v)
            continue
        tile = swatches[key]
        for li in poly.loop_indices:
            x, y, z = data.vertices[data.loops[li].vertex_index].co
            # Leave a small margin to reduce bleeding between neighboring tiles.
            u = (tile % 4 + .04 + .92 * ((x * .37 + y * .11) % 1)) / 4
            v = 1 - (tile // 4 + .04 + .92 * ((z * .37 + y * .11) % 1)) / 2
            uv.data[li].uv = (u, v)
    data.update()
    if smooth:
        for poly in data.polygons:
            poly.use_smooth = True
    return data

groups = build_groups(Mesh)
actual_triangles = {}
oad = repo / 'wfsource/source/oas/statplat.oad'
for name, mesh in groups.items():
    obj = bpy.data.objects.new(name, blender_mesh(mesh,
        smooth=name in ('reef_left', 'reef_right', 'reef_arch')))
    bpy.context.scene.collection.objects.link(obj)
    obj['wf_schema_path'] = str(oad)
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Mesh Name'] = name + '.iff'
    obj['wf_original_mesh_name'] = name + '.iff'
    if args.remesh_rocks and name in ('reef_left', 'reef_right', 'reef_arch'):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        # The anime pass has a tighter static-geometry budget. A coarser rock
        # union preserves the same placements while leaving room for life.
        obj.data.remesh_voxel_size = .17 if args.style == 'anime' else .12
        bpy.ops.object.voxel_remesh()
        obj.select_set(False)
        uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
        for loop in obj.data.loops:
            x, y, z = obj.data.vertices[loop.vertex_index].co
            u = (.04 + .92 * ((x * .37 + y * .11) % 1)) / 4
            v = 1 - (1 + .04 + .92 * ((z * .37 + y * .11) % 1)) / 2
            uv.data[loop.index].uv = (u, v)
        for poly in obj.data.polygons:
            poly.use_smooth = True
        obj.data.update()
    obj.data.calc_loop_triangles()
    actual_triangles[name] = len(obj.data.loop_triangles)

# A hidden hull satisfies Level::reset's Player requirement. All content here is
# visual; these groups do not yet provide the planned custom collision proxies.
from reef.geometry import _box
hull = Mesh('player_hull')
_box(hull, (-.05,-.05,-.05), (.05,.05,.05), 'rock')
player = bpy.data.objects['Player']
player.data = blender_mesh(hull)
player.location = anchor_map()['boxfish_spawn']
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
for name, mesh, pos in (
    ('BoxfishVisual', boxfish(Mesh), anchor_map()['boxfish_spawn']),
    ('HumbugOne', humbug(Mesh), anchor_map()['humbug_pair']),
    ('HumbugTwo', humbug(Mesh), tuple(a+b for a,b in zip(anchor_map()['humbug_pair'], (.5,.1,-.2)))),
):
    obj = bpy.data.objects.new(name, blender_mesh(mesh))
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    obj['wf_schema_path'] = str(oad)
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Mesh Name'] = mesh.name + '.iff'
    obj['wf_original_mesh_name'] = mesh.name + '.iff'

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
wide.location = (0, -16, 2.75)
for axis in 'XYZ': wide['wf_Position '+axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow','Target','Track Object'): wide['wf_'+key] = 'LookAt'
cam = bpy.data.objects['Camera']
cam.location = wide.location
cam['wf_Mass'] = 1.0
cam['wf_FoggingColor'] = 0x102b40
cam['wf_FoggingStartDistance'] = 9
cam['wf_FoggingCompleteDistance'] = 45
if args.style == 'realistic':
    cam['wf_WaterAbsorbR'] = .055
    cam['wf_WaterAbsorbG'] = .025
    cam['wf_WaterAbsorbB'] = .012
    cam['wf_CausticStrength'] = .16
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
                     'focus-z':2.75, 'cam-close':indices['cs_wide'], 'cam-wide':indices['cs_wide']}.items():
    header += f': tk-{name} {number} ;\n'
header += species.header('betta')
core = (repo/'wflevels/aquarium_tanks/controller.fth').read_text().replace(
    '\\ SPECIES_CONTROLLER', species.controller('betta'))
player['wf_Script'] = header + core + '\ntk-player-tick\n'
visual = indices['BoxfishVisual']
tick = f': reef-tick\n {indices["cs_wide"]} INDEXOF_CAMSHOT tk!\n'
for axis in 'XYZ':
    tick += f' INDEXOF_{axis}_POS tk-player read-actor-mailbox INDEXOF_{axis}_POS {visual} write-actor-mailbox\n'
tick += f' tk-heading tk@ INDEXOF_ROTATION_C {visual} write-actor-mailbox ;\nreef-tick\n'
fish_x, fish_y, fish_z = anchor_map()['humbug_pair']
shoal = ': reef-shoal\n 640 tk@ tk-dt@ .12 * + tk-frac 640 tk!\n'
shoal += (f' INDEXOF_X_POS tk-player read-actor-mailbox {fish_x} - dup * '
          f'INDEXOF_Z_POS tk-player read-actor-mailbox {fish_z} - dup * + 1.44 < 641 tk!\n')
for name, offset, phase in (('HumbugOne', 0, 0), ('HumbugTwo', .5, .25)):
    idx = indices[name]
    shoal += (f' {fish_x+offset} 640 tk@ {phase} + tk-sin .22 * + INDEXOF_X_POS {idx} write-actor-mailbox\n'
              f' {fish_z - (0 if not offset else .2)} 641 tk@ if .48 - then '
              f'INDEXOF_Z_POS {idx} write-actor-mailbox\n')
shoal += ';\n'
tick = tick.replace(': reef-tick\n', shoal + ': reef-tick\n reef-shoal\n')
bpy.data.objects['Director']['wf_Script'] = header + core + tick
triangle_total = sum(actual_triangles.values())
triangle_limit = 30000 if args.style == 'anime' else STATIC_TRIANGLES_MAX
if len(groups) > STATIC_GROUPS_MAX or triangle_total > triangle_limit:
    raise ValueError(f'static reef exceeds budget: {len(groups)} groups, {triangle_total} triangles')
(out / 'actor-map.json').write_text(json.dumps({'level':args.level_id, 'actors':indices,
    'triangles':actual_triangles, 'triangle_total':triangle_total,
    'anchors':anchor_map(), 'rock_union':args.remesh_rocks, 'unverified':True}, indent=2)+'\n')
bpy.ops.wf.export_level(filepath=str(out / f'{args.level_id}.lev'))

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
