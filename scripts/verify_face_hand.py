#!/usr/bin/env python3
"""Verify each migrated IFF byte against its reviewed pre-migration payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from audit_face_hand import find_models
from convert_face_hand import converted_model


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--decisions", type=Path, required=True)
    ap.add_argument("--path", action="append", default=[],
                    help="verify only these tracked paths (repeatable); skips the coverage check")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    inv = json.loads(args.inventory.read_text())
    decisions = json.loads(args.decisions.read_text())
    names = subprocess.check_output(["git", "ls-files", "*.iff"],
                                    cwd=root, text=True).splitlines()
    if args.path:
        missing = sorted(set(args.path) - set(names))
        if missing:
            raise SystemExit(f"not tracked IFF paths: {missing}")
        names = [name for name in names if name in set(args.path)]
    expected_hashes = {row["sha256"] for row in inv["models"] +
                       inv["unmatched_embedded_models"]}
    if set(decisions) != expected_hashes:
        raise SystemExit("decision manifest does not cover original inventory")
    seen = set()
    changed_files = changed_models = changed_faces = 0
    for name in names:
        path = root / name
        original = subprocess.check_output(["git", "show", f"{inv['base_revision']}:{name}"],
                                           cwd=root)
        if path.is_symlink():
            if original != path.readlink().as_posix().encode():
                raise SystemExit(f"{name}: tracked symlink changed")
            if not path.resolve().is_file():
                raise SystemExit(f"{name}: broken symlink")
            continue
        output = bytearray(original)
        try:
            models = list(find_models(original))
        except ValueError:
            if original != path.read_bytes():
                raise SystemExit(f"{name}: unparseable fixture changed")
            continue
        for at, model in models:
            old_hash = sha(model)
            if old_hash not in decisions:
                raise SystemExit(f"{name}@{at}: unreviewed model {old_hash}")
            migrated, count = converted_model(model, decisions[old_hash])
            output[at:at + len(model)] = migrated
            seen.add(old_hash)
            changed_models += bool(count)
            changed_faces += count
        actual = path.read_bytes()
        if actual != output:
            mismatch = next((i for i, (a, b) in enumerate(zip(actual, output))
                             if a != b), min(len(actual), len(output)))
            raise SystemExit(f"{name}: unexpected byte at offset {mismatch}")
        changed_files += actual != original
    if not args.path and seen != expected_hashes:
        raise SystemExit(f"{len(expected_hashes - seen)} reviewed models absent")
    print(f"verified {len(names)} tracked IFF paths, {len(seen)} old model hashes, "
          f"{changed_faces} selected faces, {changed_models} model occurrences, "
          f"{changed_files} regular files changed")


if __name__ == "__main__":
    main()
