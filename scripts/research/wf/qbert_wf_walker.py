#!/usr/bin/env python3
"""WF-side walker harness — Phase E parity for the ROM-grounded Q*bert walker.

Connects to a running wf_game (debug bridge on TCP/7777), enables autopilot,
watches the CAPTURE_TRIGGER mailbox (mb 432), and asks the engine to dump a
PNG via the `screenshot` op at each capture point. Output PNGs land in
docs/investigations/wf-screenshots/ as `wf_walker_L{level}R{round}_{state}.png`,
mirroring the MAME walker captures already in mame-screenshots/.

Run wf_game separately first (engine must be up before this connects):
    cd wfsource/source/game && ./wf_game cd_qbert.iff &

Then:
    python3 scripts/research/wf/qbert_wf_walker.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from tests.debug_bridge_client import BridgeClient

CAPTURE_TRIGGER = 432   # mb[432] — see blender_create_qbert.py mailbox layout
ROUND_NUMBER    = 425   # mb[425] — 0-based round counter
AUTOPILOT_ON    = 430

STATE_NAMES = {1: "state0", 2: "state1", 3: "clear"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7777)
    ap.add_argument("--actor", type=int, default=1,
                    help="Actor to watch — any actor reads mb[432] from the "
                         "level fallthrough since it's > NumberOfLocalMailboxes.")
    ap.add_argument("--out-dir", default="docs/investigations/wf-screenshots",
                    type=lambda p: str((REPO_ROOT / p).resolve()))
    ap.add_argument("--max-rounds", type=int, default=16,
                    help="Stop after this many round-clears (default 16 = 4x4).")
    ap.add_argument("--timeout", type=float, default=600.0,
                    help="Walltime ceiling in seconds (default 600 = 10 min).")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[walker] connecting to {args.host}:{args.port}")
    cli = BridgeClient(args.host, args.port)

    # Subscribe to the two mailboxes we drive off of.
    cli.watch(args.actor, CAPTURE_TRIGGER)
    cli.watch(args.actor, ROUND_NUMBER)
    time.sleep(0.1)  # let the first 0-broadcast land before we set autopilot

    print("[walker] enabling autopilot")
    cli.set_mailbox(AUTOPILOT_ON, 1, idx=args.actor)

    deadline = time.time() + args.timeout
    last_trigger = 0
    rounds_seen = 0
    cur_round = 0

    while time.time() < deadline and rounds_seen < args.max_rounds:
        time.sleep(0.05)
        with cli._lock:                                       # noqa: SLF001
            trigger = int(cli.mailbox_values.get((args.actor, CAPTURE_TRIGGER), 0))
            cur_round = int(cli.mailbox_values.get((args.actor, ROUND_NUMBER), 0))

        if trigger == last_trigger or trigger == 0:
            last_trigger = trigger
            continue

        # New non-zero capture event.
        state = STATE_NAMES.get(trigger)
        last_trigger = trigger
        if state is None:
            print(f"[walker] unknown trigger value {trigger}, skipping")
            continue

        # Convert 0-based round counter to (level, round-in-level), 1-based.
        L = cur_round // 4 + 1
        R = cur_round % 4 + 1
        filename = str(out / f"wf_walker_L{L}R{R}_{state}.png")
        print(f"[walker] L{L}R{R} {state} → {filename}")
        cli.send({"op": "screenshot", "filename": filename})
        # Wait for the engine's ack so we don't pile up screenshot ops.
        msg = cli.wait_for(
            lambda m: m.get("op") in ("screenshot_done", "error")
                      and m.get("filename") == filename,
            timeout=5.0)
        if msg is None:
            print(f"[walker]   WARN: no screenshot_done within 5s for {filename}")
        elif msg.get("op") == "error":
            print(f"[walker]   ERROR: {msg}")

        if state == "clear":
            rounds_seen += 1

    cli.set_mailbox(AUTOPILOT_ON, 0, idx=args.actor)
    cli.close()

    n = sum(1 for _ in out.glob("wf_walker_L*R*_state*.png"))
    print(f"[walker] done — {rounds_seen} round-clears, "
          f"{n} state captures in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
