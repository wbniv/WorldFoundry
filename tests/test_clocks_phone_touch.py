"""Clocks phone chooser stays touchable without drawing the gamepad."""
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import level_manifest  # noqa: E402


def test_phone_chooser_gestures(tmp_path):
    binary = tmp_path / 'clock-menu-touch'
    subprocess.run([
        'g++', '-std=c++17', '-I' + str(ROOT / 'android/screensaver/src/main/cpp'),
        '-I' + str(ROOT / 'wfsource/source'),
        str(ROOT / 'tests/clock_menu_touch_test.cpp'), '-o', str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)


def test_settings_overlay_stays_enabled_for_clocks():
    host = (ROOT / 'android/screensaver/src/main/cpp/dream_host.cc').read_text()
    java = (ROOT / 'android/screensaver/src/main/java/org/worldfoundry/screensaver/TankPlayer.java').read_text()
    assert 'private static native void nativeTouchConfigure(boolean enabled, float density);' in java
    assert 'phoneTouch.store(enabled == JNI_TRUE);' in host
    assert 'layout->stick = false;' in host and 'layout->shown = 0;' in host
    assert 'WFAndroidSetHudEnabled(menu && touchBridge.enabled() ? 1 : 0);' in host
    assert 'propertyui::touchConfigure(menu && touchBridge.enabled(), touchBridge.density());' in host


def test_minute_machine_uses_existing_global_settings_holder():
    level = (ROOT / 'wflevels/minute_machine/minute_machine.lev').read_text()
    assert '"MinuteMachineSettings"' in level
    assert '"levelsettings"' in level.lower()


def test_every_clock_has_a_settings_holder():
    manifest = level_manifest.read(ROOT / 'wflevels/clocks-menu.manifest')
    for clock in manifest.ids:
        level = (ROOT / 'wflevels' / clock / (clock + '.lev')).read_text()
        holders = re.findall(r"\{ 'NAME' \"Class Name\" \}\s*\{ 'DATA' \"([^\"]*settings)\"", level, re.I)
        assert len(holders) == 1, (clock, holders)
