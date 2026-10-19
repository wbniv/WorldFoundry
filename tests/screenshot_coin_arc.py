#!/usr/bin/env python3
"""Capture coin arc screenshots by triggering the qblock generator directly.

Uses the block-self-detect design: sets COLLIDER_IDX + COLLISION_NORMAL_Z on
the BLOCK actor (not the player), which makes its Forth script pulse its
activation mailbox and fire the Generator.

Usage:
  python3 tests/screenshot_coin_arc.py [--out-dir /home/will/tmp/coin_arc]
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7780  # separate port to avoid collision
LOG   = REPO / "tests" / ".screenshot_coin_arc.log"

MB_COLLIDER_IDX       = 3044
MB_COLLISION_NORMAL_Z = 3047

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path,
                    default=Path("/home/will/tmp/coin_arc"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    env.setdefault("DISPLAY", ":0")

    log_fp = open(LOG, "w")
    cmd = [str(WF), f"-L{LEVEL}",
           "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
           "--debug-print-actors"]
    proc = subprocess.Popen(cmd, cwd=str(CWD), env=env,
                            stdout=log_fp, stderr=subprocess.STDOUT)
    print(f"launched wf_game pid={proc.pid}")

    # qblock_00 is stable at actor idx=13 in smb_w1_1-standalone.iff.
    # (DO_TEST_CODE=0 in current build so --debug-print-actors is compiled out;
    # verified from repro log where actor idx=13 mesh=qblock_00.iff)
    QBLOCK_00_IDX = 13

    cli = None
    try:
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print(f"bridge connected on {PORT}")
        time.sleep(1.5)

        bidx = QBLOCK_00_IDX
        print(f"targeting block idx={bidx}")

        # pre-bump screenshot
        cli.send({"op": "screenshot",
                  "filename": str(args.out_dir / "00_pre.png")})
        time.sleep(0.5)

        MB_ACTIVATE = 2010  # INDEXOF_SMB_QBLOCK_ACTIVATE — Generator fires when nonzero

        # Set block collision mailboxes (Forth self-detect path) …
        print(f"faking hit-from-below on block idx={bidx}")
        cli.send({"op": "set_mailbox",
                  "idx": bidx, "mailbox": MB_COLLIDER_IDX, "value": 9})
        cli.send({"op": "set_mailbox",
                  "idx": bidx, "mailbox": MB_COLLISION_NORMAL_Z, "value": 1.0})
        time.sleep(0.05)
        # … and also directly pulse the activation mailbox so the Generator
        # fires even before the Forth script tick runs (same approach as repro).
        cli.send({"op": "set_mailbox",
                  "idx": bidx, "mailbox": MB_ACTIVATE, "value": 1})

        # Coin spawns at Z=7.50 (block top) with vel=(0,0,8), gravity=-12.
        # At ~1 fps dev machine, spawn+physics happen in one game tick (dt≈1s).
        # First rendered frame: Z = 7.5 + 8*1 - 0.5*12*1² = 9.5 m — above the block.
        # TTL=1.5 game-s; coin is despawned on the SECOND game tick (t≈2s real-time).
        # Wait 1.0 s for the first full tick, then grab 3 shots in the 1-2 s window.
        for delay, label in [(1.0, "01_above_block"),
                              (0.3, "02_still_visible"),
                              (0.3, "03_near_ttl")]:
            time.sleep(delay)
            cli.send({"op": "screenshot",
                      "filename": str(args.out_dir / f"{label}.png")})
            time.sleep(0.15)
            print(f"  captured {label}")
            if proc.poll() is not None:
                print(f"!! engine exited early: returncode={proc.returncode}")
                break

    finally:
        if cli:
            try:
                cli.close()
            except Exception:
                pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        log_fp.close()

    print(f"\nengine returncode: {proc.returncode}")
    print(f"screenshots in {args.out_dir}")
    # Show generator fires from log
    for line in LOG.read_text(errors="replace").splitlines():
        if "FIRING" in line or "AddObject" in line:
            print(" ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
