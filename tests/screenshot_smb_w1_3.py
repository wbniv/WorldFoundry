#!/usr/bin/env python3
"""Capture SMB W1-3 verification stills via the debug bridge.

Boots smb_w1_3-standalone.iff on :0, grabs the spawn frame (confirms the popup-visibility
fix — no stray score-diamond near Mario — and the sky-blue overworld matte), then teleports
Mario onto successive tree-tops (left→right, so the camera ratchet follows) and screenshots
each region: the early Koopa/coin trees, the Goomba tree + ? block, the tall tree + movers,
the wide Koopa tree + paratroopa, and the flagpole approach.

Engine FBO screenshot via the bridge ("op":"screenshot"); needs the real :0 display.
Usage: python3 tests/screenshot_smb_w1_3.py [--out-dir /home/will/tmp/smb_w13]
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys, time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_3-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7795
LOG   = REPO / "tests" / ".screenshot_smb_w1_3.log"

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402

# player-local system mailboxes
X_POS, Y_POS, Z_POS, XSPEED, ZSPEED = 3009, 3010, 3011, 3018, 3020
T = 1.5

# (label, col, canopy_top_tiles) — teleport Mario to (col*T, canopy_top + 0.6T) and shoot.
POINTS = [
    ("01_spawn",      None, None),   # no teleport: start strip + tree_a; popup-fix check
    ("02_koopa1",     22, 4),        # Koopa #1 on tree_b1
    ("03_coins3",     29, 4),        # 3 coins over tree_b2
    ("04_goombas",    45, 5),        # 2 Goombas on the tallest tree + ? block nearby
    ("05_tall_tree",  75, 6),        # tall tree (4 coins) + lift bay
    ("06_movers",     87, 4),        # two static movers + 8 coins
    ("07_koopa2_para",102, 4),       # wide tree Koopa #2 + paratroopa over the gap
    ("08_coins_para", 118, 3),       # short tree 3 coins + paratroopa #2
    ("09_flagpole",   138, 1),       # stone platform + staircase + flagpole + castle
]


def screenshot(cli, path):
    cli.send({"op": "screenshot", "filename": path})
    msg = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
    ok = msg and msg.get("op") == "screenshot_done"
    print(f"  screenshot {'OK  ' if ok else 'WARN'} {os.path.basename(path)}")


def discover_player(timeout=10.0):
    deadline = time.time() + timeout
    rx = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")
    while time.time() < deadline:
        try:
            for m in rx.finditer(LOG.read_text(errors="replace")):
                if "player" in m.group(2):
                    return int(m.group(1))
        except OSError:
            pass
        time.sleep(0.1)
    return 9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("/home/will/tmp/smb_w13"))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
    env.setdefault("DISPLAY", ":0"); env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"
    log_fp = open(LOG, "w")
    proc = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
         "--debug-print-actors"],
        cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
    try:
        time.sleep(2.5)
        player = discover_player()
        print(f"player idx={player}")
        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        time.sleep(1.0)
        for label, col, top in POINTS:
            if col is not None:
                cli.set_mailbox(idx=player, mailbox=XSPEED, value=0)
                cli.set_mailbox(idx=player, mailbox=ZSPEED, value=0)
                cli.set_mailbox(idx=player, mailbox=Y_POS, value=0)
                cli.set_mailbox(idx=player, mailbox=Z_POS, value=int((top*T + 0.6*T)))
                cli.set_mailbox(idx=player, mailbox=X_POS, value=int(col*T))
                time.sleep(0.8)   # let the camera ratchet pan + Mario settle
            else:
                time.sleep(1.0)
            screenshot(cli, str(args.out_dir / f"{label}.png"))
        print(f"\nstills → {args.out_dir}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
