"""Standalone render of a single asset for plan screenshots.
Usage: blender --background --python render_asset.py -- <asset_func> <out.png>
Imports the builder functions from blender_create_moon.py and renders a
close-up 3/4-top-front view of the named asset.
"""
import bpy, sys, os, math
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Parse args after '--'
argv = sys.argv
asset_arg = 'moon_racer'
out_png   = os.path.join(SCRIPT_DIR, 'render_asset_out.png')
if '--' in argv:
    rest = argv[argv.index('--') + 1:]
    if len(rest) >= 1:
        asset_arg = rest[0]
    if len(rest) >= 2:
        out_png = rest[1]

# ── load helpers from blender_create_moon.py without executing the full script ─
# We need _make_mat, _build_moon_racer (etc) but NOT the full level build.
# Trick: exec only the function defs by reading up to the first non-def top-level call.

import re

src_path = os.path.join(SCRIPT_DIR, 'blender_create_moon.py')
with open(src_path) as f:
    src = f.read()

# Collect only: imports, constants, and def blocks (skip everything else).
# Simple approach: exec the whole file in a sandbox that ignores I/O errors.
import numpy as np
import json
import addon_utils

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("wf_blender", default_set=False, persistent=False)

# Provide stubs for the parts of the script that do file I/O / heavy lifting
HEIGHTS_NPY = os.path.join(SCRIPT_DIR, 'terrain_heights.npy')
HEIGHTS_JSON = os.path.join(SCRIPT_DIR, 'terrain_heights.json')

heights_stub = np.zeros((10, 10), dtype=np.float32)
meta_stub = {"cell_size_m": 10.0}

# Patch numpy.load and open so the script's top-level I/O stubs out
import builtins
_real_load = np.load
_real_open = builtins.open

def _stub_load(path, *a, **kw):
    if 'terrain_heights.npy' in str(path):
        return heights_stub
    return _real_load(path, *a, **kw)

def _stub_open(path, *a, **kw):
    if 'terrain_heights.json' in str(path):
        import io
        return io.StringIO(json.dumps(meta_stub))
    return _real_open(path, *a, **kw)

np.load = _stub_load
builtins.open = _stub_open

# Also stub bpy.ops.wf so import_level / export_level are no-ops
class _NoOp:
    def __getattr__(self, name):
        return lambda *a, **kw: None
bpy.ops.wf = _NoOp()

# Stub bpy.ops.render.render so the preview render doesn't fire
_real_render = bpy.ops.render.render
bpy.ops.render.render = lambda *a, **kw: None

ns = {'__name__': '__render_asset__'}
exec(compile(src, src_path, 'exec'), ns)

# Restore
np.load = _real_load
builtins.open = _real_open
bpy.ops.render.render = _real_render

# ── find the object ────────────────────────────────────────────────────────────
obj = bpy.data.objects.get(asset_arg)
if obj is None:
    print(f"[render_asset] ERROR: object '{asset_arg}' not found in scene")
    print("[render_asset] Objects:", [o.name for o in bpy.data.objects])
    sys.exit(1)

print(f"[render_asset] Found '{obj.name}' — {len(obj.data.vertices)} verts")

# ── camera: 3/4 top-front view ────────────────────────────────────────────────
import mathutils

# Delete everything except our target object
for o in list(bpy.data.objects):
    if o != obj:
        bpy.data.objects.remove(o, do_unlink=True)

# Compute bounding box centre + size
verts_world = [obj.matrix_world @ mathutils.Vector(v.co) for v in obj.data.vertices]
xs = [v.x for v in verts_world]; ys = [v.y for v in verts_world]; zs = [v.z for v in verts_world]
cx = (max(xs)+min(xs))/2; cy = (max(ys)+min(ys))/2; cz = (max(zs)+min(zs))/2
sz = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))

# Camera at 45° azimuth, 35° elevation, distance = 2.5× bbox size
dist = sz * 2.5
az, el = math.radians(45), math.radians(35)
cam_x = cx + dist * math.cos(el) * math.cos(az)
cam_y = cy + dist * math.cos(el) * math.sin(az)
cam_z = cz + dist * math.sin(el)

cam_data = bpy.data.cameras.new('RenderCam')
cam_data.lens = 50
cam_obj = bpy.data.objects.new('RenderCam', cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = (cam_x, cam_y, cam_z)
direction = mathutils.Vector((cx, cy, cz)) - mathutils.Vector((cam_x, cam_y, cam_z))
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam_obj

# Simple 3-point lighting
sun = bpy.data.lights.new('Sun', 'SUN')
sun.energy = 3.0
sun_obj = bpy.data.objects.new('Sun', sun)
bpy.context.scene.collection.objects.link(sun_obj)
sun_obj.location = (cam_x*0.5, cam_y*0.5, cam_z*1.5)
sun_obj.rotation_euler = (math.radians(45), 0, math.radians(45))

fill = bpy.data.lights.new('Fill', 'SUN')
fill.energy = 0.8
fill_obj = bpy.data.objects.new('Fill', fill)
bpy.context.scene.collection.objects.link(fill_obj)
fill_obj.location = (-cam_x, -cam_y*0.5, cam_z)
fill_obj.rotation_euler = (math.radians(60), 0, math.radians(225))

# Grey world background
world = bpy.data.worlds.new('World')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.15, 0.15, 0.18, 1)
bpy.context.scene.world = world

# Render
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600
bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print(f"[render_asset] → {out_png}")
