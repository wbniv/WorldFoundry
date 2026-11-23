import bpy, math
from pathlib import Path
from mathutils import Vector
P=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(P/'discus.blend'))
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=16;s.render.resolution_x=1000;s.render.resolution_y=700;s.render.resolution_percentage=100
s.world=bpy.data.worlds.new('Preview');s.world.color=(.2,.2,.2)
bpy.ops.object.light_add(type='AREA',location=(.12,-.25,.28));bpy.context.object.data.energy=60;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=.3
bpy.ops.object.camera_add(location=(0,-.45,.01));c=bpy.context.object;c.rotation_euler=(Vector((-.01,0,0))-c.location).to_track_quat('-Z','Y').to_euler();c.data.type='ORTHO';c.data.ortho_scale=.29;s.camera=c
s.render.filepath=str(P/'preview.png');bpy.ops.render.render(write_still=True)
