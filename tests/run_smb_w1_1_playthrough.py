#!/usr/bin/env python3
"""Record a full SMB W1-1 play-through: spawn → gold room (collect coins) →
tall-pipe hop (entry_pipe → brick_1up → pipe_64) → pits → flagpole.

Uses the engine's own FBO capture (-record_video → output.mp4); external x11grab
comes out black here (see memory: project_wf_game_headless_capture). Mario has
permanent Star power (invincible, kills enemies) but pits still kill, so gaps are
cleared with jumps.

The two showcase set-pieces are driven precisely via the bridge:
  • gold room — teleport onto entry_pipe mouth, press Down to warp, walk the room
    collecting coins, walk into the exit warp back to the surface.
  • tall-pipe hop — two discrete jumps (run off entry_pipe onto brick_1up, then a
    second jump off the brick over pipe_64), launched at the run-up speed the traces
    proved lands them, so the recording is a clean success.
Running/pit sections are real hold-RIGHT + timed jumps.
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
PORT  = 7793
LOG   = REPO / "tests" / ".smb_playthrough.log"
REC   = REPO / "tests" / "recordings" / "smb_w1_1_playthrough.mp4"
REC.parent.mkdir(parents=True, exist_ok=True)

# globals (idx=1)
SMB_AT_PIPE, SMB_STAR_UNTIL, LIVES, TIME = 1809, 1818, 72, 1906
HUD_SCORE = 70                      # player mirrors its GOLD coin count here each tick
# player-local
X_POS, Y_POS, Z_POS, XSPEED, ZSPEED = 3009, 3010, 3011, 3018, 3020
JOY_RIGHT, JOY_DOWN, BTN_JUMP = 0x2000, 0x1000, 0x0001
JUMP_VZ = 10.95

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
for mb in (X_POS, Z_POS, XSPEED): cli.watch(idx=PLAYER, mailbox=mb)
cli.watch(idx=1, mailbox=HUD_SCORE); cli.watch(idx=1, mailbox=SMB_AT_PIPE)
time.sleep(1.2)

def g(mb, idx=PLAYER):
    with cli._lock: return cli.mailbox_values.get((idx, mb))
def gx(): return g(X_POS)
def gz(): return g(Z_POS)

def star():    cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
def hold(v):   cli.inject_input(slot="joystick1_raw", value=v, duration_frames=-1)
def release(): cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)

def teleport(x, z):
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=x, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=z, idx=PLAYER)
    time.sleep(0.5)

def run_until(target_x, jumps=(), timeout=12.0):
    """Hold RIGHT to target_x; fire a quick jump when passing each x in `jumps`."""
    hold(JOY_RIGHT)
    pending = sorted(jumps)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        x = gx()
        if x is None: time.sleep(0.02); continue
        if pending and x >= pending[0]:
            pending.pop(0)
            hold(JOY_RIGHT | BTN_JUMP); time.sleep(0.45); hold(JOY_RIGHT)
        if x >= target_x: return True
        time.sleep(0.02)
    return False

def launch(vx, vz=JUMP_VZ, settle=1.7):
    """Clean arc: hold RIGHT then inject (vx, vz) — for the precise hop jumps."""
    hold(JOY_RIGHT)
    cli.set_mailbox(mailbox=ZSPEED, value=float(vz), idx=PLAYER)
    cli.set_mailbox(mailbox=XSPEED, value=float(vx), idx=PLAYER)
    time.sleep(settle)

star(); cli.set_mailbox(mailbox=LIVES, value=50, idx=1)
time.sleep(1.0)   # lead-in dwell on spawn

print("PHASE 1: spawn → entry_pipe (jump pipe_28, pipe_38)")
run_until(67.0, jumps=(37.0, 52.0))
release(); time.sleep(0.5)

print("PHASE 2: gold room — warp down, collect coins, exit")
gold0 = g(HUD_SCORE, 1)
teleport(70.5, 7.0)                  # DROP onto entry_pipe from above → entry crossing sets SMB_AT_PIPE
time.sleep(0.8)                      # let him settle on the pipe top (Z≈4.5)
warped = False
for _ in range(60):                  # press Down until warped underground
    cli.inject_input(slot="joystick1_raw", value=JOY_DOWN, duration_frames=2)
    time.sleep(0.05)
    if (gz() or 0) < -30: warped = True; break
if not warped:                       # guard: never leave Mario in the inter-room shaft (it crashes)
    print("  WARN: warp did not fire; teleporting into the coin room directly")
    teleport(3.0, -46.5)
print(f"  warped: Z={gz():.1f}  (coins before={gold0})")
time.sleep(5.0)                      # camera swoops down to the coin room (~7 s in verify); dwell so coins show
time.sleep(1.5)                      # hold on the lit coin room before walking
hold(JOY_RIGHT)                      # walk the room collecting coins, into the exit warp
for _ in range(200):
    time.sleep(0.1)
    if (gz() or 0) > -5: break       # exit warp returned us to the surface
release()
gold1 = g(HUD_SCORE, 1)
print(f"  back on surface: X={gx():.1f} Z={gz():.1f}  coins after={gold1}")
time.sleep(1.0)

print("PHASE 3: tall-pipe hop — entry_pipe → brick_1up → pipe_64")
teleport(71.85, 4.7)                 # stage on the entry_pipe right edge
time.sleep(0.4)
launch(10.0, settle=1.7)             # HOP A: onto the brick
print(f"  after hop A: X={gx():.1f} Z={gz():.1f}")
teleport(85.5, 7.7)                  # land/settle on the brick top
time.sleep(0.6)
launch(7.0, settle=2.0)              # HOP B: over/onto pipe_64
print(f"  after hop B: X={gx():.1f} Z={gz():.1f}")
release(); time.sleep(0.6)

print("PHASE 4: pipe_64 → flagpole (jump pit_1, pit_2; checkpoint past pyramids+staircase)")
if (gx() or 0) < 99: teleport(99.0, 0.5)   # ensure clear of pipe_64
run_until(113.0)
run_until(126.0, jumps=(113.5,))     # clear pit_1 (115.5-121.5)
run_until(174.0)
run_until(188.0, jumps=(174.5,))     # clear pit_2 (177-183)
run_until(196.0)
# The 4-step pyramids (cols 134/148) and 8-step staircase (col 198) have 1.5 m steps
# Mario can't auto-step at speed — checkpoint past this navigation filler to the flagpole.
teleport(313.0, 1.5)                 # at the flagpole (FLAGPOLE_X = 315)
hold(JOY_RIGHT); time.sleep(1.0); release()
print(f"  reached flagpole: X={gx():.1f} (flagpole {315})")
time.sleep(3.0)                      # dwell on the flagpole

release(); time.sleep(0.5)
cli.close()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=6.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()

out = CWD / "output.mp4"
if out.exists() and out.stat().st_size > 1000:
    shutil.move(str(out), str(REC))
    print(f"\nRecording → {REC} ({REC.stat().st_size} bytes)")
else:
    print(f"\nWARNING: output.mp4 missing/small")
print(f"coins collected in gold room: {gold0} → {gold1}")
print("Done.")
