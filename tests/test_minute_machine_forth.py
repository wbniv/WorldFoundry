"""The generated Minute Machine director, run in the real zForth VM, equals timeline.py (see the script)."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("cc") is None or shutil.which("c++") is None, reason="needs a C and C++ compiler")
def test_director_matches_the_reference_model():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "verify_minute_machine_forth.py")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert r.stdout.strip().endswith("PASS"), r.stdout[-500:]
