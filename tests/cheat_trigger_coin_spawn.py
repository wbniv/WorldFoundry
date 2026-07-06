#!/usr/bin/env python3
"""Cheat-trigger SMB W1-1 coin spawn via the debug bridge.

Forces Mario's bump-detection path to fire COIN_SPAWN without needing to
walk-and-jump Mario into a `?` block. Used during Phase 2 template-object
bring-up — see docs/plans/2026-05-19-template-object-jolt-body-sync.md.

Usage:
  python3 tests/cheat_trigger_coin_spawn.py [--port 7779] [--idx 9]

Mario's bump-detection script (in blender_create_smb.py) reads three
mailboxes:
  - INDEXOF_COLLIDER_IDX        (3044) — must be nonzero (block actor index)
  - INDEXOF_COLLISION_NORMAL_Z  (3047) — must be > 0 (hit from below)
  - INDEXOF_SMB_QBLOCK_0_NORMAL (1803) — must be nonzero (block in "fresh" state)

We write per-actor mailboxes 3044/3047 on Mario (default idx=9) to fake
"head bumped block 13 with normal pointing up." Mario's script then runs
its bump branch which pulses INDEXOF_SMB_QBLOCK_0_COIN_SPAWN to 1, and the
per-block Generator picks that up next tick to fire one coin instance.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402

MAILBOX_COLLIDER_IDX       = 3044  # per-actor
MAILBOX_COLLISION_NORMAL_Z = 3047  # per-actor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7779)
    ap.add_argument("--idx",  type=int, default=9,
                    help="Mario's actor index (default 9 for smb_w1_1)")
    ap.add_argument("--block-idx", type=int, default=13,
                    help="Fake collider actor index (default 13 = qblock_00)")
    ap.add_argument("--screenshot-dir", type=Path, default=None,
                    help="If set, capture coin arc PNGs into this directory")
    args = ap.parse_args()

    b = BridgeClient(host=args.host, port=args.port, timeout=4.0)
    time.sleep(0.3)

    if args.screenshot_dir:
        args.screenshot_dir.mkdir(parents=True, exist_ok=True)
        b.send({"op": "screenshot",
                "filename": str(args.screenshot_dir / "00_pre.png")})
        time.sleep(0.2)

    print(f"cheat-triggering bump: idx={args.idx} block={args.block_idx}")
    b.set_mailbox(mailbox=MAILBOX_COLLIDER_IDX,       value=args.block_idx, idx=args.idx)
    b.set_mailbox(mailbox=MAILBOX_COLLISION_NORMAL_Z, value=1.0,            idx=args.idx)

    if args.screenshot_dir:
        # Capture the arc — coin should be visible in early frames, then arc + fall
        for t_ms, label in [(150, "01_spawn"), (400, "02_rising"),
                             (700, "03_apex"),   (1100, "04_falling"),
                             (1700, "05_late")]:
            time.sleep(max(0.0, t_ms / 1000.0 - (time.time() - 0)))
            b.send({"op": "screenshot",
                    "filename": str(args.screenshot_dir / f"{label}.png")})
            time.sleep(0.2)

    b.close()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
