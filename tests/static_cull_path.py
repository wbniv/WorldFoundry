#!/usr/bin/env python3
"""Which back-face form the static path runs, read from wf_game's frame-profile counters.

RenderObject3D::RenderStatic counts the faces of every opaque baked run under
the form it was tested with: static-cull-exact-faces (WfFaceIsBackfacing),
static-cull-fast-faces (WfFaceIsBackfacingFast) or static-cull-off-faces. The
shipped default must be the exact form; --static-mesh-cull=fast must reach the
fast form. Counters print in 5 s frame-profile windows, so the run is lengthened
until at least one window appears.

Usage: static_cull_path.py --binary wf_game --level L.iff [--cwd DIR]
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

COUNT_RE = re.compile(r"^frame-count: (static-cull-(?:exact|fast|off)-faces) frames=(\d+) mean=([\d.]+)", re.M)


def faces(binary: str, level: str, cwd: str, extra: list[str]) -> dict[str, float]:
    env = {k: v for k, v in os.environ.items() if k not in ("WF_STATIC_MESH_CULL", "WF_CULL")}
    for frames in (400, 1600, 6400):
        argv = [binary, f"-L{level}", f"--frame-step-smoke={frames}", "--cycles=1", "--no-fps",
                "--static-mesh=1", "--frame-profile", *extra]
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                              errors="replace", timeout=900)
        text = proc.stdout + proc.stderr
        if proc.returncode != 0:
            sys.exit(f"FAIL {level}: wf_game exited {proc.returncode}\n{text[-2000:]}")
        totals: dict[str, float] = {"static-cull-exact-faces": 0.0, "static-cull-fast-faces": 0.0,
                                    "static-cull-off-faces": 0.0}
        windows = 0
        for name, n, mean in COUNT_RE.findall(text):
            totals[name] += int(n) * float(mean)
            windows += name == "static-cull-exact-faces"
        if windows:
            return totals
    sys.exit(f"FAIL {level}: no frame-profile window in {frames} frames")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--level", required=True)
    ap.add_argument("--cwd", default=str(Path(__file__).resolve().parent.parent / "wfsource/source/game"))
    a = ap.parse_args()
    default = faces(a.binary, a.level, a.cwd, [])
    fast = faces(a.binary, a.level, a.cwd, ["--static-mesh-cull=fast"])
    print("default:", default)
    print("--static-mesh-cull=fast:", fast)
    ok = (default["static-cull-exact-faces"] > 0 and default["static-cull-fast-faces"] == 0
          and fast["static-cull-fast-faces"] > 0)
    print("PASS" if ok else "FAIL", Path(a.level).name)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
