#!/usr/bin/env python3
"""Verify SMB W1-4 fire-bars orbit their pivots (Phase 2).

Boots smb_w1_4 headless with the debug bridge, discovers the first segment of
fire-bar #1 by authored position, watches its X_POS / Z_POS for a couple of
seconds, and asserts:
  1. the segment MOVES (position changes frame-over-frame), and
  2. it stays ON ITS CIRCLE — distance to the baked pivot (px=33, pz=3) holds
     near the authored radius (0.4T = 0.6 m) within tolerance (symplectic Euler
     keeps the orbit bounded; explicit Euler would spiral it out).

Run:  python3 tests/verify_smb_w1_4_firebars.py
"""
from __future__ import annotations
import os, sys, time, math, signal, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient, discover_by_pos

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_4-standalone.iff"
LEV   = REPO / "wflevels" / "smb_w1_4" / "smb_w1_4.lev"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7794
LOG   = REPO / "tests" / ".firebar_run.log"

X_POS, Z_POS = 3009, 3011
# fire-bar #1: pivot col 22 → px=33 m, pivot z 2T = 3 m; seg1 radius 0.4T = 0.6 m.
PIVOT_X, PIVOT_Z = 33.0, 3.0
SEG_RADIUS = 0.6
SEG_NAME = "fb1_seg1"

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}",
     "--debug-port", str(PORT), "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

def shutdown():
    try:
        proc.send_signal(signal.SIGTERM); proc.wait(timeout=3)
    except Exception:
        proc.kill()

try:
    time.sleep(2.5)
    seg = discover_by_pos(LOG, LEV, {SEG_NAME}, timeout=10.0, tol=0.6)
    idx = seg[SEG_NAME]
    print(f"[firebar] {SEG_NAME} = actor idx {idx}")

    cli = BridgeClient(port=PORT)
    cli.watch(idx, X_POS); cli.watch(idx, Z_POS)

    samples: list[tuple[float, float]] = []
    deadline = time.time() + 2.5
    while time.time() < deadline:
        x = cli.mailbox_values.get((idx, X_POS))
        z = cli.mailbox_values.get((idx, Z_POS))
        if x is not None and z is not None:
            if not samples or (x, z) != samples[-1]:
                samples.append((x, z))
        time.sleep(0.05)

    cli.close()

    print(f"[firebar] collected {len(samples)} distinct (X,Z) samples")
    for x, z in samples[:8]:
        r = math.hypot(x - PIVOT_X, z - PIVOT_Z)
        print(f"          X={x:7.3f}  Z={z:7.3f}   r={r:5.3f}")

    assert len(samples) >= 4, f"segment did not move enough ({len(samples)} samples)"
    xs = [s[0] for s in samples]; zs = [s[1] for s in samples]
    span = max(max(xs) - min(xs), max(zs) - min(zs))
    assert span > 0.3, f"segment barely moved (span {span:.3f} m) — not orbiting"
    radii = [math.hypot(x - PIVOT_X, z - PIVOT_Z) for x, z in samples]
    rmin, rmax = min(radii), max(radii)
    assert rmax < SEG_RADIUS + 0.6, f"orbit radius blew up to {rmax:.3f} (spiral?)"
    assert rmin > SEG_RADIUS - 0.5, f"orbit collapsed to {rmin:.3f}"

    print(f"[firebar] PASS — orbits (span {span:.2f} m, r∈[{rmin:.2f},{rmax:.2f}] "
          f"around authored {SEG_RADIUS})")
finally:
    shutdown()
    log_fp.close()
