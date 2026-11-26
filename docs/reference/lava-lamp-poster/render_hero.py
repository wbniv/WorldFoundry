"""Render the lava lamp poster's hero image: the shipped scene (wflevels/lava_lamp/lava_lamp.blend) in CPU Cycles.

    df -h /                                   # stop below 5 GB free
    WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh \
        blender --background wflevels/lava_lamp/lava_lamp.blend --python docs/reference/lava-lamp-poster/render_hero.py

Writes docs/reference/lava-lamp-poster/hero-cycles.png (portrait, 720 x 1080). Plan: docs/plans/2026-11-26-lava-lamp.md
(Phase P, "the hero image is a Cycles render of the shipped scene").

The scene is prelit: every surface carries its shading in the `shade` colour layer, and the engine draws
vertex colour = tint x shade x glow (the Morph deformer, E1). So each material here becomes an emission of
`shade`, multiplied by the object's colour, which this script sets to the tint and glow the director would write.
The wax is posed as the engine poses it on its first frame: model.warmed() (the 150 s warm-up baked into the
script) through model.pose(), with the default colours (Orange lava in Violet water) and 21:47 in the base.
The camera is the level's: its position, its look-at point and the engine's fixed 60 degree vertical view, on a
portrait frame, so the room crops at the sides as it does on a phone. No GPU and no GL: CPU Cycles only.
"""
import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEVEL = ROOT / 'wflevels' / 'lava_lamp'
sys.path.insert(0, str(LEVEL))
import lamp as L  # noqa: E402
import model as M  # noqa: E402

OUT = HERE / 'hero-cycles.png'
TIME = '2147'                       # the base shows 21:47, as the plan's mockups do
WIDTH, HEIGHT, SAMPLES = 720, 1080, 96


