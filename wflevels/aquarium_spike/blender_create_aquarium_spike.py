#!/usr/bin/env python3
"""blender_create_aquarium_spike.py — Phase 0 translucency test card for the aquarium level.

Plan: docs/plans/2026-09-30-aquarium-level.md § Verification, Phase 0 steps 1–4.

A renderer test, not art. Seen from a parked camera at y = CAM_Y looking +Y:

    backdrop  y = +3   6 × 4 m quad, 24-bit checker.tga (8 × 8 cells)
    fish-far  y = +1.5 yellow UV sphere, entirely behind the pane in screen space
    pane      y =  0   quad, 16-bit pane.tga — every texel has bit 15 set (→ alpha 128)
                       its left strip hangs past the backdrop over the empty background
    fish-near y = -1.5 magenta UV sphere, half over the pane's right edge

Actor order in the exported .lev follows creation order: fish-a, pane, fish-b, backdrop.
The default build puts fish-a behind the pane and fish-b in front; `-- swap` swaps their
*positions*, so the far fish moves from before the pane in actor order to after it. That is
the plan's "swap the two fish's order" (step 3) without depending on object names.
`-- pane-last` creates the pane after the backdrop (the draw-order fix the plan proposed).

Run (headless):
  python3 wflevels/aquarium_spike/make_pane_texture.py
  blender --background --python-exit-code 1 \
      --python wflevels/aquarium_spike/blender_create_aquarium_spike.py [-- swap] [pane-last]
  bash wftools/wf_blender/build_level_binary.sh aquarium_spike
Or all of it plus the captures and pixel samples: python3 wflevels/aquarium_spike/run_spike.py
"""
import math
import os
import sys

import addon_utils
import bpy

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
REPO          = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OAD_DIR       = os.path.join(REPO, 'wftools', 'wf_oad', 'tests', 'fixtures')
LEVEL_NAME    = 'aquarium_spike'
OUT_LEV       = os.path.join(SCRIPT_DIR, LEVEL_NAME + '.lev')

ARGV = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SWAP = 'swap' in ARGV
PANE_LAST = 'pane-last' in ARGV

# ── Card geometry (metres; X right, Y depth away from camera, Z up) ──────────
CARD_Z        = 2.0                        # card centre height
BACKDROP_Y    = 3.0
BACKDROP_X    = (-3.0, 3.0)
BACKDROP_Z    = (0.0, 4.0)
PANE_Y        = 0.0
PANE_X        = (-4.5, 1.5)                # x < -3 overhangs the empty background
PANE_Z        = (0.5, 3.5)
FISH_R        = 0.6
FAR_POS       = (-1.0, 1.5, CARD_Z)
NEAR_POS      = (1.5, -1.5, CARD_Z)
CAM_POS       = (0.0, -12.0, CARD_Z)
LOOK_POS      = (0.0, 0.0, CARD_Z)
PLAYER_POS    = (0.0, -25.0, 1.0)          # anchored, behind the camera, out of frame
FISH_A_RGB    = (0.95, 0.85, 0.10)         # yellow
FISH_B_RGB    = (0.85, 0.15, 0.75)         # magenta

KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light', 'room', 'camshot',
                'target', 'player'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


def find_by_class(cn):
    return next((o for o in bpy.data.objects if get_class(o) == cn), None)


def attach_schema(obj, oad):
    obj['wf_schema_path'] = os.path.join(OAD_DIR, oad + '.oad')


# 1. Clean scene, add-on, snowgoons scaffold stripped to one of each infrastructure class.
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable('wf_blender', default_set=False, persistent=False)
scene = bpy.context.scene
bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)
for obj in list(bpy.data.objects):
    if get_class(obj) not in KEEP_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in seen:
        bpy.data.objects.remove(obj, do_unlink=True)
    else:
        seen.add(cn)
print('[aquarium_spike] scaffold classes:', sorted(seen))

# Rename survivors so no snowgoons name leaks into an object reference.
for cn, new in (('director', 'Director'), ('camera', 'Camera'), ('levelobj', 'LevelObj'),
                ('matte', 'Matte'), ('room', 'Room'), ('camshot', 'cs_card'),
                ('target', 'LookAt'), ('player', 'Player'), ('light', 'SunLight')):
    o = find_by_class(cn)
    assert o is not None, f'no {cn} in the snowgoons scaffold'
    o.name = new


# 2. Materials.
def flat_material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def textured_material(name, tga):
    """White base + image: the fragment shader samples the texture only for white vertex colour."""
    path = os.path.join(SCRIPT_DIR, tga)
    if not os.path.isfile(path):
        raise SystemExit(f'[aquarium_spike] missing {tga} — run make_pane_texture.py')
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(path)
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
    return mat


def statplat(name, mesh, location):
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.location = location
    attach_schema(obj, 'statplat')
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Mass'] = 0.0
    obj['wf_Mesh Name'] = name.replace('-', '_') + '.iff'
    obj['wf_original_mesh_name'] = name.replace('-', '_') + '.iff'
    return obj


def card_quad(name, x, z, mat):
    """XZ-plane quad facing -Y (towards the camera), wound CCW as seen from -Y; UV 0..1 with
    WF v = 0 at the top row (gfx/material.cc CalcVRAMuv)."""
    me = bpy.data.meshes.new(name)
    (x0, x1), (z0, z1) = x, z
    me.from_pydata([(x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for li, (u, v) in enumerate(((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0))):
        uv.data[li].uv = (u, v)
    me.materials.append(mat)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)          # keep the pinned winding
    bm.to_mesh(me)
    bm.free()
    me.update()
    return me


def fish_mesh(name, rgb):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=FISH_R)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)  # outward
    bm.to_mesh(me)
    bm.free()
    me.materials.append(flat_material(name + '-mat', rgb))
    me.update()
    return me


