"""Print tower triangle counts from the generated Blender scene."""
from pathlib import Path
import bpy
root = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(root / 'village_layout.blend'))
total = 0
for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
    if obj.type != 'MESH' or not (obj.name in ('clock_tower', 'hour_hand', 'minute_hand', 'bird_door', 'tower_glow') or obj.name.startswith(('tower_case', 'tower_figure_', 'tower_bird', 'tower_carved_panel'))):
        continue
    obj.data.calc_loop_triangles()
    n = len(obj.data.loop_triangles)
    total += n
    print(f'TOWER_MESH {obj.name}: {n} triangles')
print(f'TOWER_TOTAL {total} triangles')
