"""
blender_create_mm_practice.py — drive Blender to produce mm_practice.lev.

Run headlessly:
  blender --background --python blender_create_mm_practice.py

Strategy: import snowgoons-blender.lev (gets all infrastructure objects with
correct OAD schemas attached), delete everything except the reusable
infrastructure, reposition objects for the ramp layout, add a new Ramp
statplat mesh, then export to mm_practice.lev.
"""

import bpy
import os
import sys
import math

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..'))
SNOWGOONS_LEV = os.path.join(REPO, 'wflevels', 'snowgoons-blender', 'snowgoons-blender.lev')
OUT_LEV = os.path.join(SCRIPT_DIR, 'mm_practice_blender.lev')
OAD_DIR = os.path.join(REPO, 'wfsource', 'source', 'oas')

# ── 1. Start with a clean scene ─────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
# Enable the wf_blender addon AFTER factory reset (reset clears addon state)
import addon_utils
addon_utils.enable("wf_blender", default_set=False, persistent=False)
scene = bpy.context.scene

# ── 2. Import the snowgoons reference level ─────────────────────────────────────
print(f"[mm_practice] Importing {SNOWGOONS_LEV}")
bpy.ops.wf.import_level(filepath=SNOWGOONS_LEV)

# ── 3. Identify what to keep vs delete ─────────────────────────────────────────
# The wf_blender importer stores class name via wf_schema_path: basename without .oad
KEEP_CLASSES = {'director', 'camera', 'levelobj', 'matte', 'light',
                'room', 'camshot', 'target', 'actboxor', 'player'}
DELETE_CLASSES = {'statplat', 'enemy', 'snowman01', 'missile',
                  'tool', 'tool01', 'ground01', 'hp'}


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    if schema:
        return os.path.splitext(os.path.basename(schema))[0]
    return ''


# Delete gameplay objects
for obj in list(bpy.data.objects):
    if get_class(obj) in DELETE_CLASSES:
        bpy.data.objects.remove(obj, do_unlink=True)

# Drop duplicates: keep only the first of each infrastructure class
seen = set()
for obj in list(bpy.data.objects):
    cn = get_class(obj)
    if cn in KEEP_CLASSES:
        if cn in seen:
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            seen.add(cn)

print("[mm_practice] Classes found:", sorted({get_class(o) for o in bpy.data.objects}))
print("[mm_practice] Remaining objects:", [o.name for o in bpy.data.objects])

# ── 4. Reposition infrastructure for the ramp layout ──────────────────────────
# Coordinate system: WF Z-up = Blender Z-up (identity)
#
# Ramp runs world y=[0..20], z=[4..0], x=[-5..5]
# Player spawns at (0, 0, 5)

def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None

def move(obj, x, y, z):
    if obj:
        obj.location = (x, y, z)

move(find_by_class('director'),  0, 10,  5)
move(find_by_class('levelobj'),  0, 10,  5)
move(find_by_class('matte'),     0, 10,  5)
move(find_by_class('camera'),   20, -10, 15)
move(find_by_class('light'),     0,  10, 20)
move(find_by_class('player'),    0,   0,  5)

# Room — large box covering the ramp
room = find_by_class('room')
if room:
    room.location = (0, 10, 3)
    room.scale = (1, 1, 1)

# Actboxor — camera activation box covering whole level
actboxor = find_by_class('actboxor')
if actboxor:
    actboxor.location = (0, 10, 3)

# CamShot — isometric view
camshot = find_by_class('camshot')
if camshot:
    camshot.location = (20, -10, 15)

# Targets
targets = [o for o in bpy.data.objects if get_class(o) == 'target']
if len(targets) >= 1:
    targets[0].location = (5, 0, 4.5)   # Target01: camera position reference
    targets[0].name = 'Target01'
if len(targets) >= 2:
    targets[1].location = (0, 10, 2)    # Target02: look-at
    targets[1].name = 'Target02'

# Player
pl = find_by_class('player')
if pl:
    pl.location = (0, 0, 5)

# ── 5. Add the Ramp mesh as a statplat ─────────────────────────────────────────
# Create a quad ramp mesh in Blender, then attach the statplat OAD schema

verts = [
    (-5, -10,  2),   # v0 high-left
    ( 5, -10,  2),   # v1 high-right
    ( 5,  10, -2),   # v2 low-right
    (-5,  10, -2),   # v3 low-left
]
faces = [(0, 1, 2, 3)]  # quad; Blender will triangulate on export

mesh_data = bpy.data.meshes.new("RampMesh")
mesh_data.from_pydata(verts, [], faces)
mesh_data.update()

ramp_obj = bpy.data.objects.new("Ramp", mesh_data)
ramp_obj.location = (0, 10, 2)
scene.collection.objects.link(ramp_obj)

# Attach UV map (simple planar unwrap)
bpy.context.view_layer.objects.active = ramp_obj
bpy.ops.object.select_all(action='DESELECT')
ramp_obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)
bpy.ops.object.mode_set(mode='OBJECT')

# Add material with texture
mat = bpy.data.materials.new("RampMat")
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
tex_node = nt.nodes.new('ShaderNodeTexImage')
tex_node.image = bpy.data.images.load(
    os.path.join(SCRIPT_DIR, 'G_SnowyGrass1.tga'), check_existing=True)
nt.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
mesh_data.materials.append(mat)
ramp_obj.data.materials.append(mat)

# Attach statplat OAD schema
statplat_oad = os.path.join(
    REPO, 'wftools', 'wf_oad', 'tests', 'fixtures', 'statplat.oad')
ramp_obj['wf_schema_path'] = statplat_oad

# Set key statplat properties (wf_ prefix matches _prop_key convention)
ramp_obj['wf_Mesh Name'] = 'ramp.iff'
ramp_obj['wf_Model Type'] = 'Mesh'
ramp_obj['wf_Mobility'] = 'Anchored'
ramp_obj['wf_Surface Friction'] = 0.5
ramp_obj['wf_Mass'] = 0.0

print(f"[mm_practice] Ramp object created at {ramp_obj.location}")

# ── 6. Export the level ─────────────────────────────────────────────────────────
print(f"[mm_practice] Exporting to {OUT_LEV}")
bpy.ops.wf.export_level(filepath=OUT_LEV)
print(f"[mm_practice] Done — {OUT_LEV}")
