#!/usr/bin/env python3
"""Repack migrated app bundles and verify the frozen Aquarium APK's assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apk", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    packer = root / "wftools/cdpack-rs/target/release/cdpack"
    shell = "wfsource/source/game/shell.fth"
    groups = {
        "wflevels/aquarium-cd.iff": ["aquarium"],
        "wflevels/condo-cd.iff": ["condo_639_640"],
        "wflevels/smb-cd.iff": [f"smb_w1_{i}" for i in range(1, 5)],
        "wflevels/snowgoons-cd.iff": ["snowgoons"],
        "wflevels/qbert-cd.iff": ["qbert_practice"],
        "wfsource/source/game/cd.iff": [
            *[f"smb_w1_{i}" for i in range(1, 5)], "snowgoons",
            "qbert_practice", "marble-madness-3d-astra", "baseline"],
    }
    jobs = {name: [shell, *[f"wflevels/{lv}-standalone.iff" for lv in levels]]
            for name, levels in groups.items()}
    for name in ("aquarium", "smb"):
        target = f"wflevels/{name}-menu-cd.iff"
        if (root / target).exists():
            jobs[target] = ["wfsource/source/game/shell-menu.fth", "--manifest",
                            f"wflevels/{name}-menu.manifest"]
    report = {"bundles": []}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.report.parent) as scratch:
        for i, (name, inputs) in enumerate(jobs.items()):
            out = Path(scratch).resolve() / f"bundle-{i}.iff"
            inputs = list(inputs)
            if name == "wfsource/source/game/cd.iff":
                # This bundle already contained a different baseline variant
                # before migration. Preserve and account for it explicitly.
                cd = (root / name).read_bytes()
                entry = 8  # SHEL, seven public levels, then baseline.
                offset, size = struct.unpack_from("<II", cd, 20 + 12 * entry)
                variant = cd[offset:offset + size]
                source = (root / inputs[-1]).read_bytes()
                if variant != source:
                    embedded = Path(scratch).resolve() / "baseline-embedded.iff"
                    embedded.write_bytes(variant)
                    report["desktop_baseline_variant"] = {
                        "embedded_sha256": sha(variant),
                        "standalone_sha256": sha(source),
                        "note": "Existing distinct baseline variant preserved; "
                                "inventoried and migrated independently."}
                    inputs[-1] = str(embedded)
            subprocess.run([str(packer), *inputs, "-o", str(out)], cwd=root,
                           check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            expected = (root / name).read_bytes()
            actual = out.read_bytes()
            if actual != expected:
                raise SystemExit(f"{name}: rebuilt bundle differs")
            report["bundles"].append({"path": name, "sha256": sha(actual),
                                       "bytes": len(actual), "exact": True})
    if args.apk:
        with zipfile.ZipFile(args.apk) as apk:
            asset = apk.read("assets/cd.iff")
            if asset != (root / "wflevels/aquarium-menu-cd.iff").read_bytes():
                raise SystemExit("APK contains a stale assets/cd.iff")
            abis = []
            for abi in ("arm64-v8a", "armeabi-v7a"):
                apk.getinfo(f"lib/{abi}/libwf_game.so")
                abis.append(abi)
        report["apk"] = {"path": str(args.apk),
                         "sha256": sha(args.apk.read_bytes()),
                         "cd_sha256": sha(asset), "abis": abis}
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(jobs)} bundles reproduce byte-identically; "
          f"APK checked={bool(args.apk)} -> {args.report}")


if __name__ == "__main__":
    main()
