"""The Discus tank's fish: one textured discus mesh per actor, a larger school.

The species module for AQUARIUM_TANK=discus, with the same API as tiger_barb.py
(LENGTH_M, geometry(), blender_mesh(), forth_constants(), school_length(), mailbox_ranges()),
so blender_create_aquarium.py builds the Discus tank on the Tiger Barbs tank's school
framework. Plan: docs/plans/2026-11-22-discus-tank.md.

The mesh is the discus asset's (wflevels/discus_asset/discus_geometry.py, shared with its
model.py), scaled from its 0.167 m source length to LENGTH_M. X points toward the nose,
Y through the body, Z up; the origin is the asset's. The tank shares one indexed image
and twelve lookup tables; `wild-brown` (the photograph's own colours) is the default.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSET = HERE.parent / 'discus_asset'
sys.path.insert(0, str(ASSET))
import discus_geometry as DG                                        # noqa: E402
import discus_palettes as DP                                        # noqa: E402
from tiger_barb import forth_constants, mailbox_ranges              # noqa: E402,F401  same mailbox layout (≤ 29 residents)

TITLE = 'Discus'
ACTOR_STEM = 'discus'              # actors discus-player, discus-1 .. discus-9
MESH_NAME = 'discus'               # discus.iff
PLAYER_TICK = 'discus-player-tick'
# Smaller juvenile-sized fish, approximately 7.5 cm at WORLD_SCALE = 10.
LENGTH_M = 0.75
SCHOOL_N = 29                      # residents; thirty fish including the player
TANK_HEIGHT_IN = 29.0
WATER_HEIGHT_IN = 27.0
COLOURWAY = 'wild-brown'
TEXTURE_SIZE = 512                 # the asset's 1024² map resampled; 512² pages (textile.flags)
# Discus cruise slowly: the tank's speeds are the clownfish's 3.4 body lengths a second
# scaled by length (as the barbs'), times this, so 2.0 BL/s.
SPEED_SCALE = 0.45
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

# Resident lengths are roughly 6.2–8.2 cm at WORLD_SCALE = 10.
SCHOOL_LENGTHS_M = (0.62, 0.65, 0.68, 0.70, 0.73, 0.75, 0.78, 0.80, 0.82)


def school_length(k):
    # Multiplication by 4 permutes 0..8, so neighbouring residents differ in size.
    return SCHOOL_LENGTHS_M[((k - 1) * 4) % len(SCHOOL_LENGTHS_M)]


def geometry(quad=False, refined=False):
    """Metre-space vertices and polygons at LENGTH_M; fins stay in the same mesh."""
    assert not quad, 'the discus has no card variant'
    return [(x * SCALE, y * SCALE, z * SCALE) for x, y, z in _SOURCE_VERTS], list(_FACES)


def texture_path(out_dir):
    return Path(out_dir) / 'discus-index-rgb555.png'


def prepare_texture(out_dir):
    """Prepare one encoded index image and the separate color lookup tables."""
    out = texture_path(out_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    DP.write_palette_assets(out.parent)
    return out


def blender_mesh(bpy, quad, texture, refined=False):
    verts, faces = geometry(quad)
    me = bpy.data.meshes.new(MESH_NAME)
    me.from_pydata(verts, [], faces); me.update()
    mat = bpy.data.materials.new('discus-textured')
    mat.use_nodes = True
    mat['wf_prelit'] = True          # the asset's flags: prelit photograph, single-face fins drawn
    mat['wf_double_sided'] = True    # from both sides
    mat['wf_indexed_palette'] = True
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
