#!/usr/bin/env python3
"""Test the pipe→brick→pipe_64 hop sequence by teleporting Mario to each step."""
from __future__ import annotations
import os, sys, time, re, signal, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient

REPO   = Path(__file__).resolve().parent.parent
WF     = REPO / "engine" / "wf_game"
LEVEL  = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB    = REPO / "engine" / "libs"
CWD    = REPO / "wfsource" / "source" / "game"
PORT   = 7785
LOG    = REPO / "tests" / ".pipe_hop.log"

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"
env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
     "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)
time.sleep(2.0)

def discover_player(timeout=10.0):
    deadline = time.time() + timeout
    _re = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")
    while time.time() < deadline:
        try:
            for m in _re.finditer(LOG.read_text(errors="replace")):
                if "player" in m.group(2): return int(m.group(1))
        except OSError: pass
        time.sleep(0.1)
    return 9

X_POS = 3009; Y_POS = 3010; Z_POS = 3011
XSPEED = 3018; ZSPEED = 3020
LIVES = 72; SMB_STAR_UNTIL = 1818
JOY_RIGHT = 0x2000; BTN_JUMP = 0x0001

PLAYER = discover_player()
print(f"player idx={PLAYER}")
cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
print("connected")

for mb in [X_POS, Y_POS, Z_POS, XSPEED, ZSPEED]:
    cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.5)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=10, idx=1)

def gx():
    with cli._lock: return cli.mailbox_values.get((PLAYER, X_POS))
def gy():
    with cli._lock: return cli.mailbox_values.get((PLAYER, Y_POS))
def gz():
    with cli._lock: return cli.mailbox_values.get((PLAYER, Z_POS))
def gvx():
    with cli._lock: return cli.mailbox_values.get((PLAYER, XSPEED))
def gvz():
    with cli._lock: return cli.mailbox_values.get((PLAYER, ZSPEED))

def teleport(x, z, wait=0.5):
    """Teleport Mario to (x, 0, z), zero velocities."""
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS,  value=x,   idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS,  value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS,  value=z,   idx=PLAYER)
    time.sleep(wait)
    print(f"  teleported → X={gx():.3f} Z={gz():.3f}")

def wait_settled(timeout=2.0):
    """Wait until Mario's Z stops changing (landed)."""
    deadline = time.monotonic() + timeout
    last_z = None
    while time.monotonic() < deadline:
        z = gz(); x = gx()
        if z is not None and last_z is not None and abs(z - last_z) < 0.005:
            return x, z
        last_z = z
        time.sleep(0.05)
    return gx(), gz()

def do_jump(trigger_x, hold_s, label=""):
    """Hold RIGHT, fire jump at trigger_x, hold for hold_s, track arc."""
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    # Wait until Mario reaches trigger_x
    timeout = time.monotonic() + 10.0
    while time.monotonic() < timeout:
        x = gx()
        if x is not None and x >= trigger_x:
            break
        time.sleep(0.02)
    t0 = time.monotonic()
    print(f"  [{label}] JUMP at X={gx():.3f} Z={gz():.3f}")
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT | BTN_JUMP, duration_frames=-1)
    max_z = gz() or 0.0
    while time.monotonic() - t0 < hold_s:
        z = gz()
        if z and z > max_z: max_z = z
        time.sleep(0.02)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    # Track for 3 seconds
    for _ in range(60):
        time.sleep(0.05)
        z = gz()
        if z and z > max_z: max_z = z
    x_land, z_land = wait_settled()
    print(f"  [{label}] peak_Z={max_z:.3f}  landed X={x_land:.3f} Z={z_land:.3f}  Vx={gvx():.3f}")
    return x_land, z_land

print("\n=== Test 1: entry_pipe top (teleport) → run right, measure speed ===")
# Entry pipe top: X=70.5, Z=4.5+0.2=4.7 (slightly above surface)
cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
teleport(70.5, 4.7)
# Measure running speed on top of the pipe
cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
x0 = gx(); t0 = time.monotonic()
time.sleep(0.5)
x1 = gx(); t1 = time.monotonic()
time.sleep(0.5)
x2 = gx(); t2 = time.monotonic()
if x0 and x1 and x2:
    print(f"  Speed on pipe: {(x1-x0)/(t1-t0):.2f} m/s (0-0.5s)  {(x2-x0)/(t2-t0):.2f} m/s (0-1s)")
cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)

print("\n=== Test 2: from pipe top, jump toward brick_1up (X=85.5m, Z=7.5m top) ===")
# Teleport to entry_pipe right edge, run and jump
cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
teleport(71.0, 4.7)
time.sleep(0.3)
# Try different holds to see if we can reach brick height
for hold in [0.25, 0.40, 0.60]:
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
    teleport(71.0, 4.7)
    time.sleep(0.3)
    x_land, z_land = do_jump(trigger_x=71.1, hold_s=hold, label=f"pipe→brick hold={hold}s")
    if z_land > 6.0:
        print(f"  *** LANDED ON ELEVATED SURFACE (Z={z_land:.3f}) ***")
    elif z_land > 4.0:
        print(f"  *** LANDED ON PIPE AGAIN (Z={z_land:.3f}) ***")

print("\n=== Test 3: from brick top (teleport), jump toward pipe_64 ===")
cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
teleport(84.0, 7.7)  # brick top: X=85.5 center, top=7.5m → teleport just before
time.sleep(0.3)
x_land, z_land = do_jump(trigger_x=84.1, hold_s=0.25, label="brick→pipe_64")
print(f"  After brick jump: X={x_land:.3f} Z={z_land:.3f}")
if x_land > 94.5:
    print("  *** CLEARED pipe_64! ***")
elif x_land > 88.0:
    print("  *** past brick, but blocked by pipe_64 at X=94.5m ***")

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.3)
cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print("\nDone.")
