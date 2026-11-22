"""Before/after renders of the cottage window-box flowers (plan docs/plans/2026-11-22-cuckoo-village-flowers.md).

Run in the blender container:  scripts/in-linux-container.sh blender --background --python <this file> -- <out dir> [full|lean] [after-only|before-only] [views=closeup,cottage,street]
Loads the committed village_assets.blend, renders three views of the cottage as it is today ("before"), removes the
old cube plants from the house mesh, adds the new flat-coloured flowers (flowers.py) and renders the same views ("after").
Prints a line per render: RENDER <view> <before|after> <seconds>. Cycles on the CPU, 48 samples, denoised.
"""
import math
import sys
import time
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flowers as fl  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = Path(argv[0] if argv else '/tmp/flowers'); out.mkdir(parents=True, exist_ok=True)
quality = argv[1] if len(argv) > 1 else 'full'

bpy.ops.wm.open_mainfile(filepath=str(HERE / 'village_assets.blend'))
scene = bpy.context.scene
house = bpy.data.objects['standard_house']
for o in list(bpy.data.objects):
    if o is not house:
        bpy.data.objects.remove(o, do_unlink=True)
house.location = (0, 0, 0)

ground = bpy.data.meshes.new('ground'); ground.from_pydata([(-30, -30, -0.05), (30, -30, -0.05), (30, 30, -0.05), (-30, 30, -0.05)], [], [(0, 1, 2, 3)])
g = bpy.data.objects.new('ground', ground); scene.collection.objects.link(g)
gm = bpy.data.materials.new('grass'); gm.use_nodes = True
next(n for n in gm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Base Color'].default_value = (0.16, 0.38, 0.12, 1)
ground.materials.append(gm)
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.2
sun.rotation_euler = (math.radians(52), math.radians(8), math.radians(28)); scene.collection.objects.link(sun)
world = bpy.data.worlds.new('w'); world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND'); bg.inputs['Color'].default_value = (0.55, 0.66, 0.78, 1); bg.inputs['Strength'].default_value = 0.9
scene.world = world
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 48
try:
    scene.cycles.use_denoising = True
except Exception:
    pass
scene.render.resolution_x, scene.render.resolution_y = 1280, 720
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); scene.collection.objects.link(cam); scene.camera = cam

BOX_TOP = 1.655
BOXES = [(-0.78, -1.12), (0.78, -1.12)]
VIEWS = {   # name: (camera position, look-at, focal length mm). The street view is what the TV shows from the tower camera.
    'closeup': ((0.45, -2.9, 1.95), (0.78, -1.12, 1.62), 50),
    'cottage': ((-1.6, -7.2, 2.6), (0, -1.0, 1.6), 50),
    'street':  ((-3.5, -11.5, 3.6), (0, -1.0, 1.6), 50),
}


def render(view, tag):
    pos, target, lens = VIEWS[view]
    cam.location = pos; cam.data.lens = lens
    cam.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(out / f'{view}-{tag}.png')
    t = time.perf_counter(); bpy.ops.render.render(write_still=True)
    print(f'RENDER {view} {tag} {time.perf_counter() - t:.1f}', flush=True)


only = [a[6:] for a in argv if a.startswith('views=')]
if only:
    VIEWS = {k: v for k, v in VIEWS.items() if k in only[0].split(',')}
if 'before-only' in argv:
    for view in VIEWS:
        render(view, 'before')
    sys.exit(0)
tris_before = sum(len(p.vertices) - 2 for p in house.data.polygons)
if 'after-only' not in argv:
    for view in VIEWS:
        render(view, 'before')

# After: drop the old cube plants (everything above the box rim on the two front window boxes) ...
bm = bmesh.new(); bm.from_mesh(house.data)
doomed = [f for f in bm.faces if f.calc_center_median().y < -1.07 and 1.66 < f.calc_center_median().z < 1.90 and 0.4 < abs(f.calc_center_median().x) < 1.2]
removed = sum(len(f.verts) - 2 for f in doomed)
bmesh.ops.delete(bm, geom=doomed, context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(house.data); bm.free()
print(f'MESH house tris before {tris_before} removed {removed} after {sum(len(p.vertices) - 2 for p in house.data.polygons)}')

# ... and add the new flowers: one mesh per flat material, colour only, no texture.
merged = fl.merge([fl.placed(fl.box_flowers(i, quality), (bx, by, BOX_TOP), 0.0, 1.0) for i, (bx, by) in enumerate(BOXES)])
print('MESH flowers tris', fl.triangle_count(merged), fl.counts(merged))
for name, (verts, faces) in merged.items():
    if not faces:
        continue
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob)
    m = bpy.data.materials.new(name); m.use_nodes = True
    r, gc, b = fl.MATERIALS[name]
    bsdf = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (r, gc, b, 1); bsdf.inputs['Roughness'].default_value = 0.8
    me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = False
for view in VIEWS:
    render(view, 'after')
print('DONE')
