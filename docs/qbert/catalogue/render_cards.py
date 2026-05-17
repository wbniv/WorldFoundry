"""Render PNGs for docs/qbert/catalogue.md.

Run from repo root:

    blender --background wflevels/qbert_practice/qbert_practice.blend \\
            --python docs/qbert/catalogue/render_cards.py

Outputs into docs/qbert/catalogue/:
    pyramid_L1R1.png            — full pyramid in L1R1 palette (1280×720)
    pyramid_R00.png … R15.png   — mini pyramids per round  (320×240)
    actor_<name>.png            — individual actor cards   (512×512)

Palette data is imported from wflevels/qbert_practice/gen_cube.py so the
canonical source-of-truth tables drive the renders. No engine state.
"""

import importlib.util
import math
import os
import sys

import bpy


REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
QBERT_DIR = os.path.join(REPO, 'wflevels', 'qbert_practice')
OUT_DIR = os.path.join(REPO, 'docs', 'qbert', 'catalogue')

os.makedirs(OUT_DIR, exist_ok=True)


def _load_gen_cube():
    spec = importlib.util.spec_from_file_location('gen_cube', os.path.join(QBERT_DIR, 'gen_cube.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gc = _load_gen_cube()


def hex_to_rgb_linear(hex_rgb):
    """Convert 0xRRGGBB int → (r, g, b) floats in linear space for Blender.

    Blender materials expect linear-space colours. The source palette values are
    arcade-style sRGB hex codes, so convert per channel.
    """
    r = ((hex_rgb >> 16) & 0xFF) / 255.0
    g = ((hex_rgb >>  8) & 0xFF) / 255.0
    b = ( hex_rgb        & 0xFF) / 255.0
    def srgb_to_linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b))


CUBE_NAMES = [f'cube_{i:02d}' for i in range(28)]

ACTOR_RENDERS = [
    # (object_name, output_basename, optional view tweak)
    ('Player',      'actor_player'),
    ('redball_0',   'actor_redball'),
    ('greenball',   'actor_greenball'),
    ('coily_egg',   'actor_coily_egg'),
    ('coily_egg_2', 'actor_coily_egg_2'),
    ('coily_snake', 'actor_coily_snake'),
    ('slick',       'actor_slick'),
    ('sam',         'actor_sam'),
    ('ugg',         'actor_ugg'),
    ('wrongway',    'actor_wrongway'),
    ('disc_left',   'actor_disc'),
    ('curse_bubble','actor_curse_bubble'),
]


def clear_render_settings():
    """Switch to Eevee with neutral colour management, world background grey."""
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.display_settings.display_device = 'sRGB'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    # Neutral background world.
    world = bpy.data.worlds.get('CatalogueWorld')
    if world is None:
        world = bpy.data.worlds.new('CatalogueWorld')
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.18, 0.18, 0.20, 1.0)
        bg.inputs['Strength'].default_value = 1.0
    scene.world = world


def ensure_camera(location, look_at):
    cam = bpy.data.objects.get('CatalogueCamera')
    if cam is None:
        cam_data = bpy.data.cameras.new('CatalogueCameraData')
        cam = bpy.data.objects.new('CatalogueCamera', cam_data)
        bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    # Aim at look_at.
    dx, dy, dz = look_at[0] - location[0], look_at[1] - location[1], look_at[2] - location[2]
    # Convert direction vector → Euler. Camera default points -Z, +Y up.
    import mathutils
    direction = mathutils.Vector((dx, dy, dz))
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = cam
    return cam


