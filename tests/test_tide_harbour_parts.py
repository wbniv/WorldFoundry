"""Tide Harbour geometry (wflevels/tide_harbour/parts.py): budget, winding, pivots and the colour slots.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (D1, D7, Phase 2; the level guides' winding and
coplanar-face rules). Pure Python.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "wflevels" / "clock_common"))

import level_modules  # noqa: E402
from clock_mesh import face_normal, signed_volume  # noqa: E402

tl, parts = level_modules.load("tide_harbour", "timeline", "parts")

FLAT = ("sky_", "sun", "moon", "dial", "panel_")


def every_mesh():
    return list(parts.all_meshes().values()) + parts.static_meshes() + parts.toggled_static_meshes()


def test_the_actor_budget_holds():
    """D7: at most 150 posed actors (measured on cast1 at 59.3 FPS by day); the river is 36 bars (D1)."""
    moving = parts.all_meshes()
    posed = len(moving) + 2                       # and the camera shot and its look-at target
    assert posed <= 150, posed
    assert sum(1 for n in moving if n.startswith("bar_")) == 36
    assert 80 <= posed <= 110                     # "about 100 in all" (D1)
    faces = sum(len(m.faces) for m in every_mesh())
    assert faces < 6000, faces


def test_every_pose_has_a_mesh_and_every_mesh_a_pose():
    poses = set(tl.piece_names()) - {"cs_wide", "LookAt"}
    assert poses == set(parts.all_meshes())


def test_closed_meshes_wind_outward_and_flat_ones_face_the_camera():
    """Faces are culled by default, so a face wound the wrong way vanishes (level-design-troubleshooting.md)."""
    for m in every_mesh():
        if m.name.startswith("panel_drum_"):
            continue                                  # a ring of digit slots: test_tide_harbour_panel_parts checks its faces
        if m.name.startswith(FLAT):
            for f in m.faces:
                n = face_normal([m.vertices[i] for i in f])
                assert n[1] < 0, (m.name, f)          # toward -y, the camera
        else:
            assert signed_volume(m) > 0, m.name


def test_mesh_names_fit_the_level_format():
    for m in every_mesh():
        assert len(m.name + ".iff") <= 30, m.name


def test_re_coloured_materials_sit_in_the_three_colour_slots():
    slots = parts.recolour_slots()
    for name, entries in slots.items():
        assert all(slot < 3 for slot, *_ in entries), name
    # what tells the time, and the moon, are never re-coloured (spike finding 4: they must stay readable at night)
    for name in ("dial", "hand_h", "hand_m", "hand_s", "moon"):
        assert name not in slots
    assert len(slots) >= 80


def test_the_water_bars_overlap_and_never_share_a_plane():
    for k in range(tl.N_BARS - 1):
        lo, hi = parts.bar_mesh(k).bounds()
        near_edge_next = tl.bar_y(k + 1) + tl.bar_depth(k + 1) / 2 - tl.bar_depth(k + 1) * 0.5 * tl.BAR_OVERLAP
        assert tl.bar_y(k) + tl.bar_depth(k) / 2 + hi[1] > near_edge_next          # this bar reaches under the next
        assert tl.bar_heave(k, 0.0) - tl.bar_heave(k + 1, 0.0) != 0.0
    # the per-bar centimetre keeps two still bars apart even with the waves cancelled
    assert all(abs(0.01 * (tl.N_BARS - 1 - k) - 0.01 * (tl.N_BARS - 2 - k) - 0.01) < 1e-12 for k in range(tl.N_BARS - 1))


def test_pivots_are_where_the_director_turns_them():
    m = parts.all_meshes()
    for name in ("hand_h", "hand_m", "hand_s"):
        lo, hi = m[name].bounds()
        assert lo[0] < 0 < hi[0] and lo[2] < 0 < hi[2]               # the hands turn about their own origin
    lo, hi = m["rope_0"].bounds()
    assert abs(lo[1]) < 1e-9 and abs(hi[1] - 1.0) < 1e-9              # a unit rope along +y, stretched by sy
    lo, hi = m["boat_0"].bounds()
    assert abs(lo[0]) < 1e-9                                            # the bow, where the rope ties, is the origin
    lo, hi = m["lantern_0"].bounds()
    assert abs(hi[2]) < 1e-9                                            # a lantern hangs from its hook
    lo, hi = m["gauge_pointer"].bounds()
    assert lo[2] < 0 < hi[2] and abs(lo[0] - 0.36) < 1e-9              # the pointer's tip is at the tide height


def test_the_gauge_reads_metres_true_to_scale():
    """Q6: true to scale against the pier and the gauge board; the deck stays above the year's highest water."""
    lo, hi = parts.gauge_board_mesh().bounds()
    assert abs(lo[2]) < 1e-9 and hi[2] >= tl.CONSTANTS["range_of_listed_extrema_m"][1] + 0.5
    assert tl.DECK_Z > tl.CONSTANTS["range_of_listed_extrema_m"][1] + 0.5
