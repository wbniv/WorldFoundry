"""Every WF Clocks level's Player is Anchored, so it cannot fall out of its room.

A clock is a screensaver: nobody plays it, and its Player only stands out of sight because the engine requires one.
Cuckoo Village and Minute Machine inherited a Physics Player from their base scenes; with nothing solid under it the
engine dropped it below the room floor within seconds, and the Debug build stopped on "is not in any room"
(found 2026-11-27; it had done so since the levels were made). The other clocks already anchored theirs.
"""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "wflevels/clocks-menu.manifest"


def clock_ids():
    ids = []
    for line in MANIFEST.read_text().splitlines():
        if line.startswith("level "):
            ids.append(line.split()[1].removesuffix("-standalone.iff"))
    return ids


def player_mobility(lev: str) -> str:
    start = lev.index("{ 'NAME' \"Player\" }")
    m = re.search(r"\"Mobility\" \} \{ 'STR' \"([^\"]+)\"", lev[start:])
    assert m, "the Player has no Mobility"
    return m.group(1)


@pytest.mark.parametrize("level_id", clock_ids())
def test_the_clock_player_is_anchored(level_id):
    lev = ROOT / "wflevels" / level_id / f"{level_id}.lev"
    if not lev.exists():
        pytest.skip(f"{lev.relative_to(ROOT)} is not tracked (built by its generator)")
    assert player_mobility(lev.read_text()) == "Anchored", f"{level_id}'s Player is not Anchored"
