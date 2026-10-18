#!/usr/bin/env python3
"""Build signed freshwater and saltwater screensaver APKs for video capture.

Only the Planted Tank's authored property catalog changes. The other seven
levels, native library, resources, and application ID come from the base APK.
These variants are capture fixtures; reinstall the base APK after recording.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import zipfile

from plant_settings_catalog import configure_level


PLANTED_TOC_INDEX = 6  # SHEL, then the eight tanks in TankChoice.IDS order.
SETTINGS = dict(seed=713, age=150, speed=0, greeting=True, seahorses=6)


def replace_planted_catalog(bundle: bytes, water: str):
    if bundle[:4] != b"GAME" or bundle[8:12] != b"TOC\0":
        raise ValueError("Expected a GAME/TOC screensaver bundle")
    toc_bytes = struct.unpack_from("<I", bundle, 12)[0]
    entries = [struct.unpack_from("<4sII", bundle, 16 + i)
               for i in range(0, toc_bytes, 12)]
    if len(entries) != 10 or entries[0][0] != b"SHEL" or entries[PLANTED_TOC_INDEX][0][:1] != b"L":
        raise ValueError("Unexpected screensaver bundle order")
    result = bytearray(bundle[:2048])
    receipt = None
    for index, (tag, start, size) in enumerate(entries):
        block = bundle[start:start + size]
        if len(block) != size:
            raise ValueError("Truncated bundle entry")
        if index == PLANTED_TOC_INDEX:
            block, receipt = configure_level(block, dict(SETTINGS, water=water))
        offset = len(result)
        result.extend(block)
        result.extend(bytes((-len(result)) % 2048))
        struct.pack_into("<II", result, 20 + 12 * index, offset, len(block))
    struct.pack_into("<I", result, 4, len(result) - 8)
    return bytes(result), receipt


def build_tools():
    properties = Path("android/local.properties")
    configured = next((line.split("=", 1)[1] for line in properties.read_text().splitlines()
                       if line.startswith("sdk.dir=")), "") if properties.exists() else ""
    root = Path(configured or os.environ.get("ANDROID_HOME", str(Path.home() / "android-sdk-local")))
    return root / "build-tools/34.0.0"


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-apk", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tools = build_tools()
    with zipfile.ZipFile(args.base_apk) as archive:
        bundle = archive.read("assets/cd.iff")
    variants = {}
    for water in ("freshwater", "saltwater"):
        modified, receipt = replace_planted_catalog(bundle, water)
        unsigned = args.out / f"planted-{water}-unsigned.apk"
        aligned = args.out / f"planted-{water}-aligned.apk"
        final = args.out / f"planted-{water}.apk"
        with zipfile.ZipFile(args.base_apk) as source, zipfile.ZipFile(unsigned, "w") as target:
            for entry in source.infolist():
                if entry.filename.startswith("META-INF/"):
                    continue
                content = modified if entry.filename == "assets/cd.iff" else source.read(entry.filename)
                target.writestr(entry, content)
        subprocess.run([str(tools / "zipalign"), "-f", "-p", "4", str(unsigned), str(aligned)], check=True)
        subprocess.run([str(tools / "apksigner"), "sign", "--ks", str(Path.home() / ".android/debug.keystore"),
                        "--ks-pass", "pass:android", "--key-pass", "pass:android",
                        "--out", str(final), str(aligned)], check=True)
        subprocess.run([str(tools / "apksigner"), "verify", str(final)], check=True)
        unsigned.unlink()
        aligned.unlink()
        variants[water] = dict(apk=str(final.resolve()), apk_sha256=sha256(final),
                               bundle_sha256=hashlib.sha256(modified).hexdigest(),
                               planted_catalog=receipt)
    report = dict(base_apk=str(args.base_apk.resolve()), base_apk_sha256=sha256(args.base_apk),
                  planted_toc_index=PLANTED_TOC_INDEX, settings=SETTINGS, variants=variants)
    (args.out / "variants.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({water: info["apk_sha256"] for water, info in variants.items()}, indent=2))


if __name__ == "__main__":
    main()
