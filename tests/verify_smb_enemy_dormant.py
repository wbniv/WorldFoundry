"""Verify SMB enemies stay dormant until they scroll on-screen, then walk (faithful).

Boots smb_w1_1-standalone.iff and checks:
  1. dormant   — for ~3 s with no input the Goomba/Koopa X stays put (not pre-walking,
                 not removed). They spawn off-screen right of the start view.
  2. reveal    — drive Mario right (real-time); once the camera ratchet's right edge
                 (SMB_MAX_CAM_X + 12) passes an enemy's X, that enemy starts moving
                 left (X decreases) — i.e. it activates only when revealed.
Screenshot: smb_enemy_meet (Mario on ground_1 facing the activated enemies).
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
PORT  = 7786
SCROT = REPO / "tests" / "screenshots"; SCROT.mkdir(parents=True, exist_ok=True)

PLAYER_IDX = 9
GOOMBA_IDX = 19      # spawn X 43.5
KOOPA_IDX  = 20      # spawn X 48.0
SMB_MAX_CAM_X = 1802
X_POS = 3009
JOY_RIGHT, JOY_JUMP = 0x2000, 0x0010   # JUMP bit (kBtnAButton) — value confirmed below if needed

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0")
log = open(REPO / "tests" / ".smb_enemy_dormant.log", "w")
proc = subprocess.Popen([str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
    "--debug-bind", "127.0.0.1", "--debug-print-actors"], cwd=str(CWD), env=env,
    stdout=log, stderr=subprocess.STDOUT)

def g(mb, idx=1):
    with cli._lock: return cli.mailbox_values.get((idx, mb))
def fmt(v): return "  None " if v is None else f"{v:+8.2f}"
def shot(label):
    out = SCROT / f"smb_{label}.png"
    cli.send({"op":"screenshot","filename":str(out)})
    m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done","error"), timeout=6.0)
    print(f"  screenshot {label}: {'OK' if m and m.get('op')=='screenshot_done' else 'WARN'}")
fails=[]
def check(c,m):
    print(f"  [{'PASS' if c else 'FAIL'}] {m}");  fails.append(m) if not c else None

try:
    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    print("bridge: connected")
    cli.watch(idx=1, mailbox=SMB_MAX_CAM_X)
    cli.watch(idx=GOOMBA_IDX, mailbox=X_POS)
    cli.watch(idx=KOOPA_IDX, mailbox=X_POS)
    cli.watch(idx=PLAYER_IDX, mailbox=X_POS)
    time.sleep(2.0)

    # ── 1. dormant at start ────────────────────────────────────────────────
    print("\n== dormant (no input, ~3 s) ==")
    gx0, kx0 = g(X_POS, GOOMBA_IDX), g(X_POS, KOOPA_IDX)
    print(f"  start: goomba X={fmt(gx0)} koopa X={fmt(kx0)} camMax={fmt(g(SMB_MAX_CAM_X))}")
    time.sleep(3.0)
    gx1, kx1 = g(X_POS, GOOMBA_IDX), g(X_POS, KOOPA_IDX)
    print(f"  +3s:   goomba X={fmt(gx1)} koopa X={fmt(kx1)}")
    check(gx0 is not None and gx1 is not None and abs(gx1-gx0) < 0.5, "Goomba dormant (X held ~constant, not pre-walking)")
    check(kx0 is not None and kx1 is not None and abs(kx1-kx0) < 0.5, "Koopa dormant (X held ~constant)")
    check(gx1 is not None and gx1 > 31.5, "Goomba still on ground_1 (not fallen into pit0)")
    check(kx1 is not None and kx1 > 31.5, "Koopa still on ground_1")

    # ── 2. activate on camera reveal ───────────────────────────────────────
    # Teleport Mario onto ground_1 (he's otherwise blocked by the solid entry pipe at
    # X=16.5 without a jump). The Director then ratchets SMB_MAX_CAM_X up to Mario's X,
    # whose right edge (+12) passes the enemies → they reveal and walk left toward him.
    print("\n== reveal (Mario on ground_1 → camera reveals enemies) ==")
    cli.send({"op":"pause"}); time.sleep(0.3)
    cli.set_mailbox(mailbox=X_POS, value=40, idx=PLAYER_IDX)   # on ground_1, left of both enemies
    for _ in range(10):
        cli.send({"op":"step"}); time.sleep(0.03)
    cli.send({"op":"resume"}); time.sleep(2.5)
    cam = g(SMB_MAX_CAM_X)
    gxf, kxf, pxf = g(X_POS, GOOMBA_IDX), g(X_POS, KOOPA_IDX), g(X_POS, PLAYER_IDX)
    print(f"  camMax={fmt(cam)} edge={fmt((cam or 0)+12)}  goomba X={fmt(gxf)} koopa X={fmt(kxf)} mario X={fmt(pxf)}")
    shot("enemy_meet")
    check(gxf is not None and gx0 is not None and gxf < gx0 - 1.0, "Goomba activated (walked left) once revealed (edge > 43.5)")
    check(kxf is not None and kx0 is not None and kxf < kx0 - 1.0, "Koopa activated (walked left) once revealed (edge > 48)")

    check(proc.poll() is None, "engine still running")
    print("\n=== RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}", "===")
finally:
    try: cli.close()
    except Exception: pass
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=2.0)
    log.close()
sys.exit(1 if fails else 0)
