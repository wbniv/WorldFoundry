#!/usr/bin/env python3
"""Phase-1 hop tuning harness for the Q*bert physics-hop plan.

See docs/plans/2026-05-10-qbert-physics-hops.md.

Boots assumes wf_game is already running with -Lwflevels/qbert_practice-standalone.iff
and the debug bridge listening on 7777. Then:

  1. Sets TUNING_MODE (mb 450) = 1 — disables joystick/autopilot/safety-net.
  2. Writes (vx, vy, vz) into mb 452/453/454.
  3. Sets LAUNCH_TRIGGER (mb 451) = 1 — director snaps Q*bert to apex, fires
     INDEXOF_XSPEED/YSPEED/ZSPEED, auto-clears the trigger.
  4. Polls INDEXOF_X_POS / Y_POS / Z_POS (mb 3009/3010/3011) until vertical
     velocity stabilises (Z delta over a few ticks < epsilon) OR Z drops
     below FALL_FLOOR.
  5. Reports landed (X, Y, Z) and total flight time.

Use it to find impulse magnitudes that produce 1-cube DR / DL / UR / UL hops
under the engine's current gravity. Cube spacing reference (from the script):
  ΔX/ΔY = ±SQRT2 ≈ ±1.414  (or 0 for diagonals along the other axis)
  ΔZ   = ±2  (CUBE_SIZE between adjacent rows)
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from tests.debug_bridge_client import BridgeClient

# Mailbox indices — see wflevels/qbert_practice/blender_create_qbert.py
TUNING_MODE     = 450
LAUNCH_TRIGGER  = 451
LAUNCH_VX       = 452
LAUNCH_VY       = 453
LAUNCH_VZ       = 454
# Engine system mailboxes (wfsource/source/mailbox/mailbox.inc)
X_POS = 3009
Y_POS = 3010
Z_POS = 3011

APEX_X = 0.0
APEX_Y = math.sqrt(2.0) * 6.0   # SQRT2 * (NUM_ROWS-1) per blender_create_qbert.py
APEX_Z = 15.0


def fetch_pos(cli: BridgeClient, actor: int) -> tuple[float, float, float]:
    with cli._lock:                                         # noqa: SLF001
        x = float(cli.mailbox_values.get((actor, X_POS), float("nan")))
        y = float(cli.mailbox_values.get((actor, Y_POS), float("nan")))
        z = float(cli.mailbox_values.get((actor, Z_POS), float("nan")))
    return (x, y, z)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vx", type=float)
    ap.add_argument("vy", type=float)
    ap.add_argument("vz", type=float)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7777)
    ap.add_argument("--actor", type=int, default=1)
    ap.add_argument("--max-flight", type=float, default=4.0,
                    help="Walltime ceiling for one launch (default 4 s)")
    ap.add_argument("--poll-hz", type=float, default=30.0)
    ap.add_argument("--land-eps", type=float, default=0.02,
                    help="|ΔZ| per tick below which we consider Q*bert landed")
    ap.add_argument("--fall-floor", type=float, default=-3.0,
                    help="Z below which we declare a fall (no cube caught him)")
    args = ap.parse_args()

    print(f"[tune] connecting {args.host}:{args.port}")
    cli = BridgeClient(args.host, args.port)

    cli.watch(args.actor, X_POS)
    cli.watch(args.actor, Y_POS)
    cli.watch(args.actor, Z_POS)
    time.sleep(0.1)

    print(f"[tune] enable TUNING_MODE")
    cli.set_mailbox(TUNING_MODE, 1, idx=args.actor)
    time.sleep(0.1)

    # Stage launch parameters first, then the trigger so the director sees
    # them all on the same tick.
    cli.set_mailbox(LAUNCH_VX, args.vx, idx=args.actor)
    cli.set_mailbox(LAUNCH_VY, args.vy, idx=args.actor)
    cli.set_mailbox(LAUNCH_VZ, args.vz, idx=args.actor)
    time.sleep(0.05)

    t_launch = time.time()
    print(f"[tune] LAUNCH (vx,vy,vz)=({args.vx:.3f}, {args.vy:.3f}, {args.vz:.3f})")
    cli.set_mailbox(LAUNCH_TRIGGER, 1, idx=args.actor)

    poll_dt = 1.0 / args.poll_hz
    last_z = None
    stable_ticks = 0
    landed_pos = None
    deadline = t_launch + args.max_flight

    # Skip the first ~150 ms — let the snap-to-apex + impulse settle before
    # checking for "landed".
    time.sleep(0.15)

    while time.time() < deadline:
        time.sleep(poll_dt)
        x, y, z = fetch_pos(cli, args.actor)
        if math.isnan(z):
            continue
        if z < args.fall_floor:
            t = time.time() - t_launch
            print(f"[tune] FELL  t={t:.3f}s  pos=({x:.3f}, {y:.3f}, {z:.3f})")
            landed_pos = (x, y, z, t, "fell")
            break
        if last_z is not None and abs(z - last_z) < args.land_eps:
            stable_ticks += 1
        else:
            stable_ticks = 0
        last_z = z
        if stable_ticks >= 6:
            t = time.time() - t_launch
            print(f"[tune] LAND  t={t:.3f}s  pos=({x:.3f}, {y:.3f}, {z:.3f})")
            landed_pos = (x, y, z, t, "land")
            break

    if landed_pos is None:
        x, y, z = fetch_pos(cli, args.actor)
        t = time.time() - t_launch
        print(f"[tune] TIMEOUT  t={t:.3f}s  pos=({x:.3f}, {y:.3f}, {z:.3f})")
        landed_pos = (x, y, z, t, "timeout")

    # Compute deltas vs apex for quick interpretation.
    x, y, z, t, verdict = landed_pos
    dx, dy, dz = x - APEX_X, y - APEX_Y, z - APEX_Z
    print(f"[tune]   Δ from apex (0, {APEX_Y:.3f}, {APEX_Z:.0f}): "
          f"dx={dx:+.3f} dy={dy:+.3f} dz={dz:+.3f}")

    # Leave TUNING_MODE on so subsequent iterations don't have to re-enable.
    cli.close()
    return 0 if verdict == "land" else 1


if __name__ == "__main__":
    raise SystemExit(main())
