"""Render a close-up preview of the Moon RACER for the plan doc."""
import bpy, math, sys, os
import mathutils

OUT_PNG = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '/tmp/moon_racer.png'

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

parts = []

def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1)
    return m

mat_white = mat('rover_white', (0.92, 0.92, 0.92))
mat_dark  = mat('rover_dark',  (0.15, 0.15, 0.17))
SEG = 8

def add_cyl(r, h, loc, m, rot=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=SEG, radius=r, depth=h, location=loc)
    o = bpy.context.object
    o.rotation_euler = rot
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    parts.append((o, m))

def add_cube(sx, sy, sz, loc, m):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.object
    o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    parts.append((o, m))

add_cube(4.0, 2.0, 0.5, (0.0, 0.0, 0.6),   mat_white)
for fx in (+1.6, -1.6):
    for fy in (+1.1, -1.1):
        add_cyl(0.5, 0.3, (fx, fy, 0.5), mat_dark, rot=(math.pi/2, 0, 0))
add_cube(1.0, 0.8, 0.4, (0.0, 0.0, 1.25),   mat_white)
add_cyl(0.06, 1.5, (1.6, 0.0, 1.6),          mat_dark)
add_cube(1.5, 0.8, 0.06, (1.6, 0.0, 2.42),   mat_white)
add_cube(1.2, 0.15, 0.15, (-1.0, -1.1, 1.1), mat_dark)

for o, m in parts:
    o.data.materials.clear()
    o.data.materials.append(m)

bpy.ops.object.select_all(action='DESELECT')
for o, _ in parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = parts[0][0]
bpy.ops.object.join()
rover = bpy.context.object

# Camera — 3/4 top-front
verts = [rover.matrix_world @ mathutils.Vector(v.co) for v in rover.data.vertices]
xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
cx = (max(xs)+min(xs))/2; cy = (max(ys)+min(ys))/2; cz = (max(zs)+min(zs))/2
sz = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
dist = sz * 2.2
az, el = math.radians(220), math.radians(30)
cam_loc = (cx + dist*math.cos(el)*math.cos(az),
           cy + dist*math.cos(el)*math.sin(az),
           cz + dist*math.sin(el))
cam_data = bpy.data.cameras.new('Cam'); cam_data.lens = 50
cam_obj  = bpy.data.objects.new('Cam', cam_data)
scene.collection.objects.link(cam_obj)
cam_obj.location = cam_loc
cam_obj.rotation_euler = (mathutils.Vector((cx,cy,cz))-mathutils.Vector(cam_loc)).to_track_quat('-Z','Y').to_euler()
scene.camera = cam_obj

# Lighting
for (loc, energy) in [((8,-6,10), 4.0), ((-5,8,6), 1.5)]:
    ld = bpy.data.lights.new('L','SUN'); ld.energy = energy
    lo = bpy.data.objects.new('L', ld); scene.collection.objects.link(lo)
    lo.location = loc

world = bpy.data.worlds.new('W'); world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.08,0.08,0.10,1)
scene.world = world

scene.render.resolution_x = 800; scene.render.resolution_y = 600
scene.render.engine = 'BLENDER_EEVEE'
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUT_PNG
bpy.ops.render.render(write_still=True)
print(f"[render] → {OUT_PNG}")
