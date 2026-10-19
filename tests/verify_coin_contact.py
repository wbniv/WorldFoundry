#!/usr/bin/env python3
"""Verify the coin-room fix: TRUE XZ-contact pickup + spinning coins.

Warps Mario into the underground coin room, then:
  A. teleport to the FLOOR under a coin column -> GOLD must NOT rise (the coins
     float 5-11 m overhead; the old X-only gate wrongly collected them).
  B. teleport onto a coin -> GOLD rises by exactly that coin (contact).
Records the room (via the engine FBO capture) so the spin is visible.
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
PORT  = 7795
LOG   = REPO / "tests" / ".coin_contact.log"
REC   = REPO / "tests" / "recordings" / "smb_coin_room.mp4"
REC.parent.mkdir(parents=True, exist_ok=True)

GOLD = 3001                      # EMAILBOX_GOLD (per-actor, on the player)
X_POS, Y_POS, Z_POS, XSPEED, ZSPEED = 3009, 3010, 3011, 3018, 3020
JOY_DOWN = 0x1000
SMB_STAR_UNTIL, LIVES = 1818, 72

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

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
for mb in (X_POS, Z_POS, GOLD): cli.watch(idx=PLAYER, mailbox=mb)
time.sleep(1.0)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=50, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))

def tp(x, z, wait=0.7):
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=x, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=z, idx=PLAYER)
    time.sleep(wait)

# Warp into the coin room: drop onto the entry_pipe mouth, press Down.
tp(70.5, 7.0, 1.0)
for _ in range(60):
    cli.inject_input(slot="joystick1_raw", value=JOY_DOWN, duration_frames=2)
    time.sleep(0.05)
    if (g(Z_POS) or 0) < -30: break
time.sleep(5.0)   # camera pan + let coins spin on camera
print(f"in coin room: Z={g(Z_POS):.1f}  GOLD={g(GOLD)}")

results = []
# A. floor under column 4.5 (coins 0 @z-41.25 and 7 @z-38.25 overhead) — NO collect
g0 = g(GOLD)
tp(6.75, -46.5)
gA = g(GOLD)
results.append(("floor under col 4.5 (no contact)", g0, gA, gA == g0))
print(f"  A floor (6.75,-46.5): GOLD {g0} -> {gA}  {'PASS (no pickup)' if gA==g0 else 'FAIL'}")

# B. onto coin 14 (top row, 8.25,-35.25) — the worst old-bug case (collected from floor by X)
g1 = g(GOLD)
tp(8.25, -35.25)
gB = g(GOLD)
results.append(("touch coin 14 (top row)", g1, gB, gB > g1))
print(f"  B touch coin14 (8.25,-35.25): GOLD {g1} -> {gB}  {'PASS (+contact)' if gB>g1 else 'FAIL'}")

# C. onto coin 0 (low row, 6.75,-41.25)
g2 = g(GOLD)
tp(6.75, -41.25)
gC = g(GOLD)
results.append(("touch coin 0 (low row)", g2, gC, gC > g2))
print(f"  C touch coin0 (6.75,-41.25): GOLD {g2} -> {gC}  {'PASS (+contact)' if gC>g2 else 'FAIL'}")

time.sleep(1.0)
print("RESULT:", "ALL PASS" if all(r[3] for r in results) else "FAIL " + str([r[0] for r in results if not r[3]]))

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.4); cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=6.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
out = CWD / "output.mp4"
if out.exists() and out.stat().st_size > 1000:
    shutil.move(str(out), str(REC)); print(f"recording -> {REC} ({REC.stat().st_size} bytes)")
print("Done.")