def lin(c):
    """sRGB 0..1 to linear (the engine multiplies display values; Blender's emission is linear)."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def tint(rgb, glow=1.0):
    return (lin(min(1.0, rgb[0] * glow)), lin(min(1.0, rgb[1] * glow)), lin(min(1.0, rgb[2] * glow)), 1.0)


def emission_material(name, opacity=1.0):
    mat = bpy.data.materials.new('poster_' + name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_name = 'shade'
    info = nt.nodes.new('ShaderNodeObjectInfo')
    mul = nt.nodes.new('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(attr.outputs['Color'], mul.inputs[6])
    nt.links.new(info.outputs['Color'], mul.inputs[7])
    emit = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(mul.outputs[2], emit.inputs['Color'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    if opacity < 1.0:
        clear = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs['Fac'].default_value = opacity
        nt.links.new(clear.outputs[0], mix.inputs[1])
        nt.links.new(emit.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
    else:
        nt.links.new(emit.outputs[0], out.inputs['Surface'])
    return mat


def main():
    scene = bpy.context.scene
    objs = bpy.data.objects
    for mat in list(bpy.data.materials):
        if mat.name.startswith('poster_'):
            continue
        new = emission_material(mat.name, float(mat.get('wf_opacity', 1.0)))
        for o in objs:
            if o.type == 'MESH':
                for slot in o.material_slots:
                    if slot.material == mat:
                        slot.material = new
    for o in objs:
        o.color = (1.0, 1.0, 1.0, 1.0)

    lava = L.rgb(L.LAVA[L.DEFAULT_LAVA][1])
    water = L.rgb(L.WATER[L.DEFAULT_WATER][1])
    mix = L.WAX_WATER_MIX
    wax = tuple(lava[c] * (1 - mix) + water[c] * mix for c in range(3))
    # the static tint actors, as forth.palette_words writes them (tint channels, then glow)
    statics = {
        'Liquid': (water, 1.0),
        'Glass': (tuple(0.5 * w + 0.5 for w in water), 1.0),
        'WallGlow': (tuple(0.65 * water[c] + 0.35 * lava[c] for c in range(3)), 0.55),
        'TableLight': (tuple(0.5 * water[c] + 0.5 * lava[c] for c in range(3)), 0.8),
    }
    for name, (rgb, glow) in statics.items():
        objs[name].color = tint(rgb, glow)

    lamp = M.warmed()
    pose = M.pose(lamp, tuple(M.F(v) for v in wax))
    keys = ('rise', 'fall', 'squash', 'neck', 'wobble_a', 'wobble_b')

    def place(o, x, z, s, block, roll=0.0):
        o.hide_render = False
        o.location = (float(x), 0.0, float(z))
        o.scale = (float(s),) * 3
        o.rotation_euler = (0.0, float(roll) * 2 * math.pi, 0.0)
        # each actor gets its own mesh copy so its morph weights are its own
        o.data = o.data.copy()
        o.color = tint(block[6:9], float(block[9]))

    blob_keys = {}
    src = objs['Blob0'].data
    if src.shape_keys:
        blob_keys = {k.name: k for k in src.shape_keys.key_blocks}
    for i, item in enumerate(pose['blobs']):
        o = objs[f'Blob{i}']
        if item is None:
            o.hide_render = True
            continue
        x, z, s, block = item
        place(o, x, z, s, block)
        for k, w in zip(keys, block[:6]):
            kb = o.data.shape_keys.key_blocks.get('morph_' + k) if o.data.shape_keys else None
            if kb:
                kb.value = float(w)
    for k in range(L.N_MERGED, 8):
        if f'Merged{k}' in objs:
            objs[f'Merged{k}'].hide_render = True
    for k, item in enumerate(pose['merged']):
        o = objs[f'Merged{k}']
        if item is None:
            o.hide_render = True
            continue
        x, z, s, roll, block = item
        place(o, x, z, s, block, roll)
        for name, w in zip(keys, block[:6]):
            kb = o.data.shape_keys.key_blocks.get('morph_' + name) if o.data.shape_keys else None
            if kb:
                kb.value = float(w)
    pool = objs['Pool']
    pool.data = pool.data.copy()
    pb = pose['pool']
    for name, w in zip(('mound', 'tower', 'neck', 'dip'), pb[:4]):
        kb = pool.data.shape_keys.key_blocks.get('morph_' + name) if pool.data.shape_keys else None
        if kb:
            kb.value = float(w)
    pool.color = tint(pb[6:9], float(pb[9]))
    if not blob_keys:
        print('render_hero: warning: the blob mesh carries no shape keys; morph weights not applied')

    # the base: 21:47 in lit holes, the dashes hidden
    for o in objs:
        if o.name.startswith('Digit'):
            p, v = o.name[5:].split('_')
            o.hide_render = TIME[int(p)] != v
    objs['Dashes'].hide_render = True
    objs['Colon'].hide_render = False

    # the level's camera: its position, its look-at point, the engine's fixed 60 degree vertical view
    cam_data = bpy.data.cameras.new('PosterCam')
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.angle_y = math.radians(60.0)
    cam_data.clip_start, cam_data.clip_end = 2.0, 600.0
    cam = bpy.data.objects.new('PosterCam', cam_data)
    scene.collection.objects.link(cam)
    cam.location = objs['Camera'].location
    look = cam.constraints.new('TRACK_TO')
    look.target = objs['LookAt']
    look.track_axis, look.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
    scene.camera = cam

    world = bpy.data.worlds.new('PosterWorld')
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs[0].default_value = tint((0x07 / 255, 0x05 / 255, 0x0b / 255))
    bg.inputs[1].default_value = 1.0
    scene.world = world

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 0
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 100
    scene.render.filepath = str(OUT)
    bpy.ops.render.render(write_still=True)
    print(f'render_hero: wrote {OUT} ({OUT.stat().st_size} bytes); '
          f'{sum(1 for b in pose["blobs"] if b)} blobs, {sum(1 for m in pose["merged"] if m)} merged, time {TIME[:2]}:{TIME[2:]}')


main()
