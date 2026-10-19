"""Run the screensaver's Player drivers in the engine's zForth interpreter."""
import re
import runpy
from pathlib import Path

import pytest

from test_urchin_motion import binaries, zf  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
BUTTONS = """
: JOYSTICK_BUTTON_UP 2048 ; : JOYSTICK_BUTTON_DOWN 4096 ;
: JOYSTICK_BUTTON_RIGHT 8192 ; : JOYSTICK_BUTTON_LEFT 16384 ;
: JOYSTICK_BUTTON_B 2 ; : JOYSTICK_BUTTON_C 4 ;
: INDEXOF_X_POS 3009 ; : INDEXOF_Y_POS 3010 ; : INDEXOF_Z_POS 3011 ;
: INDEXOF_DELTA_TIME 1907 ;
"""
MASK_TANKS = (
    ("aquarium_blue_shrimp", 3.8, 760, 761, 762),
    ("aquarium_betta", 3.3, 760, 761, 762),
    ("aquarium_jellyfish", 2.8, 760, 761, 762),
    ("aquarium_lionfish", 3.4, 760, 761, 762),
    ("aquarium_plants", 0.8, 760, 761, 762),
    ("aquarium_arowana", 8.0, 780, 781, 782),
)
VERTICAL_CASES = (
    ("aquarium_blue_shrimp", 3010, -1.0, 4, 0.0, 2),
    ("aquarium_betta", 3011, 1.0, 2048, 4.0, 4096),
    ("aquarium_jellyfish", 3011, 1.0, 2048, 4.0, 4096),
    ("aquarium_lionfish", 3011, 1.0, 2048, 4.0, 4096),
    ("aquarium_plants", 3010, -1.0, 2048, 0.0, 4096),
    ("aquarium_arowana", 3011, 4.0, 2048, 8.0, 4096),
)


@pytest.fixture(params=["float", "fixed"])
def host(request, binaries):
    zf.BIN = binaries[request.param]
    h = zf.Host()
    for line in BUTTONS.splitlines():
        if line.strip():
            assert h.eval(line) == "ok"
    h.write(1907, 0.1)
    yield h
    h.close()


@pytest.mark.parametrize("tank,target,output,leg,rest", MASK_TANKS)
def test_mask_player_holds_releases_and_reverses(host, tank, target, output, leg, rest):
    h = host
    assert h.load(ROOT / "wflevels" / tank / "screensaver_player.fth") == "ok"
    h.write(3009, 0)
    assert h.eval("1 2 ss-drive + 7999 write-mailbox") == "ok"
    assert h.read(7999) == 3
    for _ in range(2):
        assert h.eval("ss-drive") == "ok"
        assert int(h.read(output)) & 8192
        assert not int(h.read(output)) & 16384
    h.write(3009, target)
    assert h.eval("ss-drive") == "ok"
    assert h.read(output) == 0
    assert h.read(leg) == 1
    assert h.read(rest) > 0
    assert h.eval("ss-drive") == "ok"
    assert h.read(output) == 0
    for _ in range(40):
        assert h.eval("ss-drive") == "ok"
    assert h.read(rest) == 0
    assert h.eval("ss-drive") == "ok"
    assert int(h.read(output)) & 16384
    assert not int(h.read(output)) & 8192
    h.write(3009, -target)
    assert h.eval("ss-drive") == "ok"
    assert h.read(output) == 0
    assert h.read(leg) == 0


@pytest.mark.parametrize("tank,axis,low,low_bit,high,high_bit", VERTICAL_CASES)
def test_mask_player_corrects_height(host, tank, axis, low, low_bit, high, high_bit):
    h = host
    assert h.load(ROOT / "wflevels" / tank / "screensaver_player.fth") == "ok"
    output = 780 if tank == "aquarium_arowana" else 760
    h.write(3009, 0)
    for position, expected, opposite in ((low, low_bit, high_bit),
                                         (high, high_bit, low_bit)):
        h.write(axis, position)
        assert h.eval("ss-drive") == "ok"
        mask = int(h.read(output))
        assert mask & expected
        assert not mask & opposite


