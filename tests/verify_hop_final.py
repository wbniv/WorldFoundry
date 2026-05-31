#!/usr/bin/env python3
"""Final verification + recording of the entry_pipe -> brick_1up -> pipe_64 hop.

Fully real inputs (run-up + jump button, no velocity injection).  Records the
session to tests/recordings/smb_tall_pipe_hop.mp4 and reports, per jump trigger,
whether Mario lands ON the brick (Z plateau ~7.5 while X advances past 84) and
whether a follow-up jump clears pipe_64 (reaches X>97.5).

Geometry (canonical): entry_pipe top Z=4.5 X69-72 | brick_1up top Z=7.5 X84.75-86.25 | pipe_64 top Z=6.0 X94.5-97.5
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
PORT  = 7791
LOG   = REPO / "tests" / ".verify_hop_final.log"
REC   = REPO / "tests" / "recordings" / "smb_tall_pipe_hop.mp4"
REC.parent.mkdir(parents=True, exist_ok=True)

PIPE_L, PIPE_R, PIPE_Z = 69.0, 72.0, 4.5
BRICK_L, BRICK_R = 84.75, 86.25
PIPE64_R = 97.5

X_POS, Y_POS, Z_POS, XSPEED, ZSPEED = 3009, 3010, 3011, 3018, 3020
LIVES, SMB_STAR_UNTIL = 72, 1818
JOY_RIGHT, BTN_JUMP = 0x2000, 0x0001

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
     "--debug-print-actors"], cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
time.sleep(2.0)

cap = subprocess.Popen(
    ["ffmpeg", "-y", "-f", "x11grab", "-r", "30", "-s", "640x480", "-i", ":0.0+0,0",
     "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", str(REC)],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
time.sleep(1.0)
cli.set_mailbox(mailbox=SMB_STAR_UNTIL, value=9_999_999, idx=1)
cli.set_mailbox(mailbox=LIVES, value=80, idx=1)

def g(mb):
    with cli._lock: return cli.mailbox_values.get((PLAYER, mb))

def park(x, z):
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=2)
    cli.set_mailbox(mailbox=XSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=ZSPEED, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=X_POS, value=x, idx=PLAYER)
    cli.set_mailbox(mailbox=Y_POS, value=0.0, idx=PLAYER)
    cli.set_mailbox(mailbox=Z_POS, value=z, idx=PLAYER)
    time.sleep(0.5)

def run_jump_track(trigger_x, hold_s, track_s=2.4):
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    t = time.monotonic() + 4.0
    while time.monotonic() < t:
        if (g(X_POS) or 0) >= trigger_x: break
        time.sleep(0.006)
    vx = g(XSPEED) or 0.0; jx = g(X_POS)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT | BTN_JUMP, duration_frames=-1)
    time.sleep(hold_s)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    samples = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < track_s:
        samples.append((g(X_POS), g(Z_POS)))
        time.sleep(0.03)
    return jx, vx, samples

def landed_on_brick(samples):
    """Brick contact = Z holds in [6.8,8.2] for >=3 samples while X in [83.5,88]."""
    run = 0
    for (x, z) in samples:
        if x is None or z is None: continue
        if 6.8 <= z <= 8.2 and 83.5 <= x <= 89.0:
            run += 1
            if run >= 3: return True
        else:
            run = 0
    return False

print(f"\n{'trig':>5} {'hold':>5} {'jumpX':>7} {'Vx':>6} {'peakZ':>7} {'endX':>7} {'endZ':>7}  brick?")
best = None
for trigger_x in (71.3, 71.5, 71.7, 71.9):
    for hold_s in (0.30, 0.40):
        park(PIPE_L + 0.2, PIPE_Z + 0.2)
        jx, vx, s = run_jump_track(trigger_x, hold_s)
        zs = [z for (_, z) in s if z is not None]
        peak = max(zs) if zs else 0.0
        ex = next((x for (x, z) in reversed(s) if x is not None), None)
        ez = next((z for (x, z) in reversed(s) if z is not None), None)
        ob = landed_on_brick(s)
        if ob and best is None: best = (trigger_x, hold_s)
        print(f"{trigger_x:>5.1f} {hold_s:>5.2f} {jx or 0:>7.2f} {vx:>6.2f} {peak:>7.2f} "
              f"{ex or 0:>7.2f} {ez if ez is not None else 0:>7.2f}  {'YES' if ob else 'no'}")

print(f"\nbrick-landing trigger found: {best}")

# Full continuous maneuver for the recording (use the working trigger, then jump again to clear pipe_64)
if best:
    tr, ho = best
    print(f"\n=== continuous run with trigger={tr} hold={ho} ===")
    park(PIPE_L + 0.2, PIPE_Z + 0.2)
    jx, vx, s = run_jump_track(tr, ho, track_s=1.6)
    print(f"  hop A: jumpX={jx:.2f} Vx={vx:.2f} -> X={g(X_POS):.2f} Z={g(Z_POS):.2f}")
    # second jump off the brick to clear pipe_64
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT | BTN_JUMP, duration_frames=-1)
    time.sleep(0.4)
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    t0 = time.monotonic(); maxx = 0.0
    while time.monotonic() - t0 < 2.5:
        x = g(X_POS)
        if x and x > maxx: maxx = x
        time.sleep(0.03)
    print(f"  hop B: reached max X={maxx:.2f} (pipe_64 right edge {PIPE64_R})  "
          f"{'*** CLEARED ***' if maxx > PIPE64_R else 'short'}")

cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
time.sleep(0.5)
cli.close()
if cap.poll() is None:
    cap.send_signal(signal.SIGINT)
    try: cap.wait(timeout=8.0)
    except: cap.kill()
proc.send_signal(signal.SIGTERM)
try: proc.wait(timeout=3.0)
except: proc.kill(); proc.wait(timeout=2.0)
log_fp.close()
print(f"\nRecording: {REC if REC.exists() else 'NOT SAVED'}")
print("Done.")
