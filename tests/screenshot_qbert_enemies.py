#!/usr/bin/env python3
"""Capture Slick/Sam/Ugg/Wrong-Way standing on the pyramid, via the debug bridge.

These enemies are director-spawned and parked off-screen until then, so we boot
the level, jump to a round that unlocks all four, suppress the other enemies to
cut clutter, zero the four spawn timers, and grab a burst of frames (so we catch
landed poses, not just mid-hop). Used to verify the feet-origin mesh fix
(docs/plans/2026-05-22-qbert-slick-sam-feet-origin.md).

Usage:
  python3 tests/screenshot_qbert_enemies.py --out-dir /home/will/tmp/qbert_feet/before
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "qbert_practice-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7782

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402

# Mailboxes (must match blender_create_qbert.py / test_director_mailbox.py).
MB_INTRO_DONE   = 418
MB_GAME_OVER    = 420
MB_LAST_STICK   = 422
MB_ROUND_NUMBER = 425
MB_ROUND_CHANGED = 426
MB_LIVES        = 72
MB_FREEZE_TIMER = 546
MB_GO_BLOCK     = 590
MB_GO_HOLD_TIMER = 591
UP = 0x0800

MB_RB_SPAWN_TIMER      = 512
MB_COILY_SPAWN_DELAY   = 544
MB_GB_SPAWN_TIMER      = 547
MB_SLICK_SPAWN_TIMER   = 550
MB_SAM_SPAWN_TIMER     = 552
MB_UGG_SPAWN_TIMER     = 570
MB_WW_SPAWN_TIMER      = 572
MB_COILY_SPAWN_DELAY_2 = 585

MB_RB_ACTIVE_BASE      = 514
MB_GB_ACTIVE           = 548
MB_SLICK_ACTIVE        = 549
MB_SAM_ACTIVE          = 551
MB_UGG_ACTIVE          = 569
MB_WW_ACTIVE           = 571
MB_COILY_EGG_ACTIVE    = 573
MB_COILY_SNAKE_ACTIVE  = 574
MB_COILY_EGG2_ACTIVE   = 586
MB_COILY_PHASE_GLOBAL  = 543
MB_COILY_ROUND_DONE    = 542
MB_COILY_EGG2_ROUND_DONE = 584

_SUPPRESSED = 100000   # far beyond capture window — keeps clutter enemies parked

# Actor indices + per-actor mailbox layout (from the regen log / blender_create_qbert.py).
IDX = {"slick": 22, "sam": 23, "ugg": 24, "ww": 25}
BASE = {"slick": 494, "sam": 502, "ugg": 553, "ww": 561}
ACTIVE = {"slick": 549, "sam": 551, "ugg": 569, "ww": 571}
OFF_ROW, OFF_COL, OFF_CD, OFF_PHASE, OFF_START_Z, OFF_END_Z, OFF_FROM_ROW, OFF_FROM_COL = range(8)
# Per-actor world-position mailboxes (X/Y/Z), read-write. (The delta-rotation
# mailboxes 3034/3035 are write-only and abort the bridge if poked, so the
# climbers are spawned through the director instead — see arm_climbers.)
MB_X_POS, MB_Y_POS, MB_Z_POS = 3009, 3010, 3011
SQRT2, CUBE_SIZE, CUBE_BASE_Z, NUM_ROWS = 1.4142136, 2.0, 1.0, 7


def cube_top(row, col):
    """World (X, Y, Z) of the TOP-centre of cube (row, col) — the feet-contact
    point. Mirrors cube_world_position() + CUBE_SIZE/2 in blender_create_qbert.py."""
    x = SQRT2 * (col - row / 2.0) * CUBE_SIZE
    y = SQRT2 * (NUM_ROWS - 1 - row) * (CUBE_SIZE / 2.0)
    z = CUBE_BASE_Z + (NUM_ROWS - 1 - row) * CUBE_SIZE + CUBE_SIZE / 2.0  # = 14 - 2*row
    return x, y, z


def read_mb(cli: BridgeClient, mb: int, idx: int = 1) -> float | None:
    cli.watch(idx=idx, mailbox=mb)
    time.sleep(0.2)
    with cli._lock:
        val = cli.mailbox_values.get((idx, mb))
    cli.unwatch(idx=idx, mailbox=mb)
    return val


def screenshot(cli: BridgeClient, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cli.send({"op": "screenshot", "filename": path})
    msg = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
    ok = msg and msg.get("op") == "screenshot_done"
    print(f"  screenshot {'OK ' if ok else 'WARN'} {os.path.basename(path)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("/home/will/tmp/qbert_feet/shot"))
    ap.add_argument("--level", type=Path, default=LEVEL,
                    help="standalone .iff to load (point at the old build for 'before')")
    ap.add_argument("--round", type=int, default=3)   # level idx 3 = "L4": unlocks all four
    ap.add_argument("--frames", type=int, default=24)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    env.setdefault("DISPLAY", ":0")

    log = open(REPO / "tests" / ".screenshot_qbert_enemies.log", "w")
    proc = subprocess.Popen([str(WF), f"-L{args.level}",
                             "--debug-port", str(PORT), "--debug-bind", "127.0.0.1"],
                            cwd=str(CWD), env=env, stdout=log, stderr=subprocess.STDOUT)
    print(f"launched wf_game pid={proc.pid} on port {PORT}")

    cli = None
    try:
        cli = BridgeClient("127.0.0.1", PORT, timeout=20.0)
        print("bridge connected")
        time.sleep(2.0)
        screenshot(cli, str(args.out_dir / "boot.png"))

        # The level boots into the attract / GAME OVER screen. The Forth player
        # script restarts into gameplay on a joystick edge, but only once the C++
        # GO_HOLD_TIMER (armed ~180 frames on the game-over edge) has expired.
        # Wait it out, then drive the edge (prev-stick=0 -> stick!=0).
        print("  waiting out GO_HOLD_TIMER ...")
        time.sleep(7.0)
        started = False
        for attempt in range(10):
            cli.set_mailbox(mailbox=MB_GO_BLOCK, value=0, idx=0)
            cli.set_mailbox(mailbox=MB_GO_HOLD_TIMER, value=0, idx=0)
            cli.set_mailbox(mailbox=MB_LAST_STICK, value=0, idx=0)
            time.sleep(0.1)
            cli.inject_input("joystick1_raw", UP, duration_frames=4)
            time.sleep(0.5)
            go = read_mb(cli, MB_GAME_OVER)
            if go == 0:
                started = True
                break
        print(f"  restart {'OK' if started else 'FAILED'} after {attempt + 1} tries (game_over={go})")
        cli.set_mailbox(mailbox=MB_LIVES, value=3, idx=0)
        cli.set_mailbox(mailbox=MB_INTRO_DONE, value=1, idx=0)
        cli.set_mailbox(mailbox=MB_FREEZE_TIMER, value=7200, idx=0)
        time.sleep(0.3)

        # Jump to a round that unlocks Slick/Sam (L2+) and Ugg/WW (L3+).
        cli.set_mailbox(mailbox=MB_ROUND_NUMBER, value=args.round, idx=0)
        cli.set_mailbox(mailbox=MB_ROUND_CHANGED, value=1, idx=0)
        cli.set_mailbox(mailbox=MB_FREEZE_TIMER, value=7200, idx=0)
        time.sleep(0.6)

        # Clear active mirrors + Coily internal gates.
        for k in range(3):
            cli.set_mailbox(mailbox=MB_RB_ACTIVE_BASE + k, value=0, idx=0)
        for mb in (MB_GB_ACTIVE, MB_SLICK_ACTIVE, MB_SAM_ACTIVE, MB_UGG_ACTIVE,
                   MB_WW_ACTIVE, MB_COILY_EGG_ACTIVE, MB_COILY_SNAKE_ACTIVE,
                   MB_COILY_EGG2_ACTIVE):
            cli.set_mailbox(mailbox=mb, value=0, idx=0)
        for mb in (MB_COILY_PHASE_GLOBAL, MB_COILY_ROUND_DONE, MB_COILY_EGG2_ROUND_DONE):
            cli.set_mailbox(mailbox=mb, value=0, idx=0)

        # The director's sequencer is unpredictable (and blocks climbers while
        # Coily is active), so spawn the four directly by replicating their spawn
        # mailbox writes. Descenders (Slick/Sam) hop down from row 1; climbers
        # (Ugg/WW) tip onto the side faces via Euler-reset + DELTA pitch/yaw and
        # climb up from row 6.
        def amb(off, val, who):    # per-actor mailbox write
            cli.set_mailbox(mailbox=BASE[who] + off, value=val, idx=IDX[who])

        def place_descender_static(who, row, col):
            # PHASE=0 -> the enemy script early-exits and never moves the actor;
            # we then pin its position to the cube-top contact point. Identical
            # handle position in both builds, so the only difference is where the
            # mesh sits relative to its origin: old (center) sinks, new (feet)
            # stands. This is the apples-to-apples before/after.
            amb(OFF_PHASE, 0, who)
            cli.set_mailbox(mailbox=ACTIVE[who], value=1, idx=0)
            x, y, z = cube_top(row, col)
            cli.set_mailbox(mailbox=MB_X_POS, value=x, idx=IDX[who])
            cli.set_mailbox(mailbox=MB_Y_POS, value=y, idx=IDX[who])
            cli.set_mailbox(mailbox=MB_Z_POS, value=z, idx=IDX[who])

        # Climbers tilt onto the side face via DELTA_PITCH/YAW, which the bridge
        # can't write (write-only — only Forth's write-actor-mailbox can). So
        # spawn climbers through the DIRECTOR (arm their spawn timer + clear the
        # Coily gate that blocks them); the Forth spawn writes the rotation
        # correctly. Ugg/WW gate to one-at-a-time (rival check), so they alternate.
        def arm_climbers():
            for mb in (MB_COILY_PHASE_GLOBAL, MB_COILY_ROUND_DONE):
                cli.set_mailbox(mailbox=mb, value=0, idx=0)
            cli.set_mailbox(mailbox=MB_UGG_SPAWN_TIMER, value=0, idx=0)
            cli.set_mailbox(mailbox=MB_WW_SPAWN_TIMER, value=0, idx=0)

        def kill_clutter():
            for mb in (MB_RB_SPAWN_TIMER, MB_COILY_SPAWN_DELAY, MB_GB_SPAWN_TIMER,
                       MB_COILY_SPAWN_DELAY_2):
                cli.set_mailbox(mailbox=mb, value=_SUPPRESSED, idx=0)
            for k in range(3):
                cli.set_mailbox(mailbox=MB_RB_ACTIVE_BASE + k, value=0, idx=0)
            for mb in (MB_GB_ACTIVE, MB_COILY_EGG_ACTIVE, MB_COILY_SNAKE_ACTIVE,
                       MB_COILY_EGG2_ACTIVE):
                cli.set_mailbox(mailbox=mb, value=0, idx=0)

        cli.set_mailbox(mailbox=MB_FREEZE_TIMER, value=0, idx=0)
        time.sleep(0.5)
        print("  intro_done =", read_mb(cli, MB_INTRO_DONE),
              " round =", read_mb(cli, MB_ROUND_NUMBER),
              " game_over =", read_mb(cli, MB_GAME_OVER))

        for i in range(args.frames):
            cli.set_mailbox(mailbox=MB_LIVES, value=3, idx=0)
            kill_clutter()
            arm_climbers()
            # Pin the descenders standing on large front cubes (re-assert every
            # frame so nothing drifts them) for a clear, same-cube before/after.
            place_descender_static("slick", 5, 1)
            place_descender_static("sam", 5, 4)
            time.sleep(0.18)
            # Clear the GAME OVER latch immediately before the grab (the
            # uncontrolled player keeps dying and re-arms it within the gap).
            cli.set_mailbox(mailbox=MB_GAME_OVER, value=0, idx=0)
            time.sleep(0.05)
            screenshot(cli, str(args.out_dir / f"f{i:02d}.png"))
        print(f"frames written to {args.out_dir}")
        return 0
    finally:
        if cli:
            cli.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
