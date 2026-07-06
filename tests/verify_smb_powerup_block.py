#!/usr/bin/env python3
"""Verify the state-aware power-up block: one self-determining `powerup_template`.

Companion to docs/plans/2026-05-26-smb-powerup-block-and-star-reversal.md.

A Generator's "Object To Throw" is fixed at load (generator.cc:84), so the mushroom
and fire flower are ONE `powerup_template` that reads SMB_MARIO_STATE live and *becomes*
the right item: Small -> a red mushroom that slides; Super+ -> an orange flower forced
stationary; on pickup it raises the matching signal (mushroom -> Super, flower -> Fire).

The Small->mushroom path is already covered by verify_smb_mushroom_spawn.py. This test
isolates the *determination* by firing the SAME `mushroom_block` (which throws with
X-velocity 1.5) while Mario is **Super**:
  1. the spawned item comes out STATIONARY (XSPEED forced ~0 despite the 1.5 throw)
     — proving the template overrode the block's throw based on Mario's tier;
  2. collecting it turns Mario Super -> Fire (state 1 -> 2) — proving it raised
     SMB_FIREFLOWER_PICKUP, not SMB_MUSHROOM_PICKUP.

Engine constraints (same as the sibling SMB bridge tests): the real bump
(COLLIDER_IDX + NORMAL_Z) can't be faked headless (wiped per-frame), so we pulse the
block's SMB_QBLOCK_ACTIVATE directly; globals (<1900) read at idx=1; per-actor
mailboxes read at the actor's index; the player rebroadcasts SMB_PLAYER_X/Z from its
own X/Z, so we teleport the PLAYER to the item rather than poke SMB_PLAYER_X.
"""
from __future__ import annotations

import os, re, sys, time, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient, discover_by_pos  # noqa: E402

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LEV   = REPO / "wflevels" / "smb_w1_1" / "smb_w1_1.lev"   # name→pos for shared-mesh discovery
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
SCROT = REPO / "tests" / "screenshots"
LOG   = REPO / "tests" / ".verify_smb_powerup_block.log"
PORT  = 7789

SMB_MARIO_STATE       = 1814          # global (read at idx=1)
SMB_MUSHROOM_PICKUP   = 1815
SMB_FIREFLOWER_PICKUP = 1816
X_POS, Z_POS, XSPEED  = 3009, 3011, 3018
SMB_QBLOCK_ACTIVATE   = 2010
SMB_QBLOCK_USED       = 2011
SPAWN_LO, SPAWN_HI    = 50, 57        # runtime spawns land here (static actors are lower)
_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")


def discover(log_path: Path, want: set[str], timeout=8.0) -> dict[str, int]:
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    while time.time() < deadline and not want.issubset(found):
        try:
            for m in _MESH_RE.finditer(log_path.read_text(errors="replace")):
                base = m.group(2).removesuffix(".iff")
                if base in want:
                    found[base] = int(m.group(1))
        except OSError:
            pass
        if want.issubset(found):
            break
        time.sleep(0.15)
    return found


