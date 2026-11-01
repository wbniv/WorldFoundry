#!/usr/bin/env python3
"""Desktop frames of the new Field types controls, from the real engine/wf_game.

Opens the baseline's Field types form with the controller path a TV uses (hold OK, Down, OK)
through the debug bridge and screenshots each new control. Needs a display (DISPLAY, the
desktop or Xvfb) and a built engine/wf_game. Writes desktop-*.png beside this script.
    python3 docs/plans/2026-11-01-field-presentations/capture_desktop.py
"""
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from ui_font_screenshots import Session, BASELINE_VRAM, OK, DOWN, RIGHT, LEFT  # noqa: E402

UP = 1 << 11


def main():
    with tempfile.TemporaryDirectory() as cwd:
        s = Session(HERE, 7795, 'desktop-capture.log',
                    [*BASELINE_VRAM, '-L' + str(ROOT / 'wflevels/baseline-standalone.iff')], Path(cwd))
        try:
            s.hold(OK, 1.4)                  # the chooser
            s.tap(DOWN); s.tap(OK)           # Field types, Numbers, row 0
            for _ in range(3):
                s.tap(DOWN)                  # Trigger mailbox
            s.shot('desktop-numbers-mailbox')
            s.tap(LEFT); s.tap(DOWN); s.tap(RIGHT)  # rail, Choices, Mode
            s.tap(DOWN)                      # Powerup
            s.shot('desktop-choices')
            s.tap(OK); s.shot('desktop-list-numbered'); s.tap(LEFT)
            for _ in range(7):
                s.tap(DOWN)                  # Placement
            s.tap(OK); s.shot('desktop-list-wrapping'); s.tap(LEFT)
            for _ in range(3):
                s.tap(UP)                    # Direction (segments)
            s.shot('desktop-segments')
            s.tap(LEFT)                      # Forward is the first segment: to the rail
            s.tap(DOWN); s.tap(RIGHT); s.tap(DOWN)  # Switches, Sway
            s.shot('desktop-switch')
            s.tap(LEFT); s.tap(LEFT)         # On -> Off, then the rail
            s.tap(DOWN); s.tap(RIGHT)        # Text
            for _ in range(3):
                s.tap(DOWN)                  # Asset path
            s.shot('desktop-path')
        finally:
            s.close()


if __name__ == '__main__':
    main()
