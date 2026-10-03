"""Blender close views of both procedural assets with their exported UVs.
Run from repo root: blender -b --python <this file>. No smoothing/subdivision.
These are asset previews; the Chromecast captures show the actual renderer.
"""
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'wflevels/aquarium'))
import tiger_barb as tb
out=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=8
scene.render.resolution_x=1000;scene.render.resolution_y=600;scene.render.resolution_percentage=100
scene.world.color=(.04,.08,.1)
scene.view_settings.view_transform='Standard'
bpy.ops.object.camera_add(location=(0,-2,.28))
camera=bpy.context.object;camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=.64;scene.camera=camera
for refined in [False,True]:
 mesh=tb.blender_mesh(bpy,False,ROOT/'wflevels/aquarium/tiger_barb.tga',refined=refined)
 fish=bpy.data.objects.new('fish',mesh);scene.collection.objects.link(fish)
 mat=mesh.materials[0];nodes=mat.node_tree.nodes;nodes.clear()
 image=nodes.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(ROOT/'wflevels/aquarium/tiger_barb.tga'))
 emit=nodes.new('ShaderNodeEmission');transparent=nodes.new('ShaderNodeBsdfTransparent');mix=nodes.new('ShaderNodeMixShader');output=nodes.new('ShaderNodeOutputMaterial')
 links=mat.node_tree.links;links.new(image.outputs['Color'],emit.inputs['Color']);links.new(image.outputs['Alpha'],mix.inputs[0]);links.new(transparent.outputs[0],mix.inputs[1]);links.new(emit.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],output.inputs['Surface'])
 scene.render.filepath=str(out/('P3-close.png' if refined else 'P2-close.png'))
 bpy.ops.render.render(write_still=True)
 bpy.data.objects.remove(fish,do_unlink=True)