def main() -> int:
    SCROT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
    env.setdefault("DISPLAY", ":0")
    log_fp = open(LOG, "w")
    proc = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
         "--debug-bind", "127.0.0.1", "--debug-print-actors"],
        cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

    cli = None
    fails: list[str] = []

    def check(cond, msg):
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
        if not cond:
            fails.append(msg)

    def g(idx, mb):
        with cli._lock:
            return cli.mailbox_values.get((idx, mb))

    def step(n=1, dt=0.04):
        for _ in range(n):
            cli.send({"op": "step"})
            time.sleep(dt)

    def setg(mb, value):
        cli.set_mailbox(idx=PLAYER, mailbox=mb, value=value)

    def shot(label):
        out = SCROT / f"smb_powerup_block_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        ok = m and m.get("op") == "screenshot_done"
        print(f"  screenshot {label}: {'OK -> ' + out.name if ok else 'WARN ' + str(m)}")

    try:
        # player has a unique mesh (player.iff) → discover by mesh; mushroom_block
        # shares the ?-block datablock since P2b → discover by position via the .lev.
        idx = discover(LOG, {"player"})
        blocks = discover_by_pos(LOG, LEV, {"mushroom_block"})
        print("discovered indices:", idx, blocks)
        if "player" not in idx or "mushroom_block" not in blocks:
            print("FATAL: missing core actors; aborting"); return 1
        global PLAYER
        PLAYER = idx["player"]
        BLOCK  = blocks["mushroom_block"]

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected"); time.sleep(1.0)
        cli.watch(idx=1, mailbox=SMB_MARIO_STATE)
        cli.watch(idx=BLOCK, mailbox=SMB_QBLOCK_USED)

        cli.send({"op": "pause"}); time.sleep(0.2)
        step(4)

        # ── Make Mario Super, then fire the mushroom_block (throws @ X-vel 1.5) ───
        setg(SMB_MARIO_STATE, 1)
        step(2)
        cli.set_mailbox(idx=BLOCK, mailbox=SMB_QBLOCK_ACTIVATE, value=1)

        # The spawn's exact index is printed by the generator: "AddObject ok,
        # coin actor_idx=N" — robust vs. guessing the band (static bricks sit in 50-56,
        # and the flower barely moves so a Z-span heuristic won't find it). Step until
        # the generator actually throws (timing varies — poll the log, don't fix a count).
        mover = None
        for _ in range(60):
            step(1, dt=0.04)
            m = re.search(r"AddObject ok, coin actor_idx=(\d+)", LOG.read_text(errors="replace"))
            if m:
                mover = int(m.group(1)); break
        print(f"  block USED={g(BLOCK, SMB_QBLOCK_USED)}  spawned item idx={mover}")
        check(mover is not None, "mushroom_block dispensed an item while Super")
        if mover is None:
            raise SystemExit  # handled in finally

        cli.watch(idx=mover, mailbox=XSPEED)
        cli.watch(idx=mover, mailbox=X_POS)
        cli.watch(idx=mover, mailbox=Z_POS)
        # Wait for BOTH X and Z broadcasts to settle (change-only delivery lags a few
        # frames; the flower is near the block @X=9, well above the ground in Z).
        item_x = item_z = item_vx = None
        for _ in range(40):
            step(1, dt=0.04)
            item_x, item_z, item_vx = g(mover, X_POS), g(mover, Z_POS), g(mover, XSPEED)
            if item_x is not None and item_x > 4.0 and item_z is not None and item_z > 4.0:
                break
        print(f"  spawned item: X={item_x} Z={item_z} XSPEED={item_vx}")
        # (1) determination: thrown at X-vel 1.5 but the flower forces itself stationary.
        check(item_vx is not None and abs(item_vx) < 0.5,
              f"Super -> the item is a STATIONARY flower (XSPEED~0 despite the 1.5 throw), got {item_vx}")
        shot("01_flower_from_super")

        # ── (2) collecting it turns Super -> Fire (raised SMB_FIREFLOWER_PICKUP) ──
        # Re-pin Mario onto the item each tick (it's up on the block; a one-shot
        # teleport would let him fall out of the 1.5 m pickup radius before the
        # 1-tick-lagged proximity check fires).
        end_state = None
        for _ in range(50):
            ix, iz = g(mover, X_POS), g(mover, Z_POS)
            if ix is not None:
                cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=ix)
            if iz is not None:
                cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=iz)
            step(1, dt=0.03)
            end_state = g(1, SMB_MARIO_STATE)
            if end_state == 2.0:
                break
        print(f"  after collecting the flower while Super: SMB_MARIO_STATE={end_state}")
        check(end_state == 2.0,
              f"collecting the flower raised SMB_FIREFLOWER_PICKUP -> Fire (state 2), got {end_state}")
        shot("02_fire_after_pickup")

    finally:
        if cli:
            try: cli.close()
            except Exception: pass
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=3)
            except Exception: proc.kill()
        log_fp.close()

    print()
    if fails:
        print(f"FAIL — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"   - {f}")
        return 1
    print("PASS — state-aware power-up block: Super bump -> stationary flower -> Fire")
    return 0


if __name__ == "__main__":
    sys.exit(main())
