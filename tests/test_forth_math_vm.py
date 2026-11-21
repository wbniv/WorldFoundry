"""The Forth math words in the real zForth VM (see tests/verify_forth_math.py)."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("cc") is None or shutil.which("c++") is None, reason="needs a C and C++ compiler")
def test_every_word_in_the_real_vm():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "verify_forth_math.py")], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "PASS" in r.stdout


def test_the_committed_vectors_are_up_to_date():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "gen_forth_math_vectors.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
