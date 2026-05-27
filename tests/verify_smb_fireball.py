#!/usr/bin/env python3
"""Verify Fire Mario's fireball — WF's first runtime-positioned spawn.

Companion to docs/plans/2026-05-26-fire-mario-fireball-pooled-generator.md
(Approach A from docs/investigations/2026-05-26-spawn-template-forth-primitive.md):
no engine `spawn-template` syscall — two hidden, non-solid pool Generators
(`fireball_gen_r/l`) self-park on a point the player publishes each tick and throw
a `Missile` when Mario pulses their global Activation MailBox (SMB_FIREBALL_FIRE_R/L).

Checks:
  1. In Fire state (SMB_MARIO_STATE=2), pressing B spawns a Missile in front of Mario,
     moving RIGHT (XSPEED ~ +12) — proving spawn-at-runtime-position works.
  2. Holding B yields exactly ONE fireball (edge-latch / cooldown), not a stream.
  3. With facing flipped left, the next press fires LEFT (XSPEED ~ -12) — proving the
     two-generator facing split.

Engine constraints (same as the sibling SMB bridge tests): globals (<1900) read at
idx=1; per-actor mailboxes read at the actor's index; SMB_MARIO_STATE is written via
the PLAYER actor; the fire button is the raw B bit (0x2) injected on joystick1_raw.
The spawned Missile's index is read from the generator's "AddObject ok, coin
actor_idx=N" stderr line (the generators are Empties, so they have no mesh name to
discover — but we don't need them: we drive everything through global mailboxes).
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
LOG   = REPO / "tests" / ".verify_smb_fireball.log"
PORT  = 7791

SMB_MARIO_STATE = 1814          # global (read at idx=1, written via PLAYER)
X_POS, Z_POS, XSPEED = 3009, 3011, 3018
JOY_RAW = 1009                  # EMAILBOX_HARDWARE_JOYSTICK1_RAW
BTN_B, BTN_LEFT, BTN_RIGHT = 0x0002, 0x4000, 0x2000

_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")
_SPAWN_RE = re.compile(r"AddObject ok, coin actor_idx=(\d+)")


def discover(want: set[str], timeout=8.0) -> dict[str, int]:
    deadline = time.time() + timeout
    found: dict[str, int] = {}
    while time.time() < deadline and not want.issubset(found):
        try:
            for m in _MESH_RE.finditer(LOG.read_text(errors="replace")):
                base = m.group(2).removesuffix(".iff")
                if base in want:
                    found[base] = int(m.group(1))
        except OSError:
            pass
        if want.issubset(found):
            break
        time.sleep(0.15)
    return found


def spawn_indices() -> list[int]:
    try:
        return [int(m.group(1)) for m in _SPAWN_RE.finditer(LOG.read_text(errors="replace"))]
    except OSError:
        return []


def main() -> int:
    SCROT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH','')}"
    env.setdefault("DISPLAY", ":0")
    log_fp = open(LOG, "w")
    proc = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT),
         "--debug-bind", "127.0.0.1", "--debug-print-actors"],
        cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

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
        out = SCROT / f"smb_fireball_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        ok = m and m.get("op") == "screenshot_done"
        print(f"  screenshot {label}: {'OK -> ' + out.name if ok else 'WARN ' + str(m)}")

    def fire_until_spawn(prev_count, max_steps=40):
        """Step (button already held) until a new spawn line appears; return its idx."""
        for _ in range(max_steps):
            step(1, dt=0.04)
            idxs = spawn_indices()
            if len(idxs) > prev_count:
                return idxs[-1]
        return None

    try:
        idx = discover({"player"})
        print("discovered indices:", idx)
        if "player" not in idx:
            print("FATAL: player actor not found; aborting"); return 1
        PLAYER = idx["player"]

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected"); time.sleep(1.0)
        cli.watch(idx=1, mailbox=SMB_MARIO_STATE)
        cli.watch(idx=PLAYER, mailbox=X_POS)

        cli.send({"op": "pause"}); time.sleep(0.2)
        step(8)   # let Mario settle on the ground

        px = g(PLAYER, X_POS)
        print(f"  player X ~ {px}")

        # ── (1) Fire state + B -> a rightward fireball ───────────────────────────
        cli.set_mailbox(idx=PLAYER, mailbox=SMB_MARIO_STATE, value=2)
        step(2)
        cli.inject_input(slot="joystick1_raw", value=BTN_B, duration_frames=-1)  # hold B
        n0 = len(spawn_indices())
        fb = fire_until_spawn(n0)
        print(f"  first fireball actor idx = {fb}")
        check(fb is not None, "Fire state + B spawned a Missile fireball")

        if fb is not None:
            cli.watch(idx=fb, mailbox=XSPEED)
            cli.watch(idx=fb, mailbox=X_POS)
            vx = fx = None
            for _ in range(20):
                step(1, dt=0.04)
                vx, fx = g(fb, XSPEED), g(fb, X_POS)
                if vx is not None and fx is not None:
                    break
            print(f"  fireball: X={fx} XSPEED={vx}  (player X~{px})")
            check(vx is not None and vx > 5.0,
                  f"fireball travels RIGHT (XSPEED ~ +12), got {vx}")
            check(fx is not None and px is not None and fx > px,
                  f"fireball spawned in FRONT of Mario (X {fx} > player {px})")
            shot("01_right_in_flight")

        # ── (2) Holding B yields exactly ONE fireball (edge-latch) ──────────────
        n_after_first = len(spawn_indices())
        step(20)   # keep holding B across the cooldown window
        n_held = len(spawn_indices())
        check(n_held == n_after_first,
              f"holding B fires exactly one fireball per press (spawns held at {n_after_first}, saw {n_held})")

        # ── (3) Face left, re-press -> a leftward fireball ──────────────────────
        cli.inject_input(slot="joystick1_raw", value=BTN_LEFT, duration_frames=-1)  # LEFT, B released
        step(4)    # latch clears (B up) + facing latches to -1; let the 0.5s cooldown pass
        step(12)
        cli.inject_input(slot="joystick1_raw", value=BTN_LEFT | BTN_B, duration_frames=-1)  # LEFT + B
        n1 = len(spawn_indices())
        fb2 = fire_until_spawn(n1)
        print(f"  second (left) fireball actor idx = {fb2}")
        check(fb2 is not None, "facing left + B spawned a second Missile")
        if fb2 is not None:
            cli.watch(idx=fb2, mailbox=XSPEED)
            vx2 = None
            for _ in range(20):
                step(1, dt=0.04)
                vx2 = g(fb2, XSPEED)
                if vx2 is not None:
                    break
            print(f"  left fireball XSPEED={vx2}")
            check(vx2 is not None and vx2 < -5.0,
                  f"left-facing fireball travels LEFT (XSPEED ~ -12), got {vx2}")
            shot("02_left_in_flight")

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
    print("PASS — Fire Mario fireball: runtime-positioned spawn, facing-aware, one-per-press")
    return 0


if __name__ == "__main__":
    sys.exit(main())
