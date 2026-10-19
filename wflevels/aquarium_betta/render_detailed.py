"""Render exactly the runtime source geometry, in the same native fin deformation pose.

blender --background --python wflevels/aquarium_betta/render_detailed.py
The studio lighting differs from the game; geometry, opaque materials and pose do not.
"""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE.parent/'aquarium_tanks')]
from detailed_model import COLORS,detailed_models
OUT=ROOT/'docs/reference/betta-history-and-biomechanics-poster/assets';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
materials={}
for key,rgb in COLORS.items():
    m=bpy.data.materials.new(key);m.use_nodes=True;m.diffuse_color=(*rgb,1)
    shader=m.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=(*rgb,1)
    shader.inputs['Roughness'].default_value=.42;materials[key]=m
phase=.21;pectoral_phase=.39;spread=.72
motion=[None,(phase,.065,0,spread),(phase+.18,.035,0,spread*.85+.15),
        (phase+.39,.040,0,spread*.75+.25),(pectoral_phase,.028,0,.85),
        (pectoral_phase+.5,.028,0,.85),(phase+.29,.038,0,1),(phase+.56,.038,0,1)]
meshes,_=detailed_models();counts={}
for k,m in enumerate(meshes):
    vertices=[tuple(int(v*65536)/65536 for v in point) for point in m.vertices]
    if motion[k]:
        ph,amp,sweep,sp=motion[k];roots={u:(x,z) for (x,y,z),(u,v) in zip(vertices,m.uvs) if v==0};posed=[]
        for (x,y,z),(u,v) in zip(vertices,m.uvs):
            rx,rz=roots[u];angle=ph*math.tau
            x=rx+(x-rx)*sp-sweep*v*v;y+=amp*v*v*math.sin(angle-v*2.4-u*3*math.pi)
            z=rz+(z-rz)*sp+amp*.25*v*v*math.cos(angle-v*1.3-u*1.1)
            posed.append(tuple(int(t*65536)/65536 for t in (x,y,z)))
        vertices=posed
    data=bpy.data.meshes.new(m.name);data.from_pydata(vertices,[],m.faces);data.update()
    keys=list(dict.fromkeys(m.colors))
    for key in keys:data.materials.append(materials[key])
    for p,key in zip(data.polygons,m.colors):p.material_index=keys.index(key);p.use_smooth=True
    ob=bpy.data.objects.new(m.name,data);bpy.context.collection.objects.link(ob);counts[m.name]=sum(len(f)-2 for f in m.faces)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.film_transparent=True;scene.render.resolution_x=3200;scene.render.resolution_y=1900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Studio world');scene.world.color=(.3,.3,.3)
def area(name,loc,power,size):
    bpy.ops.object.light_add(type='AREA',location=loc);ob=bpy.context.object;ob.name=name;ob.data.energy=power;ob.data.size=size
    ob.rotation_euler=(Vector((-.25,0,0))-ob.location).to_track_quat('-Z','Y').to_euler()
area('Key',(1,-3,4),220,3);area('Rim',(-2,2,3),140,3);area('Fill',(3,-3,.2),65,2)
bpy.ops.object.camera_add(location=(-.25,-6,.25));camera=bpy.context.object;scene.camera=camera
camera.data.type='ORTHO';camera.data.ortho_scale=2.30
for name,loc in [('runtime-betta-side.png',(-.25,-6,.15)),('runtime-betta-oblique.png',(1.9,-5,1.5))]:
    camera.location=loc;camera.rotation_euler=(Vector((-.25,0,-.04))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'runtime-betta.blend'))
(OUT/'runtime-model-manifest.json').write_text(json.dumps({'triangles':sum(counts.values()),'groups':counts,
    'phase':phase,'pectoral_phase':pectoral_phase,'spread':spread,'motion_by_group':motion,
    'geometry_source':'wflevels/aquarium_betta/detailed_model.py','note':'Same runtime geometry and native fin formula; smooth studio lighting, fully opaque surfaces.'},indent=2)+'\n')
