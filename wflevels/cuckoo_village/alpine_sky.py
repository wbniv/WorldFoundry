"""Day and night Alpine sky domes for the German Cuckoo Village."""
import math
from pathlib import Path
import bpy
import bmesh
import numpy as np

HERE=Path(__file__).resolve().parent

def build(root):
    # Ellipsoid fits the authored room and surrounds every camera position.
    segs,rings=64,24
    verts=[];uvs=[];faces=[]
    for i in range(rings+1):
        phi=-math.pi/2+math.pi*i/rings
        for j in range(segs+1):
            theta=math.tau*j/segs
            verts.append((50*math.cos(theta)*math.cos(phi),-50*math.sin(theta)*math.cos(phi),10+25*math.sin(phi)))
            uvs.append((j/segs,max(.02,min(.95,.65-.75*phi/(math.pi/2)))))
    cols=segs+1
    for i in range(rings):
        for j in range(segs):
            a=i*cols+j;b=a+1;d=(i+1)*cols+j;c=d+1
            faces.append((a,d,c) if i==0 else (a,d,b) if i==rings-1 else (a,d,c,b))
    mesh=bpy.data.meshes.new('alpine_sky');mesh.from_pydata(verts,[],faces);mesh.update()
    uv=mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:uv.data[loop.index].uv=uvs[loop.vertex_index]
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bmesh.ops.reverse_faces(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free();mesh.update()
    day=bpy.data.images.load(str(HERE/'alpine-panorama-source.png'),check_existing=True)
    day.scale(1024,256)
    pixels=np.empty(1024*256*4,dtype=np.float32)
    day.pixels.foreach_get(pixels)
    night_pixels=pixels.reshape((-1,4)).copy()
    night_pixels[:,:3] *= np.array((.20,.27,.40),dtype=np.float32)
    night=bpy.data.images.new('alpine_night_aligned',width=1024,height=256,alpha=True)
    night.pixels.foreach_set(night_pixels.ravel())
    warm_pixels=pixels.reshape((-1,4)).copy()
    warm_pixels[:,:3] = np.clip(warm_pixels[:,:3] * np.array((.90,.58,.36),dtype=np.float32)
                                 + np.array((.05,.012,0),dtype=np.float32),0,1)
    warm=bpy.data.images.new('alpine_twilight_aligned',width=1024,height=256,alpha=True)
    warm.pixels.foreach_set(warm_pixels.ravel())
    # The warm overlay is subtle and transient; keep it within the existing
    # 2048-square room texture page instead of enlarging the host allocation.
    warm.scale(512,256)
    for label,image,cell in (('AlpineSkyDay',day,284),('AlpineSkyNight',night,285),('AlpineSkyWarm',warm,286)):
        image.filepath_raw=str(HERE/(label.lower()+'.tga'));image.file_format='TARGA';image.save()
        mat=bpy.data.materials.new(label);mat.use_nodes=True;mat.diffuse_color=(1,1,1,1);mat['wf_prelit']=True
        if label != 'AlpineSkyNight': mat['wf_opacity']=0.999
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
        mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        part=mesh.copy();part.materials.append(mat)
        obj=bpy.data.objects.new(label,part);bpy.context.scene.collection.objects.link(obj)
        if label == 'AlpineSkyDay': obj.scale=(.997,.997,.997)
        if label == 'AlpineSkyWarm': obj.scale=(.994,.994,.994)
        obj['wf_schema_path']=str(root/'wfsource/source/oas/platform.oad');obj['wf_Mobility']='Anchored';obj['wf_Model Type']='Mesh';obj['wf_Mass']=0.0
        obj['wf_Moves Between Rooms']='True';obj['wf_Visibility Mailbox']=cell;obj['wf_Mesh Name']=label+'.iff';obj['wf_original_mesh_name']=label+'.iff'
