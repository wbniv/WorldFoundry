"""The river panel's geometry (wflevels/tide_harbour/panel_parts.py)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "wflevels" / "clock_common"))
import level_modules  # noqa: E402
from clock_mesh import face_normal  # noqa: E402

pn, pp = level_modules.load("tide_harbour", "panel", "panel_parts")


def area(face, mesh):
    pts = [mesh.vertices[i] for i in face]
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][2] - pts[(i + 1) % len(pts)][0] * pts[i][2] for i in range(len(pts)))) / 2


def test_every_face_faces_the_camera_and_lies_in_the_panel_plane():
    for name, m in pp.panel_meshes().items():
        for f in m.faces:
            assert face_normal([m.vertices[i] for i in f])[1] < 0, f"{name}: a face looks away from the camera"
        assert all(abs(v[1]) < 1e-9 for v in m.vertices), f"{name}: not flat"


def test_a_recoloured_material_is_in_the_first_three_slots():
    for name, m in pp.panel_meshes().items():
        for slot, key in enumerate(m.material_keys()):
            assert key in pp.PANEL_MATERIALS, (name, key)
            if pp.PANEL_MATERIALS[key][0] != "fixed":
                assert slot < 3, f"{name}: {key} is slot {slot}"


def test_the_panel_parts_fit_in_the_panel_except_the_map_which_slides_under_the_band():
    for name, m in pp.panel_meshes().items():
        if name == "panel_map":
            continue
        (x0, _y0, z0), (x1, _y1, z1) = m.bounds()
        if name == "panel_col_fill" or name.startswith("panel_drum_"):
            continue                                              # the fill is built from its foot; a drum slides behind the mask
        assert x0 >= -pn.W / 2 - 1e-6 and x1 <= pn.W / 2 + 1e-6, name
        assert z0 >= -pn.H / 2 - 1e-6 and z1 <= pn.H / 2 + 1e-6, name


def test_the_map_fits_the_width_between_the_margin_and_the_column():
    (x0, _y, _z0), (x1, _y1, _z1) = pp.map_mesh().bounds()
    left, right = -pn.W / 2 + 0.03, pn.COL_X - 0.09
    assert x0 >= left and x1 <= right, (x0, x1, left, right)


def test_the_river_fills_the_window_over_the_whole_pan():
    """The window is the panel below the band. At the pan's two ends the river must still run from the bottom of the
    window to its top (it may leave through the top only where the data ends), and the mouth must be in view at the
    southern end so the gulf shows."""
    pts = pp.river_points()
    north, south = max(z for _x, z in pts), min(z for _x, z in pts)
    top, bottom = pn.H / 2 - pn.BAND_H, -pn.H / 2
    for sod in (0.0, pn.PAN_S, 2 * pn.PAN_S * 0.5, 450.0, 1350.0):
        v = pn.map_v(sod)
        assert v + north >= top - 1e-6, (sod, "the river's north end is below the top of the window", v + north, top)
    assert pn.map_v(0.0) + south >= bottom + 0.05, "at the southern end of the pan the mouth must be in view"
    assert pn.map_v(pn.PAN_S) + south < bottom, "at the northern end the mouth has gone, as the pan intends"


def test_the_mask_leaves_a_window_for_every_digit_and_nothing_else_open():
    m = pp.band_mask_mesh()
    wood = sum(area(f, m) for f, c in zip(m.faces, m.colors) if c == "p_wood")
    rows = 2 * pn.W * pn.ROW_H
    holes = len(pp.windows()) * pn.WIN_W * pn.WIN_H
    # the icons, colons and dots lie on the wood too, so they only add: the wood is the rows minus the windows
    assert abs(wood - (rows - holes)) < 1e-6, (wood, rows - holes)


def test_a_window_is_taller_than_a_digit_and_a_drum_hides_its_neighbours():
    assert pn.GLYPH_H < pn.WIN_H
    assert pn.PITCH - pn.GLYPH_H / 2 > pn.WIN_H / 2, "the digit above or below would show through the window"


def test_the_two_copies_of_the_river_are_the_same():
    a = json.loads(pp.CENTRELINE.read_text())
    b = json.loads((ROOT / "docs" / "plans" / "2026-11-21-tide-harbour-clock" / "chao-phraya-centreline.json").read_text())
    assert a == b


def test_the_actor_budget():
    actors = len(pp.panel_meshes())
    assert actors == 19 and set(pp.DRUM_NAMES) <= set(pp.panel_meshes()), actors    # 9 meshes and 10 drums; the level has headroom to 150
