#!/usr/bin/env python3
"""Apply reviewed Blender-hand decisions to every tracked IFF model occurrence.

No decision is inferred. A missing or unresolved model aborts before any file
is written. The default mode is a dry run; --apply changes only tracked IFFs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

from audit_face_hand import chunks, find_models


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_faces(decision: dict, count: int) -> list[int]:
    action = decision.get("action")
    if action == "keep":
        return []
    if action == "reverse_all":
        return list(range(count))
    if action == "reverse_selected":
        selected = decision.get("face_indices")
        if not isinstance(selected, list) or not all(
                isinstance(i, int) and 0 <= i < count for i in selected):
            raise ValueError("invalid face_indices")
        if len(set(selected)) != len(selected):
            raise ValueError("duplicate face_indices")
        return selected
    raise ValueError(f"missing or unsupported action {action!r}")


def converted_model(model: bytes, decision: dict) -> tuple[bytes, int]:
    if model[:4] != b"MODL":
        raise ValueError("not a MODL chunk")
    size = struct.unpack_from("<I", model, 4)[0]
    if size + 8 > len(model):
        raise ValueError("truncated MODL chunk")
    face_ranges = [(a, b) for tag, _, a, b in chunks(model, 8, size + 8)
                   if tag == b"FACE"]
    if len(face_ranges) != 1:
        raise ValueError("MODL requires exactly one FACE chunk")
    start, end = face_ranges[0]
    if (end - start) % 8:
        raise ValueError("FACE size is not divisible by eight")
    count = (end - start) // 8
    selected = selected_faces(decision, count)
    output = bytearray(model)
    for i in selected:
        at = start + i * 8
        v1, v2, v3, material = struct.unpack_from("<hhhh", output, at)
        struct.pack_into("<hhhh", output, at, v1, v3, v2, material)
    return bytes(output), len(selected)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--decisions", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    inventory = json.loads(args.inventory.read_text())
    choices = json.loads(args.decisions.read_text())
    rows = inventory["models"] + inventory["unmatched_embedded_models"]
    expected = {row["sha256"]: row for row in rows}
    if len(expected) != len(rows):
        raise SystemExit("duplicate model hashes in inventory")
    missing = sorted(set(expected) - set(choices))
    extra = sorted(set(choices) - set(expected))
    if missing or extra:
        raise SystemExit(f"decision coverage mismatch: {len(missing)} missing, "
                         f"{len(extra)} extra")
    for model_hash, choice in choices.items():
        if not choice.get("evidence"):
            raise SystemExit(f"{model_hash}: missing review evidence")
        selected_faces(choice, expected[model_hash]["faces"])
    names = subprocess.check_output(["git", "ls-files", "*.iff"],
                                    cwd=root, text=True).splitlines()
    staged = []
    seen = set()
    report = []
    for name in names:
        path = root / name
        # A tracked symlink points at a separately tracked model or bundle.
        # Convert its target once and leave the packaging link intact.
        if path.is_symlink():
            continue
        original = path.read_bytes()
        output = bytearray(original)
        occurrences = []
        try:
            models = list(find_models(original))
        except ValueError as exc:
            if b"MODL" in original:
                raise SystemExit(f"{name}: unparseable IFF with possible MODL: {exc}")
            continue
        for at, model in models:
            old_hash = digest(model)
            if old_hash not in expected:
                raise SystemExit(f"{name}@{at}: model absent from inventory")
            new_model, flips = converted_model(model, choices[old_hash])
            if len(new_model) != len(model):
                raise SystemExit(f"{name}@{at}: model size changed")
            output[at:at + len(model)] = new_model
            seen.add(old_hash)
            occurrences.append({"offset": at, "before": old_hash,
                                "after": digest(new_model), "faces_reversed": flips})
        if output != original:
            staged.append((path, bytes(output)))
        if occurrences:
            report.append({"path": name, "sha256_before": digest(original),
                           "sha256_after": digest(output),
                           "models": occurrences})
    if seen != set(expected):
        raise SystemExit(f"inventory contains {len(set(expected) - seen)} models "
                         "not found in tracked IFF files")
    result = {"base_revision": inventory["base_revision"],
              "mode": "apply" if args.apply else "dry-run",
              "changed_files": len(staged), "files": report}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    if args.apply:
        for path, data in staged:
            with tempfile.NamedTemporaryFile(dir=path.parent,
                                             prefix=f".{path.name}.",
                                             delete=False) as temp:
                temp.write(data)
                temp_name = temp.name
            os.chmod(temp_name, path.stat().st_mode)
            os.replace(temp_name, path)
    print(f"{len(staged)} changed files, {len(seen)} reviewed model hashes "
          f"-> {args.report} ({result['mode']})")


if __name__ == "__main__":
    main()
