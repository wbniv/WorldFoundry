#!/usr/bin/env python3
"""WF-side walker — drives qbert through the 28-cube coverage path by
injecting joystick bits via the debug bridge.

The level's player script has the standard joystick-to-hop branch
(cardinal stick bits → diagonal hops, gated on HOP_COOLDOWN==0 and
INTRO_DONE). This script presses one direction per hop, waits for the
HOP_COOLDOWN to clear, optionally screenshots, and repeats.

Run wf_game separately first:
    cd wfsource/source/game && DISPLAY=:0 ../../../engine/wf_game \\
        -L../../../wflevels/qbert_practice-standalone.iff \\
        -record_video --debug-port 7777 &

Then:
    python3 scripts/research/wf/qbert_wf_walker.py --max-rounds 2
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from tests.debug_bridge_client import BridgeClient

# Joystick raw bits the level script branches on. Cardinal stick → diagonal
# hop (cabinet rotated 45 degrees). Bit values match
# blender_create_qbert.py player script.
UP    = 0x0800   # -> NE
DOWN  = 0x1000   # -> SW
RIGHT = 0x2000   # -> SE
LEFT  = 0x4000   # -> NW

# Warnsdorff coverage of all 28 cubes from apex. 32 hops; visits each cube
# at least once. Translated from the original `step-move` Forth table.
# Each entry is a joystick bit; the level's joystick branch turns it into
# a diagonal hop direction.
COVERAGE_PATH = [
    DOWN, UP, RIGHT, DOWN, LEFT, DOWN, DOWN, DOWN,
    UP, RIGHT, UP, RIGHT, UP, UP, RIGHT, DOWN,
    RIGHT, UP, RIGHT, RIGHT, LEFT, DOWN, LEFT, DOWN,
    LEFT, DOWN, LEFT, DOWN, LEFT, DOWN, LEFT, DOWN,
]

HOP_COOLDOWN_MB = 402   # 0 = ready for next hop
ROUND_CLEAR_MB  = 413   # 1 when all 28 cubes flipped, before respawn fires
ROUND_NUMBER_MB = 425   # increments per cleared round
INTRO_DONE_MB   = 418
GAME_OVER_MB    = 420
FALL_PHASE_MB   = 419
CAPTURE_MB      = 432   # state-trigger for walker screenshots


def wait_for_hop_cycle(cli: BridgeClient, actor: int, timeout: float = 5.0) -> bool:
    """Block until the engine has both started AND finished a hop: cooldown
    goes 0 -> >0 -> 0. Avoids a race where wait-for-zero returns immediately
    because cooldown was *already* zero from the previous step."""
    deadline = time.time() + timeout
    saw_nonzero = False
    while time.time() < deadline:
        with cli._lock:
            cd = cli.mailbox_values.get((actor, HOP_COOLDOWN_MB))
        if cd is not None:
            if not saw_nonzero and cd > 0.5:
                saw_nonzero = True
            elif saw_nonzero and abs(cd) < 1e-3:
                return True
        time.sleep(0.03)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7777)
    ap.add_argument("--actor", type=int, default=1,
                    help="Player actor index — used for mailbox watches. The "
                         "joystick mailboxes are global; idx routing falls "
                         "through to the level for non-local mailbox indices.")
    ap.add_argument("--max-rounds", type=int, default=2,
                    help="Stop after this many round clears.")
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="Walltime ceiling in seconds.")
    ap.add_argument("--press-frames", type=int, default=2,
                    help="Frames to hold each direction press.")
    ap.add_argument("--out-dir", default="docs/investigations/wf-screenshots",
                    type=lambda p: str((REPO_ROOT / p).resolve()))
    ap.add_argument("--no-screenshots", action="store_true",
                    help="Skip per-hop screenshot capture.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if not args.no_screenshots:
        out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[walker] connecting to {args.host}:{args.port}")
    cli = BridgeClient(args.host, args.port)
    for m in (HOP_COOLDOWN_MB, ROUND_NUMBER_MB, INTRO_DONE_MB,
              GAME_OVER_MB, FALL_PHASE_MB):
        cli.watch(args.actor, m)

    print("[walker] waiting for intro to finish")
    if not cli.wait_for_mailbox(args.actor, INTRO_DONE_MB, 1.0, timeout=30.0):
        print("[walker] intro never completed; bailing")
        cli.close()
        return 1

    deadline = time.time() + args.timeout
    rounds_seen = 0
    last_round = 0

    cli.watch(args.actor, 400)         # ROW
    cli.watch(args.actor, 401)         # COL
    cli.watch(args.actor, 72)          # LIVES
    cli.watch(args.actor, ROUND_CLEAR_MB)

    while rounds_seen < args.max_rounds and time.time() < deadline:
        # Optional state-0 screenshot at apex before each round.
        if not args.no_screenshots:
            r1 = last_round // 4 + 1
            r2 = last_round % 4 + 1
            fn = str(out_dir / f"wf_walker_L{r1}R{r2}_state0.png")
            cli.send({"op": "screenshot", "filename": fn})
            cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error")
                                   and m.get("filename") == fn, timeout=3.0)

        for step_idx, bit in enumerate(COVERAGE_PATH):
            if time.time() >= deadline:
                break

            with cli._lock:
                go = cli.mailbox_values.get((args.actor, GAME_OVER_MB), 0)
                lives = cli.mailbox_values.get((args.actor, 72), 3)
                row = cli.mailbox_values.get((args.actor, 400), 0)
                col = cli.mailbox_values.get((args.actor, 401), 0)
            if go and go >= 1.0:
                print(f"[walker] step {step_idx} GAME_OVER (last (r,c)=({row},{col}) lives={lives}); stopping")
                cli.close()
                return 2

            dirname = {UP:"UP", DOWN:"DOWN", LEFT:"LEFT", RIGHT:"RIGHT"}[bit]
            print(f"[walker] step {step_idx:2d} {dirname:5s} (r,c)=({row},{col}) lives={lives}")

            cli.inject_input("joystick1_raw", bit,
                             duration_frames=args.press_frames)

            if not wait_for_hop_cycle(cli, args.actor, timeout=5.0):
                print(f"[walker] step {step_idx} hop cycle stuck; stopping")
                cli.close()
                return 3

            # Round-clear watch — when ROUND_CLEAR latches we STOP injecting
            # immediately. The director's respawn handler then teleports Q*bert
            # back to apex; we wait for the round counter to bump (which also
            # clears ROUND_CLEAR) before starting the next path.
            with cli._lock:
                rc = cli.mailbox_values.get((args.actor, ROUND_CLEAR_MB), 0)
            if rc and rc >= 1.0:
                print(f"[walker] ROUND_CLEAR latched at step {step_idx} — waiting for respawn")
                # Wait for ROUND_NUMBER to advance (director's apex respawn fires
                # in the same handler that bumps the counter; if we inject during
                # this window Q*bert hops off the bottom row).
                advance_deadline = time.time() + 10.0
                while time.time() < advance_deadline:
                    with cli._lock:
                        cur_round = int(cli.mailbox_values.get(
                            (args.actor, ROUND_NUMBER_MB), 0))
                    if cur_round != last_round:
                        rounds_seen += 1
                        last_round = cur_round
                        print(f"[walker] round cleared -> {cur_round} "
                              f"({rounds_seen}/{args.max_rounds})")
                        break
                    time.sleep(0.05)
                # Extra settle frames so the first inject of the next round
                # doesn't race the respawn teleport.
                time.sleep(0.5)
                break

    cli.close()
    print(f"[walker] done — {rounds_seen} rounds cleared")
    return 0 if rounds_seen >= args.max_rounds else 4


if __name__ == "__main__":
    raise SystemExit(main())
