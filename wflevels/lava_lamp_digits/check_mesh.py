"""Report exported triangle areas against the fixed-point normal threshold."""
import bpy

limit = 8e-5
minimum = float('inf')
total_small = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH' or not obj.get('wf_schema_path'):
        continue
    obj.data.calc_loop_triangles()
    areas = []
    for tri in obj.data.loop_triangles:
        a, b, c = (obj.data.vertices[i].co for i in tri.vertices)
        areas.append((b-a).cross(c-a).length / 2)
    small = sum(area < limit for area in areas)
    total_small += small
    if areas:
        minimum = min(minimum, min(areas))
    if small:
        print(f'{obj.name}: {small}/{len(areas)} below {limit:g}; minimum {min(areas):.9g}')
print(f'minimum triangle area: {minimum:.9g}; below {limit:g}: {total_small}')
assert total_small == 0, 'triangles below the conservative normal threshold'
