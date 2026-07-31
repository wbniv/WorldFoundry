"""Render ONE thumbnail per unique SMB model (exact geometry + materials/textures)
into docs/plans/screenshots/model_<slug>.png, for per-row embedding in the plan."""
import bpy, bmesh, math, os

T = 1.5
REPO = "/home/will/WorldFoundry.2026-new-level"
TEXDIR = os.path.join(REPO, "wflevels/smb_w1_1")
OUT = os.path.join(REPO, "docs/plans/screenshots")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def mat(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = 0.6
    b.inputs["Emission Color"].default_value = (*rgb, 1.0)
    b.inputs["Emission Strength"].default_value = 0.22
    return m

def tex_mat(name, tga):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(TEXDIR, tga)); img.interpolation = 'Closest'
    nt.links.new(b.inputs["Base Color"], img.outputs["Color"])
    nt.links.new(b.inputs["Emission Color"], img.outputs["Color"])
    b.inputs["Emission Strength"].default_value = 0.20
    return m

def setmat(o, m):
    o.data.materials.clear(); o.data.materials.append(m)
    for p in o.data.polygons: p.material_index = 0; p.use_smooth = True
    return o

def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join()
    o = bpy.context.object; o.name = o.data.name = name; return o

# ---- builders (centred at origin, base ~z=0) ----
def goomba():
    br=mat('gb',(0.55,0.27,0.06)); tn=mat('gt',(0.83,0.65,0.34)); ps=[]
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.48*T,segments=16,ring_count=10,location=(0,0,0.44*T))
    bpy.context.object.scale.z=0.72; bpy.ops.object.transform_apply(scale=True); ps.append(setmat(bpy.context.object,br))
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=0.34*T,depth=0.10*T,location=(0,0,0.54*T)); ps.append(setmat(bpy.context.object,tn))
    for yo in (-0.19*T,0.19*T):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14*T,segments=8,ring_count=6,location=(0,yo,0.10*T)); ps.append(setmat(bpy.context.object,br))
    return join(ps,'g')
def koopa(red=False):
    sh=mat('ks',(0.78,0.12,0.10) if red else (0.14,0.56,0.20)); sk=mat('kk',(0.90,0.76,0.34)); ps=[]
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.48*T,segments=16,ring_count=10,location=(0,0,0.52*T))
    bpy.context.object.scale.z=0.80; bpy.ops.object.transform_apply(scale=True); ps.append(setmat(bpy.context.object,sh))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22*T,segments=12,ring_count=8,location=(0.30*T,0,0.95*T)); ps.append(setmat(bpy.context.object,sk))
    return join(ps,'k')
def mario():
    r=mat('mr',(0.87,0.14,0.07)); b=mat('mb',(0.18,0.34,0.76)); s=mat('ms',(0.96,0.73,0.41)); ps=[]
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.30*T,segments=14,ring_count=8,location=(0,0,0.95*T)); ps.append(setmat(bpy.context.object,s))
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=0.30*T,depth=0.5*T,location=(0,0,0.55*T)); ps.append(setmat(bpy.context.object,r))
    bpy.ops.mesh.primitive_cylinder_add(vertices=14,radius=0.28*T,depth=0.5*T,location=(0,0,0.18*T)); ps.append(setmat(bpy.context.object,b))
    return join(ps,'m')
def piranha():
    st=mat('ps',(0.20,0.70,0.24)); hd=mat('ph',(0.85,0.16,0.12)); ps=[]
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=0.12*T,depth=0.9*T,location=(0,0,0.45*T)); ps.append(setmat(bpy.context.object,st))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.30*T,segments=12,ring_count=8,location=(0,0,1.0*T)); ps.append(setmat(bpy.context.object,hd))
    return join(ps,'p')
def cube_m(rgb,size=1.0*T,sz=(1,1,1)):
    bpy.ops.mesh.primitive_cube_add(size=size,location=(0,0,size*0.5*sz[2]))
    o=bpy.context.object; o.scale=sz; bpy.ops.object.transform_apply(scale=True); return setmat(o,mat('c',rgb))
def cube_t(tga, w=1.0*T, d=1.0*T, h=1.0*T):
    # Textured box like the game's _add_textured_box: each face full [0,1]², V-flipped (WF VRAM
    # convention), front = -Y (camera side). So the ? glyph is upright on the face the WF
    # side-view camera sees. (WF coords: X right, Y depth, Z up.)
    x0,x1=-w/2,w/2; y0,y1=-d/2,d/2; z0,z1=0.0,h
    bm=bmesh.new(); uvl=bm.loops.layers.uv.new('UVMap')
    V=[bm.verts.new(p) for p in [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]]
    U=[(0,1),(1,1),(1,0),(0,0)]
    for fv in [[0,1,5,4],[2,3,7,6],[4,5,6,7],[3,2,1,0],[3,0,4,7],[1,2,6,5]]:
        f=bm.faces.new([V[i] for i in fv])
        for loop,uvc in zip(f.loops,U): loop[uvl].uv=uvc
    me=bpy.data.meshes.new('tb'); bm.to_mesh(me); bm.free()
    o=bpy.data.objects.new('tb',me); scene.collection.objects.link(o); bpy.context.view_layer.objects.active=o
    return setmat(o, tex_mat('t',tga))
