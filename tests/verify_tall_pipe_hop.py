#!/usr/bin/env python3
"""Verify the canonical entry_pipe → brick_1up → pipe_64 hop is reachable.

Mirrors the real maneuver: stand on the SHORTER pipe (entry_pipe, top Z=4.5),
run right across its 3 m top to build speed, jump off the right edge, and land
ON the brick (top Z=7.5, X 84.75-86.25).  Then from the brick, run+jump again
to clear the TALL pipe (pipe_64, top Z=6.0, X 94.5-97.5).

Geometry is canonical and fixed; only Mario's Running Deceleration was tuned
(0.85 -> 0.22) to raise horizontal reach.  See
docs/plans/2026-05-31-smb-tall-pipe-hop-physics.md.
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
PORT  = 7786
LOG   = REPO / "tests" / ".tall_pipe_hop.log"

# Object geometry (m) — from blender_create_smb.py
ENTRY_PIPE_TOP_L, ENTRY_PIPE_TOP_R, ENTRY_PIPE_TOP_Z = 69.0, 72.0, 4.5
BRICK_L, BRICK_R, BRICK_TOP_Z = 84.75, 86.25, 7.5
PIPE64_L, PIPE64_R, PIPE64_TOP_Z = 94.5, 97.5, 6.0

X_POS, Y_POS, Z_POS = 3009, 3010, 3011
XSPEED, ZSPEED = 3018, 3020
LIVES, SMB_STAR_UNTIL = 72, 1818
JOY_RIGHT, BTN_JUMP = 0x2000, 0x0001

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
for mb in (X_POS, Y_POS, Z_POS, XSPEED, ZSPEED):
    cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.2)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=20, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))
def gx(): return g(X_POS)
def gz(): return g(Z_POS)
def gvx(): return g(XSPEED)

def teleport(x, z, wait=0.6):
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=x, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=z, idx=PLAYER)
    time.sleep(wait)

def run_and_jump(jump_x, label, settle_timeout=3.0):
    """Hold RIGHT from current pos; fire JUMP when X>=jump_x; track peak + landing."""
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    t = time.monotonic() + 8.0
    while time.monotonic() < t:
        x = gx()
        if x is not None and x >= jump_x: break
        time.sleep(0.015)
    vx_launch = gvx() or 0.0
    x0, z0 = gx(), gz()
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT | BTN_JUMP, duration_frames=-1)
    print(f"  [{label}] JUMP at X={x0:.2f} Z={z0:.2f} Vx={vx_launch:.2f}")
    # hold jump button ~0.45s for near-max height, keep RIGHT held to sustain momentum
    peak_z, t_apex = z0 or 0.0, time.monotonic()
    while time.monotonic() - t_apex < 0.45:
        z = gz()
        if z and z > peak_z: peak_z = z
        time.sleep(0.015)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    # track until landed (Z stops changing) or timeout
    deadline = time.monotonic() + settle_timeout
    last_z, stable = None, 0
    while time.monotonic() < deadline:
        z, x = gz(), gx()
        if z and z > peak_z: peak_z = z
        if z is not None and last_z is not None and abs(z - last_z) < 0.01:
            stable += 1
            if stable >= 6: break
        else:
            stable = 0
        last_z = z
        time.sleep(0.03)
    return gx(), gz(), peak_z

print(f"\n=== HOP A: entry_pipe top → brick_1up (target Z~{BRICK_TOP_Z}, X {BRICK_L}-{BRICK_R}) ===")
cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
teleport(ENTRY_PIPE_TOP_L + 0.3, ENTRY_PIPE_TOP_Z + 0.2)   # left edge of pipe top, full runway
xa, za, pa = run_and_jump(jump_x=ENTRY_PIPE_TOP_R - 0.2, label="pipe→brick")
on_brick = za > 6.5 and (BRICK_L - 1.0) <= xa <= (BRICK_R + 1.0)
print(f"  landed X={xa:.2f} Z={za:.2f} peak={pa:.2f}  "
      f"{'*** ON BRICK ***' if on_brick else ('on ground' if za < 1.0 else 'elevated')}")

print(f"\n=== HOP B: brick_1up top → over pipe_64 (clear past X>{PIPE64_R}) ===")
cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
teleport((BRICK_L + BRICK_R) / 2, BRICK_TOP_Z + 0.25)      # centred on the brick
xb, zb, pb = run_and_jump(jump_x=(BRICK_L + BRICK_R) / 2 + 0.1, label="brick→pipe64")
cleared = xb > PIPE64_R
on_pipe = PIPE64_L <= xb <= PIPE64_R and zb > 5.0
print(f"  landed X={xb:.2f} Z={zb:.2f} peak={pb:.2f}  "
      f"{'*** CLEARED pipe_64 ***' if cleared else ('landed on pipe_64 top' if on_pipe else 'BLOCKED / short')}")

print("\n=== RESULT ===")
print(f"  HOP A (pipe→brick):  {'PASS' if on_brick else 'FAIL'}")
print(f"  HOP B (brick→pipe64): {'PASS' if (cleared or on_pipe) else 'FAIL'}")

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.3)
cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print("Done.")
