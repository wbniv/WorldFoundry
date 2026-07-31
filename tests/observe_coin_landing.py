#!/usr/bin/env python3
"""Observe where the SMB coin SETTLES at realistic (unclamped) frame rate.

Free-runs the engine (legacy RunLevel loop = unclamped dt, unlike pause/step's
100ms-clamped StepFrame) and tracks the coin's Z to see if it ends up resting on
the BLOCK top (Z≈8.25) or on the GROUND (Z≈0.75).
"""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7783
LOG   = REPO / "tests" / ".observe_coin_landing.log"
OUT   = Path("/home/will/tmp/coin_landing"); OUT.mkdir(parents=True, exist_ok=True)
BLOCK_IDX, COIN_IDX = 13, 21
MB_XPOS, MB_ZPOS = 3009, 3011
MB_COLLIDER_IDX, MB_NORMAL_Z, MB_ACTIVATE = 3044, 3047, 2010

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402


def main() -> int:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
    env.setdefault("DISPLAY", ":0")
    log_fp = open(LOG, "w")
    proc = subprocess.Popen([str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
                             "--debug-bind", "127.0.0.1"],
                            cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
    cli = None
    try:
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0); time.sleep(1.5)
        cli.watch(idx=COIN_IDX, mailbox=MB_XPOS)
        cli.watch(idx=COIN_IDX, mailbox=MB_ZPOS)
        # Fire generator WITHOUT pausing → engine free-runs at its real dt.
        cli.set_mailbox(idx=BLOCK_IDX, mailbox=MB_COLLIDER_IDX, value=9)
        cli.set_mailbox(idx=BLOCK_IDX, mailbox=MB_NORMAL_Z,     value=1.0)
        cli.set_mailbox(idx=BLOCK_IDX, mailbox=MB_ACTIVATE,     value=1)
        for i in range(24):                 # ~7 s wall time
            time.sleep(0.3)
            cx = cli.mailbox_values.get((COIN_IDX, MB_XPOS))
            cz = cli.mailbox_values.get((COIN_IDX, MB_ZPOS))
            print(f"  t={i*0.3:4.1f}s  coin X={cx} Z={cz}")
            cli.send({"op": "screenshot", "filename": str(OUT / f"{i:02d}.png")})
        cz = cli.mailbox_values.get((COIN_IDX, MB_ZPOS))
        if cz is None:
            print("\ncoin gone (despawned)")
        elif cz > 5.0:
            print(f"\nSTUCK ON BLOCK — final coin Z={cz} (block top ≈8.25)")
        else:
            print(f"\nreached ground — final coin Z={cz} (~0.75)")
    finally:
        if cli:
            try: cli.close()
            except Exception: pass
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except Exception: proc.kill()
        log_fp.close()
    # generator spawn line
    for line in LOG.read_text(errors="replace").splitlines():
        if "FIRING" in line:
            print(" ", line); break
    return 0


if __name__ == "__main__":
    sys.exit(main())
