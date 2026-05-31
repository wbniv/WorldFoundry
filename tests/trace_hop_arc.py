#!/usr/bin/env python3
"""Trace the raw pipe->brick arc for a few launch speeds (airborne clean launch).

Teleports Mario just above the pipe right edge (airborne, so the air handler runs and
the injected velocity is NOT eaten by the ground handler), injects (Vx, Vz=10.95) with
RIGHT held, and prints the (t, X, Z) trajectory.  Reading the arc directly tells us
whether he settles ON the brick (Z~7.5 around X 84.75-86.25) or passes over/through it
(Z falls to ~0, X continues past 86).
"""
from __future__ import annotations
import os, sys, time, re, signal, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7790
LOG   = REPO / "tests" / ".trace_arc.log"

EDGE_X, LAUNCH_Z, JUMP_VZ = 71.85, 4.65, 10.95
X_POS, Y_POS, Z_POS, XSPEED, ZSPEED = 3009, 3010, 3011, 3018, 3020
LIVES, SMB_STAR_UNTIL, JOY_RIGHT = 72, 1818, 0x2000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
     "--debug-print-actors"], cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
time.sleep(2.0)

def discover_player(timeout=10.0):
    deadline = time.time() + timeout
    rx = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")
    while time.time() < deadline:
        try:
            for m in rx.finditer(LOG.read_text(errors="replace")):
                if "player" in m.group(2): return int(m.group(1))
        except OSError: pass
        time.sleep(0.1)
    return 9

PLAYER = discover_player()
print(f"player idx={PLAYER}")
cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
for mb in (X_POS, Z_POS, XSPEED): cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.0)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=50, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))

def trace(vx):
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=EDGE_X, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=LAUNCH_Z, idx=PLAYER)
    time.sleep(0.4)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    cli.set_mailbox(mailbox=ZSPEED, value=JUMP_VZ, idx=PLAYER)
    cli.set_mailbox(mailbox=XSPEED, value=float(vx), idx=PLAYER)
    print(f"\n--- launch Vx={vx} from X={EDGE_X} Z={LAUNCH_Z} Vz={JUMP_VZ} ---")
    t0 = time.monotonic()
    samples = []
    while time.monotonic() - t0 < 2.6:
        samples.append((time.monotonic()-t0, g(X_POS), g(Z_POS)))
        time.sleep(0.07)
    last = None
    for (t, x, z) in samples:
        if x is None or z is None: continue
        if last is None or abs(x-last[0]) > 0.15 or abs(z-last[1]) > 0.1:
            tag = ""
            if 84.75 <= x <= 86.25 and abs(z-7.5) < 0.6: tag = "  <- AT BRICK"
            print(f"  t={t:4.2f}  X={x:6.2f}  Z={z:6.2f}{tag}")
            last = (x, z)
    fx, fz = g(X_POS), g(Z_POS)
    print(f"  FINAL X={fx:.2f} Z={fz:.2f}")

for vx in (8.0, 8.6, 9.2):
    trace(vx)

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.2); cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close(); print("\nDone.")
