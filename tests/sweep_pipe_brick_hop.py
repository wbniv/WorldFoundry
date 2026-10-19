#!/usr/bin/env python3
"""Sweep REAL engine jumps for the entry_pipe→brick_1up hop (the crux).

For each (jump trigger X on the pipe top, jump-button hold time), stand Mario on
the pipe, hold RIGHT, fire a genuine engine jump, and record the landing.  Reports
every combo that lands ON the brick (Z>6.5, X in brick span) so we can see the
achievable set without rebuilding.  RIGHT stays held throughout (air sustain).

brick_1up top: Z=7.5, X 84.75-86.25.
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
PORT  = 7788
LOG   = REPO / "tests" / ".sweep_hop.log"

PIPE_TOP_L, PIPE_TOP_R, PIPE_TOP_Z = 69.0, 72.0, 4.5
BRICK_L, BRICK_R, BRICK_TOP_Z = 84.75, 86.25, 7.5

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
for mb in (X_POS, Z_POS, XSPEED):
    cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.0)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=80, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))

def hop(start_x, trigger_x, hold_s):
    # park on the pipe top, still
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=start_x, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=PIPE_TOP_Z + 0.2, idx=PLAYER)
    time.sleep(0.5)
    # run right
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    t = time.monotonic() + 5.0
    while time.monotonic() < t:
        x = g(X_POS)
        if x is not None and x >= trigger_x: break
        time.sleep(0.008)
    vx_launch = g(XSPEED) or 0.0
    jx = g(X_POS)
    # genuine jump: press JUMP+RIGHT, hold, then release JUMP (keep RIGHT)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT | BTN_JUMP, duration_frames=-1)
    time.sleep(hold_s)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    # track to landing
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
        time.sleep(0.03)
    return jx, vx_launch, g(X_POS), g(Z_POS), peak_z

print(f"\nbrick top: Z={BRICK_TOP_Z}, X {BRICK_L}-{BRICK_R}")
print(f"{'trig':>5} {'hold':>5} {'jumpX':>7} {'Vx':>6} {'landX':>7} {'landZ':>7} {'peakZ':>7}  verdict")
hits = []
for trigger_x in (71.0, 71.4, 71.7, 71.9):
    for hold_s in (0.12, 0.18, 0.25, 0.35):
        jx, vx, lx, lz, pz = hop(PIPE_TOP_L + 0.2, trigger_x, hold_s)
        jx = jx or float('nan'); lx = lx or float('nan'); lz = lz if lz is not None else float('nan')
        on_brick = lz > 6.5 and (BRICK_L - 0.5) <= lx <= (BRICK_R + 0.5)
        verdict = "*** ON BRICK ***" if on_brick else ("ground" if lz < 1 else f"elev@{lz:.1f}")
        if on_brick: hits.append((trigger_x, hold_s, lx, lz))
        print(f"{trigger_x:>5.1f} {hold_s:>5.2f} {jx:>7.2f} {vx:>6.2f} {lx:>7.2f} {lz:>7.2f} {pz:>7.2f}  {verdict}")

print(f"\nbrick landings: {len(hits)}")
for h in hits: print(f"  trigger={h[0]} hold={h[1]} -> X={h[2]:.2f} Z={h[3]:.2f}")

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.2)
cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print("Done.")
