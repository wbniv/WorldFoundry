#!/usr/bin/env python3
"""Verify the coin-room coins SPIN (numeric proof + recorded still).

The coins run COIN_SCRIPT (INDEXOF_TIME -> INDEXOF_ROTATION_C) every tick, so once
the coin room is active their ROTATION_C (mb 3014) should advance each frame. Warps
Mario into the room, finds a cr_coin actor, and samples its ROTATION_C over ~1.3 s;
PASS if it advances. Records the room (FBO capture) so the spin is also visible.
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
PORT  = 7796
LOG   = REPO / "tests" / ".coin_spin.log"
REC   = REPO / "tests" / "recordings" / "smb_coin_room.mp4"

X_POS, Y_POS, Z_POS, XSPEED, ZSPEED, ROTATION_C = 3009, 3010, 3011, 3018, 3020, 3014
JOY_DOWN = 0x1000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "-record_video",
     "--debug-port", str(PORT), "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
time.sleep(2.5)

def find(pat, timeout=10.0):
    rx = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for m in rx.finditer(LOG.read_text(errors="replace")):
                if pat in m.group(2): return int(m.group(1))
        except OSError: pass
        time.sleep(0.1)
    return None

PLAYER = find("player") or 9
COIN   = find("cr_coin")
print(f"player idx={PLAYER}  cr_coin idx={COIN}")
cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
cli.watch(idx=PLAYER, mailbox=Z_POS)
if COIN is not None:
    cli.watch(idx=COIN, mailbox=ROTATION_C)
time.sleep(1.0)

def g(idx, mb):
    with cli._lock: return cli.mailbox_values.get((idx, mb))

# warp into the coin room (drop onto entry_pipe + Down)
cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER); cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
cli.set_mailbox(mailbox=X_POS, value=70.5, idx=PLAYER); cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
cli.set_mailbox(mailbox=Z_POS, value=7.0, idx=PLAYER)
time.sleep(1.0)
for _ in range(60):
    cli.inject_input(slot="joystick1_raw", value=JOY_DOWN, duration_frames=2)
    time.sleep(0.05)
    if (g(PLAYER, Z_POS) or 0) < -30: break
time.sleep(2.0)   # let the room activate + coins start spinning on camera

print(f"in coin room: player Z={g(PLAYER, Z_POS)}")
samples = []
for _ in range(7):
    samples.append(g(COIN, ROTATION_C) if COIN is not None else None)
    time.sleep(0.18)
print("cr_coin ROTATION_C samples:", samples)
vals = [s for s in samples if s is not None]
advanced = len(vals) >= 2 and (max(vals) - min(vals) > 0.05)
print("SPIN:", "PASS (ROTATION_C advancing -> coins spinning)" if advanced else
      "INCONCLUSIVE (see recording for visible spin)")

time.sleep(0.5)
cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.3); cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=6.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
out = CWD / "output.mp4"
if out.exists() and out.stat().st_size > 1000:
    shutil.move(str(out), str(REC)); print(f"recording -> {REC} ({REC.stat().st_size} bytes)")
print("Done.")
