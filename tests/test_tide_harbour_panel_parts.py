"""The river panel's geometry (wflevels/tide_harbour/panel_parts.py)."""
import json
import math
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


def test_every_flat_face_faces_the_camera_and_lies_in_the_panel_plane():
    for name, m in pp.panel_meshes().items():
        if name.startswith("panel_drum_"):
            continue                                              # a drum is a ring: its faces look outward, the next test
        for f in m.faces:
            assert face_normal([m.vertices[i] for i in f])[1] < 0, f"{name}: a face looks away from the camera"
        assert all(abs(v[1]) < 1e-9 for v in m.vertices), f"{name}: not flat"


def test_every_face_of_a_drum_looks_outward_from_its_axis():
    for name, m in pp.panel_meshes().items():
        if not name.startswith("panel_drum_"):
            continue
        for f in m.faces:
            pts = [m.vertices[i] for i in f]
            n = face_normal(pts)
            centre = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            assert n[1] * centre[1] + n[2] * centre[2] > 0, f"{name}: a tick faces the axis"
            assert abs(n[0]) < 1e-9


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


def test_the_band_is_solid_wood_with_a_dark_plate_behind_each_digit():
    back = pp.band_back_mesh()
    assert abs(sum(area(f, back) for f in back.faces) - pn.W * pn.BAND_H) < 1e-9
    mask = pp.band_mask_mesh()
    plates = [f for f, c in zip(mask.faces, mask.colors) if c == "p_ink" and abs(area(f, mask) - pn.WIN_W * pn.WIN_H) < 1e-9]
    assert len(plates) == len(pp.windows()) == 10
    assert mask.material_keys()[0] == "p_text"                    # the marks come first: the recoloured material is slot 0


def _turned(point, value):
    """A point of the drum's mesh once the drum is turned to show `value`: about the x axis by value slots, as panel_poses
    turns it (the engine's pitch: a larger a carries y towards +z)."""
    a = math.tau * value * pn.SLOT_REV
    x, y, z = point
    return (x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


def test_a_turned_drum_shows_its_value_at_the_front_and_hides_every_other_digit_behind_the_plate():
    """Digit slot k's glyph spans GLYPH_H high at ring slot k. Turn the drum to show v: slot v's glyph is flat at the front
    (depth 0 behind the front plane) facing the camera, and every point of every other slot is deeper than the paper layer,
    so the band's plate (and below the band the paper) lies in front of it."""
    margin = pn.LAYER_OFFSET["paper"]
    for v in range(10):
        for k in range(10):
            corners = [_turned(pp.on_ring(x, z, k), v) for x in (-pn.WIN_W / 2, pn.WIN_W / 2) for z in (-pn.GLYPH_H / 2, pn.GLYPH_H / 2)]
            depth = [c[1] + pn.R_DRUM for c in corners]                 # behind the front plane
            if k == v:
                assert all(abs(d) < 1e-9 for d in depth), (v, depth)
                n = face_normal([_turned(pp.on_ring(x, z, k), v) for x, z in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
                assert n[1] < 0 and abs(n[2]) < 1e-9
            else:
                assert min(depth) > margin + 0.004, (v, k, min(depth))


def test_the_layers_stack_so_the_front_digit_is_nearest_and_the_paper_farthest():
    order = sorted(pn.LAYER_OFFSET, key=pn.LAYER_OFFSET.get)
    assert order == ["digit", "arrow", "mask", "plate", "pointer", "fill", "column", "map", "paper"], order
    assert pn.LAYER_OFFSET["mask"] < pn.LAYER_OFFSET["plate"] < pn.LAYER_OFFSET["map"]    # the plate hides the map under the band, the mask marks the plate


def test_the_two_copies_of_the_river_are_the_same():
    a = json.loads(pp.CENTRELINE.read_text())
    b = json.loads((ROOT / "docs" / "plans" / "2026-11-21-tide-harbour-clock" / "chao-phraya-centreline.json").read_text())
    assert a == b


def test_the_actor_budget():
    actors = len(pp.panel_meshes())
    assert actors == 19 and set(pp.DRUM_NAMES) <= set(pp.panel_meshes()), actors    # 9 meshes and 10 drums; the level has headroom to 150
