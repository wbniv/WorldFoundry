"""Generate a live miniature railway clock using only existing level features."""
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT/'wftools'), str(ROOT/'wflevels/clock_common'), str(HERE)]
import wf_blender
import wf_core
from wf_blender.export_level import _seed_defaults
from clock_mesh import Mesh
import model

OAS = ROOT/'wfsource/source/oas'
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()

COLORS = {
    'grass': (.12,.29,.16), 'rim': (.20,.095,.045), 'rim_gold': (.64,.39,.12),
    'ballast': (.22,.24,.23), 'sleeper': (.31,.19,.10), 'rail': (.75,.68,.49),
    'red': (.66,.10,.085), 'red_trim': (.94,.37,.13), 'teal': (.055,.35,.36),
    'cream': (.90,.82,.59), 'roof': (.19,.18,.18), 'black': (.045,.055,.06),
    'window': (1.0,.73,.25), 'station': (.66,.55,.38), 'station_roof': (.42,.15,.11),
    'tree': (.055,.22,.12), 'tree_light': (.09,.32,.16), 'trunk': (.23,.12,.055),
    'white': (.90,.93,.88), 'express': (.72,.80,.78), 'express_trim': (.13,.42,.62),
}
COLORS.update({'grass':(.32,.55,.25), 'trunk':(.51,.32,.16),
               'tree_light':(.42,.67,.18), 'window':(.85,.67,.25),
               'sky':(.58,.75,.90), 'hill':(.30,.50,.46), 'flower':(.98,.78,.74)})
materials = {}
for key, rgb in COLORS.items():
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    mat.diffuse_color = (*rgb, 1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*rgb, 1)
    mat['wf_prelit'] = True
    mat['wf_double_sided'] = True
    materials[key] = mat

leafmat=materials['tree_light']
leafmat.diffuse_color=(1,1,1,1)
leaftex=leafmat.node_tree.nodes.new('ShaderNodeTexImage')
leaftex.image=bpy.data.images.load(str(HERE/'leaf-veins-source.png'))
_ = len(leaftex.image.pixels); leaftex.image.scale(128,128)
leaftex.image.filepath_raw=str(HERE/'leaf-study.tga'); leaftex.image.file_format='TARGA'; leaftex.image.save()
leafmat.node_tree.links.new(leaftex.outputs['Color'],leafmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])


def actor(name, cls, mesh=None, pos=(0,0,0), fields=None, bounds=None):
    data = None
    if mesh is not None:
        data = bpy.data.meshes.new(name)
        data.from_pydata(mesh.vertices, [], mesh.faces)
        keys = list(dict.fromkeys(mesh.colors))
        for key in keys:
            data.materials.append(materials[key])
        for poly, key in zip(data.polygons, mesh.colors):
            poly.material_index = keys.index(key)
        data.update()
        if 'tree_light' in keys:
            uv=data.uv_layers.new(name='UVMap')
            all_coords=[v.co for v in data.vertices]
            lowx=min(p.x for p in all_coords); lowz=min(p.z for p in all_coords)
            dx=max(.001,max(p.x for p in all_coords)-lowx); dz=max(.001,max(p.z for p in all_coords)-lowz)
            for poly in data.polygons:
                for loop in poly.loop_indices:
                    vertex=data.loops[loop].vertex_index
                    p=data.vertices[vertex].co
                    uv.data[loop].uv=getattr(mesh,'leaf_uv',{}).get(vertex,((p.x-lowx)/dx,1-(p.z-lowz)/dz))
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS/(cls+'.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    values = {'Mobility':'Anchored', 'Mass':0.0, 'Model Type':'Mesh' if data else 'None',
              'Visibility Mailbox':1 if data else 0, 'Script':'', 'Script Controls Input':'False',
              'Moves Between Rooms':'False', 'Number Of Local Mailboxes':0}
    values.update(fields or {})
    for key, value in values.items():
        obj['wf_'+key] = value
    if data:
        obj['wf_Mesh Name'] = name+'.iff'
        obj['wf_original_mesh_name'] = name+'.iff'
    if bounds or not data:
        obj['wf_original_bbox'] = tuple(bounds or (-.05,-.05,-.05,.05,.05,.05))
        obj['wf_had_authored_bbox'] = True
    return obj


