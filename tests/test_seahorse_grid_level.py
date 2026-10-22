"""Check the generated seahorse level's actor scripts and clip phases."""
import json
import runpy
from pathlib import Path
import re
import sys

import pytest

from test_urchin_motion import binaries, zf  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
generator = runpy.run_path(str(ROOT / "scripts/build-seahorse-grid-level.py"))


def test_grid_has_more_horizontal_room_and_widescreen_proportions():
    positions = [generator["grid_position"](n) for n in range(24)]
    width = max(x for x, _, _ in positions) - min(x for x, _, _ in positions)
    height = max(z for _, _, z in positions) - min(z for _, _, z in positions)
    assert width / 5 == pytest.approx(2.8)
    assert width / height == pytest.approx(16 / 9)
    assert (max(z for _, _, z in positions) + min(z for _, _, z in positions)) / 2 == \
        pytest.approx(generator["GRID_CENTER_Z"])


def test_seahorse_actor_is_visible_without_planted_tank_settings():
    source = (ROOT / "wflevels/aquarium_plants/aquarium_plants.lev").read_text()
    block = next(part for part in source.split("\t{ 'OBJ'")
                 if "{ 'NAME' \"seahorse-0-body\" }" in part)
    placed = generator["place"](block, "seahorse-23-body", 4.5, -.15, 4.15)
    assert "{ 'NAME' \"seahorse-23-body\" }" in placed
    assert "4.50000000(1.15.16) -0.15000000(1.15.16) 4.15000000(1.15.16)" in placed
    assert re.search(r'Visibility Mailbox" \} \{ \'DATA\' 1l \} \{ \'STR\' "1"', placed)


def test_abstract_level_keeps_one_seahorse_in_the_room_asset_table():
    # A level with no RM0 mesh creates a bogus room TOC entry and aborts at load.
    source = (ROOT / "wflevels/seahorse_grid/seahorse_grid.lev").read_text()
    blocks = source.split("\t{ 'OBJ'")
    names = [re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)
             for block in blocks[1:]]
    assert len(names) == 58
    assert {name for name in names if name.startswith("seahorse-")} == {
        f"seahorse-{n}-{part}" for n in range(24) for part in ("body", "fins")}
    room_body = next(block for block in blocks if "{ 'NAME' \"seahorse-0-body\" }" in block)
    assert re.search(r'Moves Between Rooms" \} \{ \'DATA\' 0l \} \{ \'STR\' "False"',
                     room_body)
    asset_map = (ROOT / "wflevels/seahorse_grid/seahorse_grid.iff.txt").read_text()
    assert "$3000001l { 'STR' \"seahorse_f_body.iff\" }" in asset_map


def test_every_body_owns_the_same_animation_script():
    level = (ROOT / "wflevels/seahorse_grid/seahorse_grid.lev").read_text()
    blocks = level.split("\t{ 'OBJ'")
    scripts = []
    for n in range(24):
        block = next(b for b in blocks if f'{{ \'NAME\' "seahorse-{n}-body" }}' in b)
        source = generator["SCRIPT_FIELD"].search(block)
        assert source is not None
        scripts.append(json.loads(source.group(2)))
    assert len(set(scripts)) == 1
    assert scripts[0].endswith("sg-tick\n")
    assert "INDEXOF_ACTOR_INDEX" in scripts[0]
    player = next(b for b in blocks if "{ 'NAME' \"Player\" }" in b)
    assert "sg-tick" not in player


def actor_host(binaries, mode, actor):
    """Run one body script in the same mailbox context as its game actor."""
    zf.BIN = binaries[mode]
    host = zf.Host()
    for line in (": INDEXOF_TIME 1906 ;", ": INDEXOF_ACTOR_INDEX 3005 ;",
                 ": dfrm-pose 2drop 0 ;",
                 ": fin-deform 2drop 2drop drop ;"):
        assert host.eval(line) == "ok"
    for line in generator["shared_animation_definitions"](11).splitlines():
        if line.strip():
            assert host.eval(line) == "ok"
    host.write(3005, 11 + 2 * actor)
    host.write(1906, .051)
    assert host.eval("sg-tick") == "ok"
    return host


@pytest.mark.parametrize("mode", ["float", "fixed"])
def test_all_24_seahorses_start_at_staggered_rest_phases(binaries, mode):
    phases = []
    for actor in range(24):
        host = actor_host(binaries, mode, actor)
        try:
            block = 100 + 40 * actor
            meta = 1200 + 4 * actor
            assert host.read(block + 25) == 6
            assert host.read(meta + 3) == 1
            phases.append(host.read(1906) - host.read(block + 26))
        finally:
            host.close()
    assert len({round(phase, 3) for phase in phases}) == 12
    assert phases[::2] == pytest.approx(phases[1::2])


@pytest.mark.parametrize("mode", ["float", "fixed"])
def test_pair_moves_through_hover_probe_and_greeting_with_rests(binaries, mode):
    hosts = [actor_host(binaries, mode, actor) for actor in (0, 1)]
    try:
        assert hosts[0].read(1201) == pytest.approx(hosts[1].read(1205))
        for now, expected_state, expected_clips, expected_cycle in (
                (8.1, 1, (8, 8), 0),
                (13.2, 0, (6, 6), 1),
                (20.8, 2, (4, 4), 1),
                (23.6, 0, (6, 6), 2),
                (31.2, 3, (1, 2), 2),
                (37.6, 0, (6, 6), 0)):
            for actor, host in enumerate(hosts):
                block = 100 + 40 * actor
                meta = 1200 + 4 * actor
                host.write(1906, now)
                assert host.eval("sg-tick") == "ok"
                assert host.read(meta) == expected_state
                assert host.read(meta + 2) == expected_cycle
                assert host.read(meta + 3) == 1
                assert host.read(block + 29) == pytest.approx(
                    1.5 if expected_state in (0, 3) else 1.3, abs=.001)
            assert tuple(host.read(100 + 40 * actor + 27)
                         for actor, host in enumerate(hosts)) == expected_clips
            assert hosts[0].read(1201) == pytest.approx(hosts[1].read(1205))
        assert tuple(host.read(100 + 40 * actor + 25)
                     for actor, host in enumerate(hosts)) == (1, 2)
    finally:
        for host in hosts:
            host.close()
