"""Unit-test which iOS launch arguments reach the engine, on Linux.

hal/ios/launch_args.hp drops NSUserDefaults pairs (-WF..., -NS..., -Apple...
with their values) from the engine's command line: game/main.cc reads the
first argument that is not a switch as the starting level, so the XCUITest
tour's "-WFTouchDiagnostics 1" made the chapter app load level 1 and abort
(Codemagic build 6af131a7). iOS cannot be built here; the header is
platform-free, so tests/ios_launch_args_test.cc compiles it with the host g++.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "wfsource" / "source"


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not available")
def test_ios_launch_args(tmp_path):
    binp = tmp_path / "ios_launch_args_test"
    r = subprocess.run(["g++", "-std=c++17", "-O0", "-Wall", "-Wextra", "-Werror", "-I", str(SRC),
                        str(HERE / "ios_launch_args_test.cc"), "-o", str(binp)],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"compile failed:\n{r.stderr}"
    r = subprocess.run([str(binp)], capture_output=True, text=True)
    assert r.returncode == 0, f"ios_launch_args_test FAIL\n{r.stdout}{r.stderr}"
    assert "PASS" in r.stdout
    print(r.stdout.strip())