# Each level object is generated using the existing actor and mesh exporter.
actor('Level','levelobj')
actor('Room','room',bounds=(-40,-40,-20,40,40,30))
director=actor('Director','director')
actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(0,-10,5.5),fields={'Mobility':'Camera','Moves Between Rooms':'True'})
actor('LookAt','target',pos=(0,0,4))
actor('cs_wide','camshot',pos=(0,-10,5.5),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':50.,'Pan Time In Seconds':0.})
actor('SunLight','light',fields={'lightType':'Directional','lightRed':.9,'lightGreen':.85,'lightBlue':.75})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':.5,'lightGreen':.5,'lightBlue':.5})
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x526e80})
actor('HourTreeSettings','hourtreesettings',fields={'Editor Label':'Hour Tree'})
backdrop=Mesh('landscape')
backdrop.quad_y(-24,-2,24,20,7,'sky')
back_obj=actor('Landscape','platform',backdrop)
backmat=bpy.data.materials.new('landscape texture'); backmat.use_nodes=True
backmat.diffuse_color=(1,1,1,1); backmat['wf_double_sided']=True; backmat['wf_prelit']=True
backtex=backmat.node_tree.nodes.new('ShaderNodeTexImage')
backtex.image=bpy.data.images.load(str(HERE/'landscape-source.png'))
_ = len(backtex.image.pixels); backtex.image.scale(128,64)
backtex.image.filepath_raw=str(HERE/'landscape-study.tga'); backtex.image.file_format='TARGA'; backtex.image.save()
backmat.node_tree.links.new(backtex.outputs['Color'],backmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
back_obj.data.materials.clear(); back_obj.data.materials.append(backmat)
back_uv=back_obj.data.uv_layers.new(name='UVMap')
for poly in back_obj.data.polygons:
    for loop in poly.loop_indices:
        p=back_obj.data.vertices[back_obj.data.loops[loop].vertex_index].co
        back_uv.data[loop].uv=((p.x+24)/48,1-(p.z+2)/22)
ground=Mesh('ground'); ground.column_z(0,0,-.3,0,18,'grass',sides=64)
random.seed(30)
for _ in range(130):
    x=random.uniform(-7,7); y=random.uniform(-5,5)
    if x*x+y*y<2: continue
    h=random.uniform(.08,.22)
    ground.face([(x-.035,y,.01),(x+.035,y,.01),(x+.02,y,h)],'tree_light')
    if random.random()<.23:
        ground.sphere((x+.02,y,h),.045,'flower',segments=6,rings=3)
actor('Ground','platform',ground)
# Model tapered curved wood as a series of rings, rather than flat boxes.
def wood(mesh, points, radii, colour='trunk'):
    from mathutils import Vector
    rings=[]
    for i,(p,r) in enumerate(zip(points,radii)):
        tangent=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(i-1,0)])
        a=tangent.cross(Vector((0,1,0))).normalized()
        if a.length < .01: a=tangent.cross(Vector((1,0,0))).normalized()
        b=tangent.normalized().cross(a).normalized()
        rings.append([tuple(Vector(p)+r*(a*math.cos(t*math.tau/10)+b*math.sin(t*math.tau/10))) for t in range(10)])
    for low,high in zip(rings,rings[1:]):
        for k in range(10): mesh.face([low[k],low[(k+1)%10],high[(k+1)%10],high[k]],colour)
    mesh.face(list(reversed(rings[0])),colour); mesh.face(rings[-1],colour)

trunk=Mesh('trunk')
# Import the actual authored Blender curves, evaluated to meshes for the level.
with bpy.data.libraries.load(str(HERE/'hour_tree_art.blend'), link=False) as (source,destination):
    destination.objects=[name for name in source.objects if name.startswith(('twisted trunk ', 'root '))]