@pytest.mark.parametrize("tank", ["aquarium", "aquarium_tiger_barbs"])
def test_direct_player_holds_releases_and_reverses(host, tank):
    h = host
    # Only the native engine supplies these names; preserve the Player source.
    shims = """
: fish@ read-mailbox ; : fish! write-mailbox ;
: fish-dt INDEXOF_DELTA_TIME read-mailbox ;
: aq-dx 770 ; : aq-dy 771 ; : aq-dz 772 ; : aq-dart-req 773 ;
: INDEXOF_INPUT 774 ; : aq-pushed 775 ;
: aq-no-kicks ; : aq-dart ; : aq-trig ; : aq-limits ; : aq-keeps ;
: aq-targets ; : aq-steer-yaw ; : aq-steer-pitch ; : aq-bank-tick ;
: aq-caps ; : aq-gait ; : aq-swim-write ; : aq-remember ; : aq-publish ;
: aq-any? 0 ; : aq-darting? 0 ; : fish-idle-sense drop ;
"""
    for line in shims.splitlines():
        if line.strip():
            assert h.eval(line) == "ok"
    source = (ROOT / "wflevels" / "aquarium" /
              ("aquarium_screensaver.fth" if tank == "aquarium" else
               "tiger_barbs_screensaver.fth"))
    assert h.load(source) == "ok"
    target = 4.0 if tank == "aquarium" else 4.5
    h.write(3009, 0)
    assert h.eval("1 2 aq-screen-input + 7999 write-mailbox") == "ok"
    assert h.read(7999) == 3
    for _ in range(2):
        assert h.eval("aq-screen-input") == "ok"
        assert h.read(770) == 1
    h.write(3009, target)
    assert h.eval("aq-screen-input") == "ok"
    assert h.read(770) == 0
    assert h.read(760) == 1
    assert h.read(761) > 0
    for _ in range(40):
        if h.read(761) == 0:
            break
        assert h.eval("aq-screen-input") == "ok"
        assert h.read(770) == 0
    assert h.read(761) == 0
    assert h.eval("aq-screen-input") == "ok"
    assert h.read(770) == -1
    h.write(3009, -target)
    assert h.eval("aq-screen-input") == "ok"
    assert h.read(770) == 0
    assert h.read(760) == 0
    h.write(3009, 0)
    h.write(761, 0)
    for axis, output, low, high in ((3010, 771, -2, 2),
                                   (3011, 772, 0, 5)):
        h.write(axis, low)
        assert h.eval("aq-screen-input") == "ok"
        assert h.read(output) == 1
        h.write(axis, high)
        assert h.eval("aq-screen-input") == "ok"
        assert h.read(output) == -1


def test_generated_player_variants_match_sources_and_tank_order():
    builder = runpy.run_path(str(ROOT / "scripts/build-aquarium-screensaver-levels.py"))
    tanks = builder["TANKS"]
    ids = (ROOT / "android/screensaver/src/main/java/org/worldfoundry/screensaver/"
           "TankChoice.java").read_text()
    declared = re.search(r"static final String\[\] IDS = \{(.*?)\};", ids, re.S)
    assert declared is not None
    assert tuple(re.findall(r'"([a-z_]+)"', declared.group(1))) == tanks
    for tank in tanks:
        name = builder["SCRIPT_NAMES"].get(tank, "screensaver_player.fth")
        source = ROOT / "wflevels" / tank
        driver_dir = ROOT / "wflevels" / "aquarium" if tank == "aquarium_tiger_barbs" else source
        expected = builder["player_script"](
            (source / f"{tank}.lev").read_text(), tank,
            (driver_dir / name).read_text())
        generated = ROOT / "wflevels" / f"{tank}_screensaver" / f"{tank}_screensaver.lev"
        assert generated.read_text() == expected, tank
