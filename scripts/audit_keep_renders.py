#!/usr/bin/env python3
"""Render each level with and without the face-hand migration's `keep` models reversed.

The Blender-normal migration (25a57d73) flipped the engine's CalculateNormal. A
model the manifest marked `keep` was left byte-identical, so its rendered normal
flipped; every other model had its FACE rows swapped so its normal did not. This
script measures what each `keep` changed on screen: it writes a copy of the level
with every keep-decision model reversed (the pre-migration appearance of those
models) and captures frame 20 of both with the macOS gate's flags. A large
difference means a keep changed what the shipped camera sees; look at both PNGs to
decide which side is the intended one.

Run in the Linux test container with a display, for example:

  scripts/in-linux-container.sh bash -c 'Xvfb :99 & export DISPLAY=:99; sleep 1; \
      python3 scripts/audit_keep_renders.py --out build-docker/keep-audit LEVEL.iff ...'
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_face_hand import find_models  # noqa: E402
from convert_face_hand import converted_model  # noqa: E402

DECISIONS = ROOT / "docs/diagnostics/blender-normal-convention/integration-model-decisions.json"


def keep_reversed(level: Path, keeps: set[str]) -> tuple[bytes, list[dict]]:
    data = bytearray(level.read_bytes())
    hits = []
    for at, model in find_models(bytes(data)):
        digest = hashlib.sha256(model).hexdigest()
        if digest in keeps:
            new, count = converted_model(model, {"action": "reverse_all"})
            data[at:at + len(model)] = new
            hits.append({"offset": at, "sha256": digest, "faces": count})
    return bytes(data), hits


def capture(engine: Path, level: Path, png: Path, extra: list[str]) -> int:
    env = dict(os.environ, LD_LIBRARY_PATH=f"{ROOT / 'engine' / 'libs'}:{os.environ.get('LD_LIBRARY_PATH', '')}")
    with open(png.with_suffix(".log"), "w") as log:
        return subprocess.run(
            [str(engine), "--frame-step-smoke=30", "--cycles=1", f"-L{level}", "-rate20", "--no-fps",
             *extra, f"--capture-frame=20={png}"],
            cwd=ROOT / "wfsource" / "source" / "game", env=env, stdout=log, stderr=subprocess.STDOUT,
            timeout=300, preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0))).returncode


def differing(a: Path, b: Path, tolerance: int = 3) -> int | None:
    from compare_renderer_frames import read_png  # tests/ helper, no dependencies
    if not (a.exists() and b.exists()):
        return None
    wa, ha, pa = read_png(str(a))
    wb, hb, pb = read_png(str(b))
    if (wa, ha) != (wb, hb):
        return -1
    return sum(1 for i in range(0, len(pa), 3)
               if max(abs(pa[i + k] - pb[i + k]) for k in range(3)) > tolerance)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("levels", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--engine", type=Path, default=ROOT / "engine" / "wf_game")
    ap.add_argument("--engine-arg", action="append", default=[], help="extra engine argument (repeatable)")
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT / "tests"))
    keeps = {h for h, d in json.loads(DECISIONS.read_text()).items() if d["action"] == "keep"}
    args.out = args.out.resolve()   # the engine runs from wfsource/source/game
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    for level in args.levels:
        level = level.resolve()
        name = f"{level.parent.name}-{level.stem}"   # several levels share a basename
        data, hits = keep_reversed(level, keeps)
        row = {"level": str(level.relative_to(ROOT)), "keep_models": hits}
        if hits:
            patched = args.out / f"{name}-keep-reversed.iff"
            patched.write_bytes(data)
            head_png, old_png = args.out / f"{name}-head.png", args.out / f"{name}-keep-reversed.png"
            row["rc"] = [capture(args.engine, level, head_png, args.engine_arg),
                         capture(args.engine, patched, old_png, args.engine_arg)]
            row["pixels_over_3"] = differing(head_png, old_png)
            patched.unlink()
        report.append(row)
        print(json.dumps({k: row[k] for k in row if k != "keep_models"} | {"keeps": len(hits)}), flush=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
