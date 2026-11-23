"""The Christmas candle geometry (wflevels/cuckoo_village/candles.py), without Blender.

Plan docs/plans/2026-11-21-cuckoo-village.md, "Christmas candles": tiny candles on the conifers, never more than a dozen
on one tree, in shared meshes, deterministic, and kept off the dial, the alcoves and the cuckoo door.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
import candles as cd  # noqa: E402
import timeline as tl  # noqa: E402

PINES = [(-13, 3, .9), (-10, 6.6, 1), (-5, 7.5, .8), (-1, 4.1, .7), (4, 6.7, 1), (9, 7, .9), (13, 3, 1), (-13, -2, .9),
         (-12, -6, .8), (-5, -6.3, .8), (12, -5, .9), (4, -7, .8)]       # wflevels/cuckoo_village_layout/generate.py


def feet(i, x, y, s):
    return cd.candle_bases(i, (x, y, 0.0), i * 31 * math.pi / 180, s)


def test_a_tree_never_carries_more_than_a_dozen_candles_and_there_are_twelve_trees():
    assert cd.PER_TREE == len(cd.TIERS) * cd.PER_TIER == 10 <= 12
    assert tl.TREES == len(PINES) == 12
    for i, (x, y, s) in enumerate(PINES):
        assert len(feet(i, x, y, s)) == cd.PER_TREE


def test_every_candle_stands_on_its_tree_inside_the_branch_tips():
    for i, (x, y, s) in enumerate(PINES):
        for fx, fy, fz in feet(i, x, y, s):
            frac = fz / (cd.PINE_HEIGHT * s)
            assert 0.0 < frac < 1.0
            assert math.hypot(fx - x, fy - y) <= cd.pine_radius(frac) * s + 1e-9, (i, frac)


def test_the_candles_stay_off_the_tower_and_out_of_the_view_of_its_front():
    """The tower (dial, alcoves, cuckoo door) is at the origin, about 2.6 wide, and its front faces -Y towards the camera.
    No candle may touch the tower or stand in the strip in front of it."""
    for i, (x, y, s) in enumerate(PINES):
        for fx, fy, _ in feet(i, x, y, s):
            assert math.hypot(fx, fy) > 2.5, (i, fx, fy)
            assert not (abs(fx) < 1.6 and fy < 0), (i, fx, fy)


def test_the_geometry_is_deterministic_and_the_angles_never_line_up():
    a = cd.tree_candles(3, (-1, 4.1, 0.5), 0.2, 0.7)
    b = cd.tree_candles(3, (-1, 4.1, 0.5), 0.2, 0.7)
    assert a == b
    angles = [round(math.atan2(fy - 4.1, fx + 1) % math.tau, 3) for fx, fy, _ in cd.candle_bases(3, (-1, 4.1, 0.5), 0.0, 0.7)]
    assert len(set(angles)) == len(angles)


def test_the_merged_meshes_have_valid_faces_and_the_flame_sits_on_the_stick():
    sticks, flames = cd.tree_candles(0, (-13, 3, 0.58), 0.0, 0.9)
    for parts in (sticks, flames):
        verts, faces = cd.merge(parts)
        assert faces and max(i for face in faces for i in face) < len(verts) and min(i for face in faces for i in face) >= 0
        assert all(len(set(face)) == len(face) >= 3 for face in faces)
    for (sv, _), (fv, _), foot in zip(sticks, flames, cd.candle_bases(0, (-13, 3, 0.58), 0.0, 0.9)):
        assert abs(max(z for _, _, z in sv) - (foot[2] + cd.STICK_HEIGHT)) < 1e-9
        assert abs(min(z for _, _, z in fv) - (foot[2] + cd.STICK_HEIGHT)) < 1e-9          # the flame's foot is the stick's top
        assert max(z for _, _, z in fv) > max(z for _, _, z in sv)


def test_the_candles_are_tiny_decorations_and_use_the_cream_and_glow_atlas_tiles():
    assert cd.STICK_HEIGHT < 0.2 and cd.STICK_RADIUS < 0.05 and cd.FLAME_HEIGHT < cd.STICK_HEIGHT
    assert (cd.STICK_TILE, cd.FLAME_TILE) == (15, 6)       # village_atlas.tga: pale cream, and the windows' warm glow


def test_each_trees_flames_have_their_own_cells_beside_the_sticks_cell():
    cells = list(tl.FLICKER_CELLS)
    assert len(set(cells)) == 48 and tl.CANDLE_CELL not in cells        # four meshes a tree: two groups, two shapes
    assert max(cells) < 600 and min(cells) > tl.CANDLE_CELL - 1        # below the director's scratch cells, above the bird (213)
