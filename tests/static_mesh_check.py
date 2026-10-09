#!/usr/bin/env python3
"""E3 phase 1 self-check gate: run wf_game with WF_STATIC_MESH_CHECK=1 and assert
the static-mesh path matches the streaming path.

With the check on, every baked object is re-recorded at every draw (under that
frame's model-view matrix and globals) and compared with its bake, and every
face's static-path cull decision is compared with the one DrawTriangle would
make from the recorded triangle. wf_game prints one line at exit:

  static-mesh-check: object-draws=N triangles=N triangle-mismatches=N
      cull-faces=N cull-exact-mismatches=N fast-faces=N fast-mismatches=N ...

  --check bake  triangle-mismatches must be 0 (plan step 1: a bake made under
                one matrix equals the recording under every later matrix,
                and equals what the renderers submit)
  --check cull  cull-exact-mismatches must be 0 (plan step 2, exact form);
                with --fast also fast-mismatches must be 0
Both require object-draws > 0, so a run that never used the static path fails
instead of passing vacuously.

Usage: static_mesh_check.py --binary wf_game --level L.iff [--level ...]
           --check bake|cull [--frames 120] [--fast] [--cwd DIR] [--extra ARG]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

LINE_RE = re.compile(r"^static-mesh-check: (.*)$", re.M)


def run(binary: str, level: str, frames: int, cwd: str, extra: list[str]) -> dict[str, int]:
    env = dict(os.environ, WF_STATIC_MESH_CHECK="1")
    argv = [binary, f"-L{level}", f"--frame-step-smoke={frames}", "--cycles=1", "--no-fps",
            "--static-mesh=1", *extra]
    proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                          errors="replace", timeout=600)
    text = proc.stdout + proc.stderr
    if proc.returncode != 0:
        sys.exit(f"FAIL {level}: wf_game exited {proc.returncode}\n{text[-2000:]}")
    m = LINE_RE.search(text)
    if not m:
        sys.exit(f"FAIL {level}: no static-mesh-check line (static path never ran?)")
    return {k: int(v) for k, v in (kv.split("=") for kv in m.group(1).split())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--level", action="append", required=True)
    ap.add_argument("--check", choices=["bake", "cull"], required=True)
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--fast", action="store_true", help="also require zero fast-form mismatches")
    ap.add_argument("--cwd", default=str(Path(__file__).resolve().parent.parent / "wfsource/source/game"))
    ap.add_argument("--extra", action="append", default=[])
    a = ap.parse_args()
    failed = False
    for level in a.level:
        c = run(a.binary, level, a.frames, a.cwd, a.extra)
        keys = ["triangle-mismatches"] if a.check == "bake" else ["cull-exact-mismatches"]
        if a.check == "cull" and a.fast:
            keys.append("fast-mismatches")
        bad = [k for k in keys if c.get(k, -1) != 0]
        vacuous = c.get("object-draws", 0) == 0 or c.get("triangles", 0) == 0
        status = "FAIL" if bad or vacuous else "PASS"
        failed |= status == "FAIL"
        print(f"{status} {Path(level).name}: " + " ".join(f"{k}={v}" for k, v in c.items()))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
