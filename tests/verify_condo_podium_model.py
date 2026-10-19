"""Blender check: lower podium matches the two unit slabs and retains the hallway."""
import sys
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

podium = bpy.data.objects['site-podium']
verts = [podium.matrix_world @ v.co for v in podium.data.vertices]
mesh = BVHTree.FromPolygons(verts, [list(p.vertices) for p in podium.data.polygons])
floors = []
for name in ('unit-639','unit-640'):
    o = bpy.data.objects[name]
    points = [o.matrix_world @ v.co for v in o.data.vertices]
    faces = [list(p.vertices) for p in o.data.polygons if p.normal.z > .99
             and all(15.679 <= points[i].z <= 15.751 for i in p.vertices)]
    assert faces, name
    floors.append(BVHTree.FromPolygons(points, faces))

def hit(tree, x, y):
    return tree.ray_cast(Vector((x,y,20)), Vector((0,0,-1)), 25)[0] is not None

mismatch = []
inside = outside = 0
for ix in range(92):
    for iy in range(94):
        # Off-grid sample avoids accidental alignment with surveyed edges.
        x, y = -9.15+ix*.20+.013, -18.0+iy*.20+.017
        expected = any(hit(f,x,y) for f in floors) or (-9 < x < 9 and -17.55 < y < -15.4)
        actual = hit(mesh,x,y)
        inside += int(expected)
        outside += int(not expected)
        if expected != actual:
            mismatch.append((round(x,3), round(y,3), expected, actual))
assert not mismatch, mismatch[:20]
print(f'PASS footprint matches combined 639/640 slabs plus full hallway: {inside} inside, {outside} outside samples')
assert all(hit(mesh,x,-16.5) for x in (-8.8,-5,0,5,8.8))
print('PASS hallway retained across its full width')
assert abs(min(v.z for v in verts)-.05) < 1e-5 and abs(max(v.z for v in verts)-15.58) < 1e-5
assert podium['wf_Mass'] == 0
print('PASS lower-five-floor height and scenery-only mass retained')
bm = bmesh.new()
bm.from_mesh(podium.data)
assert all(e.is_manifold for e in bm.edges)
assert all(f.calc_area() > 0 for f in bm.faces)
bm.free()
print('PASS podium is a closed manifold without internal open seams')
print('RESULT: PASS')
