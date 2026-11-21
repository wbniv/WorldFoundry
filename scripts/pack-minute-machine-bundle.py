#!/usr/bin/env python3
"""Pack the Minute Machine level into the Dream's cd.iff and link it into the minutemachine flavor.

    python3 scripts/pack-minute-machine-bundle.py [-h]

Needs wflevels/minute_machine-standalone.iff (task minute-machine-level) and the cdpack tool
(cargo build --release in wftools/cdpack-rs; or point WF_CDPACK at one). Writes
wflevels/minutemachine-screensaver-cd.iff and symlinks it as
android/screensaver/src/minutemachine/assets/cd.iff, as the Aquarium and Seahorse Dreams do.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVEL = ROOT / "wflevels/minute_machine-standalone.iff"
BUNDLE = ROOT / "wflevels/minutemachine-screensaver-cd.iff"
ASSETS = ROOT / "android/screensaver/src/minutemachine/assets"


def main() -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    cdpack = Path(os.environ.get("WF_CDPACK", ROOT / "wftools/cdpack-rs/target/release/cdpack"))
    if not cdpack.exists():
        print(f"cdpack not built: {cdpack} (cargo build --release in wftools/cdpack-rs, or set WF_CDPACK)", file=sys.stderr)
        return 2
    if not LEVEL.exists():
        print(f"level not built: {LEVEL} (task minute-machine-level)", file=sys.stderr)
        return 2
    subprocess.run([str(cdpack), str(ROOT / "wfsource/source/game/shell.fth"), str(LEVEL), "-o", str(BUNDLE)],
                   cwd=ROOT, check=True)
    if b"UIFT" not in BUNDLE.read_bytes()[:2048]:
        print("cdpack is stale: rebuild wftools/cdpack-rs to include the UI font", file=sys.stderr)
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    link = ASSETS / "cd.iff"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(Path(os.path.relpath(BUNDLE, ASSETS)))
    print(f"minutemachine screensaver bundle: {BUNDLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
