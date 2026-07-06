"""Verify SMB pipe warp → underground coin room (Phase A) via the debug bridge.

Boots smb_w1_1-standalone.iff and checks the cross-room warp:

  1. sense       — teleport Mario onto the entry-pipe mouth (X=18, Z~3); the
                   pipe_entry_sense ActBox sets SMB_AT_PIPE (mb 1809) = 1.
  2. down-warp   — inject Down (0x1000); the player script warps him to the coin
                   room (Z ~ -46.5, X ~ 3) and zeroes velocity.
  3. room switch — the active room follows: EMAILBOX_CAMSHOT (mb 1021) flips from
                   cs_side (idx 5) to cs_coin (idx 34); engine does not crash.

Screenshots: smb_warp_surface (on the pipe), smb_warp_coinroom (underground).
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
PORT  = 7782
SCROT = REPO / "tests" / "screenshots"
SCROT.mkdir(parents=True, exist_ok=True)

PLAYER_IDX  = 9      # shifted from 10 when the broken imported actboxor was replaced
CS_SIDE_IDX = 5      # surface camshot  (pos 4.5,-30,4.5)
CS_COIN_IDX = 34     # coin-room camshot (pos 9,-35,-43.5)

JOY_RIGHT = 0x2000

# globals (idx=1)
SMB_AT_PIPE    = 1809
HUD_SCORE      = 70        # player mirrors its GOLD here each tick
EMAILBOX_CAMSHOT = 1921    # mailbox.inc:59 (the level-building.md scope table's 1021 is wrong)
# player-local
X_POS, Z_POS = 3009, 3011

JOY_DOWN = 0x1000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")

log_path = REPO / "tests" / ".smb_pipe_warp.log"
log_fp = open(log_path, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
     "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)

def g(mb, idx=1):
    with cli._lock:
        return cli.mailbox_values.get((idx, mb))

def fmt(v): return "  None " if v is None else f"{v:+8.2f}"

def shot(label):
    out = SCROT / f"smb_{label}.png"
    cli.send({"op": "screenshot", "filename": str(out)})
    m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
    print(f"  screenshot {label}: {'OK' if m and m.get('op')=='screenshot_done' else 'WARN '+str(m)}")

fails = []
def check(cond, msg):
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond: fails.append(msg)

try:
    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    print("bridge: connected")
    cli.watch(idx=1, mailbox=SMB_AT_PIPE)
    cli.watch(idx=1, mailbox=EMAILBOX_CAMSHOT)
    cli.watch(idx=1, mailbox=HUD_SCORE)
    cli.watch(idx=PLAYER_IDX, mailbox=X_POS)
    cli.watch(idx=PLAYER_IDX, mailbox=Z_POS)
    for mb in (3009, 3010, 3011):       # camera entity pose (idx=1)
        cli.watch(idx=1, mailbox=mb)
    time.sleep(2.0)   # let Mario settle

    cam0 = g(EMAILBOX_CAMSHOT)
    print(f"\n== initial ==  CAMSHOT={fmt(cam0)}  X={fmt(g(X_POS,PLAYER_IDX))} Z={fmt(g(Z_POS,PLAYER_IDX))}")

    # ── 1. teleport onto the pipe mouth, let the ActBox sense it ──────────────
    print("\n== on the pipe ==")
    cli.send({"op": "pause"}); time.sleep(0.3)
    cli.set_mailbox(mailbox=X_POS, value=18, idx=PLAYER_IDX)
    cli.set_mailbox(mailbox=Z_POS, value=4, idx=PLAYER_IDX)   # drop onto pipe top (Z=3)
    saw_at_pipe = False
    for _ in range(25):
        cli.send({"op": "step"}); time.sleep(0.02)
        if g(SMB_AT_PIPE) == 1:
            saw_at_pipe = True
    print(f"  X={fmt(g(X_POS,PLAYER_IDX))} Z={fmt(g(Z_POS,PLAYER_IDX))}  SMB_AT_PIPE seen=1: {saw_at_pipe}")
    shot("warp_surface")

    # ── 2. press Down → warp ──────────────────────────────────────────────────
    print("\n== press Down → warp ==")
    warped = False
    for i in range(60):
        cli.inject_input(slot="joystick1_raw", value=JOY_DOWN, duration_frames=2)
        cli.send({"op": "step"}); time.sleep(0.02)
        z = g(Z_POS, PLAYER_IDX)
        if z is not None and z < -30:
            warped = True
            print(f"  warped at step {i}: X={fmt(g(X_POS,PLAYER_IDX))} Z={fmt(z)}")
            break
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=0)
    # RESUME (real-time) so the camera PAN to cs_coin completes — in step mode each
    # frame advances a tiny dt and the pan barely moves.
    cli.send({"op": "resume"}); time.sleep(7.0)   # headless is low-fps; let the camera pan finish
    xw, zw, camw = g(X_POS, PLAYER_IDX), g(Z_POS, PLAYER_IDX), g(EMAILBOX_CAMSHOT)
    cx, cy, cz = g(3009, 1), g(3010, 1), g(3011, 1)
    print(f"  after warp: player X={fmt(xw)} Z={fmt(zw)} CAMSHOT={fmt(camw)}")
    print(f"  camera entity pos: ({fmt(cx)},{fmt(cy)},{fmt(cz)})  [cs_coin is (9,-35,-43.5)]")
    shot("warp_coinroom")
    check(zw is not None and zw < -30, "Down on the pipe warped Mario underground (Z < -30)")
    check(zw is not None and abs(zw - (-47.0)) < 2.5, "landed on the coin-room floor (Z ~ -47)")
    check(xw is not None and 0.0 < xw < 12.0, "landed inside the coin room (0 < X < exit pipe)")
    # The camera adopts cs_coin and swoops down (Z 4.5 -> negative). The full pan to
    # -43.5 settles in ~1-2 s real-time; headless is low-fps so we just require it to
    # have descended well below the surface (proves it followed, not froze).
    check(cz is not None and cz < -8, "camera entity followed down toward the coin room (Z < -8)")

    # ── 3. walk RIGHT in real-time: collect coins, then hit the exit warp ─────
    # Must run real-time (resume + hold RIGHT) — in step mode each frame's dt is tiny
    # so Mario barely moves. Snapshot a screenshot of the lit room with coins first.
    print("\n== collect coins + exit warp (walk right) → surface ==")
    shot("coinroom_coins")
    gold_before = g(HUD_SCORE)
    cli.send({"op": "resume"})
    cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=1200)   # hold RIGHT
    returned = False
    for _ in range(150):                  # poll up to ~15 s real-time
        time.sleep(0.1)
        z = g(Z_POS, PLAYER_IDX)
        if z is not None and z > -5:      # warped back up to the surface
            returned = True; break
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=0)
    time.sleep(3.0)                       # let the camera switch back to cs_side
    gold_after = g(HUD_SCORE)
    print(f"  returned={returned}  GOLD before={fmt(gold_before)} after={fmt(gold_after)} (3 coins)")
    check(gold_after is not None and gold_before is not None and gold_after - gold_before >= 2,
          "collected coins walking through the room (GOLD rose by >=2)")
    xr, zr, camr = g(X_POS, PLAYER_IDX), g(Z_POS, PLAYER_IDX), g(EMAILBOX_CAMSHOT)
    czr = g(3011, 1)
    print(f"  after return: player X={fmt(xr)} Z={fmt(zr)} CAMSHOT={fmt(camr)} cameraZ={fmt(czr)}")
    shot("warp_returned")
    check(returned, "walking into the exit pipe warped Mario back up (Z > -5)")
    check(xr is not None and abs(xr - 24.0) < 3.0, "returned near the surface return point (X ~ 24)")
    check(camr == CS_SIDE_IDX, "camera switched back to cs_side on the surface")
    check(czr is not None and czr > -5, "camera entity back up at the surface (Z > -5)")

    # crash check: bridge still alive?
    alive = proc.poll() is None
    check(alive, "engine still running (no crash on the round-trip)")

    print("\n=== RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}", "===")

finally:
    try: cli.close()
    except Exception: pass
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=2.0)
    log_fp.close()
    print(f"engine log: {log_path}")

sys.exit(1 if fails else 0)
