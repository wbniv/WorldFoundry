#!/usr/bin/env python3
"""Export tracked level scenes into scratch space and compare face direction."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

from audit_face_hand import chunks


def triangles(data, reverse=False):
    end = 8 + struct.unpack_from("<I", data, 4)[0]
    parts = {tag: data[a:b] for tag, _, a, b in chunks(data, 8, end)}
    vb, fb = parts[b"VRTX"], parts[b"FACE"]
    pos = [struct.unpack_from("<iii", vb, i + 12)
           for i in range(0, len(vb), 24)]
    result = Counter()
    for i in range(0, len(fb), 8):
        a, b, c, _ = struct.unpack_from("<hhhh", fb, i)
        p, q, r = pos[a], pos[b], pos[c]
        if reverse:
            q, r = r, q
        result[min((p, q, r), (q, r, p), (r, p, q))] += 1
    return result


def signature(data):
    digest = hashlib.sha256()
    for triangle, count in sorted(triangles(data).items()):
        for point in triangle:
            digest.update(struct.pack("<iii", *point))
        digest.update(struct.pack("<I", count))
    return digest.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--blender", default="/usr/bin/blender")
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--reuse-exports", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    scratch = args.scratch.resolve()
    addon = scratch / "resources/scripts/addons/wf_blender"
    shutil.copytree(root / "wftools/wf_blender", addon, dirs_exist_ok=True)
    shutil.copy(root / "tests/.cache/wf_core.so", addon / "wf_core.so")
    scenes = [p for p in subprocess.check_output(
        ["git", "ls-files", "*.blend"], cwd=root, text=True).splitlines()
              if p.startswith("wflevels/")]
    inventory = json.loads((root / "docs/diagnostics/blender-normal-convention/post-inventory.json").read_text())
    embedded, files = {}, {}
    for row in inventory["models"] + inventory["unmatched_embedded_models"]:
        ref = row["references"][0]
        if ref["path"] not in files:
            files[ref["path"]] = (root / ref["path"]).read_bytes()
        data, at = files[ref["path"]], ref["offset"]
        end = at + 8 + struct.unpack_from("<I", data, at + 4)[0]
        model = data[at:(end + 3) & ~3]
        embedded.setdefault(signature(model), []).append(row["sha256"])
    report = []
    for scene in scenes:
        source = root / scene
        out = scratch / source.stem
        out.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "BLENDER_USER_RESOURCES": str(scratch / "resources"),
               "WF_EXPORT_OUT": str(out / (source.stem + ".lev"))}
        code = 0
        if not args.reuse_exports:
            with (out / "export.log").open("w") as log:
                proc = subprocess.run([args.blender, "--background", str(source),
                    "--python", str(root / "tests/blender_runner/run_export.py"),
                    "--python-exit-code", "1"], cwd=root, env=env,
                    stdout=log, stderr=subprocess.STDOUT, timeout=180)
            code = proc.returncode
            if code:
                raise SystemExit(f"{scene}: export failed; see {out / 'export.log'}")
        elif not (out / (source.stem + ".lev")).exists():
            raise SystemExit(f"missing previous export: {source}")
        row = {"scene": scene, "exit_code": code, "meshes": []}
        existing = {p.name.lower(): p for p in source.parent.glob("*.iff")}
        for mesh in sorted(out.glob("*.iff")):
            target = existing.get(mesh.name.lower())
            state = "no_standalone_source"
            if target and target.read_bytes()[:4] == b"MODL":
                original, exported = target.read_bytes(), mesh.read_bytes()
                if original == exported:
                    state = "byte_identical"
                elif triangles(original) == triangles(exported):
                    state = "same_face_direction"
                elif triangles(original, True) == triangles(exported):
                    state = "opposite_face_direction"
                else:
                    state = "different_geometry"
            matches = embedded.get(signature(mesh.read_bytes()), [])
            if state == "no_standalone_source" and matches:
                state = "same_embedded_face_direction"
            record = {"name": mesh.name, "comparison": state}
            if matches:
                record["matching_model_hashes"] = matches
            if source.stem == "qbert_practice" and mesh.name == "cube.iff":
                record["note"] = "Saved-scene placeholder; gen_cube.py owns the shipped override and regenerates it byte-identically."
            row["meshes"].append(record)
        report.append(row)
        print(scene, code, dict(Counter(m["comparison"] for m in row["meshes"])), flush=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
