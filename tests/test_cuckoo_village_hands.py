"""The village clock's hands pivot at the dial centre (Will, 2026-11-21: "hands on village clock not correct").

The prototype's hand meshes are bars offset sideways from their object origin, so a rotation swings each hand
around the wrong point. wflevels/cuckoo_village/blender_create_cuckoo_village.py recentres them and asserts it;
wflevels/cuckoo_village/check_dial.py renders the dial to look at. Blender is not in the test image, so this
checks that the fix and its assertion are in the build and that the timeline's angles read correctly.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels/cuckoo_village"))
import timeline as tl  # noqa: E402

BUILD = (ROOT / "wflevels/cuckoo_village/blender_create_cuckoo_village.py").read_text()


def test_the_build_recentres_both_hands_on_their_pivot_and_asserts_it():
    assert "for hand_name in ('hour_hand', 'minute_hand'):" in BUILD
    assert "v.co.x -= centre" in BUILD
    assert "is not centred on its pivot" in BUILD
    assert BUILD.index("v.co.x -= centre") < BUILD.index("poses = tl.all_poses(REFERENCE)")


def test_three_oclock_has_the_minute_hand_up_and_the_hour_hand_right():
    poses = tl.all_poses(3 * 3600.0)
    assert abs(poses["minute_hand"][4]) < 1e-9                     # 0 turns: straight up
    assert abs(poses["hour_hand"][4] - 0.25) < 1e-9               # a quarter turn clockwise: straight right


def test_half_past_six_has_the_minute_hand_down_and_the_hour_hand_just_past_down():
    poses = tl.all_poses(6 * 3600.0 + 30 * 60.0)
    assert abs(poses["minute_hand"][4] - 0.5) < 1e-9
    assert abs(poses["hour_hand"][4] - (6.5 / 12)) < 1e-9
