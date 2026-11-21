"""Rigged Blender masters and reproducible review renders of the actual game assets.

Presentation cameras/lights are added after the WF export, never exported as
runtime geometry. No downloaded or generated stand-in species photographs.
"""
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from config import SPECIES
import brittle
NAMES={'linckia':'Blue sea star','chip':'Chocolate-chip star','fromia':'Red Fromia','sand':'Sand-sifting star','brittle':'Green brittle star','cushion':'Cushion star'}

def rig(obj,kind):
    if kind=='cushion':return None
    spec=SPECIES[kind];count=brittle.sample_count(kind)
    armature=bpy.data.armatures.new(obj.name+' skeleton')
    skeleton=bpy.data.objects.new(obj.name+' rig',armature)
    bpy.context.scene.collection.objects.link(skeleton);skeleton.location=obj.location
    bpy.context.view_layer.objects.active=skeleton;skeleton.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for arm in range(5):
        angle=math.tau*arm/5;root,step=brittle.root_and_step(kind)
        parent=None
        for segment in range(count):
            bone=armature.edit_bones.new(f'arm{arm+1}.{segment+1}')
            bone.head=((root+step*segment)*math.cos(angle),(root+step*segment)*math.sin(angle),0)
            bone.tail=((root+step*(segment+1))*math.cos(angle),(root+step*(segment+1))*math.sin(angle),0)
            bone.align_roll(Vector((0,0,1)))
            if parent:bone.parent=parent;bone.use_connect=True
            parent=bone
    bpy.ops.object.mode_set(mode='OBJECT');skeleton.select_set(False)
    groups={b.name:obj.vertex_groups.new(name=b.name) for b in armature.bones}
    for v in obj.data.vertices:
        owner=brittle.binding(kind,v.co)
        if owner is None:continue
        arm,sample=owner
        groups[f'arm{arm+1}.{sample+1}'].add([v.index],1,'REPLACE')
    mod=obj.modifiers.new('Five independently posed arms','ARMATURE');mod.object=skeleton
    skeleton['source_note']=f'{count} bones per arm. Same sample binding and axes as the exported five-curve DFRM v2 mesh.'
    clips={'linckia':('glide','lead','corner','reach'),'chip':('glide','lead'),'fromia':('glide',),'sand':('glide',),'brittle':('row','hide')}[kind]
    for clip in clips:
        action=bpy.data.actions.new(kind+'_'+clip);action.use_fake_user=True
        skeleton.animation_data_create();skeleton.animation_data.action=action
        for frame in (range(1,62,5) if kind=='brittle' else (1,16,31,46,61)):
            for arm in range(5):
                for segment in range(count):
                    bone=skeleton.pose.bones[f'arm{arm+1}.{segment+1}'];bone.rotation_mode='XYZ'
                    flex=math.radians(3)*math.sin(math.tau*(frame-1)/60-segment*.7+arm*.6)
                    lateral=0
                    pulse=math.sin(math.pi*(frame-1)/60)**2
                    if clip=='lead' and arm==0:flex+=math.radians(5)*pulse
                    if clip=='corner' and arm in (0,1,4):flex+=math.radians(30)*pulse
                    if clip=='reach':flex+=math.radians(24 if arm<3 else 0)*pulse
                    if clip=='row':lateral=math.radians(15)*math.sin(math.tau*(frame-1)/60+arm*math.pi/2-segment*.5)
                    if clip=='hide':flex*=.3;lateral=math.radians(3)*math.sin(math.tau*(frame-1)/60-segment*.8)
                    # Keep proximal samples planted so posing cannot fold the disc.
                    if segment==0:flex=0;lateral=0
                    if kind=='brittle':
                        flex,lateral,_=tuple(math.radians(v) for v in brittle.angles(arm,segment,frame-1,clip))
                    bone.rotation_euler=(flex,0,lateral);bone.keyframe_insert('rotation_euler',frame=frame,group=f'Arm {arm+1}')
        skeleton.animation_data.action=None
    for bone in skeleton.pose.bones:bone.rotation_euler=(0,0,0)
    if kind=='brittle':brittle.apply_pose(skeleton)
    return skeleton

def transform_action(obj,name,values,channel='location'):
    action=bpy.data.actions.new(name);action.use_fake_user=True
    obj.animation_data_create();obj.animation_data.action=action
    original=tuple(getattr(obj,channel))
    for frame,value in values:
        setattr(obj,channel,value);obj.keyframe_insert(channel,frame=frame)
    obj.animation_data.action=None;setattr(obj,channel,original)

