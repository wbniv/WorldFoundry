"""Every shipped Aquarium variant offers the global frame-rate setting."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import level_manifest  # noqa: E402


def test_each_menu_and_dream_level_has_the_framerate_descriptor():
    for tank in level_manifest.read().ids:
        for suffix in ('-standalone.iff', '_screensaver-standalone.iff'):
            level = ROOT / 'wflevels' / (tank + suffix)
            assert b'Show framerate' in level.read_bytes(), str(level)
