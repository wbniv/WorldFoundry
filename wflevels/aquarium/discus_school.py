"""The Discus tank's fish: one textured discus mesh per actor, a loose group of ten.

The species module for AQUARIUM_TANK=discus, with the same API as tiger_barb.py
(LENGTH_M, geometry(), blender_mesh(), forth_constants(), school_length(), mailbox_ranges()),
so blender_create_aquarium.py builds the Discus tank on the Tiger Barbs tank's school
framework. Plan: docs/plans/2026-11-22-discus-tank.md.

The mesh is the discus asset's (wflevels/discus_asset/discus_geometry.py, shared with its
model.py), scaled from its 0.167 m source length to LENGTH_M. X points toward the nose,
Y through the body, Z up; the origin is the asset's. One colourway ships in the tank: the
asset's `wild-brown` (the photograph's own colours), resampled to TEXTURE_SIZE.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSET = HERE.parent / 'discus_asset'
sys.path.insert(0, str(ASSET))
import discus_geometry as DG                                        # noqa: E402
from tiger_barb import forth_constants, mailbox_ranges              # noqa: E402,F401  same mailbox layout (≤ 29 residents)

TITLE = 'Discus'
ACTOR_STEM = 'discus'              # actors discus-player, discus-1 .. discus-9
MESH_NAME = 'discus'               # discus.iff
PLAYER_TICK = 'discus-player-tick'
# 15 cm total length (nose to tail tip) at WORLD_SCALE = 10: an adult Symphysodon reaches
# 15-20 cm; the tank's 13 in (33 cm) front-to-back depth suits the low end.
LENGTH_M = 1.5
SCHOOL_N = 9                       # residents; with the player, a group of ten
COLOURWAY = 'wild-brown'
TEXTURE_SIZE = 512                 # the asset's 1024² map resampled; 512² pages (textile.flags)
# Discus cruise slowly: the tank's speeds are the clownfish's 3.4 body lengths a second
# scaled by length (as the barbs'), times this, so 2.0 BL/s.
SPEED_SCALE = 0.6
# swim.fth's body wave, in fish-deform's length-relative terms: its swim-deform call passes
# amplitude 0.085 m over the x10 review mesh's span -1.07..0.6 (1.67 m), bend 0 and fin
# amplitude 0, which is exactly fish-deform's wave (swim_deform.h: body.deform + 0 + 0) at
# 0.085 / 1.67 = 0.051 of the length; its phase advanced 0.8 cycles a second.
DEFORM_AMP = 0.051
BEAT_HZ = 0.8

_SOURCE_VERTS, _FACES = DG.mesh_data()
SOURCE_LENGTH_M = max(v[0] for v in _SOURCE_VERTS) - min(v[0] for v in _SOURCE_VERTS)   # 0.167
SCALE = LENGTH_M / SOURCE_LENGTH_M
BODY_VERTEX_COUNT = len(_SOURCE_VERTS)

# Residents 11-16 cm: sub-adults to adults, mostly near the player's size.
SCHOOL_LENGTHS_M = (1.10, 1.20, 1.30, 1.35, 1.40, 1.45, 1.50, 1.55, 1.60)


def school_length(k):
    # Multiplication by 4 permutes 0..8, so neighbouring residents differ in size.
    return SCHOOL_LENGTHS_M[((k - 1) * 4) % len(SCHOOL_LENGTHS_M)]


def geometry(quad=False, refined=False):
    """Metre-space vertices and polygons at LENGTH_M; fins stay in the same mesh."""
    assert not quad, 'the discus has no card variant'
    return [(x * SCALE, y * SCALE, z * SCALE) for x, y, z in _SOURCE_VERTS], list(_FACES)


def texture_path(out_dir):
    return Path(out_dir) / 'discus.tga'


def prepare_texture(out_dir):
    """Resample the shipped colourway to TEXTURE_SIZE² as the TGA textile reads; return its path.
    Pipeline encoding only (as the barb atlas's resize): the art is the asset's."""
    from PIL import Image
    out = texture_path(out_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(ASSET / f'{COLOURWAY}.png').convert('RGB')
    image.resize((TEXTURE_SIZE, TEXTURE_SIZE), Image.Resampling.LANCZOS).save(out)
    return out


def blender_mesh(bpy, quad, texture, refined=False):
    verts, faces = geometry(quad)
    me = bpy.data.meshes.new(MESH_NAME)
    me.from_pydata(verts, [], faces); me.update()
    mat = bpy.data.materials.new('discus-textured')
    mat.use_nodes = True
    mat['wf_prelit'] = True          # the asset's flags: prelit photograph, single-face fins drawn
    mat['wf_double_sided'] = True    # from both sides
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(Path(texture).resolve()), check_existing=True)
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    me.materials.append(mat)
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for loop in poly.loop_indices:
            x, _, z = _SOURCE_VERTS[me.loops[loop].vertex_index]
            uv.data[loop].uv = DG.uv(x, z)   # top-origin V, as the asset exports it
    return me