def disc(rgb):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=0.42*T,depth=0.10*T,location=(0,0,0.55*T))
    o=bpy.context.object; o.rotation_euler[0]=math.radians(90); bpy.ops.object.transform_apply(rotation=True); return setmat(o,mat('d',rgb))
def shroom(cap):
    c=mat('sc',cap); st=mat('ss',(0.98,0.96,0.90)); ps=[]
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.42*T,segments=14,ring_count=8,location=(0,0,0.7*T))
    bpy.context.object.scale.z=0.7; bpy.ops.object.transform_apply(scale=True); ps.append(setmat(bpy.context.object,c))
    bpy.ops.mesh.primitive_cylinder_add(vertices=14,radius=0.22*T,depth=0.4*T,location=(0,0,0.3*T)); ps.append(setmat(bpy.context.object,st))
    return join(ps,'sh')
def sphere(rgb,r=0.3*T):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r,segments=14,ring_count=8,location=(0,0,0.55*T)); return setmat(bpy.context.object,mat('sp',rgb))
def pipe():
    bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=0.55*T,depth=1.4*T,location=(0,0,0.7*T)); return setmat(bpy.context.object,mat('pi',(0.0,0.62,0.0)))
def pole():
    bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=0.10*T,depth=1.6*T,location=(0,0,0.8*T)); return setmat(bpy.context.object,mat('po',(0.72,0.72,0.72)))

MODELS = [
    ('mario',mario),('goomba',goomba),('koopa_green',lambda:koopa(False)),('koopa_red',lambda:koopa(True)),('piranha',piranha),
    ('coin',lambda:disc((1.0,0.84,0.0))),('mushroom',lambda:shroom((0.85,0.16,0.12))),('fireflower',lambda:shroom((0.98,0.95,0.95))),
    ('starman',lambda:cube_m((0.98,0.85,0.10),0.7*T)),('oneup',lambda:shroom((0.05,0.75,0.05))),
    ('fireball',lambda:sphere((0.98,0.45,0.05),0.25*T)),('spark',lambda:cube_m((1.0,0.95,0.55),0.32*T)),
    ('popup',lambda:cube_m((1.0,0.95,0.2),0.5*T,sz=(1.4,0.1,0.7))),('debris',lambda:cube_m((0.77,0.42,0.0),0.36*T)),
    ('qblock',lambda:cube_t('qblock_tex.tga')),('brick',lambda:cube_t('brick_tex.tga')),('hardblock',lambda:cube_m((0.48,0.25,0.05))),
    ('ground',lambda:cube_t('grid_tile.tga',2.2*T,T,0.6*T)),('pipe',pipe),('ceiling',lambda:cube_t('brick_tex.tga',2.2*T,T,0.5*T)),
    ('crfloor',lambda:cube_m((0.45,0.22,0.05),sz=(2.2,1,0.5))),
    ('pole',pole),('poleflag',lambda:cube_m((0.10,0.65,0.16),sz=(0.08,0.9,0.7))),
    ('castle',lambda:cube_m((0.60,0.55,0.50),1.4*T)),('castledoor',lambda:cube_m((0.05,0.04,0.06),1.0*T,sz=(0.6,0.2,1.4))),
    ('warpsign',lambda:cube_m((0.95,0.92,0.20),0.9*T,sz=(1.0,0.1,0.7))),
]

# scene: camera (3/4 view, ORTHO) + lights — aimed + sized per model so nothing clips
from mathutils import Vector
CAM_DIR = Vector((0.0, -1.0, 0.0))   # WF side-view: camera at -Y looking +Y, X right, Z up (in-game view)
bpy.ops.object.camera_add(); cam=bpy.context.object; cam.data.type='ORTHO'; scene.camera=cam
bpy.ops.object.light_add(type='SUN',location=(4,-6,8)); bpy.context.object.data.energy=3.2; bpy.context.object.rotation_euler=(math.radians(50),0,math.radians(30))
bpy.ops.object.light_add(type='SUN',location=(-4,-6,2)); bpy.context.object.data.energy=1.4; bpy.context.object.rotation_euler=(math.radians(70),0,math.radians(-40))
scene.world=bpy.data.worlds.new('w'); scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[1].default_value=0.55
scene.render.engine='BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
scene.render.resolution_x=240; scene.render.resolution_y=240
scene.render.film_transparent=True

def clear():
    for o in list(bpy.data.objects):
        if o.type in ('MESH','FONT'): bpy.data.objects.remove(o, do_unlink=True)

for slug, fn in MODELS:
    clear(); o = fn()
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs=[v.x for v in bb]; ys=[v.y for v in bb]; zs=[v.z for v in bb]
    ctr = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    ext = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    cam.location = ctr + CAM_DIR * 12.0
    cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale = ext * 1.45 + 0.25      # fit the model with a small margin
    scene.render.filepath = os.path.join(OUT, f'model_{slug}.png')
    bpy.ops.render.render(write_still=True)
print("PERMODEL_RENDERED", len(MODELS))
