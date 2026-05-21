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

    ACTOR_RE = re.compile(r"^actor idx=(\d+) mesh=(\S+)")

    def find_idx(meshes: set[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        if LOG.exists():
            for line in LOG.read_text(errors="replace").splitlines():
                m = ACTOR_RE.match(line)
                if m and m.group(2) in meshes:
                    out[m.group(2)] = int(m.group(1))
        return out

    cli = None
    try:
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print(f"bridge connected on {PORT}")
        time.sleep(1.5)

        blocks = find_idx({"qblock_00.iff"})
        print(f"blocks={blocks}")
        if not blocks:
            print("!! qblock_00.iff not found in actor log")
            return 1

        bidx = blocks["qblock_00.iff"]
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
        time.sleep(0.1)

        # Capture coin arc over ~1.5s (TTL), 0.25s intervals
        for i, label in enumerate(["01_spawn", "02_rise", "03_apex",
                                    "04_fall", "05_fall2", "06_ttl_expire"]):
            time.sleep(0.25)
            cli.send({"op": "screenshot",
                      "filename": str(args.out_dir / f"{label}.png")})
            time.sleep(0.1)
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
