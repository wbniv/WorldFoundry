"""Blender authoring preview of shared-texture lionfish; no runtime changes.
blender -b --python render_lionfish_asset.py -- OUTPUT
"""
from pathlib import Path
import sys
import math
import json
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from lionfish_model import geometry, write_textures, write_manifest, PALETTES, palette_for
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=True)
write_textures(out);mesh,metadata=write_manifest(out)
bpy.ops.wm.read_factory_settings(use_empty=True)
images={key:bpy.data.images.load(str(out/f'lionfish_{key}.tga')) for key in ['body','fins']}

def material(role,palette):
    mat=bpy.data.materials.new(role+'-'+palette['name']);mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value=.48
    if role in ('body','fin'):
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=images['body' if role=='body' else 'fins']
        ramp=mat.node_tree.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position=.08;ramp.color_ramp.elements[0].color=(*palette['dark'],1)
        ramp.color_ramp.elements[1].position=.93;ramp.color_ramp.elements[1].color=(*palette['light'],1)
        mat.node_tree.links.new(tex.outputs['Color'],ramp.inputs['Fac'])
        mat.node_tree.links.new(ramp.outputs['Color'],bsdf.inputs['Base Color'])
        if role=='fin':
            bsdf.inputs['Alpha'].default_value=.55
            mat.surface_render_method='DITHERED';mat['wf_opacity']=.55;mat['wf_double_sided']=True
    else:bsdf.inputs['Base Color'].default_value=(.009,.015,.017,1)
    return mat

objects=[]
for fish_id in range(2):
    palette=PALETTES[palette_for(0,fish_id)]
    data=bpy.data.meshes.new('lionfish-'+str(fish_id));data.from_pydata(mesh.vertices,[],mesh.faces);data.update()
    roles=list(dict.fromkeys(mesh.colors))
    for role in roles:data.materials.append(material(role,palette))
    for poly,role in zip(data.polygons,mesh.colors):poly.material_index=roles.index(role);poly.use_smooth=True
    uv=data.uv_layers.new(name='UVMap')
    for poly in data.polygons:
        for loop in poly.loop_indices:uv.data[loop].uv=mesh.uvs[data.loops[loop].vertex_index]
    obj=bpy.data.objects.new('Lionfish '+palette['name'],data);bpy.context.collection.objects.link(obj)
    obj.location=(0,fish_id*1.45,fish_id*.1);obj.rotation_euler=(0,0,fish_id*.05)
    obj['palette_id']=palette_for(0,fish_id);obj['rig_region_sidecar']='lionfish-rig.json'
    obj.shape_key_add(name='Basis')
    for name in ['hover','travel','turn','gulp']:
        key=obj.shape_key_add(name=name)
        for i,(p,region,w) in enumerate(zip(mesh.vertices,mesh.regions,mesh.weights)):
            x,y,z=p;side=-1 if 'left' in region else 1
            if region.startswith('pectoral'):
                if name=='hover':y+=side*.045*w*math.sin(mesh.uvs[i][0]*4+mesh.uvs[i][1]*2);z+=.018*w
                if name=='travel':x-=.09*w;y=side*.15+(y-side*.15)*(.65+.35*(1-w));z+=.04*w
                if name=='turn':y+=side*.08*w*(1 if side<0 else -.5)
            if region=='tail' and name in ('hover','travel'):y+=(.025 if name=='hover' else .06)*w
            if name=='gulp' and region=='jaw':
                a=.48*w;x,z=.34+(x-.34)*math.cos(a)+(z+.035)*math.sin(a),-.035-(x-.34)*math.sin(a)+(z+.035)*math.cos(a)
                x+=.04*w
            if name=='gulp' and region=='head':z+=.025*w;x+=.02*w
            if name=='gulp' and region=='trunk' and x>.1:z-=.018;y*=1.06
            key.data[i].co=(x,y,z)
        key.value=0
        if name=='hover':
            driver=key.driver_add('value').driver;driver.expression=f'0.5+0.5*sin(frame*0.03927+{fish_id*1.7})'
        elif name=='travel':
            for f,value in [(1,0),(90,0),(120,1),(175,1),(210,0)]:key.value=value;key.keyframe_insert('value',frame=f)
        elif name=='gulp':
            for f,value in [(1,0),(230,0),(232,1),(234,.35),(238,0)]:key.value=value;key.keyframe_insert('value',frame=f)
        elif name=='turn':
            for f,value in [(1,0),(180,0),(195,1),(210,0)]:key.value=value;key.keyframe_insert('value',frame=f)
    objects.append(obj)

scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=1400;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.fps=30;scene.frame_end=250
scene.world=bpy.data.worlds.new('Water backdrop');scene.world.color=(.04,.065,.08)
scene.view_settings.view_transform='AgX'
for name,pos,power,size in [('Key',(2,-3,4),550,4),('Fill',(-2,2,3),400,3)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.location=pos
    obj.rotation_euler=(Vector((0,.5,0))-obj.location).to_track_quat('-Z','Y').to_euler()
cam_data=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cam_data);bpy.context.collection.objects.link(cam)
cam.location=(2.3,-4.4,2.0);cam.rotation_euler=(Vector((0,.65,.18))-cam.location).to_track_quat('-Z','Y').to_euler()
cam_data.type='ORTHO';cam_data.ortho_scale=3.45;scene.camera=cam
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.frame_set(20)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'lionfish.blend'))
for frame,name in [(20,'hover'),(145,'travel'),(195,'turn'),(232,'gulp')]:
    scene.frame_set(frame);scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
metadata['preview']='Blender authoring mesh and shape-key study; not runtime evidence'
metadata['palette_assignment']=[o['palette_id'] for o in objects]
metadata['shared_images']=[image.filepath for image in images.values()]
(out/'preview.json').write_text(json.dumps(metadata,indent=2)+'\n')
