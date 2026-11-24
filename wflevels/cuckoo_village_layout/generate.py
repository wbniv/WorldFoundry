"""Assemble the Cuckoo Village hillside layout from the reusable asset scene.

Run via build.sh. Blender coordinates are metres, +Z up and front is -Y.
This is a layout prototype, not the clock director or camera journey.
"""
import math
import os
import shutil
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSETS = ROOT / 'wflevels/cuckoo_village_assets'
sys.path.insert(0, str(ROOT / 'wftools'))
sys.path.insert(0, str(HERE))
import wf_blender

wf_blender.register()
bpy.ops.wm.open_mainfile(filepath=str(ASSETS / 'village_assets.blend'))
# Rebase authored schema references to this checkout.
for obj in bpy.context.scene.objects:
    if obj.get('wf_schema_path'):
        obj['wf_schema_path'] = str(ROOT / 'wfsource/source/oas' / Path(obj['wf_schema_path']).name)
shutil.copyfile(ASSETS / 'village_atlas.tga', HERE / 'village_atlas.tga')
bpy.data.images['village_atlas.tga'].filepath = '//village_atlas.tga'
for name in ('house_instance_1', 'house_instance_2', 'house_glow_1', 'house_glow_2', 'Review_camera', 'Review_light'):
    obj = bpy.data.objects.get(name)
    if obj:
        bpy.data.objects.remove(obj, do_unlink=True)

# Soft, overlapping rises form a continuous model surface, including around the square.
def height(x, y):
    baseline = (0.22 + 1.18 * math.exp(-((x + 9) / 5.6)**2 - ((y - 5.7) / 3.8)**2)
            + 1.0 * math.exp(-((x - 8) / 6.4)**2 - ((y - 6) / 4.6)**2)
            + .34 * math.exp(-((x + 11) / 4.0)**2 - ((y + 3) / 3.4)**2)
            + .28 * math.exp(-((x - 10) / 4.5)**2 - ((y + 3) / 3.8)**2))
    # Raise broad, irregular hills while keeping the tower's exact datum.
    tower_clearance = 1 - math.exp(-(x*x+y*y)/30)
    return baseline + tower_clearance * (1.7*math.exp(-((x+9)/6.8)**2-((y-5)/5.0)**2)
                 + 1.4*math.exp(-((x-9)/7.2)**2-((y-5.5)/5.3)**2)
                 + .65*math.exp(-((x+10)/5.3)**2-((y+3)/4.5)**2))

