#!/usr/bin/env python3
"""Verify Fire Mario's fireball DEFEATS an enemy (Phase 2).

Companion to docs/plans/2026-05-27-smb-fireball-defeats-enemies.md.

The fireball (a Missile) broadcasts its live position + a freshness deadline each tick
(SMB_FIREBALL_LIVE_X/Z/UNTIL); the enemy self-defeats when a *fresh* fireball is within
range (ALIVE -> 0), the same proximity idiom it already uses for the Star/stomp (Jolt
fires no contact between two CharacterVirtuals).

Scenario: teleport the Goomba just right of Mario, make Mario Fire, hold B (fire right).
The fireball flies into the Goomba -> ALIVE goes 1 -> 0, and Mario is NOT hurt (clean kill).

`--record` (or WF_RECORD=1) launches the engine with the built-in -record_video flag and
relocates output.mp4 to tests/recordings/smb_fireball_defeat.mp4 on a pass.
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
SCROT = REPO / "tests" / "screenshots"
LOG   = REPO / "tests" / ".verify_smb_fireball_defeat.log"
PORT  = 7792

RECORD     = ("--record" in sys.argv) or bool(os.environ.get("WF_RECORD"))
OUTPUT_MP4 = REPO / "wfsource" / "source" / "game" / "output.mp4"
VIDEO      = REPO / "tests" / "recordings" / "smb_fireball_defeat.mp4"

SMB_MARIO_STATE  = 1814
SMB_PLAYER_HURT  = 1804          # global (read at idx=1)
X_POS, Z_POS, XSPEED, ALIVE = 3009, 3011, 3018, 3004
BTN_B = 0x0002

_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")


def discover_substr(substrs, timeout=8.0) -> dict[str, int]:
    """Map each wanted substring -> the first actor idx whose mesh name contains it."""
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
        if len(found) == len(substrs):
            break
        time.sleep(0.15)
    return found


def main() -> int:
    SCROT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
    env.setdefault("DISPLAY", ":0")
    log_fp = open(LOG, "w")
    if RECORD and OUTPUT_MP4.exists():
        OUTPUT_MP4.unlink()
    argv = [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
            "--debug-bind", "127.0.0.1", "--debug-print-actors"]
    if RECORD:
        argv.append("-record_video")
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

    def step(n=1, dt=0.04):
        for _ in range(n):
            cli.send({"op": "step"})
            time.sleep(dt)

    def shot(label):
        out = SCROT / f"smb_fireball_defeat_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        print(f"  screenshot {label}: {'OK' if m and m.get('op')=='screenshot_done' else 'WARN'}")

    try:
        idx = discover_substr({"player", "goomba"})
        print("discovered indices:", idx)
        if "player" not in idx or "goomba" not in idx:
            print("FATAL: missing player/goomba; aborting"); return 1
        PLAYER, GOOMBA = idx["player"], idx["goomba"]

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected"); time.sleep(1.0)
        cli.watch(idx=1, mailbox=SMB_PLAYER_HURT)
        cli.watch(idx=GOOMBA, mailbox=ALIVE)
        cli.watch(idx=GOOMBA, mailbox=X_POS)
        cli.watch(idx=GOOMBA, mailbox=Z_POS)
        cli.watch(idx=PLAYER, mailbox=X_POS)
        # DEBUG: the live-fireball broadcast + freshness
        cli.watch(idx=1, mailbox=1828)   # SMB_FIREBALL_LIVE_X
        cli.watch(idx=1, mailbox=1829)   # SMB_FIREBALL_LIVE_Z
        cli.watch(idx=1, mailbox=1830)   # SMB_FIREBALL_LIVE_UNTIL
        cli.watch(idx=1, mailbox=1906)   # TIME

        cli.send({"op": "pause"}); time.sleep(0.2)
        step(8)   # settle

        # Park the Goomba FAR away first so it can't block the spawn: SafelyConstructTemplateObject
        # expands the spawn box by velocity*dt (to catch fast objects), and the +12 fireball under
        # the bridge's variable step dt reaches ~1 unit ahead — an enemy in the narrow clear lane
        # (spawn ~6.2 .. mushroom_block @8.25) intermittently lands in that expanded box -> NULL spawn.
        cli.set_mailbox(idx=GOOMBA, mailbox=X_POS, value=40.0)
        cli.set_mailbox(idx=PLAYER, mailbox=SMB_MARIO_STATE, value=2)
        step(3)
        alive0 = g(GOOMBA, ALIVE)
        print(f"  setup: player X={g(PLAYER, X_POS)}  goomba parked X={g(GOOMBA, X_POS)} ALIVE={alive0}")
        check(alive0 is not None and alive0 != 0, "Goomba starts alive")

        # Fire (spawns cleanly with no enemy nearby), then once the fireball is airborne in the
        # clear lane, teleport the Goomba ONTO it (re-tracking a few ticks) — no spawn pre-check is
        # involved for an existing actor, so this deterministically puts the live fireball on the
        # enemy. This is a test rig for the *defeat* mechanic; real play just walks into a fireball.
        cli.inject_input(slot="joystick1_raw", value=BTN_B, duration_frames=-1)  # hold B -> one fireball
        shot_taken = False
        placed = 0
        for _ in range(30):
            step(1, dt=0.04)
            lx = g(1, 1828)
            if lx is not None and 6.0 < lx < 8.0:
                cli.set_mailbox(idx=GOOMBA, mailbox=X_POS, value=lx)   # drop the Goomba onto the fireball
                placed += 1
                if not shot_taken:
                    shot("01_impact"); shot_taken = True
            if placed >= 5:
                break
        print(f"  placed Goomba on the live fireball {placed}x")
        check(placed > 0, "fireball reached the clear lane (airborne, pre-block)")

        # A killed enemy is REMOVED — its change-only mailbox freezes at stale values, so we can't
        # watch ALIVE. Probe despawn directly: set_mailbox on a removed actor replies "not found".
        step(2)
        cli.set_mailbox(idx=GOOMBA, mailbox=ALIVE, value=1)
        despawned = cli.wait_for(
            lambda m: m.get("op") == "error" and "not found" in m.get("msg", ""), timeout=2.0) is not None
        print(f"  goomba despawned={despawned}")
        check(despawned, "fireball defeated the Goomba — removed (set_mailbox -> 'actor not found')")
        check(g(1, SMB_PLAYER_HURT) in (None, 0), "Mario was NOT hurt — clean ranged kill")
        shot("02_after")

        cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)

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
    print("PASS — Fire Mario fireball defeats an enemy (clean ranged kill)")
    if RECORD:
        if OUTPUT_MP4.exists():
            VIDEO.parent.mkdir(parents=True, exist_ok=True)
            os.replace(OUTPUT_MP4, VIDEO)
            print(f"  record: -> {VIDEO.relative_to(REPO)} ({VIDEO.stat().st_size // 1024} KB)")
        else:
            print("  record: WARN — engine produced no output.mp4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
