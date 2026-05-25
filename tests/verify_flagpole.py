#!/usr/bin/env python3
"""Verify the SMB flagpole ends the level (statplat + ActBox composition).

Walks Mario right into the invisible ActBox volume at the flagpole (X≈61.5–64.5)
and confirms END_OF_LEVEL fires — observed as the RunLevel loop ending (process
exit) and/or a level reload (Mario X resets). Also screenshots Mario at the pole
to confirm the ActBox renders nothing.
"""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7784
LOG   = REPO / "tests" / ".verify_flagpole.log"
OUT   = Path("/home/will/tmp/flagpole"); OUT.mkdir(parents=True, exist_ok=True)
MARIO_IDX = 10
MB_XPOS, MB_END = 3009, 1905
JOY_RIGHT = 0x2000

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
        cli.watch(idx=MARIO_IDX, mailbox=MB_XPOS)
        cli.watch(idx=0,         mailbox=MB_END)
        time.sleep(0.3)
        x0 = cli.mailbox_values.get((MARIO_IDX, MB_XPOS))
        print(f"Mario start X = {x0} (expect ~4.5; confirms idx {MARIO_IDX} = Player)")

        cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
        shot_at_pole = False
        peak_x = x0 or 0.0
        for i in range(80):                # ~16 s of held-RIGHT
            time.sleep(0.2)
            if proc.poll() is not None:
                print(f">>> level ENDED — engine exited (returncode={proc.returncode}) at step {i}")
                result = 0
                break
            x = cli.mailbox_values.get((MARIO_IDX, MB_XPOS))
            end = cli.mailbox_values.get((0, MB_END))
            if x is not None:
                peak_x = max(peak_x, x)
                if i % 5 == 0:
                    print(f"  step {i:3d}: marioX={x:.2f}  END_OF_LEVEL={end}")
                if x > 58.0 and not shot_at_pole:
                    cli.send({"op": "screenshot", "filename": str(OUT / "at_flagpole.png")})
                    shot_at_pole = True
                    print(f"  screenshot at flagpole (X={x:.2f}) — check ActBox is invisible")
                if end is not None and end >= 0.5:
                    print(f">>> END_OF_LEVEL={end} at step {i} (marioX={x:.2f})")
                    result = 0
                # reload detection: was past the pole, now reset to spawn
                if peak_x > 60.0 and x < 10.0:
                    print(f">>> level RELOADED — Mario reset to X={x:.2f} after reaching {peak_x:.2f}")
                    result = 0
                    break
        print(f"\npeak Mario X = {peak_x:.2f} (flagpole trigger spans 61.5–64.5)")
        if result == 0:
            print("PASS — reaching the flagpole ended the level")
        elif peak_x < 61.0:
            print(f"INCONCLUSIVE — Mario only reached {peak_x:.2f}, never entered the trigger")
        else:
            print("FAIL — Mario entered the trigger region but the level did not end")
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