material = bpy.data.materials['village_atlas']
def mesh_actor(name, vertices, faces, tile):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name='UVMap')
    # Atlas coordinate convention matches the existing asset exporter.
    for poly in mesh.polygons:
        face_tile = tile[poly.index] if isinstance(tile, list) else tile
        for li in poly.loop_indices:
            p = mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv = ((face_tile % 4 + .08 + .84 * ((p.x * .13) % 1)) / 4,
                              (face_tile // 4 + .08 + .84 * ((p.y * .13) % 1)) / 4)
    obj['wf_schema_path'] = str(ROOT / 'wfsource/source/oas/platform.oad')
    obj['wf_Mobility'] = 'Anchored'
    obj['wf_Model Type'] = 'Mesh'
    obj['wf_Mass'] = 0.0
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Mesh Name'] = name + '.iff'
    obj['wf_original_mesh_name'] = name + '.iff'
    return obj

# A rounded, irregular tabletop silhouette, with an actual sloping height field.
N, RINGS = 64, 12
vertices = [(0, 0, height(0, 0))]
for r in range(1, RINGS + 1):
    for i in range(N):
        a = 2 * math.pi * i / N
        wobble = 1 + .045 * math.sin(3*a + .4) + .025 * math.sin(5*a - 1)
        x = 19 * r / RINGS * wobble * math.cos(a)
        y = 12 * r / RINGS * wobble * math.sin(a)
        vertices.append((x, y, height(x, y)))
faces = [(0, 1+i, 1+(i+1)%N) for i in range(N)]
for r in range(RINGS-1):
    lo, hi = 1+r*N, 1+(r+1)*N
    for i in range(N):
        j = (i+1)%N
        faces.append((lo+i, hi+i, hi+j, lo+j))
mesh_actor('rolling_terrain', vertices, faces, 4)
# Wooden plinth below the height field.
outer = vertices[1+(RINGS-1)*N:1+RINGS*N]
baseverts = [(x,y,-.7) for x,y,z in outer] + [(x,y,z-.04) for x,y,z in outer]
# The village now blends directly into the surrounding grass rather than
# exposing the old tabletop rim in the middle of the hillside.

# Continue the grass beyond the original model rim, so elevated camera views
# meet foothills instead of the stretched underside of the panorama.
foothill_verts=[]
for ring in range(17):
    t=ring/16
    for x,y,z in outer:
        scale=1+1.3*t
        zz=(z-.06)*(1-t)+(-1.5+.35*math.sin(x*.35)*math.cos(y*.3))*t
        foothill_verts.append((x*scale,y*scale,zz))
foothill_faces=[]
for ring in range(16):
    for i in range(N):
        j=(i+1)%N;lo=ring*N;hi=(ring+1)*N
        foothill_faces.append((lo+i,hi+i,hi+j,lo+j))
mesh_actor('alpine_foothills',foothill_verts,foothill_faces,4)

def ribbon(name, points, width, tile, lift=.045):
    verts = []
    for i, (x, y) in enumerate(points):
        a = Vector(points[max(0, i-1)]); b = Vector(points[min(len(points)-1, i+1)])
        d = (b-a).normalized(); n = Vector((-d.y, d.x)) * width/2
        for side in (-1,1):
            xx, yy = x+side*n.x, y+side*n.y
            verts.append((xx, yy, height(xx, yy)+lift))
    return mesh_actor(name, verts, [(2*i+2,2*i+3,2*i+1,2*i) for i in range(len(points)-1)], tile)

def smooth(points, steps=8):
    out=[]
    for i in range(len(points)-1):
        p0=Vector(points[max(i-1,0)]); p1=Vector(points[i]); p2=Vector(points[i+1]); p3=Vector(points[min(i+2,len(points)-1)])
        for j in range(steps):
            t=j/steps
            v=.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)
            out.append((v.x,v.y))
    return out+[points[-1]]

ribbon('main_lane', smooth([(-14,0),(-11,3),(-8,3),(-5,1),(-2,1.2),(1,2),(4,1),(7,2),(10,0),(13,0),(14,1)]), 1.25, 3)
ribbon('lower_lane', smooth([(-9,3),(-10,4),(-8,5),(-5,4),(-5,1),(-6,-2),(-3,-3),(0,-3),(3,-5),(6,-6),(9,-5),(12,-6),(14,-3)]), 1.05, 3, .055)
ribbon('bridge_lane', smooth([(-6,-2),(-8,-3),(-10,-4),(-11,-6)]), 1.0, 3, .06)
ribbon('stream', smooth([(-12.5,-4.8),(-11.5,-4.8),(-10,-5.8),(-8,-6.3),(-6,-6.3),(-4.8,-6.8)]), 1.0, 14, .08)
# Raised bridge deck across the stream, independent of the path and water.
bx, by = -10.25, -5.35
z = height(bx, by) + .23
mesh_actor('bridge', [(bx-1,by-.45,z),(bx+1,by-.45,z),(bx+1,by+.45,z),(bx-1,by+.45,z)], [(0,1,2,3)], 0)
# Garden plots occupy a small terrace alongside the lower lane.
garden = [(4.1,-6.7),(6.6,-6.6),(6.9,-8.0),(4.4,-8.0)]
mesh_actor('garden', [(x,y,height(x,y)+.08) for x,y in garden], [(0,3,2,1)], 9)
for i in range(4):
    x = 4.4 + i*.55
    ribbon('garden_row_%d' % i, [(x,-6.85),(x+.2,-7.8)], .12, 4, .11)
# Paved square as a small irregular patch in front of the tower.
sq = [(-1.7,-.4),(-.7,.1),(1.1,.1),(2.3,-.7),(2,-2),(.8,-2.5),(-.8,-2.1),(-1.8,-1.4)]
mesh_actor('village_square', [(x,y,height(x,y)+.09) for x,y in sq], [tuple(range(len(sq)-1,-1,-1))], 3)

def place(source, name, x, y, angle=0, scale=1):
    original=bpy.data.objects[source]
    obj=original.copy(); obj.data=original.data; obj.name=name
    bpy.context.scene.collection.objects.link(obj)
    obj.location=(x,y,height(x,y)-.08); obj.rotation_euler=(0,0,math.radians(angle)); obj.scale=(scale,scale,scale)
    return obj

# Irregular neighborhoods follow the lanes and contours; no ring of inward-facing houses.
houses=[(-11,4.2,-25,.90),(-7,6.2,15,1.0),(-3.4,4.2,-15,.86),
        (1.2,6.4,20,.90),(7,6,-18,1.0),(11.5,3.8,32,.90),
        (-11,1,-12,.95),(-7.8,-.7,35,.88),(-4,-.5,-28,.82),
        (8.6,3,10,.80),(11,-2.7,-22,.96),(7,-3.2,24,1.02),(-8,-3.9,-14,.86),
        (-14,-5,-10,.82),(-9,-8.3,15,.80),(-5,-9,-18,.78),(0,-8,12,.80),(6.5,-8.8,-14,.78),
        (10,-7,18,.80),(14,-4,-12,.78),(15,0,20,.75),(13,6,-20,.78),(8,9,12,.76),(1,9,-12,.76)]
for i,(x,y,a,s) in enumerate(houses):
    place('standard_house',f'cottage_{i+1:02}',x,y,a,s)
    place('house_glow',f'cottage_light_{i+1:02}',x,y,a,s)
for i,(x,y,s) in enumerate([(-13,3,.9),(-10,6.6,1),(-5,7.5,.8),(-1,4.1,.7),(4,6.7,1),(9,7,.9),(14,2,1),(-13,-2,.9),(-10.5,-5.5,.8),(-5,-6.3,.8),(12,-5.7,.9),(4,-7,.8),
                            (-16,0,.8),(-15,-7,.8),(-8,-9,.8),(-3,-9,.8),(3,-9,.8),(8,-9,.8),
                            (15,-7,.8),(17,2,.8),(15,7,.8),(10,9,.8),(4,9,.8),(-5,9,.8)]):
    place('pine_tree',f'pine_{i+1:02}',x,y,i*31,s)
# Move the tower and all its independently pivoted pieces together.
tower_z=height(0,0)-.08
for name in ('clock_tower','tower_glow','hour_hand','minute_hand','bird_door'):
    bpy.data.objects[name].location.z += tower_z
# Remove the old gabled roof from the joined stock shell so it cannot poke
# through the new hipped roof. All its vertices are above the upper wall.
shell = bpy.data.objects['clock_tower']
shell.data = shell.data.copy()
bm = bmesh.new(); bm.from_mesh(shell.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(v.co.z >= 4.8 for v in f.verts)], context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(shell.data); bm.free(); shell.data.update()
# The original dark hands need gold UVs to remain legible on the dark face.
for name in ('hour_hand', 'minute_hand'):
    hand=bpy.data.objects[name]; hand.data=hand.data.copy()
    for loop in hand.data.uv_layers.active.data:
        loop.uv.y += .25
# Add concept-inspired carved clock case, roof, cuckoo and performers.
import tower_art
tower_art.build(mesh_actor, tower_z)
# Dedicated high-resolution carved panel, inset behind the clock rim and bird.
# The model and clock remain real 3D; this texture supplies fine surface relief.
carved = bpy.data.materials.new('tower_carved_wood'); carved.use_nodes = True
carved_image = bpy.data.images.load(str(HERE/'tower-carved-wood.tga'), check_existing=True)
carved_image.filepath = bpy.path.relpath(str(HERE/'tower-carved-wood.tga'))
carved_nodes=carved.node_tree.nodes
carved_tex=carved_nodes.new('ShaderNodeTexImage'); carved_tex.image=carved_image
carved_uv=carved_nodes.new('ShaderNodeUVMap'); carved_uv.uv_map='UVMap'
carved_map=carved_nodes.new('ShaderNodeMapping')
carved_map.inputs['Scale'].default_value=(1,-1,1); carved_map.inputs['Location'].default_value=(0,1,0)
carved.node_tree.links.new(carved_uv.outputs['UV'],carved_map.inputs['Vector'])
carved.node_tree.links.new(carved_map.outputs['Vector'],carved_tex.inputs['Vector'])
carved.node_tree.links.new(carved_tex.outputs['Color'],carved_nodes.get('Principled BSDF').inputs['Base Color']
)
panel=mesh_actor('tower_carved_panel', [(-1.07,-1.066,3.58+tower_z),(1.07,-1.066,3.58+tower_z),(1.07,-1.066,4.73+tower_z),(-1.07,-1.066,4.73+tower_z)], [(0,1,2,3)], 0)
panel.data.materials.clear(); panel.data.materials.append(carved)
for poly in panel.data.polygons:
    for li in poly.loop_indices:
        v=panel.data.vertices[panel.data.loops[li].vertex_index].co
        panel.data.uv_layers.active.data[li].uv=((v.x+1.07)/2.14,(v.z-tower_z-3.58)/1.15)
# Remove the stock base's window glow: the lower facade is now an open mechanism.
bpy.data.objects.remove(bpy.data.objects['tower_glow'], do_unlink=True)
for name in ('standard_house','house_glow','pine_tree'):
    bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

look=bpy.data.objects['LookAt']; look.location=(0,0,1.0)
wide=bpy.data.objects['cs_wide']; wide.location=(14,-25,18)
camera=bpy.data.objects['Camera']; camera.location=wide.location
camera['wf_FoggingColor']=0x000000
camera['wf_FoggingStartDistance']=999.0
camera['wf_FoggingCompleteDistance']=1000.0
bpy.data.objects['Room']['wf_original_bbox']=(-60,-60,-10,60,60,40)
scene=bpy.context.scene
scene.render.resolution_x=1400; scene.render.resolution_y=900; scene.render.resolution_percentage=100
scene.cycles.samples=20
bpy.ops.object.light_add(type='AREA', location=(0,-12,25))
light=bpy.context.object; light.name='Review_light'; light.data.energy=11000; light.data.size=18
bpy.ops.object.camera_add(location=(24,-38,30))
cam=bpy.context.object; cam.name='Review_camera'; cam.rotation_euler=(Vector((0,0,.5))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='ORTHO'; cam.data.ortho_scale=37; scene.camera=cam
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'village_layout.blend'))
if not os.environ.get('CUCKOO_SKIP_PREVIEW'):
    scene.render.filepath=str(HERE/'preview.png'); bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(light,do_unlink=True); bpy.data.objects.remove(cam,do_unlink=True)
bpy.ops.wf.export_level(filepath=str(HERE/'cuckoo_village_layout.lev'))
print('LAYOUT_BUILD_OK')