# 3. Card actors. Creation order = actor index order = draw order within the room
#    (game/level.cc RenderScene walks ROOM_OBJECT_LIST_RENDER; no translucent pass, no sort).
#    Default: fish-a, pane, fish-b, backdrop. `-- pane-last` moves the pane after the backdrop,
#    i.e. every opaque actor is drawn before the translucent one.
pos_a, pos_b = (NEAR_POS, FAR_POS) if SWAP else (FAR_POS, NEAR_POS)


def make_pane():
    return statplat('pane', card_quad('pane', PANE_X, PANE_Z, textured_material('pane-mat', 'pane.tga')),
                    (0.0, PANE_Y, 0.0))


fish_a = statplat('fish-a', fish_mesh('fish-a', FISH_A_RGB), pos_a)
if not PANE_LAST:
    make_pane()
fish_b = statplat('fish-b', fish_mesh('fish-b', FISH_B_RGB), pos_b)
backdrop = statplat('backdrop', card_quad('backdrop', BACKDROP_X, BACKDROP_Z,
                                          textured_material('checker-mat', 'checker.tga')),
                    (0.0, BACKDROP_Y, 0.0))
if PANE_LAST:
    make_pane()
print(f'[aquarium_spike] swap={SWAP} pane_last={PANE_LAST}: fish-a at {pos_a}, fish-b at {pos_b}')

# 4. Lights: Directional + Ambient (both required — docs/level-building.md § Lighting).
#    Direction vector = (cos B cos C, cos B sin C, -sin B) points *toward* the light:
#    B = -30°, C = -90° → (0, -0.87, 0.5), i.e. from the camera side and above.
sun = bpy.data.objects['SunLight']
sun.location = (0.0, -6.0, 6.0)
sun.rotation_euler = (0.0, -math.radians(30.0), math.radians(-90.0))
sun['wf_lightType'] = 'Directional'
for ch in ('Red', 'Green', 'Blue'):
    sun[f'wf_light{ch}'] = 0.30
amb = sun.copy()
scene.collection.objects.link(amb)
amb.name = 'AmbientLight'
amb['wf_lightType'] = 'Ambient'
for ch in ('Red', 'Green', 'Blue'):
    amb[f'wf_light{ch}'] = 0.70

# 5. Parked camera (the "vista" rig, docs/level-building.md § CamShot): Absolute ×3, Fixed,
#    Follow = Target = LookAt. The camshot selects itself every tick from its own script.
look = bpy.data.objects['LookAt']
look.location = LOOK_POS
look['wf_Model Type'] = 'None'
look['wf_Script'] = ''
cs = bpy.data.objects['cs_card']
cs.location = CAM_POS
for axis in ('X', 'Y', 'Z'):
    cs[f'wf_Position {axis}'] = 'Absolute'
cs['wf_Rotation'] = 'Fixed'
cs['wf_Follow'] = 'LookAt'
cs['wf_Target'] = 'LookAt'
# Bungee mode (the wrapper's FLAG bungeecam = 1) aims at Target − Follow + Track Object
# (movecam.cc BungeeCameraHandler::update), so Track Object must be LookAt too — with
# Player there the camera turns round and stares at the player behind it.
cs['wf_Track Object'] = 'LookAt'
cs['wf_Model Type'] = 'None'
cs['wf_Script'] = '\\ wf\nINDEXOF_ACTOR_INDEX read-mailbox INDEXOF_CAMSHOT write-mailbox\n'
cam = bpy.data.objects['Camera']
cam.location = CAM_POS                               # start where the shot lands (bungee spring)
cam['wf_Model Type'] = 'None'
cam['wf_FoggingColor'] = 0x000000                    # fog off: it would tint the measured pixels
cam['wf_FoggingStartDistance'] = 999.0
cam['wf_FoggingCompleteDistance'] = 1000.0

# 6. Player: anchored, out of frame (the level needs one; the test does not).
player = bpy.data.objects['Player']
player.location = PLAYER_POS
player['wf_Mobility'] = 'Anchored'
player['wf_Script'] = ''

director = bpy.data.objects['Director']
director['wf_Script'] = ''                           # snowgoons' ActBoxOR forwarding is not needed
# Director and LevelObj keep snowgoons' Box models; parked where they left them, the LevelObj box
# showed up beside the backdrop (3.07, 3.64, 1.37). Park both behind the camera.
director.location = (-4.0, -20.0, 1.0)
bpy.data.objects['LevelObj'].location = (4.0, -20.0, 1.0)
# The snowgoons matte is a Box model at (3.07, 3.64, 1.37) — it drew a dim magenta block just
# right of the backdrop. Same fix as moon_site01: black colour matte, no model, out of frame.
matte = bpy.data.objects['Matte']
matte.location = (0.0, -20.0, 1.0)
matte['wf_Matte Type'] = 'Color'
matte['wf_Background Color'] = 0x000000
matte['wf_Model Type'] = 'None'

room = bpy.data.objects['Room']
room.location = (0.0, 0.0, 0.0)
room['wf_original_bbox'] = (-30.0, -40.0, -10.0, 30.0, 30.0, 20.0)

# 7. Export.
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SCRIPT_DIR, LEVEL_NAME + '.blend'))
print(f'[aquarium_spike] exporting {OUT_LEV}')
bpy.ops.wf.export_level(filepath=OUT_LEV)
print('[aquarium_spike] done')
