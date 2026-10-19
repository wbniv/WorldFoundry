#!/usr/bin/env python3
"""Reproduce the SMB ?-block "generate a gold" crash.

New block-IS-generator design (docs/plans/2026-05-19-smb-block-generator-coin.md):
the block self-detects a hit-from-below by reading its OWN per-actor collision
mailboxes (3044 COLLIDER_IDX, 3047 COLLISION_NORMAL_Z), then pulses its
activation mailbox (2010) so its Generator fires one `coin_template` (class
`gold`).

This forces that path without driving Mario: we set the BLOCK's own 3044/3047,
so its self-detect script runs the hit-from-below branch and the generator
throws a gold. Watch the engine log for `Generato::FIRING` then the crash.

Usage: python3 tests/repro_gold_spawn_crash.py
"""
from __future__ import annotations
import os, re, subprocess, sys, time
from pathlib import Path

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7779
LOG   = REPO / "tests" / ".repro_gold_spawn.log"

MB_COLLIDER_IDX       = 3044
MB_COLLISION_NORMAL_Z = 3047
MB_ACTIVATE           = 2010   # qblock local activation mailbox

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0")

log_fp = open(LOG, "w")
USE_GDB = os.environ.get("REPRO_GDB") == "1"
if USE_GDB:
    cmd = ["gdb", "-batch", "-ex", "run", "-ex", "bt", "-ex", "quit",
           "--args", str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
           "--debug-bind", "127.0.0.1", "--debug-print-actors"]
else:
    cmd = [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
           "--debug-bind", "127.0.0.1", "--debug-print-actors"]
proc = subprocess.Popen(cmd, cwd=str(CWD), env=env,
                        stdout=log_fp, stderr=subprocess.STDOUT)
print(f"launched {'gdb-wrapped ' if USE_GDB else ''}wf_game pid={proc.pid}")

ACTOR_RE = re.compile(r"^actor idx=(\d+) mesh=(\S+)")

def find_idx(meshes):
    out = {}
    if LOG.exists():
        for line in LOG.read_text(errors="replace").splitlines():
            m = ACTOR_RE.match(line)
            if m and m.group(2) in meshes:
                out[m.group(2)] = int(m.group(1))
    return out

cli = None
try:
    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    print(f"bridge connected on {PORT}")
    time.sleep(1.5)  # let actor-print pass + main loop spin up

    blocks = find_idx(("qblock_00.iff", "qblock_01.iff", "qblock_02.iff"))
    mario  = find_idx(("player.iff",))
    print(f"blocks={blocks} mario={mario}")
    if not blocks:
        print("!! no qblock actors found in log; dumping actor lines:")
        for line in LOG.read_text(errors='replace').splitlines():
            if line.startswith("actor idx="):
                print("   ", line)
        raise SystemExit("cannot locate qblock")

    bidx = sorted(blocks.values())[0]
    midx = next(iter(mario.values())) if mario else 9
    print(f"==> faking hit-from-below on block idx={bidx} (collider={midx}, normalZ=+1)")
    cli.set_mailbox(mailbox=MB_COLLIDER_IDX,       value=midx, idx=bidx)
    cli.set_mailbox(mailbox=MB_COLLISION_NORMAL_Z, value=1.0,  idx=bidx)
    time.sleep(0.5)
    # Belt-and-suspenders: also pulse the activation mailbox directly.
    print(f"==> pulsing activation mailbox {MB_ACTIVATE} on block idx={bidx}")
    cli.set_mailbox(mailbox=MB_ACTIVATE, value=1, idx=bidx)

    # Give the engine a couple seconds to fire the generator (and crash).
    for _ in range(20):
        if proc.poll() is not None:
            print(f"!! engine EXITED early, returncode={proc.returncode}")
            break
        time.sleep(0.25)
finally:
    if cli:
        try: cli.close()
        except Exception: pass
    if proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=3)
        except Exception: proc.kill()
    log_fp.close()

print(f"\n==== engine returncode: {proc.returncode} ====")
print(f"==== tail of {LOG} ====")
lines = LOG.read_text(errors="replace").splitlines()
for line in lines[-40:]:
    print(line)
