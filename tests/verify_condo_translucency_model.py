"""Inspect optical coverage and unchanged collision surfaces in the saved condo (Blender)."""
import sys
import bpy
from mathutils import Vector

failures = []
def check(label, condition):
    print(('PASS' if condition else 'FAIL') + ' ' + label)
    if not condition:
        failures.append(label)

def sheet(obj):
    return [p for p in obj.data.polygons if 0 < obj.data.materials[p.material_index].get('wf_opacity', 1) < 1]

slats = [bpy.data.objects[f'639-balcony-shade-slat-{i}'] for i in range(8)]
for o in slats:
    optical = sheet(o)
    check(o.name + ' one two-sided optical quad (two exported triangles)', len(optical) == 2)
    check(o.name + ' fabric opacity 0.32, prelit and two-sided',
          all(o.data.materials[p.material_index].get('wf_opacity') == .32 and
              o.data.materials[p.material_index].get('wf_double_sided') and
              o.data.materials[p.material_index].get('wf_prelit') for p in optical))
    check(o.name + ' original collision sides retained',
          len([p for p in o.data.polygons if o.data.materials[p.material_index].get('wf_opacity') == 0]) == 8)

# Use saved optical vertices plus the actual generated park offsets. This exercises
# geometric coverage through 101 travel positions rather than only the end poses.
h = (2.05 - 1.072) / 8
for step in range(101):
    c = step / 100
    intervals = []
    planes = []
    for i, o in enumerate(slats):
        vertices = {v for p in sheet(o) for v in p.vertices}
        points = [o.matrix_world @ Vector((o.data.vertices[v].co.x, o.data.vertices[v].co.y,
                                          o.data.vertices[v].co.z * c)) for v in vertices]
        park = (i + 1) * h + .03 + .005
        intervals.append((min(p.z for p in points) + park * (1-c),
                          max(p.z for p in points) + park * (1-c)))
        planes += [p.y for p in points]
    check(f'closedness {c:.2f}: all seven joins meet without overlap/gaps, including oblique views',
          all(abs(intervals[i][0] - intervals[i+1][1]) < 1/65536 for i in range(7)) and
          max(planes) - min(planes) < 1e-6)
    bar_top = 15.75 + 1.072 + (8*h + .035)*(1-c)
    check(f'closedness {c:.2f}: bottom sheet meets the moving bar', abs(intervals[-1][0]-bar_top) < 1/65536)
    if c == 0:
        check('raised optical fabric has zero area, parked above cassette bottom',
              all(abs(b-a) < 1e-6 and a > 17.8 for a,b in intervals))
for i in range(3):
    o = bpy.data.objects[f'639-project-door-panel-{i}']
    check(o.name + ' exactly one optical pane from either side', len(sheet(o)) == 2)
    check(o.name + ' 0.12 glass uses dedicated material',
          all(o.data.materials[p.material_index].name == 'door-glass' and
              o.data.materials[p.material_index].get('wf_opacity') == .12 for p in sheet(o)))
    optical_vertices = {v for p in sheet(o) for v in p.vertices}
    glass_points = [o.data.vertices[v].co for v in optical_vertices]
    all_points = [v.co for v in o.data.vertices]
    check(o.name + ' glass inset 10 cm within black aluminum border',
          abs(min(p.x for p in glass_points)-min(p.x for p in all_points)-.10) < 1e-5 and
          abs(max(p.x for p in all_points)-max(p.x for p in glass_points)-.10) < 1e-5 and
          abs(min(p.z for p in glass_points)-.10) < 1e-5 and
          abs(max(p.z for p in glass_points)-2.60) < 1e-5)
    width = max(p.x for p in all_points)-min(p.x for p in all_points)
    frame_area = width*2.7-(width-.2)*2.5
    for side in (-1,1):
        area = sum(p.area for p in o.data.polygons if p.material_index == 1 and p.normal.y*side > .99)
        # The handled leaf also contains opaque lock/handle faces.
        check(o.name + f' black frame coverage from side {side}',
              area >= frame_area-1e-5 if i == 0 else abs(area-frame_area) < 1e-5)
    if i == 0:
        x0 = min(p.x for p in all_points)
        yc = glass_points[0].y
        # Hardware projects beyond the frame's front/back faces; the key has
        # its own material. Its full footprint must sit within the 10 cm stile.
        hardware = {v for p in o.data.polygons
                    if p.material_index == 2 or
                    (p.material_index == 1 and any(abs(o.data.vertices[v].co.y-yc) > .051 for v in p.vertices))
                    for v in p.vertices}
        check('handle and lock on both sides fit inside the black frame',
              bool(hardware) and all(x0-1e-5 <= o.data.vertices[v].co.x <= x0+.10+1e-5 for v in hardware))
    check(o.name + ' closed collision box retained',
          len([p for p in o.data.polygons if o.data.materials[p.material_index].get('wf_opacity') == 0]) == 12)
    check(o.name + ' collision mass stays 75', o['wf_Mass'] == 75)
for name in ('door-hardware-black', 'door-key-metal', 'shade-cassette', 'shade-solar', 'shade-guide', 'shade-bar'):
    check(name + ' stays opaque', bpy.data.materials[name].get('wf_opacity', 1) == 1)
check('unrelated windows keep imported glass opacity contract', 'wf_opacity' not in bpy.data.materials['glass'])
print('RESULT:', 'PASS' if not failures else failures)
sys.exit(bool(failures))
