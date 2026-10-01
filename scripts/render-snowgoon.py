#!/usr/bin/env python3
"""render-snowgoon.py: render the snowgoons icon art: a menacing three-armed snowman, low-poly and flat-shaded like the game.

Run with Blender in the background:   blender -b --python scripts/render-snowgoon.py -- OUT.png [--size WxH]   (default 1920x1080)

"Snow goons" are the three-armed snowmen of the original level (Calvin and Hobbes' menacing snowmen are the
inspiration). The repository has no snowman mesh (the level's actors are placeholder boxes), so this model is authored
here from primitives: three stacked low-poly snow balls, coal eyes under angled brows, a carrot nose, a jagged coal
scowl and **three** stick arms, one raised on each side and a third on the left shoulder, all from the upper torso. Original art; nothing is traced.
"""
import math, sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[0] if argv else "/tmp/snowgoon.png"
W, H = (int(v) for v in (argv[argv.index("--size") + 1] if "--size" in argv else "1920x1080").lower().split("x"))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def mat(name, rgb, rough=0.9):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    return m


SNOW, COAL, CARROT, WOOD = mat("snow", (0.93, 0.96, 1.0)), mat("coal", (0.02, 0.02, 0.03), 0.5), mat("carrot", (0.95, 0.35, 0.05)), mat("wood", (0.25, 0.14, 0.07))


def flat(o, m):
    o.data.materials.append(m)
    for p in o.data.polygons: p.use_smooth = False
    return o


def ball(loc, r, m, sub=2, squash=1.0):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=r, location=loc)
    o = bpy.context.object; o.scale.z = squash
    return flat(o, m)


def stick(a, b, r, m):
    a, b = Vector(a), Vector(b); d = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=r, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object; o.rotation_mode = "QUATERNION"; o.rotation_quaternion = d.to_track_quat("Z", "Y")
    return flat(o, m)


# body: three snow balls, the middle one leaning toward the viewer a little
ball((0, 0, 0.62), 0.62, SNOW); ball((0, -0.04, 1.42), 0.47, SNOW); ball((0, -0.08, 2.08), 0.34, SNOW)
# face on the head (the viewer looks along +Y from -Y): eyes, angled brows, nose, scowl
for sx in (-1, 1):
    ball((sx * 0.13, -0.38, 2.16), 0.055, COAL, 1)
    stick((sx * 0.30, -0.36, 2.34), (sx * 0.06, -0.38, 2.24), 0.022, COAL)          # brows slanting down to the nose
bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.06, radius2=0.0, depth=0.32, location=(0, -0.55, 2.04))
n = bpy.context.object; n.rotation_euler = (math.radians(90), 0, 0); flat(n, CARROT)
for i in range(7):                                                                 # a jagged, downturned scowl
    t = i / 6.0; x = (t - 0.5) * 0.46; z = 1.89 - 0.11 * (1 - abs(2 * t - 1) ** 1.5) * -1 - 0.0
    ball((x, -0.36 + 0.05 * abs(x) * 0, 1.86 + 0.08 * (1 - (2 * t - 1) ** 2)), 0.032, COAL, 1)
# coal buttons
for z in (1.62, 1.40, 1.18): ball((0, -0.45, z), 0.04, COAL, 1)
# three arms, ALL on the torso (the middle ball; nothing on the head or the back), and every arm has a JOINT: an upper arm and a
# forearm meeting at an elbow knob, then a forked hand. Left and right are raised from the shoulders; the third leaves the centre of
# the upper chest between them, forward at the elbow, then steeply up (kept clear of the face).
def arm(shoulder, elbow, hand, fork=(0.14, 0.34)):
    stick(shoulder, elbow, 0.055, WOOD)                                   # upper arm
    ball(elbow, 0.085, WOOD, 1)                                           # the joint
    stick(elbow, hand, 0.045, WOOD)                                       # forearm
    h, e = Vector(hand), Vector(elbow); d = (h - e).normalized()
    side = Vector((0, -1, 0)).cross(d).normalized() if abs(d.y) < 0.9 else Vector((1, 0, 0))
    for k in (-1, 1):                                                     # forked hand: two twigs off the end of the forearm
        stick(h - d * 0.10, h + d * fork[1] + side * k * fork[0], 0.03, WOOD)


arm((-0.38, -0.02, 1.68), (-0.88, -0.08, 1.60), (-1.16, -0.12, 2.18))
arm((0.38, -0.02, 1.68), (0.88, -0.08, 1.60), (1.16, -0.12, 2.18))
arm((0.0, -0.40, 1.60), (0.18, -0.72, 1.70), (0.60, -0.88, 2.20))
# ground and sky
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0)); g = bpy.context.object; flat(g, mat("ground", (0.78, 0.85, 0.95)))
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True
bg = sc.world.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.05, 0.09, 0.2, 1); bg.inputs["Strength"].default_value = 1.0
# lights: cold rim from behind, warm key from the front-left
for loc, e, col in (((-3, -4, 4.5), 700, (1.0, 0.93, 0.85)), ((3, 4, 3), 500, (0.55, 0.7, 1.0))):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object; L.data.energy = e; L.data.size = 3; L.data.color = col
    L.rotation_euler = (Vector((0, 0, 1.4)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
# camera: slightly below the head, looking up at it: menacing
bpy.ops.object.camera_add(location=(0.10, -5.0, 1.35)); cam = bpy.context.object
cam.rotation_euler = (Vector((0.05, 0, 1.45)) - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 55; sc.camera = cam
sc.render.engine = "CYCLES"; sc.cycles.samples = 48; sc.cycles.device = "CPU"
try: sc.cycles.use_denoising = True
except Exception: pass
cam.data.sensor_fit = "VERTICAL"; cam.data.sensor_height = 36    # same vertical framing at any aspect
sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.filepath = out; sc.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
print("wrote", out)
