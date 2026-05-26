"""Verify the SMB Super Mushroom power-up state machine (Small <-> Super).

Drives the state machine directly through the engine mailboxes (independent of
the spawn/slide physics, which reuse the proven coin path):

  1. Small at start (SMB_MARIO_STATE == 0).
  2. Mushroom pickup -> Super: inject SMB_MUSHROOM_PICKUP=1, expect MARIO_STATE 0->1
     and the mesh scale grow (Z_SCALE -> 1.9, X_SCALE -> 1.25).
  3. Power-down (not death): while Super, inject SMB_PLAYER_HURT=1, expect
     MARIO_STATE 1->0, scale reset to 1.0, and LIVES UNCHANGED.
  4. Small death still works: after i-frames clear, inject SMB_PLAYER_HURT=1 again,
     expect LIVES to decrement (existing death path).

Captures screenshots (small vs super) for visual proof.

Companion to docs/plans/2026-05-26-smb-super-mushroom-powerup.md.
"""
from __future__ import annotations

import os, re, sys, time, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
SCROT = REPO / "tests" / "screenshots"
PORT  = 7781

PLAYER_IDX = 9   # discovered from the actor log at runtime (see find_player_idx); fallback default
# globals (idx=1)
SMB_MARIO_STATE     = 1814
SMB_MUSHROOM_PICKUP = 1815
SMB_PLAYER_HURT     = 1804
SMB_INVULN_UNTIL    = 1805
TIME                = 1906
LIVES               = 72
# player-local
X_SCALE = 3040
Z_SCALE = 3042
GOLD    = 3001

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")

SCROT.mkdir(parents=True, exist_ok=True)
log_path = REPO / "tests" / ".smb_mushroom.log"
log_fp = open(log_path, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
     "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)

_PLAYER_RE = re.compile(r"actor idx=(\d+) mesh=player\.iff")
def find_player_idx(default: int) -> int:
    """Parse the engine log for Mario's actor index (robust to actor-list shifts)."""
    for _ in range(40):
        try:
            m = _PLAYER_RE.search(log_path.read_text(errors="replace"))
            if m: return int(m.group(1))
        except OSError:
            pass
        time.sleep(0.1)
    return default

def g(mb, idx=1):
    with cli._lock:
        return cli.mailbox_values.get((idx, mb))

def fmt(v): return " None " if v is None else f"{v:+7.2f}"

def shot(label):
    out = SCROT / f"smb_mushroom_{label}.png"
    cli.send({"op": "screenshot", "filename": str(out)})
    m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
    ok = m and m.get("op") == "screenshot_done"
    print(f"  screenshot {label}: {'OK -> '+str(out) if ok else 'WARN '+str(m)}")

fails = []
def check(cond, msg):
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond: fails.append(msg)

try:
    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    print("bridge: connected")
    PLAYER_IDX = find_player_idx(PLAYER_IDX)
    print(f"player actor idx = {PLAYER_IDX}")
    for mb in (SMB_MARIO_STATE, SMB_PLAYER_HURT, SMB_INVULN_UNTIL, TIME, LIVES):
        cli.watch(idx=1, mailbox=mb)
    for mb in (X_SCALE, Z_SCALE, GOLD):
        cli.watch(idx=PLAYER_IDX, mailbox=mb)
    time.sleep(2.0)   # let Mario settle + scripts spin up

    # ── 1. Small at start ───────────────────────────────────────────────────
    print("\n== 1. small at start ==")
    print(f"  STATE={fmt(g(SMB_MARIO_STATE))} LIVES={fmt(g(LIVES))} "
          f"X_SCALE={fmt(g(X_SCALE,PLAYER_IDX))} Z_SCALE={fmt(g(Z_SCALE,PLAYER_IDX))}")
    check(g(SMB_MARIO_STATE) == 0, "MARIO_STATE starts 0 (Small)")
    check(g(LIVES) == 3, "LIVES seeded to 3")
    shot("01_small")
    lives_small = g(LIVES)

    # ── 2. mushroom pickup -> Super ─────────────────────────────────────────
    print("\n== 2. mushroom pickup -> Super ==")
    cli.set_mailbox(mailbox=SMB_MUSHROOM_PICKUP, value=1, idx=1)
    cli.wait_for_mailbox(idx=1, mailbox=SMB_MARIO_STATE, expected=1, timeout=3.0)
    time.sleep(0.3)
    print(f"  STATE={fmt(g(SMB_MARIO_STATE))} X_SCALE={fmt(g(X_SCALE,PLAYER_IDX))} "
          f"Z_SCALE={fmt(g(Z_SCALE,PLAYER_IDX))}")
    check(g(SMB_MARIO_STATE) == 1, "MARIO_STATE 0->1 on mushroom pickup")
    zs = g(Z_SCALE, PLAYER_IDX); xs = g(X_SCALE, PLAYER_IDX)
    check(zs is not None and abs(zs - 1.9) < 0.05, "Z_SCALE grew to 1.9 (taller)")
    check(xs is not None and abs(xs - 1.25) < 0.05, "X_SCALE grew to 1.25")
    shot("02_super")

    # ── 3. power-down (Super + hurt -> Small, no life lost) ─────────────────
    print("\n== 3. power-down, not death ==")
    lives_before = g(LIVES)
    cli.set_mailbox(mailbox=SMB_PLAYER_HURT, value=1, idx=1)
    cli.wait_for_mailbox(idx=1, mailbox=SMB_MARIO_STATE, expected=0, timeout=3.0)
    time.sleep(0.3)
    print(f"  STATE={fmt(g(SMB_MARIO_STATE))} LIVES={fmt(g(LIVES))} "
          f"Z_SCALE={fmt(g(Z_SCALE,PLAYER_IDX))}")
    check(g(SMB_MARIO_STATE) == 0, "MARIO_STATE 1->0 on hurt while Super")
    check(g(LIVES) == lives_before, "LIVES UNCHANGED on power-down")
    zs2 = g(Z_SCALE, PLAYER_IDX)
    check(zs2 is not None and abs(zs2 - 1.0) < 0.05, "Z_SCALE reset to 1.0 (Small)")
    shot("03_powered_down")

    # ── 4. Small death still works (after i-frames clear) ───────────────────
    print("\n== 4. small death still costs a life ==")
    # power-down set SMB_INVULN_UNTIL = TIME + 1.5; wait it out.
    time.sleep(2.5)
    lives_pre_death = g(LIVES)
    cli.set_mailbox(mailbox=SMB_PLAYER_HURT, value=1, idx=1)
    deadline = time.time() + 3.0
    while time.time() < deadline and g(LIVES) == lives_pre_death:
        time.sleep(0.05)
    print(f"  LIVES {fmt(lives_pre_death)} -> {fmt(g(LIVES))}")
    check(g(LIVES) is not None and g(LIVES) == lives_pre_death - 1,
          "LIVES decrements on hurt while Small")

finally:
    print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
    try: cli.close()
    except Exception: pass
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()

sys.exit(1 if fails else 0)
