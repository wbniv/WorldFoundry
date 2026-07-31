"""Compile the C++ pilot_core and prove it matches the Python reference.

Builds the standalone conformance runner (pilot_test) and the frame-resumable
await self-test (pilot_resume_test) with g++, then runs the VM-tier corpus
through the C++ core — it must reach the same PASS verdicts as the Python
reference driver (test_pilot_corpus.py). Skips if g++ is unavailable.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PILOT = REPO / "engine" / "pilot"
CORE = PILOT / "pilot_core.cc"

sys.path.insert(0, str(HERE / "pilot"))
import pilot_driver as pd  # noqa: E402

VM_CASES = [p for p in sorted((HERE / "pilot").glob("*.pilot")) if pd.tier_of(p) == "vm"]

pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not available")


def _build(out: Path, *srcs: Path) -> Path:
    cmd = ["g++", "-std=c++17", "-O0", "-I", str(PILOT), *map(str, srcs), "-o", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"compile failed:\n{r.stderr}"
    return out


def test_cpp_core_matches_corpus(tmp_path):
    binp = _build(tmp_path / "pilot_test", CORE, PILOT / "pilot_test.cc")
    for case in VM_CASES:
        r = subprocess.run([str(binp), str(case)], capture_output=True, text=True)
        assert r.returncode == 0, f"{case.name}: C++ core FAIL\n{r.stdout}{r.stderr}"


def test_cpp_frame_resumable_await(tmp_path):
    binp = _build(tmp_path / "pilot_resume_test", CORE, PILOT / "pilot_resume_test.cc")
    r = subprocess.run([str(binp)], capture_output=True, text=True)
    assert r.returncode == 0, f"resume self-test FAIL\n{r.stdout}{r.stderr}"
