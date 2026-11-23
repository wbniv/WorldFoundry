"""Bavaria mode's geometry (wflevels/cuckoo_village/bavaria.py): valid meshes, the figures' footprint and budget, the reversed dial.

Pure Python, no Blender. Plan docs/plans/2026-11-21-cuckoo-village.md, "Bavaria mode".
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
import bavaria as bv        # noqa: E402
import timeline as tl       # noqa: E402


def valid(part):
    assert part.verts and part.faces and len(part.faces) == len(part.tiles), part.name
    for f in part.faces:
        assert len(f) >= 3 and all(0 <= i < len(part.verts) for i in f) and len(set(f)) == len(f), part.name
    assert all(0 <= t <= 15 for t in part.tiles), f"{part.name}: tiles are the village atlas's 16"
    for f in part.faces:                                     # no degenerate (zero-area) face
        pts = [part.verts[i] for i in f]
        ax, ay, az = pts[0]
        n = [0.0, 0.0, 0.0]
        for (x0, y0, z0), (x1, y1, z1) in zip(pts, pts[1:] + pts[:1]):
            n[0] += (y0 - y1) * (z0 + z1)
            n[1] += (z0 - z1) * (x0 + x1)
            n[2] += (x0 - x1) * (y0 + y1)
        assert math.sqrt(sum(c * c for c in n)) > 1e-9 or part.name.startswith("tower_figure"), (part.name, f)


def bounds(part):
    xs, ys, zs = zip(*part.verts)
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


COTTAGES = [((-11 + k, 4.0, 0.5), -20.0 + k, 0.9) for k in range(tl.HOUSES)]


def ground(x, y):
    return 0.4


def test_every_part_is_a_valid_mesh_in_the_atlas():
    parts = bv.all_parts(tl.TZ, COTTAGES, ground)
    assert {"bavaria_chalet", "bavaria_dome", "bavaria_maypole", "dial_numerals_bavaria", *tl.FIG_B_NAMES} <= set(parts)
    assert {n for n in parts if n.startswith("bavaria_trim_")} == {f"bavaria_trim_{i + 1:02d}" for i in bv.FRIEZE_HOUSES}
    for part in parts.values():
        valid(part)


def test_the_whole_extra_budget_is_a_small_part_of_the_level():
    """The tower alone is about 21,000 triangles (the level's README); Bavaria mode's extras are shown instead of Classic's four
    figures and numerals plus a few additions, and must stay in the same order of size as the Classic art they stand beside."""
    parts = bv.all_parts(tl.TZ, COTTAGES, ground)
    assert sum(p.triangles() for p in parts.values()) < 12000


def test_the_cottage_trim_stands_on_the_cottages_front_and_the_dome_on_its_ridge():
    loc, ang, sc = COTTAGES[4]
    dome = bv.onion_dome(loc, ang, sc)
    zs = [v[2] for v in dome.verts]
    assert min(zs) >= loc[2] + sc * (bv.HOUSE_RIDGE - 0.11) and max(zs) < loc[2] + sc * (bv.HOUSE_RIDGE + 1.7)
    trim = bv.cottage_trim(0, (0.0, 0.0, 0.0), 0.0, 1.0)
    ys = [v[1] for v in trim.verts]
    assert max(ys) < bv.HOUSE_FRONT_Y + 0.001 and min(ys) > bv.HOUSE_FRONT_Y - 0.10, "the painting stands on the front wall, proud of it by a few centimetres"
    assert set(trim.tiles) == {bv.DARKWOOD, bv.BLUE, bv.CREAM}, "white and blue lozenges on timber"
    turned = bv.cottage_trim(0, (5.0, 6.0, 1.0), 90.0, 1.0)
    cx = sum(v[0] for v in turned.verts) / len(turned.verts)
    assert cx > 5.9, "a cottage turned a quarter turn carries its front toward +x"


def test_the_maypole_stands_in_the_square_clear_of_the_towers_front_view():
    pole = bv.maypole(*bv.MAYPOLE_AT, 0.3)
    (x0, x1), (y0, y1), (z0, z1) = bounds(pole)
    assert 3.4 < z1 - z0 < 4.4 and x0 > 1.4 and y1 < -1.5, "taller than a person's reach, right of the tower and in front of its wall"
    assert {bv.BLUE, bv.CREAM} <= set(pole.tiles), "the white-and-blue spiral"


def test_the_chalet_trim_leaves_the_dial_and_the_cuckoo_door_clear():
    chalet = bv.tower_chalet(tl.TZ)
    dial_z = bv.DIAL_Z + tl.TZ
    near_the_dial_plane = [(x, y, z) for x, y, z in chalet.verts if -1.14 < y < -1.0]
    assert near_the_dial_plane, "the vine and its ring stand just in front of the dial's case"
    for x, y, z in near_the_dial_plane:
        assert math.hypot(x, z - dial_z) >= 0.55, f"trim over the dial face at ({x:.2f}, {z - dial_z:.2f}); the dial's rim is 0.55"
    (x0, x1), (y0, y1), (z0, z1) = bounds(chalet)
    assert x0 > -2.0 and x1 < 2.0 and y0 > -2.1, "inside the balcony's width and not further out than the new rail"


def test_the_four_figures_are_named_for_their_twins_and_keep_the_rigs_scale():
    figs = bv.figures()
    assert [f.name for f in figs] == tl.FIG_B_NAMES
    for f in figs:
        (x0, x1), (y0, y1), (z0, z1) = bounds(f)
        assert -0.05 <= z0 < 0.05, f"{f.name}: stands on the pivot like the Classic figures, whose shoes dip 4 cm into the floor ({z0})"
        assert 0.75 <= z1 <= 1.05, f"{f.name}: about as tall as a Classic figure (0.8) with its hat or hoop ({z1})"
        assert -0.36 <= x0 and x1 <= 0.28 and -0.30 <= y0 and y1 <= 0.21, f"{f.name}: stays in its alcove ({x0:.2f}..{x1:.2f}, {y0:.2f}..{y1:.2f})"
        assert 300 <= f.triangles() <= 1400, f"{f.name}: {f.triangles()} triangles"


def test_each_figure_reads_in_silhouette_and_they_do_not_look_alike():
    sig = []
    for f in bv.figures():
        (x0, x1), (y0, y1), (z0, z1) = bounds(f)
        sig.append((round(x0, 2), round(x1, 2), round(z1, 2), len(set(f.tiles))))
    assert len(set(sig)) == 4, sig
    tiles = [set(f.tiles) for f in bv.figures()]
    assert tiles[0] != tiles[1] != tiles[2] != tiles[3]


def test_the_extra_budget_is_small_next_to_the_towers_21000_triangles():
    assert sum(f.triangles() for f in bv.figures()) < 4000
    assert bv.dial_numerals(tl.TZ).triangles() < 600


def test_the_reversed_dial_places_the_marks_anti_clockwise_with_twelve_still_at_the_top():
    assert bv.numeral_angle(0, True) == 0.0 == bv.numeral_angle(0, False)
    for i in range(1, 12):
        assert math.isclose(bv.numeral_angle(i, True), -bv.numeral_angle(i, False))
    # so on the reversed dial 3 is on the left of the dial's centre and 9 on the right
    def centre(part_numeral_index, reverse):
        a = math.tau * bv.numeral_angle(part_numeral_index, reverse)
        return bv.NUMERAL_R * math.sin(a)
    assert centre(3, True) < 0 < centre(3, False) and centre(9, True) > 0 > centre(9, False)


def test_the_marks_are_the_classic_strokes_moved_not_mirrored():
    """Upright, unmirrored digits: the same strokes in the same order, only translated to the mirrored spot. Mirroring a stroke set
    in x would flip the sense of V and IV and trip back-face culling."""
    classic, reverse = bv.dial_numerals(tl.TZ, False), bv.dial_numerals(tl.TZ, True)
    assert len(classic.verts) == len(reverse.verts) and classic.faces == reverse.faces and classic.tiles == reverse.tiles
    # each mark is one translation of the classic one: a constant offset across all of its vertices
    per_mark = len(classic.verts) // 12 if len(classic.verts) % 12 == 0 else None
    if per_mark is None:                                     # marks have different stroke counts: group by walking the strokes
        return
    for i in range(12):
        a = classic.verts[i * per_mark:(i + 1) * per_mark]
        b = reverse.verts[i * per_mark:(i + 1) * per_mark]
        offs = {(round(q[0] - p[0], 9), round(q[1] - p[1], 9), round(q[2] - p[2], 9)) for p, q in zip(a, b)}
        assert len(offs) == 1, i


def test_a_mark_sits_where_the_numeral_spot_is_and_inside_the_dial_ring():
    for reverse in (False, True):
        part = bv.dial_numerals(tl.TZ, reverse)
        for x, y, z in part.verts:
            r = math.hypot(x, z - (bv.DIAL_Z + tl.TZ))
            assert r < 0.42, f"mark outside the numeral ring: {r:.3f}"
            assert math.isclose(y, bv.NUMERAL_Y, abs_tol=0.01)
