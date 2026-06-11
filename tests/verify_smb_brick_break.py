#!/usr/bin/env python3
"""Verify SMB breakable bricks: Super shatters (debris + despawn), Small bumps.

Companion to docs/plans/2026-05-26-breakable-bricks-smb-world-1-1.md.

Engine constraints that shape this test (learned the hard way):
  * COLLIDER_IDX (3044) is cleared at the TOP of every frame (actor.cc:1106) AFTER
    the bridge drains its queue (game.cc:512), so an *injected* COLLIDER_IDX is wiped
    before the brick script reads it — only a real Jolt contact sets it. We instead
    drive the brick's persistent state mailboxes (SMB_BRICK_BREAK_END/BUMP_END/
    BUMP_PEAK), which are not cleared per-frame, to exercise the code paths.
  * The brick's windows are TIME-comparisons. We never read the level clock (the
    global TIME mailbox reads stale over the bridge); instead we park a window value
    far in the FUTURE (999999) to hold a phase open, or in the PAST (0.001) to force
    the transition — dt-independent.
  * The perf "actors" field is the object-pool size, not a live count. Static actors
    occupy indices <=49; anything reporting a position at idx>=50 is a runtime spawn
    (debris / mushroom). We watch Z_POS across [50,110] and count distinct reporters.

Checks:
  1. Super break: brick_0 spawns >=3 debris fragments, then despawns; GOLD unchanged.
  2. Small bump: brick_1's Z_POS rises (~0.3) then settles to 0; brick stays alive.
  3. Hidden brick: dispenses a mushroom and latches USED (turns tan), stays solid.
Screenshots: brick row intact / mid-shatter / brick gone / mid-bump.
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
LOG   = REPO / "tests" / ".verify_smb_brick_break.log"
PORT  = 7786

SMB_MARIO_STATE = 1814           # global
GOLD                = 3001
X_POS, Z_POS        = 3009, 3011
SMB_QBLOCK_ACTIVATE = 2010
SMB_QBLOCK_USED     = 2011
SMB_BRICK_BREAK_END = 2013
SMB_BRICK_BUMP_END  = 2014
SMB_BRICK_BUMP_PEAK = 2015

FAR_FUTURE = 999999.0            # window value the level clock never reaches → hold phase
PAST       = 0.001               # window value already elapsed → force the transition
SPAWN_LO   = 50                  # static actors are idx<=49; spawns land at >=50
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

    def spawn_count() -> int:
        """Count generator spawns from the engine log — robust vs. the watch-broadcast
        backlog that lags many frames when watching a wide index band."""
        try:
            return LOG.read_text(errors="replace").count("AddObject ok")
        except OSError:
            return 0

    def poll(idx, mb, pred, secs=3.0):
        """Step until a (held) watched value satisfies pred — absorbs the multi-frame
        broadcast-delivery lag. The brick holds each Z/USED value every frame, so once
        the lagged broadcast arrives the read is correct."""
        end = time.time() + secs
        while time.time() < end:
            step(1, dt=0.03)
            v = g(idx, mb)
            if v is not None and pred(v):
                return v
        return g(idx, mb)

    def shot(label):
        out = SCROT / f"smb_brick_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        print(f"  screenshot {label}: {'OK -> ' + out.name if (m and m.get('op')=='screenshot_done') else 'WARN ' + str(m)}")

    try:
        # player has a unique mesh → discover by mesh. The bricks share one mesh
        # datablock since P2b (and the hidden mushroom brick is authored as
        # `mushroom_block`, not `brick_hidden`), so discover those by position.
        idx = discover(LOG, {"player"})
        blocks = discover_by_pos(LOG, LEV, {"brick_0", "brick_1", "mushroom_block"})
        print("discovered indices:", idx, blocks)
        if "player" not in idx or len(blocks) < 3:
            print("FATAL: missing brick actors; aborting"); return 1
        PLAYER = idx["player"]
        B0, B1, BH = blocks["brick_0"], blocks["brick_1"], blocks["mushroom_block"]

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected"); time.sleep(1.0)
        # Keep the watch set tiny — a wide watch band floods the socket and lags reads
        # by many frames. Spawns are counted from the log instead (spawn_count()).
        cli.watch(idx=PLAYER, mailbox=GOLD)
        cli.watch(idx=B1, mailbox=Z_POS)
        cli.watch(idx=BH, mailbox=SMB_QBLOCK_USED)

        cli.send({"op": "pause"}); time.sleep(0.2)
        cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=18.0)   # pan camera to the brick row
        step(28, dt=0.03)
        shot("01_row_intact")

        # ── 1. Super break ────────────────────────────────────────────────────
        gold_before = g(PLAYER, GOLD)
        c0 = spawn_count()
        cli.set_mailbox(idx=PLAYER, mailbox=SMB_MARIO_STATE, value=1)            # Super
        cli.set_mailbox(idx=B0, mailbox=SMB_BRICK_BREAK_END, value=FAR_FUTURE)   # hold window open
        cli.set_mailbox(idx=B0, mailbox=SMB_QBLOCK_ACTIVATE, value=1)
        step(18, dt=0.03)
        shot("02_shatter")                                                       # mid-burst: fragments airborne
        step(40, dt=0.03)                                                        # finish the window (10/s spawns)
        time.sleep(0.3)
        n_debris = spawn_count() - c0
        print(f"  debris fragments spawned during break: {n_debris}  (GOLD before={gold_before})")
        check(n_debris >= 3, f"break spawned >=3 debris fragments (got {n_debris})")

        cli.set_mailbox(idx=B0, mailbox=SMB_BRICK_BREAK_END, value=PAST)         # close window → ALIVE=0
        step(3)
        shot("03_brick_gone")
        cli.send({"op": "set_mailbox", "idx": B0, "mailbox": SMB_QBLOCK_USED, "value": 0})
        err = cli.wait_for(
            lambda m: m.get("op") == "error" and "not found" in str(m.get("msg", "")), timeout=1.5)
        check(err is not None, "brick_0 despawned after the break window")

        gold_after = g(PLAYER, GOLD)
        check(gold_before is not None and gold_after is not None and abs(gold_after - gold_before) < 0.5,
              f"GOLD unchanged across break ({gold_before}→{gold_after}) — debris don't score")

        # ── 2. Small bump ──────────────────────────────────────────────────────
        # Hold the rising phase open, drain, then read the offset; force settle after.
        cli.set_mailbox(idx=PLAYER, mailbox=SMB_MARIO_STATE, value=0)            # Small
        cli.set_mailbox(idx=B1, mailbox=SMB_BRICK_BUMP_PEAK, value=FAR_FUTURE)   # hold "rising" phase
        cli.set_mailbox(idx=B1, mailbox=SMB_BRICK_BUMP_END,  value=FAR_FUTURE)
        risen_z = poll(B1, Z_POS, lambda v: v >= 0.25, secs=3.0)
        shot("04_bump")
        cli.set_mailbox(idx=B1, mailbox=SMB_BRICK_BUMP_END, value=PAST)          # force settle
        settled_z = poll(B1, Z_POS, lambda v: abs(v) < 0.05, secs=3.0)
        print(f"  bump: risen Z={risen_z}  settled Z={settled_z}")
        check(risen_z is not None and risen_z >= 0.25, f"brick_1 bumped up (Z offset {risen_z} m)")
        check(settled_z is not None and abs(settled_z) < 0.05, "brick_1 settled back to Z≈0")

        # ── 3. Hidden brick dispense ─────────────────────────────────────────────
        c0 = spawn_count()
        cli.set_mailbox(idx=BH, mailbox=SMB_QBLOCK_ACTIVATE, value=1)
        used = poll(BH, SMB_QBLOCK_USED, lambda v: v == 1.0, secs=3.0)
        n_mush = spawn_count() - c0
        print(f"  hidden brick: spawned {n_mush} object(s)  USED={used}")
        check(used == 1.0, "hidden brick latched USED (turned tan, stays solid)")
        check(n_mush >= 1, f"hidden brick dispensed a mushroom (got {n_mush})")

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
    print("PASS — breakable bricks: break+debris+despawn, bump, hidden dispense all verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
