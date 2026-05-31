#!/usr/bin/env python3
"""Record the pipe->brick->pipe_64 hop with the engine's own FBO capture (-record_video),
which is immune to X11 occlusion (external x11grab came out black here).

Drives a clean arc with the launch velocity the trajectory traces proved lands ON the
brick (~9.3 m/s), pauses on the brick, then launches over pipe_64.  Output -> output.mp4
in the game CWD, moved to tests/recordings/smb_tall_pipe_hop.mp4.
"""
from __future__ import annotations
import os, sys, time, re, signal, subprocess, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7792
LOG   = REPO / "tests" / ".record_hop.log"
REC   = REPO / "tests" / "recordings" / "smb_tall_pipe_hop.mp4"
REC.parent.mkdir(parents=True, exist_ok=True)

PIPE_EDGE_X, PIPE_Z = 71.85, 4.65
BRICK_C, BRICK_TOP_Z = 85.5, 7.5
JUMP_VZ = 10.95
X_POS, Y_POS, Z_POS, XSPEED, ZSPEED = 3009, 3010, 3011, 3018, 3020
LIVES, SMB_STAR_UNTIL, JOY_RIGHT = 72, 1818, 0x2000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"
env["WF_GAME_SCREENSHOT_PPM"] = str(REPO / "tests" / "screenshots" / "smb_tall_pipe_hop.ppm")
(REPO / "tests" / "screenshots").mkdir(parents=True, exist_ok=True)

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "-record_video",
     "--debug-port", str(PORT), "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
time.sleep(2.5)

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
for mb in (X_POS, Z_POS): cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.0)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=50, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))

def launch(x, z, vx, vz, settle=1.6):
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=x, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=z, idx=PLAYER)
    time.sleep(0.5)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    cli.set_mailbox(mailbox=ZSPEED, value=float(vz), idx=PLAYER)
    cli.set_mailbox(mailbox=XSPEED, value=float(vx), idx=PLAYER)
    t0 = time.monotonic(); peak = g(Z_POS) or 0.0
    while time.monotonic() - t0 < settle:
        z = g(Z_POS)
        if z and z > peak: peak = z
        time.sleep(0.03)
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
    return g(X_POS), g(Z_POS), peak

# let camera settle on spawn, then dwell so the recording has lead-in
time.sleep(1.5)
print("HOP A: pipe edge -> brick")
ax, az, ap = launch(PIPE_EDGE_X, PIPE_Z, 9.4, JUMP_VZ, settle=1.8)
print(f"  -> X={ax:.2f} Z={az:.2f} peak={ap:.2f}")
time.sleep(1.2)
print("HOP B: brick -> over pipe_64")
bx, bz, bp = launch(BRICK_C, BRICK_TOP_Z + 0.1, 7.0, JUMP_VZ, settle=2.0)
print(f"  -> X={bx:.2f} Z={bz:.2f} peak={bp:.2f}")
time.sleep(1.0)

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.4)
cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=6.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()

out = CWD / "output.mp4"
if out.exists() and out.stat().st_size > 1000:
    shutil.move(str(out), str(REC))
    print(f"Recording -> {REC} ({REC.stat().st_size} bytes)")
else:
    print(f"WARNING: output.mp4 missing/small ({out.exists()})")
ppm = Path(env["WF_GAME_SCREENSHOT_PPM"])
print(f"PPM screenshot: {ppm if ppm.exists() else 'NOT WRITTEN'}"
      + (f" ({ppm.stat().st_size} bytes)" if ppm.exists() else ""))
print("Done.")
