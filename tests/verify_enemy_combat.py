#!/usr/bin/env python3
"""Verify SMB enemy combat: lives seed + hurt/respawn when a Goomba reaches Mario.

TEMP setup: Mario spawned at X=28 (in the Goomba's leftward path). We screenshot
the HUD (LIVES count) before and after contact, and watch Mario's X for a respawn
jump. Also answers the key question: does player<->enemy (CharacterVirtual vs
CharacterVirtual) contact fire at all under Jolt?
"""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
WF, LEVEL = REPO/"engine"/"wf_game", REPO/"wflevels"/"smb_w1_1-standalone.iff"
LIB, CWD = REPO/"engine"/"libs", REPO/"wfsource"/"source"/"game"
PORT, LOG = 7791, REPO/"tests"/".verify_enemy_combat.log"
OUT = Path("/home/will/tmp/enemy_combat"); OUT.mkdir(parents=True, exist_ok=True)
MB_XPOS = 3009
sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa

def main() -> int:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"; env.setdefault("DISPLAY", ":0")
    proc = subprocess.Popen([str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1"],
                            cwd=str(CWD), env=env, stdout=open(LOG,"w"), stderr=subprocess.STDOUT)
    cli = None
    try:
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0); time.sleep(1.5)
        # find Mario (X near 28) and Goomba (X near 33)
        for i in range(6, 22): cli.watch(idx=i, mailbox=MB_XPOS)
        time.sleep(0.4)
        xs = {i: cli.mailbox_values.get((i, MB_XPOS)) for i in range(6,22)}
        mario = next((i for i,x in xs.items() if x is not None and 26 < x < 30), None)
        print("idx X:", {i: round(x,1) for i,x in xs.items() if x is not None})
        print(f"Mario idx guess = {mario}")
        cli.send({"op":"screenshot","filename":str(OUT/"00_start.png")}); time.sleep(0.3)
        # let the goomba walk into Mario (Mario stationary, no input)
        for t in (1.5, 3.0, 5.0):
            time.sleep(t - (0 if t==1.5 else (1.5 if t==3.0 else 3.0)))
            mx = cli.mailbox_values.get((mario, MB_XPOS)) if mario else None
            print(f"  t~{t}s marioX={mx}")
            cli.send({"op":"screenshot","filename":str(OUT/f"{int(t*10):02d}.png")}); time.sleep(0.2)
    finally:
        if cli:
            try: cli.close()
            except Exception: pass
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except Exception: proc.kill()
    print(f"screenshots in {OUT}; engine log {LOG}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
