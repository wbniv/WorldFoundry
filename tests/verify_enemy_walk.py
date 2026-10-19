#!/usr/bin/env python3
"""Verify SMB Goomba/Koopa walk left. Free-runs and tracks enemy X (should decrease)."""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
WF, LEVEL = REPO/"engine"/"wf_game", REPO/"wflevels"/"smb_w1_1-standalone.iff"
LIB, CWD = REPO/"engine"/"libs", REPO/"wfsource"/"source"/"game"
PORT, LOG = 7785, REPO/"tests"/".verify_enemy_walk.log"
MB_XPOS = 3009
sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa

def main() -> int:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"; env.setdefault("DISPLAY", ":0")
    proc = subprocess.Popen([str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1"],
                            cwd=str(CWD), env=env, stdout=open(LOG,"w"), stderr=subprocess.STDOUT)
    cli = None; result = 1
    try:
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0); time.sleep(1.5)
        for i in range(6, 22):
            cli.watch(idx=i, mailbox=MB_XPOS)
        time.sleep(0.5)
        # Identify enemies: GOOMBA_X=33, KOOPA_X=42 at spawn
        start = {i: cli.mailbox_values.get((i, MB_XPOS)) for i in range(6, 22)}
        enemies = {i: x for i, x in start.items() if x is not None and (28 < x < 36 or 38 < x < 46)}
        print("candidate enemy indices (X near 33 / 42):", {i: round(x,1) for i,x in enemies.items()})
        time.sleep(4.0)  # let them walk
        moved = {}
        for i in enemies:
            x = cli.mailbox_values.get((i, MB_XPOS))
            moved[i] = (round(start[i],2), round(x,2) if x is not None else None)
        print("enemy X start -> after 4s:", moved)
        walked = [i for i,(s,e) in moved.items() if e is not None and s - e > 1.0]  # moved left >1
        if walked:
            print(f"PASS — enemies {walked} walked left"); result = 0
        else:
            print("FAIL — no enemy moved left")
    finally:
        if cli:
            try: cli.close()
            except Exception: pass
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except Exception: proc.kill()
    return result

if __name__ == "__main__":
    sys.exit(main())
