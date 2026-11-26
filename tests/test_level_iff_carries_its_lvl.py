"""A committed level .iff carries its committed .lvl, so a level and the bundles built from it cannot drift apart.

Regression guard (triage 2026-11-26). 7ed6d60c5 ("Check in Aquarium and Clocks development build inputs") committed
an smb_w1_1.iff and smb_w1_1-standalone.iff built from an older .lvl, one without the Level Settings object
("Show framerate") that 8c78b004a gave every reachable level; wflevels/smb_w1_1/smb_w1_1.lvl still had it. The SMB
bundles (smb-cd.iff, smb-menu-cd.iff, the main cd.iff) were built from the right level, so five bundle tests failed
saying the bundles were stale, when the level was. iffcomp copies the .lvl into the .iff byte for byte, so checking
the copy finds this at the level, before any bundle is blamed.

Scope: the levels whose .lvl carries the global Level Settings sheet (the reachable levels, docs/level-building.md).
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRACKED = set(subprocess.run(["git", "-C", str(ROOT), "ls-files", "wflevels"], capture_output=True, text=True).stdout.split())


def pairs():
    for lvl in sorted((ROOT / "wflevels").glob("*/*.lvl")):
        name = lvl.stem
        if lvl.parent.name != name or str(lvl.relative_to(ROOT)) not in TRACKED or b"Show framerate" not in lvl.read_bytes():
            continue
        for iff in (ROOT / "wflevels" / f"{name}.iff", ROOT / "wflevels" / f"{name}-standalone.iff"):
            if str(iff.relative_to(ROOT)) in TRACKED:
                yield pytest.param(lvl, iff, id=iff.name)


@pytest.mark.parametrize("lvl, iff", list(pairs()))
def test_the_iff_holds_the_committed_lvl(lvl, iff):
    assert lvl.read_bytes() in iff.read_bytes(), \
        f"{iff.relative_to(ROOT)} was not built from {lvl.relative_to(ROOT)}: rebuild the level (task build-level -- {lvl.stem})"


@pytest.mark.parametrize('filename', ['filesys.iff', 'filesys-standalone.iff'])
def test_filesys_iff_holds_its_committed_lvl(filename):
    # This historical level has no Level Settings sheet, but its checked-in
    # binaries must still correspond to its checked-in level source.
    lvl = (ROOT / 'wflevels/filesys/filesys.lvl').read_bytes()
    assert lvl in (ROOT / 'wflevels' / filename).read_bytes()
