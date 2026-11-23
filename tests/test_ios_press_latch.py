"""Unit-test the iOS press latch on Linux.

hal/ios/press_latch.hp keeps a touch press until the engine thread has read
it, for at least one engine frame: Codemagic build 6b01461c lost a 51 ms
XCUITest tap on the iPad because the HAL handed over only the current state.
iOS cannot be built here; the header is platform-free, so
tests/ios_press_latch_test.cc compiles it with the host g++ (two threads).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "wfsource" / "source"


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not available")
def test_ios_press_latch(tmp_path):
    binp = tmp_path / "ios_press_latch_test"
    r = subprocess.run(["g++", "-std=c++17", "-O1", "-Wall", "-Wextra", "-Werror", "-pthread",
                        "-I", str(SRC), str(HERE / "ios_press_latch_test.cc"), "-o", str(binp)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"compile failed:\n{r.stderr}"
    r = subprocess.run([str(binp)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"ios_press_latch_test FAIL\n{r.stdout}{r.stderr}"
    assert "PASS" in r.stdout
    print(r.stdout.strip())
