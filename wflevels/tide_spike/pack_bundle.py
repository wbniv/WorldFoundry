#!/usr/bin/env python3
"""Pack the seven spike levels into one cd.iff (level 0 to 6 = variants a, b, c, d, n, v, g) and link it into the tidespike flavor.

    python3 wflevels/tide_spike/pack_bundle.py [-h]

Needs wflevels/tide_spike_{a,b,c,d,n,v,g}-standalone.iff (bash wflevels/tide_spike/build.sh) and a built cdpack
(WF_CDPACK, or wftools/cdpack-rs/target/release/cdpack here or in the main checkout).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEVELS = [ROOT / f"wflevels/tide_spike_{v}-standalone.iff" for v in "abcdnvg"]
BUNDLE = ROOT / "wflevels/tide_spike_cd.iff"
ASSETS = ROOT / "android/screensaver/src/tidespike/assets"


def find_cdpack():
    if os.environ.get("WF_CDPACK"):
        return Path(os.environ["WF_CDPACK"])
    for base in (ROOT, *ROOT.parents):
        p = base / "wftools/cdpack-rs/target/release/cdpack"
        if p.exists():
            return p
    return None


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    cdpack = find_cdpack()
    if not cdpack:
        print("cdpack not found: cargo build --release in wftools/cdpack-rs, or set WF_CDPACK", file=sys.stderr)
        return 2
    missing = [str(p) for p in LEVELS if not p.exists()]
    if missing:
        print("levels not built:", *missing, file=sys.stderr)
        return 2
    subprocess.run([str(cdpack), str(ROOT / "wfsource/source/game/shell.fth"), *map(str, LEVELS), "-o", str(BUNDLE)], cwd=ROOT, check=True)
    if b"UIFT" not in BUNDLE.read_bytes()[:2048]:
        print("cdpack is stale: rebuild wftools/cdpack-rs to include the UI font", file=sys.stderr)
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    link = ASSETS / "cd.iff"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(Path(os.path.relpath(BUNDLE, ASSETS)))
    print(f"tide spike bundle: {BUNDLE} ({BUNDLE.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