for item in destination.objects:
    if item is None: continue
    bpy.context.scene.collection.objects.link(item)
    bpy.context.view_layer.update()
    evaluated=item.evaluated_get(bpy.context.evaluated_depsgraph_get())
    baked=evaluated.to_mesh()
    for poly in baked.polygons:
        trunk.face([tuple(item.matrix_world @ baked.vertices[v].co) for v in poly.vertices],'trunk')
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(item,do_unlink=True)
trunk_obj=actor('Trunk','platform',trunk)
# Representative textured trunk section for the engine compatibility check.
barkmat=bpy.data.materials.new('textured bark study'); barkmat.use_nodes=True
barkmat.diffuse_color=(1,1,1,1); barkmat['wf_double_sided']=True
image_node=barkmat.node_tree.nodes.new('ShaderNodeTexImage')
image_node.image=bpy.data.images.load(str(HERE/'bark-source.png'))
_ = len(image_node.image.pixels)
image_node.image.scale(64,64)
image_node.image.filepath_raw=str(HERE/'bark-study.tga'); image_node.image.file_format='TARGA'; image_node.image.save()
barkmat.node_tree.links.new(image_node.outputs['Color'],barkmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
trunk_obj.data.materials.clear(); trunk_obj.data.materials.append(barkmat)
uv=trunk_obj.data.uv_layers.new(name='UVMap')
for poly in trunk_obj.data.polygons:
    for loop in poly.loop_indices:
        p=trunk_obj.data.vertices[trunk_obj.data.loops[loop].vertex_index].co
        uv.data[loop].uv=((math.atan2(p.y,p.x)/math.tau+.5), 1-max(0,min(1,p.z/7.5)))
def leaf(mesh,x,y,z,side=1,scale=1):
    # Veined, pointed leaf, with a raised centre for a soft three-dimensional silhouette.
    tip=(x+side*.30*scale,y,z+.10*scale); base=(x-side*.10*scale,y,z-.03*scale)
    top=(x+side*.08*scale,y,z+.16*scale); bottom=(x+side*.10*scale,y,z-.12*scale)
    centre=(x+side*.10*scale,y-.035*scale,z+.02*scale)
    for a,b in ((base,top),(top,tip),(tip,bottom),(bottom,base)):
        mesh.face([a,b,centre],'tree_light')
with bpy.data.libraries.load(str(HERE/'hour_tree_art.blend'),link=False) as (source,destination):
    destination.objects=[name for name in source.objects if name.startswith(('hour branch ', 'branch '))]
assets={item.name:item for item in destination.objects if item is not None}
for item in assets.values(): bpy.context.scene.collection.objects.link(item)
bpy.context.view_layer.update()
def add_asset(mesh,item,colour):
    evaluated=item.evaluated_get(bpy.context.evaluated_depsgraph_get())
    baked=evaluated.to_mesh()
    for poly in baked.polygons:
        start=len(mesh.vertices)
        mesh.face([tuple(item.matrix_world @ baked.vertices[v].co) for v in poly.vertices],colour)
        if colour=='tree_light':
            if not hasattr(mesh,'leaf_uv'): mesh.leaf_uv={}
            for n,v in enumerate(poly.vertices):
                local=baked.vertices[v].co
                mesh.leaf_uv[start+n]=(max(0,min(1,local.x)),max(0,min(1,1-(local.y+.30)/.60)))
    evaluated.to_mesh_clear()
leaf_positions=[]
fall=Mesh('falling-leaves')
for i in range(12):
    branch=assets[f'hour branch {i+1:02d}']
    tip=tuple(branch.data.splines[0].bezier_points[-1].co)
    direction=-1 if tip[0]>0 else 1
    positions=[(tip[0]+direction*(.20+j*.25),tip[1]-.1,tip[2]+(.22 if j%2 else -.22)) for j in range(11)]
    leaf_positions.append(positions+[(tip[0]+direction*2.9,tip[1]-.1,tip[2]+j*.22) for j in range(4)])
    for j in (1,5,9): add_asset(fall,assets[f'branch {i+1:02d} leaf {j+1:02d}'],'tree_light')
    for full in (False,True):
        mesh=Mesh('branch')
        add_asset(mesh,branch,'trunk')
        if full:
            for j in (1,5,9): add_asset(mesh,assets[f'branch {i+1:02d} leaf {j+1:02d}'],'tree_light')
        actor(('Full' if full else 'Growing')+str(i),'platform',mesh,fields={'Visibility Mailbox':800+i*2+(1 if full else 0)})
for item in assets.values(): bpy.data.objects.remove(item,do_unlink=True)
shoot=Mesh('counting-shoot'); wood(shoot,[(0,0,0),(1.4,0,0),(2.9,0,0)],[.06,.04,.015])
actor('CountingShoot','platform',shoot)
for j in range(15):
    mesh=Mesh('leaf' if j<11 else 'bud')
    if j<11: leaf(mesh,0,0,0,scale=.55)
    else: mesh.sphere((0,0,0),.07,'window',segments=8,rings=4)
    actor(('Leaf' if j<11 else 'Bud')+str(j if j<11 else j-11),'platform',mesh,fields={'Visibility Mailbox':830+j})
actor('FallingLeaves','platform',fall,fields={'Visibility Mailbox':850})
bpy.context.view_layer.update()
objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'hourtreesettings.oad')],text=True))
fields={f['key']:f for f in catalog['fields']}
lines=[': ht-hour INDEXOF_WALL_HOUR read-mailbox 12 mod ;', ': ht-tick']
for axis,mailbox in enumerate(('INDEXOF_X_POS','INDEXOF_Y_POS','INDEXOF_Z_POS')):
    tips=[(leaf_positions[i][0][0]-(.20 if leaf_positions[i][1][0]>leaf_positions[i][0][0] else -.20),leaf_positions[i][0][1]+.1,leaf_positions[i][0][2]+.22)[axis] for i in range(12)]
    expr=' '.join(f'ht-hour {i} = if {tips[i]:.7f} else' for i in range(11))+f' {tips[11]:.7f} '+'then '*11
    lines.append(f' {expr} {mailbox} {idx["CountingShoot"]} write-actor-mailbox')
