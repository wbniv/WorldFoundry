#!/usr/bin/env python3
"""Diagnose whether standing on the 3T entry_pipe triggers SMB_AT_PIPE + the warp.

Suspect: pipe_entry_sense band is [2.8,4.0] (authored for the old 2T pipe) but
entry_pipe is now 3T (top 4.5), so a player on top is above the band → no trigger.
Uses pause/step so the ActBox gets clean frames to detect the overlap.
"""
from __future__ import annotations
import os, sys, time, re, subprocess, signal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7794
LOG   = REPO / "tests" / ".diag_warp.log"
SMB_AT_PIPE = 1809
X_POS, Y_POS, Z_POS, XSPEED, ZSPEED = 3009, 3010, 3011, 3018, 3020
JOY_DOWN = 0x1000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"

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
cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
cli.watch(idx=1, mailbox=SMB_AT_PIPE)
for mb in (X_POS, Z_POS): cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.0)
def g(mb, idx=PLAYER):
    with cli._lock: return cli.mailbox_values.get((idx, mb))

print(f"player idx={PLAYER}")
# DROP Mario onto the pipe from ABOVE the sense band so he crosses INTO it (entry event),
# like a real jump-onto-pipe — placing him already-inside does not fire entry actboxes.
cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
cli.set_mailbox(mailbox=X_POS, value=70.5, idx=PLAYER)
cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
cli.set_mailbox(mailbox=Z_POS, value=7.0, idx=PLAYER)   # above band → falls in
seen = 0
for _ in range(60):
    time.sleep(0.03)
    if g(SMB_AT_PIPE, 1) == 1: seen += 1
print(f"  drop-onto-pipe: settled Z={g(Z_POS):.2f}  SMB_AT_PIPE set on {seen}/60 polls")

warped_z = None
for _ in range(80):
    cli.inject_input(slot="joystick1_raw", value=JOY_DOWN, duration_frames=2)
    time.sleep(0.03)
    z = g(Z_POS)
    if z is not None and z < -30: warped_z = z; break
print(f"  Down-warp result: {'WARPED to Z=%.1f' % warped_z if warped_z else 'NO WARP (stuck on surface)'}")

cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print("Done.")
