"""Unit-test the iOS touch controls on Linux.

iOS runs the same touch control code as Android (wfsource/source/hal/
touch_controls.h: layout, hit test, finger ownership, the card-open narrowing
to A and C), driven from UIKit through wf_touch::Pad (hal/ios/touch_pad.{hp,cc}).
iOS itself cannot be built here, so this compiles that seam with the host g++
together with tests/touch_pad_test.cc (iPhone and iPad sizes in both
orientations with their safe areas, bit-for-bit parity with Android's layout,
the joystick, multi-touch with UITouch-sized ids, the card narrowing, rotation,
the CI touch-script grammar) and checks the button bits still match the
engine's EJ_BUTTONB_* definitions in hal/sjoystic.h. Skips if g++ is absent.
Plan: finding-your-way docs/plans/2026-11-08-ios-touch-parity.md.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = REPO / "wfsource" / "source"
IOS_HAL = SRC / "hal" / "ios"
SHARED = SRC / "hal" / "touch_controls.h"
SJOYSTIC = SRC / "hal" / "sjoystic.h"


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not available")
def test_touch_pad_logic(tmp_path):
    binp = tmp_path / "touch_pad_test"
    cmd = [
        "g++", "-std=c++17", "-O0", "-Wall", "-Wextra", "-Werror",
        "-I", str(SRC), "-I", str(IOS_HAL),
        str(IOS_HAL / "touch_pad.cc"), str(HERE / "touch_pad_test.cc"),
        "-o", str(binp),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"compile failed:\n{r.stderr}"
    r = subprocess.run([str(binp)], capture_output=True, text=True)
    assert r.returncode == 0, f"touch_pad_test FAIL\n{r.stdout}{r.stderr}"
    assert "PASS" in r.stdout
    print(r.stdout.strip())


def test_touch_bits_match_engine():
    """hal/touch_controls.h's bits must equal hal/sjoystic.h's EJ_BUTTONB_* shifts.

    input.mm static_asserts the same thing, but only on an iOS build; this is
    the Linux-side guard against the two drifting apart.
    """
    engine: dict[str, int] = {}
    for m in re.finditer(r"^#define\s+EJ_BUTTONB_(UP|DOWN|LEFT|RIGHT|A|B|C|D)\s+(\d+)\b",
                         SJOYSTIC.read_text(), re.M):
        engine.setdefault(m.group(1), int(m.group(2)))   # first live #define wins
    text = SHARED.read_text()
    shared: dict[str, int] = {}
    for m in re.finditer(r"\b(A|B|C|D)=(\d+)\b", text.split("struct Rect")[0]):
        shared[m.group(1)] = int(m.group(2)).bit_length() - 1
    for m in re.finditer(r"\b(Up|Down|Right|Left)=1u<<(\d+)", text):
        shared[m.group(1).upper()] = int(m.group(2))
    assert set(engine) == {"UP", "DOWN", "LEFT", "RIGHT", "A", "B", "C", "D"}, engine
    assert shared == engine


def test_android_header_is_only_an_alias():
    """Android keeps compiling its sources unchanged through a namespace alias."""
    text = (SRC / "hal" / "android" / "touch_controls.h").read_text()
    assert "#include <hal/touch_controls.h>" in text
    assert "namespace androidtouch = wftouch;" in text
    assert "inline" not in text