expr=' '.join(f'ht-hour {i} = if {0 if leaf_positions[i][1][0]>leaf_positions[i][0][0] else .5} else' for i in range(11))
expr+=f' {0 if leaf_positions[11][1][0]>leaf_positions[11][0][0] else .5} '+'then '*11
lines += [f' {expr} INDEXOF_ROTATION_C {idx["CountingShoot"]} write-actor-mailbox',f' 0 0 {idx["CountingShoot"]} fish-deform']
drift=fields['Camera drift']['index']
lines += [f' {idx["HourTreeSettings"]} {drift} property@ if 0 <> else drop 0 then',
          ' if 0 else INDEXOF_WALL_SECOND read-mailbox 60 / sin-rev 2.0 * then',
          f' INDEXOF_X_POS {idx["cs_wide"]} write-actor-mailbox',
          f' {idx["HourTreeSettings"]} {drift} property@ if 0 <> else drop 0 then',
          ' if -10 else INDEXOF_WALL_SECOND read-mailbox 60 / cos-rev .8 * -10 + then',
          f' INDEXOF_Y_POS {idx["cs_wide"]} write-actor-mailbox',
          f' {idx["HourTreeSettings"]} {drift} property@ if 0 <> else drop 0 then',
          ' if 5.5 else INDEXOF_WALL_SECOND read-mailbox 60 / sin-rev .5 * 5.5 + then',
          f' INDEXOF_Z_POS {idx["cs_wide"]} write-actor-mailbox']
lines += [f' ht-hour 0 = if INDEXOF_WALL_MINUTE read-mailbox 0 = if INDEXOF_WALL_SECOND read-mailbox 8 < else 0 then else 0 then 850 write-mailbox',
          f' ht-hour 0 = if INDEXOF_WALL_MINUTE read-mailbox 0 = if INDEXOF_WALL_SECOND read-mailbox 8 < if INDEXOF_WALL_SECOND read-mailbox -.65 * else 0 then else 0 then else 0 then INDEXOF_Z_POS {idx["FallingLeaves"]} write-actor-mailbox',
          f' 0 0 {idx["FallingLeaves"]} fish-deform']
for i in range(12):
    lines.append(f' ht-hour {i} = {800+i*2} write-mailbox ht-hour {i} > {801+i*2} write-mailbox')
    for name in ('Full'+str(i),'Growing'+str(i)):
        lines.append(f' 0 0 {idx[name]} fish-deform')
        lines.append(f' INDEXOF_WALL_SECOND read-mailbox 10 / {i*.07:.3f} + sin-rev .0015 * INDEXOF_ROTATION_C {idx[name]} write-actor-mailbox')
for j in range(15):
    name=('Leaf'+str(j)) if j<11 else ('Bud'+str(j-11))
    threshold=((j+1)*5-1) if j<11 else j-11
    count='INDEXOF_WALL_MINUTE read-mailbox' if j<11 else 'INDEXOF_WALL_MINUTE read-mailbox 5 mod'
    lines.append(f' {count} {threshold} > {830+j} write-mailbox')
    for axis,mailbox in enumerate(('INDEXOF_X_POS','INDEXOF_Y_POS','INDEXOF_Z_POS')):
        expr=' '.join(f'ht-hour {i} = if {leaf_positions[i][j][axis]:.7f} else' for i in range(11))
        expr+=f' {leaf_positions[11][j][axis]:.7f} '+'then '*11
        lines.append(f' {expr} {mailbox} {idx[name]} write-actor-mailbox')
    lines.append(f' 0 0 {idx[name]} fish-deform')
    if j<11:
        lines.append(f' INDEXOF_WALL_SECOND read-mailbox 6 / {j*.08:.3f} + sin-rev .025 * INDEXOF_ROTATION_C {idx[name]} write-actor-mailbox')
lines += [';','ht-tick']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'hour_tree.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'hour_tree.lev'))
