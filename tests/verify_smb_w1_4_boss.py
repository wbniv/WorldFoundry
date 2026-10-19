#!/usr/bin/env python3
"""Verify SMB W1-4 boss (Phase 3): Fake Bowser walks + fires, axe ends the level.

Boots smb_w1_4 headless with the debug bridge and asserts:
  1. clean boot (no assertion),
  2. Fake Bowser PATROLS — its X_POS changes over time and stays within the bridge
     rails [184, 228],
  3. Bowser FIRES — the global SMB_BOWSER_FIRE pulses to 1 within a few seconds,
  4. the AXE ENDS the level — teleporting Mario onto the axe raises SMB_CELEBRATE
     and the Director then writes END_OF_LEVEL.

Run:  python3 tests/verify_smb_w1_4_boss.py
"""
from __future__ import annotations
import os, sys, time, signal, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient, discover_by_pos

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_4-standalone.iff"
LEV   = REPO / "wflevels" / "smb_w1_4" / "smb_w1_4.lev"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7788
LOG   = REPO / "tests" / ".boss_run.log"

X_POS, Z_POS, XSPEED, ZSPEED = 3009, 3011, 3018, 3020
PIDX = 9                                  # player actor idx
SMB_CELEBRATE, SMB_BOWSER_FIRE, END_OF_LEVEL = 1862, 1872, 1905
AXE_X = 152 * 1.5                          # col 152 → 228 m

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}",
     "--debug-port", str(PORT), "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

def shutdown():
    try:
        proc.send_signal(signal.SIGTERM); proc.wait(timeout=3)
    except Exception:
        proc.kill()

ok = True
try:
    time.sleep(2.5)
    assert "ASSERTION FAILED" not in LOG.read_text(errors="ignore"), "engine assert on boot"

    bowser = discover_by_pos(LOG, LEV, {"bowser"}, timeout=10.0, tol=0.8)
    bidx = bowser["bowser"]
    print(f"[boss] bowser = actor idx {bidx}")

    cli = BridgeClient(port=PORT)
    cli.watch(bidx, X_POS)
    cli.watch(1, SMB_BOWSER_FIRE)

    xs: list[float] = []
    fired = False
    t_end = time.time() + 6.0   # ≥ 2× the 2.5 s fire interval so a pulse is guaranteed
    while time.time() < t_end:
        x = cli.mailbox_values.get((bidx, X_POS))
        if x is not None and (not xs or abs(x - xs[-1]) > 1e-4):
            xs.append(x)
        # SMB_BOWSER_FIRE pulses for a single frame — scan every broadcast, not the
        # latched value (which we'd almost always sample as 0).
        with cli._lock:
            for m in cli._inbox:
                if m.get("op") == "mailbox" and m.get("mailbox") == SMB_BOWSER_FIRE \
                        and (m.get("value") or 0) >= 1:
                    fired = True
                    break
        time.sleep(0.05)

    print(f"[boss] bowser X span: {min(xs):.1f}..{max(xs):.1f} ({len(xs)} samples); "
          f"fired={fired}")
    assert len(xs) >= 4, f"bowser did not move ({len(xs)} samples)"
    assert max(xs) - min(xs) > 1.0, "bowser barely moved (not patrolling)"
    assert min(xs) > 180 and max(xs) < 232, f"bowser left the bridge: {min(xs)}..{max(xs)}"
    assert fired, "bowser never pulsed SMB_BOWSER_FIRE"

    # --- axe ends the level ---
    # Teleport Mario onto the axe until SMB_CELEBRATE latches, THEN stop forcing his
    # position (the celebration sequencer walks him into the castle) and wait out the
    # ~4.5 s cutscene for END_OF_LEVEL.
    cli.watch(1, SMB_CELEBRATE); cli.watch(1, END_OF_LEVEL)
    celebrated = ended = False
    t_end = time.time() + 10.0
    while time.time() < t_end:
        if not celebrated:
            cli.set_mailbox(X_POS, int(AXE_X), idx=PIDX)
            cli.set_mailbox(Z_POS, 2, idx=PIDX)
            cli.set_mailbox(XSPEED, 0, idx=PIDX); cli.set_mailbox(ZSPEED, 0, idx=PIDX)
        if (cli.mailbox_values.get((1, SMB_CELEBRATE)) or 0) >= 1:
            celebrated = True
        with cli._lock:
            for m in cli._inbox:
                if m.get("op") == "mailbox" and m.get("mailbox") == END_OF_LEVEL \
                        and (m.get("value") or 0) >= 1:
                    ended = True
                    break
        if ended:
            break
        time.sleep(0.05)
    cli.close()

    print(f"[boss] axe → SMB_CELEBRATE={celebrated}  END_OF_LEVEL={ended}")
    assert celebrated, "axe touch did not raise SMB_CELEBRATE"
    assert ended, "celebration did not fire END_OF_LEVEL"

    print("[boss] PASS — Bowser patrols + fires; axe ends the level")
except AssertionError as e:
    ok = False
    print(f"[boss] FAIL — {e}")
finally:
    shutdown()
    log_fp.close()
sys.exit(0 if ok else 1)
