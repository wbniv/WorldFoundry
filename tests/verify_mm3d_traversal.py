#!/usr/bin/env python3
"""Drive the marble across the real arcade Practice course with injected input.

Launches wf_game on wflevels/marble-madness-3d-standalone.iff with the debug
bridge and -record_video, holds joystick directions in phases (sticky
inject_input on joystick1_raw), and parses the engine's periodic
`ball pos: (x, y, z)` trace.  Passes when the marble travels a meaningful
distance across the terrain, descends, never drops below the course, and the
log has no asserts.

Usage: tests/verify_mm3d_traversal.py [--phases "DOWN:8,DOWN+LEFT:8,DOWN+RIGHT:8"] [--out tests/screenshots/mm3d_traversal.mp4]
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WF = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "marble-madness-3d-standalone.iff"
LIB = REPO / "engine" / "libs"
CWD = REPO / "wfsource" / "source" / "game"     # output.mp4 lands here
PORT = 7781
BITS = {"UP": 0x0800, "DOWN": 0x1000, "RIGHT": 0x2000, "LEFT": 0x4000}
POS_RE = re.compile(r"ball pos: \(\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\)")
BAD_RE = re.compile(r"AssertMsg|zforth compile|fell out of room|ignoring zone body|terminate called")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phases", default="DOWN:8,DOWN+LEFT:8,DOWN+RIGHT:8")
    ap.add_argument("--out", default=str(REPO / "tests" / "screenshots" / "mm3d_traversal.mp4"))
    ap.add_argument("--settle", type=float, default=3.0)
    a = ap.parse_args()

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    env.setdefault("DISPLAY", ":0")
    log_path = REPO / "tests" / ".mm3d_traversal.log"
    log_fp = open(log_path, "w")
    proc = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1", "-record_video"],
        cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
    rc = 1
    try:
        client = BridgeClient(port=PORT, timeout=30.0)
        time.sleep(a.settle)
        for phase in a.phases.split(","):
            keys, secs = phase.split(":")
            value = sum(BITS[k] for k in keys.split("+"))
            print(f"{time.strftime('%H:%M:%S')} hold {keys} (0x{value:04X}) for {secs}s", flush=True)
            client.inject_input("joystick1_raw", value, -1)
            time.sleep(float(secs))
        client.inject_input("joystick1_raw", 0, -1)
        time.sleep(1.5)
        client.close()
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fp.close()
    text = log_path.read_text(errors="replace")
    pos = [tuple(float(v) for v in m.groups()) for m in POS_RE.finditer(text)]
    bad = [ln for ln in text.splitlines() if BAD_RE.search(ln)]
    print(f"{len(pos)} ball-pos samples; {len(bad)} bad log lines")
    for p in pos[:: max(1, len(pos) // 12)]:
        print("  ball pos: (%.2f, %.2f, %.2f)" % p)
    if pos:
        x0, y0, z0 = pos[0]
        dist = max(((x - x0) ** 2 + (y - y0) ** 2) ** 0.5 for x, y, _ in pos)
        zmin = min(z for _, _, z in pos)
        print(f"max horizontal travel {dist:.2f} m; z from {z0:.2f} to min {zmin:.2f}")
        ok = dist >= 5.0 and zmin < z0 - 0.5 and zmin > -6.0 and not bad
    else:
        ok = False
    mp4 = CWD / "output.mp4"
    if mp4.exists():
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(mp4), a.out)
        print(f"video -> {a.out}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
