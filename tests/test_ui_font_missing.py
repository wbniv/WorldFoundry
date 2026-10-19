"""F6 of docs/plans/2026-10-17-settings-editor-font.md: no UI font, no start.

A cd.iff packed without the UI font (cdpack --no-ui-font) must stop wf_game at start-up,
non-zero, with exactly one "UI_FONT unavailable" line; the same bundle with the font starts.
Needs a built engine/wf_game and a display (Xvfb in the container):

    scripts/in-linux-container.sh <Xvfb wrapper> python3 -m pytest -q tests/test_ui_font_missing.py
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from level_menu_harness import LEVELS, SHELL, cdpack

ROOT = Path(__file__).resolve().parent.parent
WF_GAME = ROOT / "engine" / "wf_game"


def run(tmp: Path, *extra: str) -> tuple[int, str]:
    cdpack(SHELL, LEVELS / "snowgoons-standalone.iff", *extra, "-o", tmp / "cd.iff")
    # Plays the bundle's level 0 (no -L: --frame-step-smoke needs one) and quits after 60 frames.
    p = subprocess.run([str(WF_GAME), "--menu-input=wait:60,quit"], cwd=tmp, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


@pytest.mark.skipif(not WF_GAME.exists() or not os.environ.get("DISPLAY"), reason="needs engine/wf_game and a display")
def test_a_bundle_without_the_font_stops_start_up(tmp_path):
    code, log = run(tmp_path, "--no-ui-font")
    lines = [line for line in log.splitlines() if "UI_FONT unavailable" in line]
    assert code != 0, log[-2000:]
    assert lines == ["UI_FONT unavailable: cd.iff has no UIFT chunk (repack it with cdpack, which adds "
                     "wfsource/source/game/ui-font.wfga)"], lines


@pytest.mark.skipif(not WF_GAME.exists() or not os.environ.get("DISPLAY"), reason="needs engine/wf_game and a display")
def test_the_same_bundle_with_the_font_starts(tmp_path):
    code, log = run(tmp_path)
    assert code == 0 and "UI_FONT unavailable" not in log and "UI_FONT 1024x2048 atlas" in log, log[-2000:]
