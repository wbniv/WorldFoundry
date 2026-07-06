#!/usr/bin/env python3
"""Measure Mario's actual running speed and max jump height in WF."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient

REPO   = Path(__file__).resolve().parent.parent
WF     = REPO / "engine" / "wf_game"
LEVEL  = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB    = REPO / "engine" / "libs"
CWD    = REPO / "wfsource" / "source" / "game"
PORT   = 7785
import subprocess, re, signal

_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")
LOG_PATH = REPO / "tests" / ".phys_diag.log"

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"
env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG_PATH, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
     "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)
time.sleep(2.0)

def discover_player(timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for m in _MESH_RE.finditer(LOG_PATH.read_text(errors="replace")):
                if "player" in m.group(2):
                    return int(m.group(1))
        except OSError:
            pass
        time.sleep(0.1)
    return 9

X_POS  = 3009
Z_POS  = 3011
XSPEED = 3018
ZSPEED = 3020
LIVES  = 72
SMB_STAR_UNTIL = 1818
JOY_RIGHT = 0x2000
BTN_JUMP  = 0x0001

PLAYER = discover_player()
print(f"player idx={PLAYER}")

cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
print("connected")

cli.watch(idx=PLAYER, mailbox=X_POS)
cli.watch(idx=PLAYER, mailbox=Z_POS)
cli.watch(idx=PLAYER, mailbox=XSPEED)
cli.watch(idx=PLAYER, mailbox=ZSPEED)
time.sleep(1.5)

cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=10, idx=1)

def gx():
    with cli._lock: return cli.mailbox_values.get((PLAYER, X_POS))
def gz():
    with cli._lock: return cli.mailbox_values.get((PLAYER, Z_POS))
def gvx():
    with cli._lock: return cli.mailbox_values.get((PLAYER, XSPEED))
def gvz():
    with cli._lock: return cli.mailbox_values.get((PLAYER, ZSPEED))

# ── Phase 1: measure steady-state running speed ──────────────────────────────
print("\n=== Phase 1: steady-state running speed ===")
cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
time.sleep(0.5)  # let Mario settle to steady state

samples = []
t0 = time.monotonic()
for _ in range(20):
    time.sleep(0.1)
    vx = gvx(); x = gx(); z = gz()
    samples.append((time.monotonic()-t0, x, z, vx))
    print(f"  t={time.monotonic()-t0:.2f}  X={x:.3f}  Z={z:.3f}  Vx={vx:.3f}")

# Calculate speed from position delta
x_start = samples[5][1]  # skip first 5 (still accelerating)
x_end   = samples[-1][1]
t_start = samples[5][0]
t_end   = samples[-1][0]
if x_start and x_end and t_end > t_start:
    speed = (x_end - x_start) / (t_end - t_start)
    print(f"  >> Steady-state running speed: {speed:.3f} m/s")

# ── Phase 2: measure max jump height ─────────────────────────────────────────
print("\n=== Phase 2: max jump height ===")
time.sleep(0.3)
cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
time.sleep(0.2)  # settle on ground

jump_start_x = gx()
jump_start_z = gz()
print(f"  Jump start: X={jump_start_x:.3f} Z={jump_start_z:.3f}")

# Fire max-hold jump
cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT | BTN_JUMP, duration_frames=-1)
t_jump = time.monotonic()
max_z = 0.0
peak_time = 0.0
samples2 = []
while time.monotonic() - t_jump < 2.0:
    time.sleep(0.02)
    z = gz(); vz = gvz(); x = gx()
    elapsed = time.monotonic() - t_jump
    if z is not None and z > max_z:
        max_z = z
        peak_time = elapsed
    samples2.append((elapsed, x, z, vz))
    if elapsed > 0.25:  # hold for 0.25s to get near-max jump
        cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)

print(f"  Max Z reached: {max_z:.3f} m at t={peak_time:.3f}s")
for s in samples2[:25]:
    print(f"    t={s[0]:.3f}  X={s[1]:.3f}  Z={s[2]:.3f}  Vz={s[3]:.3f}")

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.5)

cli.close()
proc.send_signal(signal.SIGTERM)
try:    proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print("\nDone.")
