"""Render close-up preview PNGs of all moon surface assets for plan doc.
Usage: blender --background --python render_assets.py -- <out_dir>
"""
import bpy, math, sys, os
import mathutils

OUT_DIR = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '/tmp'

def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*rgb, 1)
    return m

def render_asset(name, build_fn, out_png):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    build_fn()
    obj = bpy.context.object

    verts = [obj.matrix_world @ mathutils.Vector(v.co) for v in obj.data.vertices]
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    cx=(max(xs)+min(xs))/2; cy=(max(ys)+min(ys))/2; cz=(max(zs)+min(zs))/2
    sz = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    dist = sz * 2.4
    az, el = math.radians(220), math.radians(30)
    cam_loc = (cx+dist*math.cos(el)*math.cos(az),
               cy+dist*math.cos(el)*math.sin(az),
               cz+dist*math.sin(el))

    cam_data = bpy.data.cameras.new('Cam'); cam_data.lens = 50
    cam_obj  = bpy.data.objects.new('Cam', cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = cam_loc
    cam_obj.rotation_euler = (mathutils.Vector((cx,cy,cz))-mathutils.Vector(cam_loc)).to_track_quat('-Z','Y').to_euler()
    scene.camera = cam_obj

    for (eloc, energy) in [((cam_loc[0]*0.8, cam_loc[1]*0.5, cam_loc[2]*1.5), 4.0),
                            ((-cam_loc[0], -cam_loc[1]*0.5, cam_loc[2]), 1.2)]:
        ld = bpy.data.lights.new('L','SUN'); ld.energy = energy
        lo = bpy.data.objects.new('L', ld); scene.collection.objects.link(lo)
        lo.location = eloc

    world = bpy.data.worlds.new('W'); world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.08,0.08,0.10,1)
    scene.world = world

    scene.render.resolution_x = 800; scene.render.resolution_y = 600
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
    print(f'[render_assets] {name} → {out_png}')

SEG = 8

# ── VSAT Tower ────────────────────────────────────────────────────────────────
def build_vsat():
    parts = []
    mat_dark   = mat('vsat_dark',   (0.18,0.18,0.20))
    mat_silver = mat('vsat_silver', (0.78,0.78,0.80))
    mat_white  = mat('vsat_white',  (0.92,0.92,0.92))
    def cyl(r,h,loc,m):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG,radius=r,depth=h,location=loc)
        parts.append((bpy.context.object, m))
    def cube(sx,sy,sz,loc,m):
        bpy.ops.mesh.primitive_cube_add(size=1.0,location=loc)
        o=bpy.context.object; o.scale=(sx,sy,sz)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        parts.append((o,m))
    cube(1.5,1.5,0.4,(0,0,0.2),mat_dark)
    cyl(0.12,9.5,(0,0,5.15),mat_silver)
    cube(2.5,0.06,2.0,(0,0,10.5),mat_white)
    cube(0.06,2.5,2.0,(0,0,10.5),mat_white)
    for o,m in parts:
        o.data.materials.clear(); o.data.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT')
    for o,_ in parts: o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0][0]
    bpy.ops.object.join()

# ── Lunar Cruiser ─────────────────────────────────────────────────────────────
def build_cruiser():
    parts = []
    mat_white = mat('cruiser_white', (0.90,0.90,0.88))
    mat_dark  = mat('cruiser_dark',  (0.18,0.19,0.20))
    def cyl(r,h,loc,m,rot=(0,0,0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG,radius=r,depth=h,location=loc)
        o=bpy.context.object; o.rotation_euler=rot
        bpy.ops.object.transform_apply(location=False,rotation=True,scale=False)
        parts.append((o,m))
    def cube(sx,sy,sz,loc,m):
        bpy.ops.mesh.primitive_cube_add(size=1.0,location=loc)
        o=bpy.context.object; o.scale=(sx,sy,sz)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        parts.append((o,m))
    cube(5.5,4.5,2.2,(0,0,1.8),mat_white)
    cube(5.6,4.6,0.4,(0,0,2.9),mat_dark)
    cube(0.5,3.0,2.0,(3.0,0,1.8),mat_dark)
    for fx in (1.9,0.0,-1.9):
        for fy in (2.6,-2.6):
            cyl(0.7,0.35,(fx,fy,0.7),mat_dark,rot=(math.pi/2,0,0))
    cube(2.0,0.10,0.08,(0,0,3.19),mat_dark)
    cube(2.0,1.50,0.06,(0,0,3.27),mat_white)
    cyl(0.05,1.0,(0,0,3.82),mat_dark)
    for o,m in parts:
        o.data.materials.clear(); o.data.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT')
    for o,_ in parts: o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0][0]
    bpy.ops.object.join()

