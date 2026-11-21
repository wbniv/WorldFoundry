"""Render the village clock face at 3:00, 6:30 and 10:08 (hands posed from timeline.py, as the level does).

Run in the Blender container and read the images: at 3:00 the minute hand points straight up and the hour hand
straight right, both pivoting at the dial centre; a hand that starts anywhere else is off its pivot.

    WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender --background --python wflevels/cuckoo_village/check_dial.py

Writes build-docker/dialcheck/fixed-<h>-<mm>.png (git-ignored).
"""
import math, sys
from pathlib import Path
import bpy
ROOT = Path('/src'); HERE = ROOT/'wflevels/cuckoo_village'; LAYOUT = ROOT/'wflevels/cuckoo_village_layout'
sys.path.insert(0, str(HERE))
import timeline as tl
source = (LAYOUT/'generate.py').read_text()
cut = source.index('scene=bpy.context.scene')
scope = {'__file__': str(LAYOUT/'generate.py'), '__name__': 'dial'}
exec(compile(source[:cut], str(LAYOUT/'generate.py'), 'exec'), scope)
objs = bpy.data.objects
for hn in ('hour_hand', 'minute_hand'):
    h = objs[hn]; h.data = h.data.copy()
    xs = [v.co.x for v in h.data.vertices]; c = (min(xs) + max(xs)) / 2
    for v in h.data.vertices: v.co.x -= c
    h.data.update()
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.device = 'CPU'
sc.render.resolution_x = 900; sc.render.resolution_y = 900
cam = bpy.data.cameras.new('c'); cam.lens = 85
co = bpy.data.objects.new('c', cam); sc.collection.objects.link(co); sc.camera = co
cx, cy, cz = tl.DIAL
co.location = (cx, cy - 4.0, cz); co.rotation_euler = (math.pi/2, 0, 0)    # looks along +Y
for t in ('3:00:00', '6:30:00', '10:08:22'):
    h, m, s = [int(float(x)) for x in t.split(':')]
    p = tl.all_poses(h*3600 + m*60 + s)
    for name in ('hour_hand', 'minute_hand'):
        o = objs[name]
        o.rotation_euler = (p[name][3]*math.tau, p[name][4]*math.tau, p[name][5]*math.tau)
    sc.render.filepath = f"/src/build-docker/dialcheck/fixed-{h}-{m:02d}.png"
    bpy.ops.render.render(write_still=True)
    print('rendered', t, p['hour_hand'][4], p['minute_hand'][4])