def ensure_lights():
    """Three-point lighting: key, fill, rim.

    Energy chosen high enough that mid-tone materials (e.g. orange #FF8700)
    light up close to their authored hue under Lambertian shading. Without
    this, orange darkens perceptually toward yellow on a curved surface.
    """
    specs = [
        ('CatalogueKey',  'AREA', (-6.0, -8.0, 18.0), 2400.0),
        ('CatalogueFill', 'AREA', ( 8.0, -6.0, 12.0), 1200.0),
        ('CatalogueRim',  'AREA', ( 0.0,  8.0, 18.0),  900.0),
    ]
    for name, ltype, loc, energy in specs:
        obj = bpy.data.objects.get(name)
        if obj is None:
            data = bpy.data.lights.new(name + '_data', ltype)
            obj = bpy.data.objects.new(name, data)
            bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        obj.data.energy = energy
        if ltype == 'AREA':
            obj.data.size = 5.0
        # Aim at origin.
        import mathutils
        v = mathutils.Vector((-loc[0], -loc[1], -loc[2]))
        obj.rotation_euler = v.to_track_quat('-Z', 'Y').to_euler()


_PALETTE_MATS = {}  # name → bpy.types.Material; recreated per call

def _make_emission_material(name, rgb):
    """Create a flat shaded Principled BSDF material with the requested colour.

    Emission is set non-zero so the colour reads cleanly even in shadowed
    side-face regions — matches the in-game LIGHTING_PRELIT path which skips
    dynamic lighting.
    """
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        emission = bsdf.inputs.get('Emission Color') or bsdf.inputs.get('Emission')
        if emission is not None:
            emission.default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        strength = bsdf.inputs.get('Emission Strength')
        if strength is not None:
            strength.default_value = 0.6
    return mat


def _ensure_cube_has_slots(obj, mat_top, mat_lit, mat_shadow):
    """Ensure obj has 3 material slots (top/lit/shadow) and per-face material_index
    is assigned by face-normal direction.

    Normal classification (after 45° Z rotation baked into object_rotation):
      face.normal.z > +0.5 → TOP    (slot 0)
      face.normal.z < -0.5 → SHADOW (slot 2, hidden bottom)
      face.normal.x < 0    → LIT    (slot 1) — back-left/back-right after rot
      face.normal.x >= 0   → SHADOW (slot 2) — front-left/front-right after rot
    """
    while len(obj.material_slots) < 3:
        obj.data.materials.append(None)
    obj.material_slots[0].material = mat_top
    obj.material_slots[1].material = mat_lit
    obj.material_slots[2].material = mat_shadow
    # Assign per-face material_index using WORLD-space normal (object rotation included).
    rot = obj.rotation_euler.to_matrix()
    for poly in obj.data.polygons:
        wn = rot @ poly.normal
        if wn.z > 0.5:
            poly.material_index = 0
        elif wn.z < -0.5:
            poly.material_index = 2
        elif wn.x < 0:
            poly.material_index = 1
        else:
            poly.material_index = 2


def set_cube_palette(round_idx):
    """Apply ROUND_TOP_COLORS[round_idx] + level/round side colours to every cube.

    Each cube gets 3 fresh materials assigned to per-face slots based on world-space
    face normal. Static render uses state-2 (final/cleared) top colour — what the
    cube looks like after Q*bert has fully cleared it that round.
    """
    top0, top1, top2 = gc.ROUND_TOP_COLORS[round_idx]
    level = round_idx // 4
    if round_idx in gc.ROUND_SIDE_OVERRIDES:
        side_lit, side_shadow = gc.ROUND_SIDE_OVERRIDES[round_idx]
    else:
        side_lit, side_shadow = gc.LEVEL_SIDE_COLORS[level]

    rgb_top    = hex_to_rgb_linear(top2)
    rgb_lit    = hex_to_rgb_linear(side_lit)
    rgb_shadow = hex_to_rgb_linear(side_shadow)

    mat_top    = _make_emission_material(f'cube_top_r{round_idx:02d}',    rgb_top)
    mat_lit    = _make_emission_material(f'cube_lit_r{round_idx:02d}',    rgb_lit)
    mat_shadow = _make_emission_material(f'cube_shadow_r{round_idx:02d}', rgb_shadow)

    for name in CUBE_NAMES:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        _ensure_cube_has_slots(obj, mat_top, mat_lit, mat_shadow)


def render_to(path, resolution):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f'[render] wrote {path}')


def hide_all_except(visible_names):
    """Hide every mesh object except those named. Cameras and lights stay."""
    keep = set(visible_names)
    for obj in bpy.data.objects:
        if obj.type in ('CAMERA', 'LIGHT'):
            continue
        obj.hide_render = (obj.name not in keep)


