"""Window-box flower geometry (wflevels/cuckoo_village_assets/flowers.py), without Blender.

Plan docs/plans/2026-11-22-cuckoo-village-flowers.md: petunia boxes (two in three) and geranium boxes (one in three), each
with edelweiss, in flat-coloured materials, inside a triangle budget, baked into one actor for all 26 boxes.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village_assets"))
import flowers as fl  # noqa: E402

BOXES = 26                       # 13 cottages with two front window boxes each
FULL_PER_BOX, LEAN_PER_BOX = 700, 350
FULL_TOTAL = 18_200              # 26 x 700: the plan's budget


def all_boxes(quality):
    return [fl.box_flowers(i, quality) for i in range(BOXES)]


def test_the_triangle_budget_holds_for_every_box_and_for_the_whole_village():
    for quality, per_box in (("full", FULL_PER_BOX), ("lean", LEAN_PER_BOX)):
        counts = [fl.triangle_count(b) for b in all_boxes(quality)]
        assert max(counts) <= per_box, (quality, max(counts))
    assert fl.triangle_count(fl.merge(all_boxes("full"))) <= FULL_TOTAL
    assert fl.triangle_count(fl.merge(all_boxes("lean"))) < fl.triangle_count(fl.merge(all_boxes("full")))


def test_materials_are_flat_colours_and_there_are_at_most_ten():
    assert len(fl.MATERIALS) <= 10
    for name, rgb in fl.MATERIALS.items():
        assert len(rgb) == 3 and all(0.0 <= c <= 1.0 for c in rgb), name
    assert fl.DOUBLE_SIDED <= set(fl.MATERIALS) and "soil" not in fl.DOUBLE_SIDED and "stem_green" not in fl.DOUBLE_SIDED


def test_every_face_is_a_real_triangle_with_valid_indices():
    for parts in all_boxes("full"):
        for name, (verts, faces) in parts.items():
            for face in faces:
                assert len(face) == 3 and len(set(face)) == 3 and 0 <= min(face) and max(face) < len(verts), name
                a, b, c = (verts[i] for i in face)
                ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2]); ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
                cross = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
                assert math.sqrt(sum(x * x for x in cross)) > 1e-9, (name, face)


def test_the_flowers_stay_on_the_box_and_never_reach_into_the_wall():
    """Local frame: x along the box (0.69 wide), y out of the wall (front is -y, the wall is at +0.11), z up from the box top."""
    for quality in fl.QUALITY:
        for parts in all_boxes(quality):
            for name, (verts, _) in parts.items():
                for x, y, z in verts:
                    assert abs(x) <= fl.BOX_WIDTH / 2 + 0.01, x
                    assert -0.24 <= y <= (0.10 if name == "soil" else 0.0), (name, y)   # plants stay forward of the glazing bars
                    assert -0.20 <= z <= 0.22, z          # a vine hangs down the front, blooms stand a hand above the rim


def test_one_box_in_three_is_a_geranium_box():
    kinds = [fl.box_kind(i) for i in range(BOXES)]
    assert kinds.count("geranium") == 9 and kinds.count("petunia") == 17
    assert all(fl.box_kind(i) == "geranium" for i in range(0, BOXES, 3))


def test_every_box_has_edelweiss_and_a_yellow_heart_and_its_own_flowers():
    for i, parts in enumerate(all_boxes("full")):
        assert parts["edelweiss_felt"][1] and parts["flower_centre"][1] and parts["leaf_silver"][1]
        if fl.box_kind(i) == "geranium":
            assert parts["bloom_red"][1], i                     # geraniums are mostly red
        else:
            assert len([n for n in ("bloom_magenta", "bloom_violet", "bloom_white") if parts[n][1]]) >= 2, i
            assert not parts["bloom_red"][1], i                 # no red on a petunia box


def test_a_geranium_box_has_florets_of_ten_triangles_and_stays_inside_the_petunia_budget():
    box = fl.box_flowers(0, "full")                              # box 0 is a geranium box
    assert fl.box_kind(0) == "geranium"
    q = fl.QUALITY["full"]
    florets = q["g_plants"] * q["g_florets"] + q["g_vines"] * q["vine_blooms"]          # 21: ten petal triangles each
    buds = q["g_plants"] * q["g_buds"]                                                 # 5: four triangles each
    petals = sum(len(box[n][1]) for n in ("bloom_red", "bloom_magenta", "bloom_white"))
    assert petals == 10 * florets + 4 * buds == 230
    assert fl.triangle_count(box) <= FULL_PER_BOX
    assert fl.triangle_count(fl.box_flowers(1, "full")) <= FULL_PER_BOX


def test_the_soil_sits_above_the_box_top_so_it_shows():
    verts, faces = fl.box_flowers(3)["soil"]
    assert faces and min(z for _, _, z in verts) > 0.0


def test_the_geometry_is_deterministic_and_boxes_differ():
    assert fl.box_flowers(5) == fl.box_flowers(5)
    assert fl.box_flowers(4)["bloom_violet"] != fl.box_flowers(5)["bloom_violet"]       # two petunia boxes


def test_placing_and_merging_keep_the_triangle_count_and_move_the_flowers():
    one = fl.box_flowers(1)
    world = fl.placed(one, (3.7, -1.12, 1.655), math.pi / 2, 1.0)
    assert fl.triangle_count(world) == fl.triangle_count(one)
    merged = fl.merge([world, fl.placed(one, (-3.7, 0.0, 1.655), 0.0, 1.0)])
    assert fl.triangle_count(merged) == 2 * fl.triangle_count(one)
    for verts, faces in merged.values():
        assert not faces or max(i for f in faces for i in f) < len(verts)
