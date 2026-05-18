"""Verify SMB scrolling camera end-to-end via the debug bridge.

Launches wf_game on smb_w1_1-standalone.iff, watches the three SMB scroll
mailboxes (1800/1801/1802), drives Mario via input injection, and captures
four screenshots:

  1. spawn        — Mario at spawn; camera clamped at left edge (X=9.0).
  2. right_walk   — Mario walks right ~6 m; camera has scrolled to follow.
  3. left_walk    — Mario walks back left; camera unchanged (one-way ratchet).
  4. flagpole     — Mario walks to far right; camera clamped at right edge (X=58.5).
"""
from __future__ import annotations

import os, sys, time, subprocess, signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7779
SCROT = REPO / "tests" / "screenshots"
SCROT.mkdir(parents=True, exist_ok=True)

SMB_PLAYER_X      = 1800
SMB_TARGET_CAM_X  = 1801
SMB_MAX_CAM_X     = 1802

JOY_RIGHT = 0x2000
JOY_LEFT  = 0x4000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
if "DISPLAY" not in env:
    env["DISPLAY"] = ":0"

log_path = REPO / "tests" / ".smb_verify.log"
log_fp = open(log_path, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}",
     "--debug-port", str(PORT),
     "--debug-bind", "127.0.0.1",
     "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)

def fmt(v):
    if v is None: return "  None  "
    return f"{v:+8.3f}"

try:
    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    # Skip ping/pong handshake — wait_for() races against the fast inline
    # pong response (it intentionally skips messages already in the inbox
    # to avoid matching prior replies). Connect success is enough.
    print("bridge: connected")

    # Watch the three SMB globals; idx doesn't matter for globals.
    for mb in (SMB_PLAYER_X, SMB_TARGET_CAM_X, SMB_MAX_CAM_X):
        cli.watch(idx=1, mailbox=mb)
    time.sleep(0.4)

    def snapshot(label: str, hold_secs: float = 0.0):
        time.sleep(hold_secs)
        with cli._lock:
            vals = {mb: cli.mailbox_values.get((1, mb)) for mb in
                    (SMB_PLAYER_X, SMB_TARGET_CAM_X, SMB_MAX_CAM_X)}
        print(f"[{label:18s}] "
              f"PLAYER_X={fmt(vals[SMB_PLAYER_X])}  "
              f"TARGET_CAM_X={fmt(vals[SMB_TARGET_CAM_X])}  "
              f"MAX_CAM_X={fmt(vals[SMB_MAX_CAM_X])}")
        out = SCROT / f"smb_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"),
                         timeout=6.0)
        print(f"  screenshot: {'OK' if m and m.get('op')=='screenshot_done' else 'WARN ' + str(m)}")

    # Let Mario settle on the ground (Physics mobility, gravity).
    time.sleep(1.5)
    snapshot("01_spawn")

    # Walk right ~2 s (Mario maxes at 6 m/s; should travel ~10–12 m).
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=-1)
    time.sleep(2.0)
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
    snapshot("02_right_walk", hold_secs=0.3)

    # Walk back left ~1.5 s. Camera MUST stay put (one-way ratchet).
    cli.inject_input(slot="joystick1_raw", value=JOY_LEFT, duration_frames=-1)
    time.sleep(1.5)
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
    snapshot("03_left_walk_ratchet", hold_secs=0.3)

    # Teleport Mario near the flagpole (X≈60, flagpole at X=63) by writing
    # directly to his INDEXOF_X_POS (slot 3009) on actor idx=9. Director will
    # see player_x=60 next tick → desired=61.5 → target=60 → clamped to 58.5
    # (X_MAX - HALF_FRUSTUM). Demonstrates the right-edge clamp definitively.
    MARIO_ACTOR_IDX = 9
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
    time.sleep(0.2)
    cli.set_mailbox(mailbox=3009, value=60, idx=MARIO_ACTOR_IDX)
    snapshot("04_flagpole_clamp", hold_secs=1.0)

finally:
    try:
        cli.close()
    except Exception:
        pass
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2.0)
    log_fp.close()
    print(f"\nengine log: {log_path}")
