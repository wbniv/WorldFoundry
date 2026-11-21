import bpy
from mathutils import Vector
from pathlib import Path
root=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(root/'village_layout.blend'))
s=bpy.context.scene
s.cycles.samples=8
s.render.resolution_x=1000
s.render.resolution_y=700
s.render.resolution_percentage=100
s.render.filepath=str(root/'preview.png')
bpy.ops.render.render(write_still=True)
cam=bpy.data.objects['Review_camera']
cam.location=(8,-15,9)
cam.rotation_euler=(Vector((0,0,3.5))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.ortho_scale=10
s.render.filepath=str(root/'tower-review.png')
bpy.ops.render.render(write_still=True)
