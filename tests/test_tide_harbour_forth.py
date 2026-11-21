"""The generated Tide Harbour director, run in the real zForth VM, equals timeline.py (see the script).

Poses, colours, visibility, the tide cell and every value of every setting. Plan:
docs/plans/2026-11-21-tide-harbour-clock.md, Verification 1, 10 and 13.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))


@pytest.mark.skipif(shutil.which("cc") is None or shutil.which("c++") is None, reason="needs a C and C++ compiler")
def test_director_matches_the_reference_model():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "verify_tide_harbour_forth.py")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert r.stdout.strip().endswith("PASS"), r.stdout[-500:]


def test_the_script_obeys_the_level_guides():
    """docs/level-design-troubleshooting.md: ASCII only, a backslash comment only on the first line, no and/or/<0,
    the definitions above and the per-tick call last."""
    import forth
    text = forth.director_script(forth.default_indices())
    assert text.isascii()
    lines = text.strip().split("\n")
    assert lines[0].startswith("\\ ") and not any("\\" in line for line in lines[1:])
    words = text.split()
    assert not {"and", "or", "<0"} & set(words)
    assert lines[-1] == "th-tick"
