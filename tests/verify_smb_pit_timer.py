"""Verify SMB pit/fall death + level countdown timer via the debug bridge.

Launches wf_game on smb_w1_1-standalone.iff and checks:

  1. timer_running  — HUD_TIMER (mb 71) seeds ~400 and counts DOWN over time.
  2. pit death      — Mario walks off the first pit lip (X=28.5), falls into the
                      pit-death ActBox band, LIVES 3->2, and respawns at spawn.
  3. timer expiry   — forcing SMB_TIMER_START into the past drains the clock to 0;
                      "TIME UP" fires SMB_PLAYER_HURT -> LIVES 2->1 + respawn, and
                      HUD_TIMER resets to ~400.

Screenshots: smb_timer_running, smb_pit_falling, smb_after_respawn, smb_timer_expired.
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
PORT  = 7780
SCROT = REPO / "tests" / "screenshots"
SCROT.mkdir(parents=True, exist_ok=True)

PLAYER_IDX = 10
# globals (watched/written with idx=1, like verify_smb_scroll.py)
TIME            = 1906
HUD_TIMER       = 71
LIVES           = 72
SMB_TIMER_START = 1808
SMB_PLAYER_HURT = 1804
# player-local
X_POS = 3009
Z_POS = 3011

JOY_RIGHT = 0x2000

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")

log_path = REPO / "tests" / ".smb_pit_timer.log"
log_fp = open(log_path, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
     "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)

def g(mb, idx=1):     # latest watched value or None
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
    for mb in (TIME, HUD_TIMER, LIVES, SMB_TIMER_START, SMB_PLAYER_HURT):
        cli.watch(idx=1, mailbox=mb)
    cli.watch(idx=PLAYER_IDX, mailbox=X_POS)
    cli.watch(idx=PLAYER_IDX, mailbox=Z_POS)
    time.sleep(2.0)   # let Mario settle + Director seed the timer

    # ── 1. timer counts down ────────────────────────────────────────────────
    print("\n== timer countdown ==")
    t0 = g(HUD_TIMER); lives0 = g(LIVES)
    print(f"  HUD_TIMER={fmt(t0)}  LIVES={fmt(lives0)}")
    shot("timer_running")
    time.sleep(4.0)
    t1 = g(HUD_TIMER)
    print(f"  HUD_TIMER after 4s={fmt(t1)}")
    check(t0 is not None and 380 <= t0 <= 401, "HUD_TIMER seeds ~400")
    check(t0 is not None and t1 is not None and t1 < t0, "HUD_TIMER counts DOWN")
    check(lives0 == 3, "LIVES seeded to 3")

    # ── 2. pit / fall death (deterministic via pause + step) ────────────────
    print("\n== pit death ==")
    lives_before_pit = g(LIVES)
    cli.send({"op": "pause"}); time.sleep(0.3)
    # Teleport Mario to the lip of pit 0 (ground_0 ends at X=28.5), then walk
    # right off the edge. Reliable + fast vs. walking 24 m from spawn.
    cli.set_mailbox(mailbox=X_POS, value=27, idx=PLAYER_IDX)
    for _ in range(4):
        cli.send({"op": "step"}); time.sleep(0.03)
    fell = respawned = False
    for i in range(300):
        cli.inject_input(slot="joystick1_raw", value=JOY_RIGHT, duration_frames=2)
        cli.send({"op": "step"}); time.sleep(0.03)
        z = g(Z_POS, PLAYER_IDX); x = g(X_POS, PLAYER_IDX); lv = g(LIVES)
        if not fell and z is not None and z < -0.2:        # off the ground, falling
            fell = True
            print(f"  falling: X={fmt(x)} Z={fmt(z)} LIVES={fmt(lv)}")
            shot("pit_falling")
        if lv is not None and lives_before_pit is not None and lv == lives_before_pit - 1:
            respawned = True
            print(f"  respawned at step {i}: X={fmt(x)} Z={fmt(z)} LIVES={fmt(lv)}")
            break
    cli.inject_input(slot="joystick1_raw", value=0, duration_frames=0)
    for _ in range(30):            # let respawn settle to the ground
        cli.send({"op": "step"}); time.sleep(0.02)
    xr = g(X_POS, PLAYER_IDX); zr = g(Z_POS, PLAYER_IDX); lvr = g(LIVES)
    print(f"  after pit: X={fmt(xr)} Z={fmt(zr)} LIVES={fmt(lvr)}")
    shot("after_respawn")
    check(fell, "Mario fell below ground (Z < -0.2)")
    check(respawned and lvr == 2, "pit death decremented LIVES 3->2")
    check(xr is not None and abs(xr - 4.5) < 1.5, "Mario respawned near spawn X=4.5")
    cli.send({"op": "resume"}); time.sleep(0.2)

    # ── 3. forced timer expiry ──────────────────────────────────────────────
    # Re-arm the timeout each iteration (set SMB_TIMER_START into the past) until
    # a life is actually lost — robust against the post-respawn i-frame window
    # that can swallow a single timeout hurt (the documented v1 limitation).
    print("\n== timer expiry (TIME UP) ==")
    lives_before_to = g(LIVES)
    ok = False
    for _ in range(50):            # up to ~10 s
        now = g(TIME) or 0.0
        cli.set_mailbox(mailbox=SMB_TIMER_START, value=int(now - 200), idx=1)
        time.sleep(0.2)
        lv = g(LIVES)
        if lv is not None and lives_before_to is not None and lv == lives_before_to - 1:
            ok = True; break
    time.sleep(0.8)
    ht = g(HUD_TIMER); lvf = g(LIVES); xf = g(X_POS, PLAYER_IDX)
    print(f"  after expiry: HUD_TIMER={fmt(ht)} LIVES={fmt(lvf)} X={fmt(xf)}")
    shot("timer_expired")
    check(ok and lvf == 1, "timeout decremented LIVES 2->1")
    check(ht is not None and ht > 380, "HUD_TIMER reset to ~400 after timeout")

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
