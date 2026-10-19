#!/usr/bin/env python3
"""Deterministic demo: entry_pipe -> brick_1up -> over pipe_64.

Removes the flaky jump-BUTTON frame-timing by injecting the jump's ZSPEED directly
at the pipe/brick edge after a real ground run-up builds horizontal speed.  This is
a clean, repeatable arc, so it answers two questions:
  1. Does a ~run-up-speed launch land ON the brick (not tunnel through it)?
  2. From the brick, does a launch clear pipe_64 (land past X=97.5)?

Geometry (canonical, fixed):
  entry_pipe top Z=4.5, X 69-72   brick_1up top Z=7.5, X 84.75-86.25   pipe_64 top Z=6.0, X 94.5-97.5
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
PORT  = 7789
LOG   = REPO / "tests" / ".demo_hop.log"

PIPE_TOP_L, PIPE_TOP_R, PIPE_TOP_Z = 69.0, 72.0, 4.5
BRICK_L, BRICK_R, BRICK_C, BRICK_TOP_Z = 84.75, 86.25, 85.5, 7.5
PIPE64_R, PIPE64_TOP_Z = 97.5, 6.0
JUMP_VZ = 10.95

X_POS, Y_POS, Z_POS = 3009, 3010, 3011
XSPEED, ZSPEED = 3018, 3020
LIVES, SMB_STAR_UNTIL = 72, 1818
JOY_RIGHT = 0x2000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
     "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
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
for mb in (X_POS, Z_POS, XSPEED):
    cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.0)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=50, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))

def park(x, z):
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=x, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=z, idx=PLAYER)
    time.sleep(0.5)

def run_to(edge_x, timeout=5.0):
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    t = time.monotonic() + timeout
    while time.monotonic() < t:
        x = g(X_POS)
        if x is not None and x >= edge_x: break
        time.sleep(0.006)

def clean_jump_track():
    """Inject ZSPEED (deterministic jump) with RIGHT held; track to landing."""
    cli.set_mailbox(mailbox=ZSPEED, value=JUMP_VZ, idx=PLAYER)   # clean take-off
    peak_z = g(Z_POS) or 0.0
    deadline = time.monotonic() + 3.5
    last_z, stable = None, 0
    while time.monotonic() < deadline:
        z = g(Z_POS)
        if z and z > peak_z: peak_z = z
        if z is not None and last_z is not None and abs(z - last_z) < 0.01:
            stable += 1
            if stable >= 6: break
        else:
            stable = 0
        last_z = z
        time.sleep(0.02)
    return g(X_POS), g(Z_POS), peak_z

print("\n=== HOP A: entry_pipe -> brick_1up ===")
park(PIPE_TOP_L + 0.2, PIPE_TOP_Z + 0.2)
run_to(PIPE_TOP_R - 0.15)               # accelerate across the 3 m pipe top
vx = g(XSPEED) or 0.0
print(f"  launch X={g(X_POS):.2f} Z={g(Z_POS):.2f} Vx={vx:.2f}")
ax, az, ap = clean_jump_track()
on_brick = az is not None and az > 6.5 and (BRICK_L - 0.5) <= ax <= (BRICK_R + 0.5)
print(f"  -> land X={ax:.2f} Z={az:.2f} peak={ap:.2f}  "
      f"{'*** ON BRICK ***' if on_brick else ('tunneled/over' if (az or 0)<1 and ax>BRICK_R else 'short/other')}")

print("\n=== HOP B: brick_1up -> over pipe_64 ===")
park(BRICK_C, BRICK_TOP_Z + 0.2)
run_to(BRICK_C + 0.4)
vxb = g(XSPEED) or 0.0
print(f"  launch X={g(X_POS):.2f} Z={g(Z_POS):.2f} Vx={vxb:.2f}")
bx, bz, bp = clean_jump_track()
cleared = bx is not None and bx > PIPE64_R
print(f"  -> land X={bx:.2f} Z={bz:.2f} peak={bp:.2f}  "
      f"{'*** CLEARED pipe_64 ***' if cleared else 'blocked/short'}")

print("\n=== RESULT ===")
print(f"  HOP A pipe->brick:  {'PASS' if on_brick else 'FAIL'}")
print(f"  HOP B brick->pipe:  {'PASS' if cleared else 'FAIL'}")

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.2)
cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print("Done.")
