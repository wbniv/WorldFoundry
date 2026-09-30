"""Unit-test the platform-independent half of the iOS touch shim on Linux.

wfsource/source/hal/ios/touch_pad.{hp,cc} holds the layout math, hit testing
and multi-touch bookkeeping that hal/ios/input.mm drives from UITouch events.
iOS itself cannot be built here, so this compiles that seam with the host g++
together with tests/touch_pad_test.cc (D-pad arms and diagonals, A+B chords,
drags across buttons, cancel/suspend clearing, iPhone and iPad sizes, safe-area
insets, the CI touch-script grammar) and checks its button bits still match
the engine's EJ_BUTTONF_* definitions in hal/sjoystic.h. Skips if g++ is absent.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
IOS_HAL = REPO / "wfsource" / "source" / "hal" / "ios"
SJOYSTIC = REPO / "wfsource" / "source" / "hal" / "sjoystic.h"


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not available")
def test_touch_pad_logic(tmp_path):
    binp = tmp_path / "touch_pad_test"
    cmd = [
        "g++", "-std=c++17", "-O0", "-Wall", "-Wextra", "-Werror",
        "-I", str(IOS_HAL),
        str(IOS_HAL / "touch_pad.cc"), str(HERE / "touch_pad_test.cc"),
        "-o", str(binp),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"compile failed:\n{r.stderr}"
    r = subprocess.run([str(binp)], capture_output=True, text=True)
    assert r.returncode == 0, f"touch_pad_test FAIL\n{r.stdout}{r.stderr}"
    assert "PASS" in r.stdout


def test_touch_pad_bits_match_engine():
    """touch_pad.hp's kBtn* must equal hal/sjoystic.h's EJ_BUTTONB_* shifts.

    input.mm static_asserts the same thing, but only on an iOS build; this is
    the Linux-side guard against the two drifting apart.
    """
    engine: dict[str, int] = {}
    for m in re.finditer(r"^#define\s+EJ_BUTTONB_(UP|DOWN|LEFT|RIGHT|A|B)\s+(\d+)\b",
                         SJOYSTIC.read_text(), re.M):
        engine.setdefault(m.group(1), int(m.group(2)))   # first live #define wins
    pad = {m.group(1).upper(): int(m.group(2)) for m in re.finditer(
        r"constexpr uint32_t kBtn(A|B|Up|Down|Right|Left)\s*=\s*1u\s*<<\s*(\d+);",
        (IOS_HAL / "touch_pad.hp").read_text())}
    assert set(engine) == {"UP", "DOWN", "LEFT", "RIGHT", "A", "B"}, engine
    assert pad == engine
