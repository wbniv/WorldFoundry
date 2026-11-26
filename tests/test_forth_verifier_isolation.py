"""The level verifiers that borrow Minute Machine's zForth VM host leave it as they found it.

tests/verify_cuckoo_village_forth.py and tests/verify_tide_harbour_forth.py build their VM host by editing
verify_minute_machine_forth.HOST when they are imported, and run its build() with their own host, constants and
director. Until 2026-11-26 their build() assigned mm.HOST and mm.CONSTANTS and never put them back, so in one
pytest process a Cuckoo Village test that built its VM (test_cuckoo_village_daynight, _population, Dutch) left
Cuckoo's host behind; Tide Harbour's verifier, imported later, then derived its host from Cuckoo's, found no
'mm-tick' to rename and failed its import assertion. All 11 VM tests in test_tide_harbour_settings.py errored in
the full suite and passed alone (docs/diagnostics/2026-11-26-pytest-triage.md).
"""
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

pytestmark = pytest.mark.skipif(shutil.which("cc") is None or shutil.which("c++") is None,
                                reason="needs a C and C++ compiler")


def test_cuckoo_build_then_tide_import_still_derives_from_minute_machines_host():
    import verify_minute_machine_forth as mm
    import verify_cuckoo_village_forth as cv
    host, constants, gen = mm.HOST, list(mm.CONSTANTS), mm.forth
    with tempfile.TemporaryDirectory(prefix="vm-iso-") as t:
        cv.build(Path(t))
    assert (mm.HOST, list(mm.CONSTANTS), mm.forth) == (host, constants, gen)
    sys.modules.pop("verify_tide_harbour_forth", None)       # import it fresh, after Cuckoo's build, as the suite does
    import verify_tide_harbour_forth as th                   # its import-time assertion is the original failure
    assert th.HOST.count("th-tick") == 1
    with tempfile.TemporaryDirectory(prefix="vm-iso-") as t:
        th.build(Path(t))
    assert (mm.HOST, list(mm.CONSTANTS), mm.forth) == (host, constants, gen)
