"""The built Tide Harbour level (wflevels/tide_harbour/tide_harbour.lev) is what the model and the director say.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md, Verification 2. Pure Python over the committed .lev and
actor-map.json, so a stale or wrongly placed build fails here before the engine is run.

Regression guard (2026-11-21): the first build exported every moving actor at the origin, because the exporter
reads matrix_world and the build script set locations without a depsgraph update. The engine check found it as a
112 m error in the sun's y; test_every_actor_is_placed_at_its_reference_pose would have caught it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))
sys.path.insert(0, str(ROOT / "tests"))

import forth  # noqa: E402
import parts  # noqa: E402
import timeline as tl  # noqa: E402
from debug_bridge_client import lev_name_to_pos  # noqa: E402

LEV = ROOT / "wflevels" / "tide_harbour" / "tide_harbour.lev"
MAP = json.loads((ROOT / "wflevels" / "tide_harbour" / "actor-map.json").read_text())


def objects():
    """name -> the object's chunk text, in file order."""
    out = {}
    for chunk in LEV.read_text(errors="ignore").split("{ 'OBJ'")[1:]:
        m = re.search(r"'NAME' \"([^\"]+)\"", chunk)
        out[m.group(1)] = chunk
    return out


def test_the_actor_map_is_the_level_order_and_within_budget():
    names = list(objects())
    assert MAP["indices"] == {n: i + 1 for i, n in enumerate(names)}
    assert len(parts.all_meshes()) + 2 <= 150


def test_every_actor_is_placed_at_its_reference_pose():
    day, sod = MAP["reference"]
    poses = tl.all_poses(int(day), sod)
    pos = lev_name_to_pos(LEV)
    for name in parts.all_meshes():
        want = poses[name]
        got = pos[name]
        assert max(abs(a - b) for a, b in zip(got, want[:3])) < 1e-3, (name, got, want[:3])
    cam = poses["cs_wide"]
    assert max(abs(a - b) for a, b in zip(pos["cs_wide"], cam[:3])) < 1e-3


def test_the_director_in_the_level_is_the_generated_one():
    chunk = objects()["Director"]
    script = forth.director_script(MAP["indices"])
    # the .lev carries the script as a quoted string; compare its words
    m = re.search(r"'NAME' \"Script\" \} \{ 'STR' \"(.*?)\" \}", chunk, re.S)
    assert m, "the Director has no Script field"
    body = m.group(1).encode().decode("unicode_escape")
    assert body.split() == script.split()


def test_toggled_actors_have_their_visibility_cells():
    obj = objects()
    for name, group in [("gauge_board", "gauge"), ("gauge_pointer", "gauge"), ("numerals_thai", "numerals_thai"),
                        ("numerals_roman", "numerals_roman"), ("sun", "sun"), ("boat_0", "boats"), ("bird_0", "birds")]:
        m = re.search(r"'NAME' \"Visibility Mailbox\" \} \{ 'DATA' (\d+)l", obj[name])
        assert m and int(m.group(1)) == tl.VIS[group], (name, m and m.group(1))
