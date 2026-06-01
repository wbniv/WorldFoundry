#!/usr/bin/env python3
"""Find the launch speed that carries Mario from the entry_pipe edge onto brick_1up.

Decouples "what launch speed is needed" from "what Running Deceleration yields it".
Teleports Mario to the pipe's right-edge height, injects a known X velocity + the
jump's Z velocity while RIGHT is held (air "sustain" keeps Vx), and reports where he
lands.  Sweeps launch speeds so we can read the speed→landing-X relationship directly.

brick_1up top: Z=7.5, X 84.75-86.25.  pipe_64 top: Z=6.0, X 94.5-97.5.
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
PORT  = 7787
LOG   = REPO / "tests" / ".probe_launch.log"

ENTRY_PIPE_TOP_R, ENTRY_PIPE_TOP_Z = 72.0, 4.5
BRICK_L, BRICK_R, BRICK_TOP_Z = 84.75, 86.25, 7.5
JUMP_VZ = 10.95          # measured jump take-off Vz

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
for mb in (X_POS, Z_POS, XSPEED, ZSPEED):
    cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.0)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=50, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))

def launch_from_edge(vx):
    """Place Mario airborne at the pipe right edge, inject (vx, JUMP_VZ), RIGHT held."""
    # park still first
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=ENTRY_PIPE_TOP_R - 0.1, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=ENTRY_PIPE_TOP_Z + 0.3, idx=PLAYER)
    time.sleep(0.4)
    # hold RIGHT (sustain), then inject the launch velocities
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    cli.set_mailbox(mailbox=ZSPEED, value=JUMP_VZ, idx=PLAYER)
    cli.set_mailbox(mailbox=XSPEED, value=float(vx), idx=PLAYER)
    # track arc → landing
    peak_z = g(Z_POS) or 0.0
    deadline = time.monotonic() + 4.0
    last_z, stable = None, 0
    while time.monotonic() < deadline:
        z, x = g(Z_POS), g(X_POS)
        if z and z > peak_z: peak_z = z
        if z is not None and last_z is not None and abs(z - last_z) < 0.01:
            stable += 1
            if stable >= 6: break
        else:
            stable = 0
        last_z = z
        time.sleep(0.03)
    return g(X_POS), g(Z_POS), peak_z

print(f"\nlaunch from X={ENTRY_PIPE_TOP_R - 0.1} Z={ENTRY_PIPE_TOP_Z + 0.3}, Vz={JUMP_VZ}")
print(f"brick top: Z={BRICK_TOP_Z}, X {BRICK_L}-{BRICK_R}\n")
print(f"{'Vx':>5} {'land_X':>8} {'land_Z':>8} {'peak_Z':>8}  verdict")
for vx in (7.0, 8.0, 8.5, 9.0, 9.5, 10.0, 11.0, 12.0):
    lx, lz, pz = launch_from_edge(vx)
    lx = lx if lx is not None else float('nan')
    lz = lz if lz is not None else float('nan')
    on_brick = (lz is not None and lz > 6.5 and (BRICK_L - 0.6) <= lx <= (BRICK_R + 0.6))
    verdict = "*** ON BRICK ***" if on_brick else ("ground/short" if (lz or 0) < 1 else f"elevated@{lz:.1f}")
    print(f"{vx:>5.1f} {lx:>8.2f} {lz:>8.2f} {pz:>8.2f}  {verdict}")

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.2)
cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print("Done.")
