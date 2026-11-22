#!/usr/bin/env python3
"""Make a game APK whose Sea Stars row plays the static tank with no animated actors.

Verification step 10 of docs/plans/2026-11-10-starfish-tank.md is the early gate: the
static tank with no actors must run at <= 38 ms on cast1. The shipped menu always plays
the full tank, so this builds a one-off APK for the measurement. It reuses the exact
native libraries of --base-apk and replaces only assets/cd.iff, as scripts/
the archived docs/reference/device-harnesses/build-aquarium-variant.py.txt did with --base-apk, then aligns and signs with the debug key.

  bash wflevels/aquarium_sea_stars/build.sh --empty        # writes the empty standalone
  cp wflevels/aquarium_sea_stars-standalone.iff build-docker/sea-stars-empty/
  bash wflevels/aquarium_sea_stars/build.sh                # restore the normal level
  python3 scripts/sea-stars-empty-apk.py --base-apk <aquarium release apk> \\
      --empty-iff build-docker/sea-stars-empty/aquarium_sea_stars-standalone.iff \\
      --out build-docker/sea-stars-empty/worldfoundry-aquarium-sea-stars-empty.apk
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "wflevels/aquarium-menu.manifest"
SEA_STARS = "aquarium_sea_stars-standalone.iff"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-apk", type=Path, required=True)
    ap.add_argument("--empty-iff", type=Path, required=True, help="the standalone built by build.sh --empty")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    cdpack = ROOT / "wftools/cdpack-rs/target/release/cdpack"
    sdk = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "android-sdk-local")))
    tools = sdk / "build-tools/34.0.0"
    for path in (cdpack, a.base_apk, a.empty_iff, tools / "zipalign", tools / "apksigner"):
        if not path.exists():
            print(f"missing: {path}", file=sys.stderr)
            return 1

    with tempfile.TemporaryDirectory(prefix="sea-stars-empty-") as tmp:
        work = Path(tmp)
        # The menu bundle with every row as committed, except Sea Stars is the empty tank.
        shutil.copy(MANIFEST, work / "aquarium-menu.manifest")
        for line in MANIFEST.read_text().splitlines():
            if line.startswith("level "):
                name = line[len("level "):].split("|")[0].strip()
                shutil.copy(a.empty_iff if name == SEA_STARS else ROOT / "wflevels" / name, work / name)
        cd = work / "cd.iff"
        subprocess.run([str(cdpack), str(ROOT / "wfsource/source/game/shell-menu.fth"),
                        "--manifest", str(work / "aquarium-menu.manifest"), "-o", str(cd)], check=True)
        unsigned, aligned = work / "unsigned.apk", work / "aligned.apk"
        with zipfile.ZipFile(a.base_apk) as src, zipfile.ZipFile(unsigned, "w") as dst:
            for entry in src.infolist():
                if entry.filename.startswith("META-INF/") or entry.filename == "assets/cd.iff":
                    continue
                dst.writestr(entry, src.read(entry.filename))
            dst.write(cd, "assets/cd.iff", compress_type=zipfile.ZIP_DEFLATED)
        subprocess.run([str(tools / "zipalign"), "-f", "-p", "4", str(unsigned), str(aligned)], check=True)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(tools / "apksigner"), "sign", "--ks", str(Path.home() / ".android/debug.keystore"),
                        "--ks-pass", "pass:android", "--key-pass", "pass:android",
                        "--out", str(a.out), str(aligned)], check=True)
    print(f"{a.out}  sha256 {hashlib.sha256(a.out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
