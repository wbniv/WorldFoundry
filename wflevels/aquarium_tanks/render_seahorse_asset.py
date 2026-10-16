"""Review sheet for the seahorse asset, without the engine: both colourways in
the bind pose and in every clip, posed by the Blender armature that the DFRM
exporter samples. The engine capture is seahorse_capture.py.

    blender --background --python wflevels/aquarium_tanks/render_seahorse_asset.py -- --out DIR
"""
import argparse
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bpy  # noqa: E402
import seahorse as sh  # noqa: E402

# Clip and the frame shown (30 fps): a characteristic moment of each.
POSES = [('bind pose', None, 0), ('rest_coil', 'rest_coil', 30), ('swim', 'swim', 10), ('hold_idle', 'hold_idle', 40),
         ('probe', 'probe', 50), ('release', 'release', 15), ('startle', 'startle', 4), ('greet_f', 'greet_f', 45),
         ('greet_m', 'greet_m', 45)]


def blender_mesh(m, image):
    d = bpy.data.meshes.new(m.name)
    d.from_pydata(m.vertices, [], m.faces)
    mat = bpy.data.materials.new(m.name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image, tex.interpolation = image, 'Closest'
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    d.materials.append(mat)
    uv = d.uv_layers.new(name='UVMap')
    for poly in d.polygons:
        for li in poly.loop_indices:
            u, v = m.uvs[d.loops[li].vertex_index]
            uv.data[li].uv = (u, 1 - v)            # atlas rows run top-down; Blender's V runs up
    d.update()
    return d


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(argv)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    sh.write_texture(out)
    image = bpy.data.images.load(str(out / sh.TEXTURE))
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.color_type = 'TEXTURE'
    scene.render.resolution_x, scene.render.resolution_y = 300, 420
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new('world')
    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera'))
    scene.collection.objects.link(cam)
    cam.location, cam.rotation_euler = (.06, -1.6, -.16), (math.pi / 2, 0, 0)
    cam.data.type, cam.data.ortho_scale = 'ORTHO', 1.75
    scene.camera = cam
    tiles = {}
    actions = None
    for sex in sh.SEXES:
        bm, fm = sh.body(sex), sh.fins(sex)
        body = bpy.data.objects.new(f'body-{sex}', blender_mesh(bm, image))
        fins = bpy.data.objects.new(f'fins-{sex}', blender_mesh(fm, image))
        for obj in (body, fins):
            scene.collection.objects.link(obj)
        sh.add_vertex_groups(body, bm)
        rig, actions = sh.armature(bpy, f'rig-{sex}', body, actions)
        fins.parent = rig
        for other in scene.objects:
            other.hide_render = other.type == 'MESH' and other not in (body, fins)
        for label, clip, frame in POSES:
            rig.animation_data.action = actions[clip] if clip else None
            if rig.animation_data.action is not None and rig.animation_data.action_slot is None:
                rig.animation_data.action_slot = actions[clip].slots[0]
            if clip is None:
                for pb in rig.pose.bones:
                    pb.rotation_quaternion = (1, 0, 0, 0)
            scene.frame_set(1 + frame)
            path = out / f'pose-{sex}-{label.replace(" ", "-")}.png'
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            tiles[(sex, label)] = path
    from PIL import Image, ImageDraw
    w, h = scene.render.resolution_x, scene.render.resolution_y
    sheet = Image.new('RGB', (w * len(POSES), (h + 24) * 2), (24, 28, 32))
    draw = ImageDraw.Draw(sheet)
    for r, sex in enumerate(sh.SEXES):
        for c, (label, _clip, frame) in enumerate(POSES):
            sheet.paste(Image.open(tiles[(sex, label)]).convert('RGB'), (c * w, r * (h + 24) + 24))
            text = f'{sh.COLOURWAY[sex].split(" ")[0]} {label}' + (f' @ {frame / 30:.2f} s' if _clip else '')
            draw.text((c * w + 8, r * (h + 24) + 6), text, fill=(230, 230, 230))
            tiles[(sex, label)].unlink()
    sheet.save(out / 'clip-poses.png')
    (out / sh.TEXTURE).unlink()
    print('wrote', out / 'clip-poses.png')


main()
