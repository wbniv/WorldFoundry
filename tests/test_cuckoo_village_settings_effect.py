"""What the settings do to the director's reference timeline and its generated Forth (wflevels/cuckoo_village).

docs/plans/2026-11-21-cuckoo-village.md, "Opening the settings, and what is built". Pure Python: the engine
comparison of the same behaviour is scripts/check-cuckoo-village.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
import forth                      # noqa: E402
import timeline as tl             # noqa: E402

NIGHT = 23 * 3600.0


def test_window_lights_off_keeps_every_window_dark_at_night():
    assert all(tl.window_states(NIGHT))
    assert not any(tl.window_states(NIGHT, {"Window lights": 0}))


def test_camera_still_is_the_wide_front_view_for_the_whole_lap():
    first = tl.camera(1.0, True)
    for t in (30.0, 100.0, 200.0):
        assert tl.camera(t, True) == first
    assert first[0][1] < 0, "the front of the village is -Y"


def test_the_default_settings_leave_the_journey_unchanged():
    assert tl.camera(100.0, False) != tl.camera(100.0, True)
    assert tl.all_poses(40000.0) == tl.all_poses(40000.0, dict(tl.SETTINGS_DEFAULTS))


def test_the_director_reads_every_field_with_property_at_and_the_given_indices():
    names = ["tower_figure_1", "tower_figure_2", "tower_figure_3", "tower_figure_4", "tower_bird",
             "hour_hand", "minute_hand", "cs_wide", "LookAt", "CuckooVillageSettings"]
    ix = {n: 50 + i for i, n in enumerate(names)}
    fields = {label: 200 + i for i, label in enumerate(tl.SETTINGS_DEFAULTS)}
    script = forth.director_script(ix, fields)
    for label, default in tl.SETTINGS_DEFAULTS.items():
        word = "cv-s-" + label.lower().replace(" ", "-")
        assert f": {word} {ix['CuckooVillageSettings']} {fields[label]} property@ if else drop {default} then ;" in script
    assert "cv-s-window-lights *" in script and "cv-s-camera-motion if" in script
