#!/usr/bin/env python3
"""walk_condo.py — drive the condo_639_640 player over the debug bridge and check
the geometry-derived collision: front door passable, partition wall solid,
party-wall connector passable, Z pinned to the floor throughout.

Verification step 6 of docs/plans/2026-09-19-condo-639-640-level.md.

Run:  python3 tests/walk_condo.py      (needs engine/wf_game + wflevels/condo_639_640-standalone.iff)
Exit 0 = every check passed; prints one line per check.
"""
import os, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient   # noqa: E402

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "condo_639_640-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = int(os.environ.get("WF_BRIDGE_PORT", "7791"))
LOG   = REPO / "tests" / ".walk_condo.log"

X_POS, Y_POS, Z_POS = 3009, 3010, 3011
JOY_UP, JOY_DOWN, JOY_RIGHT, JOY_LEFT = 1 << 11, 1 << 12, 1 << 13, 1 << 14   # hal/sjoystic.h EJ_BUTTONB_*

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"; env["__GL_SYNC_TO_VBLANK"] = "0"

log_fp = open(LOG, "w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1",
     "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)
time.sleep(2.5)

failures = []


def check(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    if not ok:
        failures.append(name)


try:
    rx = re.compile(r"actor idx=(\d+) mesh=player\.iff mobility=Physics")
    player = None
    for _ in range(100):
        m = rx.search(LOG.read_text(errors="replace"))
        if m:
            player = int(m.group(1)); break
        time.sleep(0.1)
    assert player is not None, "player (mesh=player.iff mobility=Physics) not found in --debug-print-actors output"
    print(f"player idx={player}")

    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    for mb in (X_POS, Y_POS, Z_POS):
        cli.watch(idx=player, mailbox=mb)
    time.sleep(1.0)

    def pos():
        with cli._lock:
            return tuple(cli.mailbox_values.get((player, mb)) for mb in (X_POS, Y_POS, Z_POS))

    def hold(bits, until, timeout):
        """Hold joystick bits until `until(pos)` or timeout; returns final pos."""
        cli.inject_input(slot="joystick1_raw", value=bits, duration_frames=-1)
        deadline = time.time() + timeout
        p = pos()
        while time.time() < deadline:
            p = pos()
            if None not in p and until(p):
                break
            time.sleep(0.05)
        cli.inject_input(slot="joystick1_raw", value=0, duration_frames=1)
        time.sleep(0.4)
        return pos()

    zs = []
    p0 = pos()
    check("spawn settled", p0[2] is not None and -0.1 < p0[2] < 0.35, f"pos={p0}")

    # 1. walk +Y through 639's front door (y=-15.35, x 3.86..5.46) into the kitchen
    p = hold(JOY_UP, lambda p: p[1] > -11.0, 20)
    zs.append(p[2])
    check("front door passable", p[1] > -15.0, f"y={p[1]:.2f} (started {p0[1]:.2f})")

    # 2. strafe -X to the party-wall side, then walk +Y into 639-kitchen-N-wall-jamb0 (y=-8.05..-7.95)
    p = hold(JOY_LEFT, lambda p: p[0] < 1.2, 15)
    zs.append(p[2])
    p = hold(JOY_UP, lambda p: p[1] > -7.5, 8)          # must NOT reach -7.5: wall blocks
    zs.append(p[2])
    check("partition wall solid", -8.6 < p[1] < -7.9, f"y={p[1]:.2f} vs wall face -8.05 (capsule r≈0.2)")

    # 2b. through the guest-bedroom door (x 2.85..3.65 at y=-8) and the new bath-N door
    #     (x 0.30..1.10 at y=-2, added to the source model 2026-09-19), then back to the kitchen
    p = hold(JOY_RIGHT, lambda p: p[0] > 3.2, 8)
    p = hold(JOY_UP, lambda p: p[1] > -5.0, 8)
    zs.append(p[2])
    check("guest-bed door passable", p[1] > -7.9, f"y={p[1]:.2f} x={p[0]:.2f}")
    p = hold(JOY_LEFT, lambda p: p[0] < 0.75, 8)
    p = hold(JOY_UP, lambda p: p[1] > -1.2, 8)
    zs.append(p[2])
    check("bath-N door passable", p[1] > -1.9, f"y={p[1]:.2f} x={p[0]:.2f} (door y=-2.0)")
    p = hold(JOY_DOWN, lambda p: p[1] < -5.0, 8)
    p = hold(JOY_RIGHT, lambda p: p[0] > 3.2, 8)
    p = hold(JOY_DOWN, lambda p: p[1] < -9.1, 8)
    p = hold(JOY_LEFT, lambda p: p[0] < 1.0, 8)
    zs.append(p[2])
    check("back in kitchen", -9.6 < p[1] < -8.4 and p[0] < 1.2, f"pos={p}")

    # 3. south of the connector (y < -9.55): strafe -X into the party wall — blocked, x stays > 0
    p = hold(JOY_DOWN, lambda p: p[1] < -10.8, 8)
    p = hold(JOY_LEFT, lambda p: p[0] < 0.0, 6)
    zs.append(p[2])
    check("party wall solid", 0.0 < p[0] < 0.6, f"x={p[0]:.2f} vs wall face +0.05")

    # 4. up into the connector doorway (y -9.55..-8.60), strafe -X into 640
    p = hold(JOY_UP, lambda p: p[1] > -9.3, 8)
    zs.append(p[2])
    p = hold(JOY_LEFT, lambda p: p[0] < -0.8, 12)
    zs.append(p[2])
    check("party-wall connector passable", p[0] < -0.3, f"x={p[0]:.2f} y={p[1]:.2f}")

    check("Z pinned to floor", all(z is not None and -0.1 < z < 0.3 for z in zs),
          f"z samples={[round(z, 3) if z is not None else None for z in zs]}")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_fp.close()

print("RESULT:", "PASS" if not failures else f"FAIL {failures}")
sys.exit(1 if failures else 0)
