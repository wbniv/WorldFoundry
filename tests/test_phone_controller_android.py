"""The phone as a gamepad, static checks on the Android side (Phase E; docs/plans/2026-09-30-aquarium-chromecast.md).

  * each app's layout.json uses the engine's real EJ_BUTTONF_* bits (read from wfsource/source/hal/sjoystic.h,
    not restated), and carries exactly the buttons the plan gives it: aquarium = stick + A + B; condo = stick +
    A (doors / shade) + C (teleport) + D (orbit, held) + E/F (zoom), and **no B** (since 2026-10-01, commit
    41742943, the condo's A toggles the doors and the shade and B does nothing on its own).
  * snowgoons ships no phone controller.

No device, no build. python3 -m pytest tests/test_phone_controller_android.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "android" / "app" / "src"
SJOYSTIC = REPO / "wfsource" / "source" / "hal" / "sjoystic.h"


def engine_bits() -> dict[str, int]:
    """EJ_BUTTONB_* from the live #if 1 block of sjoystic.h, as masks."""
    text = SJOYSTIC.read_text()
    live = text[text.index("#if 1"):text.index("#else", text.index("#if 1"))]
    return {m.group(1): 1 << int(m.group(2)) for m in re.finditer(r"#define\s+EJ_BUTTONB_(\w+)\s+(\d+)", live)
            if int(m.group(2)) < 16}


def layout(app: str) -> dict:
    return json.loads((SRC / app / "assets" / "layout.json").read_text())


@pytest.mark.parametrize("app", ["aquarium", "condo"])
def test_layout_uses_the_engine_bits(app):
    bits, lay = engine_bits(), layout(app)
    assert lay["app"] == app
    assert lay["stick"] == {"up": bits["UP"], "down": bits["DOWN"], "right": bits["RIGHT"], "left": bits["LEFT"]}
    assert lay["threshold"] == 0.5, "the engine's analog-stick threshold (kJoystickThreshold)"
    for b in lay["buttons"]:
        assert b["bit"] == bits[b["id"]], b
        assert 0 < b["x"] < 1 and 0 < b["y"] < 1, b
    mask = sum(b["bit"] for b in lay["buttons"]) | sum(lay["stick"].values())
    assert mask < 1 << 16, "the protocol carries a 16-bit mask"


def test_aquarium_is_stick_a_b():
    assert [b["id"] for b in layout("aquarium")["buttons"]] == ["A", "B"]


def test_condo_has_no_b_and_a_is_doors_and_shade():
    buttons = {b["id"]: b["label"] for b in layout("condo")["buttons"]}
    assert buttons == {"A": "doors / shade", "C": "teleport", "D": "orbit (hold)", "E": "zoom in", "F": "zoom out"}
    # E zooms in and F out: camera_controls.fth adds (F - E) to the camera's range (mailbox 137 -> 116).
    fth = (REPO / "wflevels" / "condo_639_640" / "camera_controls.fth").read_text()
    assert re.search(r"JOYSTICK_BUTTON_F cc-key if 1 else 0 then\s+JOYSTICK_BUTTON_E cc-key if 1 else 0 then -", fth)
    # ... and A, not B, fires the door / shade pulse (mailbox 119) outside the D-held branch.
    assert "A (not B) toggles the glass doors and the balcony shade" in fth


def test_snowgoons_has_no_phone_controller():
    names = {p.name for p in (SRC / "snowgoons" / "assets").iterdir()}
    assert not names & {"controller.html", "layout.json"}
