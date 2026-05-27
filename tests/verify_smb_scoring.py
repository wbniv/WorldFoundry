#!/usr/bin/env python3
"""Verify the SMB scoring system and 1UP mushroom.

Companion to docs/plans/2026-05-27-smb-scoring-and-1up-mushroom.md.

Checks:
  1. HUD_SCORE comes from SMB_SCORE (not raw GOLD count).
  2. Coin pickup (GOLD increment) → HUD_SCORE += 200 per coin.
  3. Stomp event (SMB_STOMP = 1) → HUD_SCORE += 100.
  4. 1UP signal (SMB_ONEUP_PICKUP = 1) → LIVES += 1.
  5. Flagpole / END_OF_LEVEL edge → HUD_SCORE increases by at least 100.

All checks use mailbox injection (no physics) — fast and deterministic.
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
LOG   = REPO / "tests" / ".verify_smb_scoring.log"
PORT  = 7793

# Global mailboxes (read at idx=1)
HUD_SCORE       = 70
LIVES           = 72
TIME_MB         = 1906
SMB_SCORE       = 1838
SMB_LAST_GOLD   = 1839
SMB_EOL_LATCH   = 1840
SMB_ONEUP_PICKUP = 1841
SMB_STOMP       = 1806
SMB_LIVES_INIT  = 1807
END_OF_LEVEL    = 1905

# Per-actor mailboxes (offset >= 3000)
GOLD_MB         = 3001   # player's cumulative coin count

_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")


def discover_substr(substrs, timeout=8.0) -> dict[str, int]:
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    while time.time() < deadline and len(found) < len(substrs):
        try:
            for m in _MESH_RE.finditer(LOG.read_text(errors="replace")):
                mesh = m.group(2)
                for s in substrs:
                    if s not in found and s in mesh:
                        found[s] = int(m.group(1))
        except OSError:
            pass
        if len(found) < len(substrs):
            time.sleep(0.15)
    return found


def main() -> int:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    env.setdefault("DISPLAY", ":0")
    log_fp = open(LOG, "w")
    argv = [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
            "--debug-bind", "127.0.0.1", "--debug-print-actors"]
    proc = subprocess.Popen(argv, cwd=str(CWD), env=env,
                            stdout=log_fp, stderr=subprocess.STDOUT)

    cli = None
    fails: list[str] = []

    def check(cond, msg):
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
        if not cond:
            fails.append(msg)

    def g(idx, mb):
        with cli._lock:
            return cli.mailbox_values.get((idx, mb))

    def step(n=1, dt=0.05):
        for _ in range(n):
            cli.send({"op": "step"})
            time.sleep(dt)

    def cached(idx, mb):
        with cli._lock:
            return cli.mailbox_values.get((idx, mb)) or 0

    def wait_gt(idx, mb, baseline, timeout=3.0):
        """Wait for mailbox to exceed baseline; returns current value."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with cli._lock:
                v = cli.mailbox_values.get((idx, mb))
            if v is not None and v > baseline:
                return v
            time.sleep(0.05)
        return cached(idx, mb)

    try:
        idx = discover_substr({"player"})
        if "player" not in idx:
            print("FATAL: could not find player"); return 1
        PLAYER = idx["player"]
        print(f"discovered: player={PLAYER}")

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected")
        time.sleep(0.8)

        cli.watch(idx=1, mailbox=HUD_SCORE)
        cli.watch(idx=1, mailbox=SMB_SCORE)
        cli.watch(idx=1, mailbox=LIVES)
        cli.watch(idx=1, mailbox=TIME_MB)
        cli.watch(idx=1, mailbox=SMB_LAST_GOLD)
        # END_OF_LEVEL (1905) is write-only — watching it terminates the engine
        cli.watch(idx=PLAYER, mailbox=GOLD_MB)

        cli.send({"op": "pause"}); time.sleep(0.2)

        # ── Force known state (change-only bridge: we must inject to get notifications) ──
        # Set each to a distinctive sentinel first so the subsequent forced value triggers
        # a change notification even if the field was already at the target.
        cli.set_mailbox(idx=1,      mailbox=SMB_SCORE,    value=9999.0)
        cli.set_mailbox(idx=1,      mailbox=SMB_LAST_GOLD, value=9999.0)
        cli.set_mailbox(idx=PLAYER, mailbox=GOLD_MB,       value=9999.0)
        cli.set_mailbox(idx=1,      mailbox=LIVES,         value=99.0)
        cli.set_mailbox(idx=1,      mailbox=SMB_LIVES_INIT, value=1.0)
        cli.set_mailbox(idx=1,      mailbox=SMB_EOL_LATCH,  value=0.0)
        step(2)
        # Now reset to the real initial values
        cli.set_mailbox(idx=1,      mailbox=SMB_SCORE,    value=0.0)
        cli.set_mailbox(idx=1,      mailbox=SMB_LAST_GOLD, value=0.0)
        cli.set_mailbox(idx=PLAYER, mailbox=GOLD_MB,       value=0.0)
        cli.set_mailbox(idx=1,      mailbox=LIVES,         value=3.0)
        step(4)
        # wait for change notifications to arrive
        if not cli.wait_for_mailbox(1, LIVES, 3.0, timeout=5.0):
            print(f"FATAL: LIVES watch not delivering (got {cached(1, LIVES)})")
            return 1
        # Script writes HUD_SCORE = SMB_SCORE every frame; wait for the 0 round-trip
        if not cli.wait_for_mailbox(1, HUD_SCORE, 0.0, timeout=5.0):
            print(f"WARN: HUD_SCORE watch lag (cached={cached(1, HUD_SCORE)})")

        # ── 1. HUD_SCORE == SMB_SCORE (probed via a sentinel round-trip) ─────
        cli.set_mailbox(idx=1, mailbox=SMB_SCORE, value=42.0)
        step(2)
        cli.wait_for_mailbox(1, HUD_SCORE, 42.0, timeout=3.0)
        hud_probe = cached(1, HUD_SCORE)
        smb_probe = cached(1, SMB_SCORE)
        print(f"  sentinel probe: HUD_SCORE={hud_probe}  SMB_SCORE={smb_probe}")
        check(hud_probe == smb_probe, f"HUD_SCORE ({hud_probe}) mirrors SMB_SCORE ({smb_probe})")
        # reset score to 0 for coin test
        cli.set_mailbox(idx=1, mailbox=SMB_SCORE, value=0.0)
        step(2)
        cli.wait_for_mailbox(1, HUD_SCORE, 0.0, timeout=3.0)
        hud0 = 0

        # ── 2. Coin pickup: GOLD+1 → HUD_SCORE += 200 ────────────────────────
        cli.set_mailbox(idx=PLAYER, mailbox=GOLD_MB, value=1.0)
        step(4)
        cli.wait_for_mailbox(1, HUD_SCORE, 200.0, timeout=3.0)
        hud1 = cached(1, HUD_SCORE)
        smb1 = cached(1, SMB_SCORE)
        print(f"  after 1 coin injection: HUD_SCORE={hud1}  SMB_SCORE={smb1}")
        check(hud1 - hud0 == 200, f"1 coin → HUD_SCORE + 200 (got +{hud1 - hud0})")
        check(smb1 == hud1, f"SMB_SCORE ({smb1}) == HUD_SCORE ({hud1})")

        # Inject two more coins in one step → +400
        cli.set_mailbox(idx=PLAYER, mailbox=GOLD_MB, value=3.0)
        step(4)
        cli.wait_for_mailbox(1, HUD_SCORE, hud1 + 400, timeout=3.0)
        hud2 = cached(1, HUD_SCORE)
        print(f"  after 3 total coins: HUD_SCORE={hud2}")
        check(hud2 - hud1 == 400, f"2 coins at once → HUD_SCORE + 400 (got +{hud2 - hud1})")

        # ── 3. Stomp event → HUD_SCORE += 100 ────────────────────────────────
        cli.set_mailbox(idx=1, mailbox=SMB_STOMP, value=1.0)
        step(4)
        cli.wait_for_mailbox(1, HUD_SCORE, hud2 + 100, timeout=3.0)
        hud3 = cached(1, HUD_SCORE)
        print(f"  after stomp signal: HUD_SCORE={hud3}")
        check(hud3 - hud2 == 100, f"stomp → HUD_SCORE + 100 (got +{hud3 - hud2})")

        # ── 4. 1UP mushroom signal → LIVES += 1 ──────────────────────────────
        # LIVES was forced to 3 above; confirmed by wait_for_mailbox
        lives0 = cached(1, LIVES)
        print(f"  lives before 1UP: {lives0}")
        check(lives0 == 3, f"LIVES is 3 before 1UP (got {lives0})")
        cli.set_mailbox(idx=1, mailbox=SMB_ONEUP_PICKUP, value=1.0)
        step(4)
        cli.wait_for_mailbox(1, LIVES, 4.0, timeout=3.0)
        lives1 = cached(1, LIVES)
        print(f"  lives after 1UP: {lives1}")
        check(lives1 == 4, f"1UP signal → LIVES {lives0} → {lives1}")

        # ── 5. Flagpole / END_OF_LEVEL → HUD_SCORE += height + time bonus ────
        hud_before_eol = cached(1, HUD_SCORE)
        # clear latch so the EOL edge fires once
        cli.set_mailbox(idx=1, mailbox=SMB_EOL_LATCH, value=0.0)
        step(2)
        cli.set_mailbox(idx=1, mailbox=END_OF_LEVEL, value=1.0)
        step(4)
        hud_after_eol = wait_gt(1, HUD_SCORE, hud_before_eol + 99, timeout=5.0)
        bonus = hud_after_eol - hud_before_eol
        print(f"  flagpole bonus: HUD_SCORE {hud_before_eol} → {hud_after_eol}  bonus={bonus}")
        check(bonus >= 100, f"flagpole bonus >= 100 (got {bonus})")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        fails.append(str(e))
    finally:
        if cli:
            try: cli.close()
            except Exception: pass
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()

    print()
    if fails:
        print(f"FAILED ({len(fails)} checks):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"ALL PASS (5 checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
