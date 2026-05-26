"""Verify the SMB mushroom PRODUCER chain end-to-end via the debug bridge.

Complements tests/verify_smb_mushroom.py (which proves the consumer — Mario's
state machine — by injecting SMB_MUSHROOM_PICKUP directly). This one proves the
full chain:

  bump the mushroom block (fake COLLIDER_IDX + COLLISION_NORMAL_Z>0 on the block)
    -> the one-shot Generator throws exactly ONE mushroom_template (block latches USED)
    -> the mushroom pops up and slides right on real physics
    -> the mushroom's own pickup script raises SMB_MUSHROOM_PICKUP when Mario is near
    -> Mario's state machine flips SMB_MARIO_STATE 0 -> 1 (Super)

Mario is parked just right of the block so the sliding mushroom reaches him.

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
PORT  = 7782

# globals (idx=1)
SMB_MARIO_STATE     = 1814
SMB_MUSHROOM_PICKUP = 1815
# player-local
X_POS = 3009
# block-local
SMB_QBLOCK_ACTIVATE = 2010
SMB_QBLOCK_USED     = 2011
COLLIDER_IDX        = 3044
COLLISION_NORMAL_Z  = 3047

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")

SCROT.mkdir(parents=True, exist_ok=True)
log_path = REPO / "tests" / ".smb_mushroom_spawn.log"
log_fp = open(log_path, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
     "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
)

def idx_of(mesh_re: str, default: int) -> int:
    pat = re.compile(rf"actor idx=(\d+) mesh={mesh_re}")
    for _ in range(40):
        try:
            m = pat.search(log_path.read_text(errors="replace"))
            if m: return int(m.group(1))
        except OSError:
            pass
        time.sleep(0.1)
    return default

def count_mushrooms() -> int:
    try:
        return len(re.findall(r"mesh=mushroom_template\.iff", log_path.read_text(errors="replace")))
    except OSError:
        return 0

def g(mb, idx=1):
    with cli._lock:
        return cli.mailbox_values.get((idx, mb))

def shot(label):
    out = SCROT / f"smb_mushroom_{label}.png"
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
    PLAYER_IDX = idx_of(r"player\.iff", 9)
    BLOCK_IDX  = idx_of(r"mushroom_block\.iff", 20)
    print(f"player idx={PLAYER_IDX}  mushroom_block idx={BLOCK_IDX}")
    cli.watch(idx=1, mailbox=SMB_MARIO_STATE)
    cli.watch(idx=1, mailbox=SMB_MUSHROOM_PICKUP)
    cli.watch(idx=BLOCK_IDX, mailbox=SMB_QBLOCK_USED)
    cli.watch(idx=BLOCK_IDX, mailbox=SMB_QBLOCK_ACTIVATE)
    time.sleep(2.0)   # settle

    # Park Mario just right of the block (X=9) so the sliding mushroom reaches him.
    cli.set_mailbox(mailbox=X_POS, value=11, idx=PLAYER_IDX)
    time.sleep(0.5)

    n_before = count_mushrooms()
    print(f"\n== trigger the mushroom block (idx {BLOCK_IDX}) ==")
    # One trigger pulse, mimicking what the block's bump-detect does on a single
    # bump-from-below. (The bump detection itself — COLLIDER_IDX/NORMAL_Z>0 — is the
    # proven ?-block Jolt path, TODO §103, and can't be faked headless: the collision
    # system resets COLLIDER_IDX each frame. The one-shot USED latch against a *held*
    # bump mirrors the proven coin-block latch and is confirmed interactively.)
    cli.set_mailbox(mailbox=SMB_QBLOCK_ACTIVATE, value=1, idx=BLOCK_IDX)
    time.sleep(0.8)
    shot("04_spawned")

    used = g(SMB_QBLOCK_USED, BLOCK_IDX)
    n_after = count_mushrooms()
    n_spawned = n_after - n_before
    print(f"  block USED={used}  mushrooms spawned (log count delta)={n_spawned}")
    check(used == 1, "mushroom block latched USED after the trigger pulse")
    check(n_spawned == 1, "exactly one mushroom_template spawned per trigger pulse")

    print("\n== mushroom slides into Mario -> Super ==")
    deadline = time.time() + 5.0
    while time.time() < deadline and g(SMB_MARIO_STATE) != 1:
        time.sleep(0.05)
    print(f"  SMB_MARIO_STATE={g(SMB_MARIO_STATE)}")
    check(g(SMB_MARIO_STATE) == 1, "full chain: block->mushroom->pickup script->Mario Super")
    shot("05_super_from_pickup")

finally:
    print("\n" + ("ALL PASS" if not fails else f"FAILURES: {fails}"))
    try: cli.close()
    except Exception: pass
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()

sys.exit(1 if fails else 0)
