#!/usr/bin/env python3
"""Verify the SMB coin keeps its +X drift on the ground (Running Deceleration=0).

Fires the block-0 generator and steps; confirms the coin's X keeps increasing
*after* it lands (Z≈0.75) instead of freezing. Regression guard for the
"coin should slide right with no friction" behavior.
"""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7782
LOG   = REPO / "tests" / ".verify_coin_slide.log"
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
    cli = None; result = 1
    try:
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0); time.sleep(1.5)
        cli.watch(idx=COIN_IDX, mailbox=MB_XPOS)
        cli.watch(idx=COIN_IDX, mailbox=MB_ZPOS)
        cli.send({"op": "pause"}); time.sleep(0.2)
        cli.set_mailbox(idx=BLOCK_IDX, mailbox=MB_COLLIDER_IDX, value=9)
        cli.set_mailbox(idx=BLOCK_IDX, mailbox=MB_NORMAL_Z,     value=1.0)
        cli.set_mailbox(idx=BLOCK_IDX, mailbox=MB_ACTIVATE,     value=1)
        time.sleep(0.1)

        landed_x = None; last_x = None
        for i in range(160):
            cli.send({"op": "step"}); time.sleep(0.03)
            cx = cli.mailbox_values.get((COIN_IDX, MB_XPOS))
            cz = cli.mailbox_values.get((COIN_IDX, MB_ZPOS))
            if cx is None:
                continue
            last_x = cx
            if landed_x is None and cz is not None and cz < 0.9:   # reached ground rest height
                landed_x = cx
                print(f"  landed at X={cx:.3f} (step {i})")
            if i % 15 == 0:
                print(f"  step {i:3d}: coin X={cx:.3f} Z={cz}")
        print(f"\nlanded_x={landed_x}  final_x={last_x}")
        if landed_x is not None and last_x is not None and (last_x - landed_x) > 1.0:
            print(f"PASS — coin slid {last_x - landed_x:.2f} m right after landing (no ground friction)")
            result = 0
        else:
            print("FAIL — coin did not keep sliding after landing")
    finally:
        if cli:
            try: cli.close()
            except Exception: pass
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except Exception: proc.kill()
        log_fp.close()
    return result


if __name__ == "__main__":
    sys.exit(main())