def restore_visibility():
    for obj in bpy.data.objects:
        obj.hide_render = False


def render_pyramid_full():
    """Big L1R1 pyramid render (1280×720)."""
    hide_all_except(set(CUBE_NAMES))
    set_cube_palette(0)
    # Frame the pyramid: it spans X∈[-8.5, 8.5], Y∈[0, 8.5], Z∈[1, 13].
    ensure_camera(location=(0.0, -18.0, 18.0), look_at=(0.0, 4.0, 7.0))
    ensure_lights()
    render_to(os.path.join(OUT_DIR, 'pyramid_L1R1.png'), (1280, 720))


def render_pyramid_minis():
    """16 small pyramids, one per round (320×240)."""
    hide_all_except(set(CUBE_NAMES))
    ensure_camera(location=(0.0, -18.0, 18.0), look_at=(0.0, 4.0, 7.0))
    ensure_lights()
    for r in range(16):
        set_cube_palette(r)
        render_to(os.path.join(OUT_DIR, f'pyramid_R{r:02d}.png'), (320, 240))


def render_actors():
    """One render per actor on a neutral background, 512×512.

    Q*bert and the eggs have their snout/nose pointing +X (engine "forward");
    the camera is in -Y/+X quadrant, so without rotation the snout foreshortens.
    Apply a Z-rotation so the snout reads in 3/4 profile, matching the iconic
    arcade-cabinet pose.
    """
    SNOUT_FACING_ACTORS = {
        'Player', 'coily_egg', 'coily_egg_2', 'coily_snake',
        'redball_0', 'greenball', 'slick', 'sam', 'ugg', 'wrongway',
    }
    ensure_lights()
    for obj_name, out_base in ACTOR_RENDERS:
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            print(f'[render] WARNING: object {obj_name!r} not found, skipping')
            continue
        # Move actor to origin and rotate so the snout/face is in 3/4 profile.
        saved_loc = tuple(obj.location)
        saved_rot = tuple(obj.rotation_euler)
        obj.location = (0.0, 0.0, 0.0)
        if obj_name in SNOUT_FACING_ACTORS:
            obj.rotation_euler = (0.0, 0.0, math.radians(20))
        obj.hide_render = False
        hide_all_except({obj_name})
        # Frame close: actors are ~1 unit, use a tight camera.
        ensure_camera(location=(2.8, -3.6, 2.4), look_at=(0.0, 0.0, 0.0))
        render_to(os.path.join(OUT_DIR, f'{out_base}.png'), (512, 512))
        # Restore location + rotation.
        obj.location = saved_loc
        obj.rotation_euler = saved_rot


def render_player_turntable():
    """Six 384×384 renders of the Player actor at Z-rotations 0,60,...,300°.

    Output: actor_player_t000.png … actor_player_t300.png. Useful for design
    review — see the whole silhouette from every side without leaving Blender.
    """
    obj = bpy.data.objects.get('Player')
    if obj is None:
        print('[render] WARNING: Player not found, skipping turntable')
        return
    ensure_lights()
    saved_loc = tuple(obj.location)
    saved_rot = tuple(obj.rotation_euler)
    obj.location = (0.0, 0.0, 0.0)
    hide_all_except({'Player'})
    ensure_camera(location=(2.8, -3.6, 2.4), look_at=(0.0, 0.0, 0.0))
    for deg in (0, 60, 120, 180, 240, 300):
        obj.rotation_euler = (0.0, 0.0, math.radians(deg))
        render_to(os.path.join(OUT_DIR, f'actor_player_t{deg:03d}.png'), (384, 384))
    obj.location = saved_loc
    obj.rotation_euler = saved_rot


def main():
    print(f'[render] OUT_DIR = {OUT_DIR}')
    clear_render_settings()
    render_pyramid_full()
    render_pyramid_minis()
    render_actors()
    render_player_turntable()
    restore_visibility()
    print('[render] done.')


if __name__ == '__main__':
    main()
