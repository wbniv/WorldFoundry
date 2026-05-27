#!/usr/bin/env python3
"""Verify the SMB Piranha Plant (docs/plans/2026-05-27-smb-piranha-plant.md).

An Anchored, non-colliding Enemy that slides its own Z_POS out of a pipe and back
(RATE*DELTA_TIME, framerate-independent), hurting Mario on contact, retracting while
Mario stands on the pipe, and dying to a fireball.

Checks (debug bridge):
  1. OSCILLATES — with Mario away, the plant's Z_POS rises and sinks (max-min above a bar).
  2. RETRACT-ON-TOP — pinning Mario on the pipe (|dx|<1) keeps the plant low.
  3. HURT — Mario at the emerged plant's height beside the pipe loses a life (LIVES drops).
  4. FIREBALL DEFEAT — a fresh fireball broadcast on the plant despawns it ("actor not found").

Reuses the fireball-defeat idioms: discover-by-mesh-substring, the despawn probe, and the
LIVE-fireball injection. `--record` -> tests/recordings/.
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
LOG   = REPO / "tests" / ".verify_smb_piranha.log"
PORT  = 7794

RECORD     = ("--record" in sys.argv) or bool(os.environ.get("WF_RECORD"))
OUTPUT_MP4 = REPO / "wfsource" / "source" / "game" / "output.mp4"
VIDEO      = REPO / "tests" / "recordings" / "smb_piranha.mp4"

PIRANHA_X = 24.0
LIVES = 72
SMB_FIREBALL_LIVE_X, SMB_FIREBALL_LIVE_Z, SMB_FIREBALL_LIVE_UNTIL = 1828, 1829, 1830
TIME_MB = 1906
X_POS, Z_POS, ALIVE = 3009, 3011, 3004

_MESH_RE = re.compile(r"actor idx=(\d+) mesh=([^\s]+)")


def discover_substr(substrs, timeout=8.0):
    deadline = time.time() + timeout
    found = {}
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
        out = SCROT / f"smb_piranha_{label}.png"
        cli.send({"op": "screenshot", "filename": str(out)})
        m = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=6.0)
        print(f"  screenshot {label}: {'OK' if m and m.get('op')=='screenshot_done' else 'WARN'}")

    def setp(x=None, z=None):
        if x is not None: cli.set_mailbox(idx=PLAYER, mailbox=X_POS, value=x)
        if z is not None: cli.set_mailbox(idx=PLAYER, mailbox=Z_POS, value=z)

    try:
        idx = discover_substr({"player", "piranha_00"})   # "piranha_00" = the plant ("piranha_pipe" also matches "piranha")
        print("discovered indices:", idx)
        if not {"player", "piranha_00"}.issubset(idx):
            print("FATAL: missing actors; aborting"); return 1
        PLAYER, PIRANHA = idx["player"], idx["piranha_00"]

        cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
        print("bridge: connected"); time.sleep(1.0)
        cli.watch(idx=PIRANHA, mailbox=Z_POS)
        cli.watch(idx=1, mailbox=LIVES)
        cli.watch(idx=1, mailbox=1906)   # TIME (level-clock) — drive windows by level-time, not steps

        # The bridge's per-step dt is wildly variable, so step COUNT != level-TIME. Drive every
        # window by elapsed TIME (the plant's oscillation phase is on a level-time deadline too).
        def now():
            return g(1, 1906) or 0.0
        def run_secs(secs, body=None, cap=900):
            t0 = now(); n = 0
            while n < cap:
                if body is not None and body():
                    return True
                step(1); n += 1
                if now() - t0 >= secs:
                    return False
            return False

        cli.send({"op": "pause"}); time.sleep(0.2)
        step(6)

        # ── (1) OSCILLATES (Mario far away) — sample Z over ~5 level-seconds (> a full cycle) ──
        setp(x=0.0)
        zr = [1e9, -1e9]; flag = {"shot": False}
        def osc(_=None):
            z = g(PIRANHA, Z_POS)
            if z is not None:
                zr[0] = min(zr[0], z); zr[1] = max(zr[1], z)
                if z > 2.0 and not flag["shot"]:
                    shot("01_emerged"); flag["shot"] = True
            return False
        run_secs(5.0, osc)
        print(f"  piranha Z range while idle: [{zr[0]:.2f}, {zr[1]:.2f}] (span {zr[1]-zr[0]:.2f})")
        check(zr[1] - zr[0] > 1.5, "plant oscillates out of the pipe (Z span > 1.5)")

        # ── (2) HURT — Mario beside the pipe at the emerged plant's height loses a life ──
        # Before the retract test (teleporting onto an emerged plant bites Mario faithfully, and
        # those i-frames would mask this). Mario's been idle far away -> full lives, no i-frames.
        lives0 = g(1, LIVES)
        print(f"  lives before hurt = {lives0}")
        def hurt_body():
            setp(x=PIRANHA_X + 1.1, z=3.0)   # off the pipe (no retract) but in the hurt band
            lv = g(1, LIVES)
            return lives0 is not None and lv is not None and lv < lives0
        hurt = run_secs(6.0, hurt_body)      # > a full cycle so an emerge is guaranteed
        print(f"  lives after = {g(1, LIVES)}")
        check(lives0 is not None and hurt, "emerged plant hurts Mario on contact (a life lost)")

        # ── (3) RETRACT while Mario is on the pipe — pin high above (no bite), watch it stay down ──
        setp(x=PIRANHA_X, z=6.0)
        run_secs(2.0, lambda: (setp(x=PIRANHA_X, z=6.0), False)[1])   # let it sink first
        zmax_late = [-1e9]
        def retract_body():
            setp(x=PIRANHA_X, z=6.0)          # |dx|<1 -> retract; Z high -> too far above to be bitten
            z = g(PIRANHA, Z_POS)
            if z is not None:
                zmax_late[0] = max(zmax_late[0], z)
            return False
        run_secs(2.0, retract_body)
        print(f"  piranha Z max while Mario on pipe (after settle): {zmax_late[0]:.2f}")
        check(zmax_late[0] < 1.8, "plant stays retracted while Mario stands on the pipe")
        shot("02_retracted")

        # ── (4) FIREBALL DEFEAT — inject a fresh fireball broadcast on the plant ──
        setp(x=0.0)                          # move Mario away
        def inject(_=None):
            pz = g(PIRANHA, Z_POS) or 1.5
            cli.set_mailbox(idx=PLAYER, mailbox=SMB_FIREBALL_LIVE_X, value=PIRANHA_X)
            cli.set_mailbox(idx=PLAYER, mailbox=SMB_FIREBALL_LIVE_Z, value=pz)
            cli.set_mailbox(idx=PLAYER, mailbox=SMB_FIREBALL_LIVE_UNTIL, value=now() + 5.0)
            return False
        run_secs(1.0, inject)
        cli.set_mailbox(idx=PIRANHA, mailbox=ALIVE, value=1)
        gone = cli.wait_for(lambda m: m.get("op") == "error" and "not found" in m.get("msg", ""),
                            timeout=2.0) is not None
        print(f"  piranha despawned by fireball = {gone}")
        check(gone, "a fireball defeats the plant (removed)")
        shot("03_after")

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
    print("PASS — Piranha Plant: oscillates, retracts on the pipe, hurts on contact, dies to fireball")
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
