"""The screensaver host must hide the engine overlay (planted seed strip, settings panel, menu).

The engine draws that overlay only while levelmenu::Drawer() is set (gfx/gl/display.cc). Display installs
it once, so the Dream host clears it each frame from WFAndroidPumpEvents. This is a source guard: if the
engine stops gating the overlay on the drawer, or the host stops clearing it, the strip reappears on the TV.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "android/screensaver/src/main/cpp/dream_host.cc").read_text()
DISPLAY = (ROOT / "wfsource/source/gfx/gl/display.cc").read_text()


def test_engine_draws_overlay_only_through_the_drawer():
    line = next(l for l in DISPLAY.splitlines() if "planted::buildUI" in l)
    assert "levelmenu::Drawer()" in line.split("planted::buildUI")[0]


def test_host_clears_the_drawer_every_frame():
    body = re.search(r'WFAndroidPumpEvents\(\)\s*\{(.*?)\n\}', HOST, re.S)
    assert body, "WFAndroidPumpEvents must be defined by the host"
    assert "levelmenu::SetDrawer(nullptr)" in body.group(1)
    assert "#include <game/level_menu.h>" in HOST


def test_screensaver_bundles_use_the_non_menu_shell():
    builder = (ROOT / "scripts/build-aquarium-screensaver-levels.py").read_text()
    assert "shell.fth" in builder and "shell-menu.fth" not in builder