def build_review(repo,out,dest,mode='full'):
    dest.mkdir(parents=True,exist_ok=True)
    sc=bpy.context.scene
    # Convert only the Blender view of the atlas to bottom-up coordinates.
    for obj in sc.objects:
        if obj.get('wf_Visibility Mailbox')==0 or obj.get('wf_Model Type')=='None':
            obj.hide_render=True;obj.hide_set(True)
    # Use a shader coordinate conversion, preserving export UVs in the master.
    for mat in bpy.data.materials:
        if not mat.use_nodes:continue
        tree=mat.node_tree
        for tex in [n for n in tree.nodes if n.type=='TEX_IMAGE']:
            uv=tree.nodes.new('ShaderNodeTexCoord')
            separate=tree.nodes.new('ShaderNodeSeparateXYZ')
            invert=tree.nodes.new('ShaderNodeMath');invert.operation='SUBTRACT';invert.inputs[0].default_value=1
            combine=tree.nodes.new('ShaderNodeCombineXYZ')
            tree.links.new(uv.outputs['UV'],separate.inputs[0]);tree.links.new(separate.outputs['Y'],invert.inputs[1])
            tree.links.new(separate.outputs['X'],combine.inputs['X']);tree.links.new(invert.outputs[0],combine.inputs['Y'])
            tree.links.new(combine.outputs[0],tex.inputs['Vector'])
    specimen={}
    for name,kind in (('BlueStar','linckia'),('ChipOne','chip'),('FromiaOne','fromia'),('SandOne','sand'),('Brittle','brittle'),('Cushion','cushion')):
        obj=bpy.data.objects[name];specimen[kind]=obj
        obj['scientific_name']=SPECIES[kind]['scientific'];obj['display_diameter_cm']=SPECIES[kind]['radius']*20
        obj['asset_status']='Authored Sea Stars asset; gameplay acceptance pending'
    rigs={}
    for obj in list(sc.objects):
        kind=next((k for k in SPECIES if obj.get('wf_Mesh Name')=='star_'+k+'.iff'),None)
        if kind:
            rigs[obj.name]=rig(obj,kind)
            if kind=='sand':
                x,y,z=obj.location
                transform_action(obj,obj.name+'_bury',((1,(x,y,z)),(31,(x,y,z-.12))))
                transform_action(obj,obj.name+'_rise',((1,(x,y,z-.12)),(121,(x,y,z))))
            if kind=='cushion':transform_action(obj,'cushion_puff',((1,(1,1,1)),(151,(1,1,1.08)),(301,(1,1,1))),'scale')
    # Lighting setup is deliberately distinct from the runtime Camera shader.
    # Review images show topology, source skin and arm poses under soft light.
    sc.world=bpy.data.worlds.new('Lagoon blue environment');sc.world.use_nodes=True
    sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.045,.095,.13,1)
    sc.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    for name,pos,energy,size,color in (
        ('Soft daylight',(-4,-5,9),1800,7,(.80,.91,1)),
        ('Warm sand bounce',(4,-1,5),1000,5,(1,.88,.68)),
        ('Water rim',(0,4,6),2200,5,(.38,.73,1))):
        ld=bpy.data.lights.new(name,'AREA');ld.energy=energy;ld.shape='DISK';ld.size=size;ld.color=color
        obj=bpy.data.objects.new(name,ld);sc.collection.objects.link(obj);obj.location=pos
        obj.rotation_euler=(Vector((0,0,.8))-obj.location).to_track_quat('-Z','Y').to_euler()
    cd=bpy.data.cameras.new('Asset review camera');camera=bpy.data.objects.new('Asset review camera',cd);sc.collection.objects.link(camera);sc.camera=camera
    def view(pos,target,ortho=None):
        camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        cd.type='ORTHO' if ortho else 'PERSP'
        if ortho:cd.ortho_scale=ortho
        else:cd.lens=44
    sc.render.engine='CYCLES';sc.cycles.samples=24 if mode=='brittle' else 40;sc.cycles.use_denoising=True
    sc.render.threads_mode='FIXED';sc.render.threads=4
    sc.render.image_settings.file_format='PNG';sc.render.resolution_percentage=100
    sc.view_settings.view_transform='AgX'
    def render(name,width=1440,height=900):
        sc.render.resolution_x=width;sc.render.resolution_y=height;sc.render.filepath=str(dest/(name+'.png'))
        bpy.ops.render.render(write_still=True)
    # Remove unused template materials/meshes before packing the source master.
    bpy.data.orphans_purge(do_recursive=True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.shading.type='MATERIAL'
    # Pack the actual texture so the master has no external image dependency.
    for image in bpy.data.images:
        if image.source=='FILE':image.pack()
    view((0,-17,10),(0,.1,1.05))
    sc['Sea Stars review']='Actual export meshes and atlas. Lighting is for source-asset review. Runtime verification pending.'
    sc.frame_start=1;sc.frame_end=301
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'sea_stars_assets.blend'))
    if mode!='poses':render('01-tank-wide')
    if mode=='scene':
        return
    # Preserve the tank, then isolate individual animals on a sand plinth.
    objects=list(sc.objects)
    saved={obj.name:(obj.hide_render,tuple(obj.location),tuple(obj.rotation_euler)) for obj in objects}
    for obj in objects:
        if obj.type=='MESH':obj.hide_render=True
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.028))
    ground=bpy.context.object;ground.name='Specimen sand stage'
    mat=bpy.data.materials.new('Specimen sand');mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.27,.24,.18,1);bs.inputs['Roughness'].default_value=.9
    noise=mat.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=170
    bump=mat.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.15;bump.inputs['Distance'].default_value=.012
    mat.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);mat.node_tree.links.new(bump.outputs['Normal'],bs.inputs['Normal']);ground.data.materials.append(mat)
    files=[]
    for kind,obj in specimen.items():
        if (mode in ('revisions','poses') and (kind!='linckia' or mode=='poses')) or (mode=='brittle' and kind!='brittle'):
            files.append(dict(kind=kind,name=NAMES[kind],scientific=SPECIES[kind]['scientific'],image='species-'+kind+'.png'))
            continue
        obj.hide_render=False;obj.location=(0,0,.025);obj.rotation_euler=(0,0,math.radians(18))
        skeleton=rigs[obj.name]
        if skeleton:skeleton.location=obj.location;skeleton.rotation_euler=obj.rotation_euler
        r=SPECIES[kind]['radius']
        view((0,-3,4),(0,0,0),r*2.6)
        render('species-'+kind,960,800)
        if skeleton:
            skeleton['neutral_render']='species-'+kind+'.png'
        files.append(dict(kind=kind,name=NAMES[kind],scientific=SPECIES[kind]['scientific'],image='species-'+kind+'.png'))
        obj.hide_render=True
    if mode!='brittle':
        # The actual oral mesh and skin, viewed through the front wall: top faces
        # inward (+Y), the pale underside faces the observer (-Y).
        obj=specimen['linckia'];skeleton=rigs[obj.name]
        ground.hide_render=True;obj.hide_render=False
        obj.location=(0,0,1.1);obj.rotation_euler=(-math.pi/2,0,0)
        skeleton.location=obj.location;skeleton.rotation_euler=obj.rotation_euler
        view((0,-4,1.1),(0,0,1.1),2.5)
        if mode!='poses':render('player-underside',1200,1000)
        # Pose renders exercise the saved source rig, rather than painted mockups.
        ground.hide_render=False
        for clip,frame,label in (('lead',31,'player-leading-arm'),('corner',31,'player-corner'),('reach',31,'player-reach')):
            obj.location=(0,0,.025);obj.rotation_euler=(0,0,.25)
            skeleton.location=obj.location;skeleton.rotation_euler=obj.rotation_euler
            skeleton.animation_data.action=bpy.data.actions['linckia_'+clip];sc.frame_set(frame)
            view((0,-3.4,2.6),(0,0,.15),2.5)
            render(label,1200,900)
        skeleton.animation_data.action=None
        for bone in skeleton.pose.bones:bone.rotation_euler=(0,0,0)
        sc.frame_set(1)
    # Restore the master for inspection in Blender.
    bpy.data.objects.remove(ground,do_unlink=True)
    for obj in objects:
        hidden,pos,rotation=saved[obj.name];obj.hide_render=hidden;obj.location=pos;obj.rotation_euler=rotation
    for name,skeleton in rigs.items():
        if skeleton:skeleton.location=bpy.data.objects[name].location;skeleton.rotation_euler=bpy.data.objects[name].rotation_euler
    view((0,-17,10),(0,.1,1.05))
    sc.render.resolution_x=1440;sc.render.resolution_y=900
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'sea_stars_assets.blend'))
    (dest/'assets.json').write_text(json.dumps(dict(species=files,source='wflevels/aquarium_sea_stars/sea_stars_assets.blend',
        renders='Actual authored meshes and atlas under presentation lighting; no runtime verification implied.'),indent=2)+'\n')
