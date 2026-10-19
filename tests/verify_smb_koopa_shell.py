#!/usr/bin/env python3
"""Verify the SMB Koopa shell-kick state machine (docs/plans/2026-05-27-smb-koopa-shell-kick.md).

SMB_KOOPA_STATE: 0=walk, 1=shell-at-rest, 2=shell-sliding.

Checks (debug bridge):
  1. STOMP a walking Koopa (player ABOVE) -> state 0->1 and the Koopa SURVIVES (it retracts into a
     shell, it does NOT despawn — the opposite of the goomba stomp).
  2. KICK the resting shell (player to the SIDE, level) -> state 1->2 with a high |XSPEED|, aimed
     away from the player.
  3. The SLIDING shell DEFEATS the Goomba: drop the Goomba onto the shell's live broadcast
     (SMB_SHELL_LIVE_X) -> the Goomba despawns ("actor not found").

Reuses the fireball-defeat rig's idioms: discover-by-mesh-substring, the despawn probe (a removed
actor's change-only mailbox freezes stale, so set_mailbox -> "not found" is the kill signal), and
dropping a victim onto a projectile's live position. `--record` -> tests/recordings/.
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
LOG   = REPO / "tests" / ".verify_smb_koopa_shell.log"
PORT  = 7793

RECORD     = ("--record" in sys.argv) or bool(os.environ.get("WF_RECORD"))
OUTPUT_MP4 = REPO / "wfsource" / "source" / "game" / "output.mp4"
VIDEO      = REPO / "tests" / "recordings" / "smb_koopa_shell.mp4"

SMB_KOOPA_STATE  = 1831
SMB_SHELL_LIVE_X = 1832
SMB_PLAYER_HURT  = 1804
X_POS, Z_POS, XSPEED, ALIVE = 3009, 3011, 3018, 3004

_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")


def discover_substr(substrs, timeout=8.0) -> dict[str, int]:
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    while time.time() < deadline and len(found) < len(substrs):
        try:
            for m in _MESH_RE.finditer(LOG.read_text(errors="replace")):
                for s in substrs:
                    if s not in found and s in m.group(2):
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
    proc = subprocess.Popen(argv, cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

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
        out = SCROT / f"smb_koopa_shell_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        print(f"  screenshot {label}: {'OK' if m and m.get('op')=='screenshot_done' else 'WARN'}")

    def despawned(idx):
        cli.set_mailbox(idx=idx, mailbox=ALIVE, value=1)
        return cli.wait_for(lambda m: m.get("op") == "error" and "not found" in m.get("msg", ""),
                            timeout=1.0) is not None

    try:
        idx = discover_substr({"player", "koopa", "goomba"})
        print("discovered indices:", idx)
        if not {"player", "koopa", "goomba"}.issubset(idx):
            print("FATAL: missing actors; aborting"); return 1
        PLAYER, KOOPA, GOOMBA = idx["player"], idx["koopa"], idx["goomba"]

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected"); time.sleep(1.0)
        for mb in (X_POS, Z_POS, XSPEED):
            cli.watch(idx=KOOPA, mailbox=mb)
        cli.watch(idx=1, mailbox=SMB_KOOPA_STATE)
        cli.watch(idx=1, mailbox=SMB_SHELL_LIVE_X)
        cli.watch(idx=1, mailbox=SMB_PLAYER_HURT)

        cli.send({"op": "pause"}); time.sleep(0.2)
        step(6)

        # Park the Goomba far; put the Koopa in a clear lane.
        cli.set_mailbox(idx=GOOMBA, mailbox=X_POS, value=40.0)
        KX = 7.0
        cli.set_mailbox(idx=KOOPA, mailbox=X_POS, value=KX)
        step(3)
        kz = g(KOOPA, Z_POS) or 1.5
        print(f"  koopa parked X={g(KOOPA, X_POS)} Z={kz} state={g(1, SMB_KOOPA_STATE)}")

        # ── (1) STOMP: hold the player just ABOVE the Koopa (re-pin so it doesn't fall away) ──
        for _ in range(6):
            cli.set_mailbox(idx=KOOPA, mailbox=X_POS, value=KX)          # keep the Koopa put
            cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=KX)
            cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=kz + 1.5)   # above -> dz > 0.7 = stomp
            step(1)
        st = g(1, SMB_KOOPA_STATE)
        alive_after_stomp = not despawned(KOOPA)
        print(f"  after stomp: state={st}  koopa alive={alive_after_stomp}")
        check(st == 1, "stomp retracts the Koopa to a shell (SMB_KOOPA_STATE -> 1)")
        check(alive_after_stomp, "stomped Koopa SURVIVES as a shell (not despawned)")
        shot("01_shell")

        # ── (2) KICK: player to the SIDE (left), level with the resting shell ──
        for _ in range(5):
            cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=KX - 0.7)  # on the LEFT -> kick right
            cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=kz)        # level -> side touch
            step(1)
        st = g(1, SMB_KOOPA_STATE)
        vx = g(KOOPA, XSPEED)
        print(f"  after kick: state={st}  koopa XSPEED={vx}")
        check(st == 2, "side touch kicks the resting shell into a slide (state -> 2)")
        check(vx is not None and vx > 8.0, f"shell slides fast, away from the player (XSPEED ~ +14), got {vx}")
        shot("02_kicked")

        # ── (3) the sliding shell defeats the Goomba ──
        # Move the player away so it doesn't interfere; drop the Goomba onto the live shell.
        cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=0.0)
        placed = 0
        for _ in range(30):
            step(1)
            sx = g(1, SMB_SHELL_LIVE_X)
            if sx is not None and sx > 2.0:
                cli.set_mailbox(idx=GOOMBA, mailbox=X_POS, value=sx)   # drop the Goomba onto the shell
                placed += 1
            if placed >= 6:
                break
        step(2)
        goomba_dead = despawned(GOOMBA)
        print(f"  placed Goomba on the live shell {placed}x  goomba despawned={goomba_dead}")
        check(placed > 0, "shell is sliding and broadcasting its live position")
        check(goomba_dead, "the sliding shell defeated the Goomba (removed)")
        shot("03_shell_kills_goomba")

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
    print("PASS — Koopa shell-kick: stomp->shell, kick->slide, sliding shell defeats enemies")
    if RECORD:
        if OUTPUT_MP4.exists():
            VIDEO.parent.mkdir(parents=True, exist_ok=True)
            os.replace(OUTPUT_MP4, VIDEO)
            print(f"  record: -> {VIDEO.relative_to(REPO)} ({VIDEO.stat().st_size // 1024} KB)")
        else:
            print("  record: WARN — no output.mp4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