# ── Blue Moon MK1 ─────────────────────────────────────────────────────────────
def build_mk1():
    parts = []
    mat_gold   = mat('mk1_gold',   (0.72,0.55,0.10))
    mat_silver = mat('mk1_silver', (0.70,0.72,0.73))
    mat_dark   = mat('mk1_dark',   (0.20,0.20,0.22))
    SEG12 = 12
    def cyl(r,h,loc,m,rot=(0,0,0)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG12,radius=r,depth=h,location=loc)
        o=bpy.context.object; o.rotation_euler=rot
        bpy.ops.object.transform_apply(location=False,rotation=True,scale=False)
        parts.append((o,m))
    def cone(r1,r2,h,loc,m):
        bpy.ops.mesh.primitive_cone_add(vertices=SEG12,radius1=r1,radius2=r2,depth=h,location=loc)
        parts.append((bpy.context.object,m))
    def cube(sx,sy,sz,loc,m):
        bpy.ops.mesh.primitive_cube_add(size=1.0,location=loc)
        o=bpy.context.object; o.scale=(sx,sy,sz)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        parts.append((o,m))
    cyl(1.4,5.0,(0,0,4.5),mat_gold)
    cyl(1.6,0.6,(0,0,1.8),mat_dark)
    cone(1.0,0.4,1.5,(0,0,0.75),mat_dark)
    cube(3.2,3.2,0.4,(0,0,7.2),mat_silver)
    for ang_deg in (45.0,135.0,225.0,315.0):
        ang=math.radians(ang_deg)
        cyl(0.08,2.2,(2.2*math.cos(ang),2.2*math.sin(ang),0.9),mat_dark,
            rot=(0,math.radians(34),ang))
        cyl(0.25,0.1,(2.8*math.cos(ang),2.8*math.sin(ang),0.05),mat_dark)
    for o,m in parts:
        o.data.materials.clear(); o.data.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT')
    for o,_ in parts: o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0][0]
    bpy.ops.object.join()

# ── Foundation Surface Habitat ────────────────────────────────────────────────
def build_fsh():
    parts = []
    mat_white = mat('fsh_white', (0.90,0.90,0.88))
    mat_dark  = mat('fsh_dark',  (0.25,0.27,0.30))
    SEG16 = 16
    def cyl(r,h,loc,m):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG16,radius=r,depth=h,location=loc)
        parts.append((bpy.context.object,m))
    def cube(sx,sy,sz,loc,m):
        bpy.ops.mesh.primitive_cube_add(size=1.0,location=loc)
        o=bpy.context.object; o.scale=(sx,sy,sz)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        parts.append((o,m))
    cyl(2.0,3.0,(0,0,1.5),mat_dark)
    cube(2.0,1.8,2.0,(2.9,0,1.5),mat_dark)
    cyl(2.6,0.8,(0,0,3.4),mat_dark)
    cyl(3.2,6.5,(0,0,6.75),mat_white)
    cube(0.1,1.0,2.0,(3.2,0,6.75),mat_white)
    cube(0.1,1.0,2.0,(-3.2,0,6.75),mat_white)
    for o,m in parts:
        o.data.materials.clear(); o.data.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT')
    for o,_ in parts: o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0][0]
    bpy.ops.object.join()

# ── FSP Reactor ───────────────────────────────────────────────────────────────
def build_fsp():
    parts = []
    mat_dark   = mat('fsp_dark',   (0.30,0.30,0.32))
    mat_silver = mat('fsp_silver', (0.65,0.65,0.68))
    mat_lunar  = mat('fsp_lunar',  (0.82,0.80,0.73))
    SEG12 = 12
    def cyl(r,h,loc,m):
        bpy.ops.mesh.primitive_cylinder_add(vertices=SEG12,radius=r,depth=h,location=loc)
        parts.append((bpy.context.object,m))
    def cone(r1,r2,h,loc,m):
        bpy.ops.mesh.primitive_cone_add(vertices=SEG12,radius1=r1,radius2=r2,depth=h,location=loc)
        parts.append((bpy.context.object,m))
    cyl(2.5,0.5,(0,0,0.25),mat_lunar)
    cyl(0.9,2.0,(0,0,1.0),mat_dark)
    cone(0.9,0.5,1.0,(0,0,2.5),mat_dark)
    for ang_deg in (0.0,45.0,90.0,135.0):
        bpy.ops.mesh.primitive_cube_add(size=1.0,location=(0,0,1.0))
        fin=bpy.context.object; fin.scale=(2.8,0.06,1.6)
        fin.rotation_euler=(0,0,math.radians(ang_deg))
        bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
        parts.append((fin,mat_silver))
    for o,m in parts:
        o.data.materials.clear(); o.data.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT')
    for o,_ in parts: o.select_set(True)
    bpy.context.view_layer.objects.active=parts[0][0]
    bpy.ops.object.join()

# ── Run all renders ───────────────────────────────────────────────────────────
assets = [
    ('vsat_tower',    build_vsat,    'moon_vsat_tower.png'),
    ('lunar_cruiser', build_cruiser, 'moon_lunar_cruiser.png'),
    ('blue_moon_mk1', build_mk1,     'moon_blue_moon_mk1.png'),
    ('fsh',           build_fsh,     'moon_fsh.png'),
    ('fsp_reactor',   build_fsp,     'moon_fsp_reactor.png'),
]

for name, fn, fname in assets:
    render_asset(name, fn, os.path.join(OUT_DIR, fname))
