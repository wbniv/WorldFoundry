#!/usr/bin/env python3
"""In-engine verification for the 639 balcony zip screen and the 7 cm floor recess.

Plan: docs/plans/2026-09-30-condo-balcony-shade.md, Verification 4 and 7 (and the
camera half of 6). Drives the real wf_game over the debug bridge:

  * the level loads open (closedness 0) with every slat parked inside the cassette;
  * walking from the project room onto the balcony steps DOWN 6 cm (7 cm recess under 1 cm
    of artificial grass) and back UP again;
  * the pony wall (at both guides and mid-span) and the north jamb stop the player;
  * B away from the opening does nothing; B within reach closes over ~2 s, the slats
    and bar land on their baked (closed) positions, a second press mid-travel reverses
    without a snap, and a held press toggles once;
  * B in the shade's reach moves only the shade, B in the glass doors' reach only the
    doors (the two reach bands are disjoint in y), and the wall switch is there;
  * walking onto the patio and to 640's master window produces no camera cut: with
    CONDO_POV_TRIGGERS off (the default since 2026-09-30) cs_dollhouse is the only
    automatic shot, and the doll-house camera holds its 9 m offset over the balcony.

Run after ``task condo-level``:

    python3 tests/verify_condo_balcony_shade.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WF = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "condo_639_640-standalone.iff"
LIB = REPO / "engine" / "libs"
CWD = REPO / "wfsource" / "source" / "game"
PORT = int(os.environ.get("WF_BRIDGE_PORT", "7798"))
LOG = Path("/tmp/wfgame_condo_balcony_shade.log")

X_POS, Y_POS, Z_POS = 3009, 3010, 3011
CAMSHOT = 1921                        # INDEXOF_CAMSHOT (troubleshooting: 1921, not 1021)
MB_DOOR_TARGET, MB_DOOR_CLOSEDNESS = 93, 94
TIME = 1906                           # level clock (mailbox.inc) — the integrator runs on DELTA_TIME
MB_REACH, MB_TARGET, MB_CLOSEDNESS = 62, 63, 64
BUTTON_B = 1 << 1
JOY_UP, JOY_DOWN = 1 << 11, 1 << 12
UNIT_Z = 15.75
SLAT_H = (2.05 - 1.072) / 8          # blender_create_condo.py § 7d
PARK0 = SLAT_H + 0.03 + 0.005        # slat 0 parked offset: SLAT_H + BAR_H + eps
PARK_BAR = 8 * SLAT_H + 0.03 + 0.005  # the bar stows 5 mm inside the cassette (bottom z 2.055)
CAM_DZ = 9.0                          # cs_dollhouse relative Z offset (0, −3.5, 9)
shots_seen: list[float] = []          # every INDEXOF_CAMSHOT sample taken while walking / dwelling
STEP = 0.06                           # 7 cm recess − 1 cm artificial grass (lies flat)

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"
env["__GL_SYNC_TO_VBLANK"] = "0"
env["LSAN_OPTIONS"] = "detect_leaks=0"

log_fp = LOG.open("w")
proc = subprocess.Popen(
    [str(WF), f"-L{LEVEL}",
     "--vram-width=4096", "--vram-height=2048", "--vram-slot-width=1024", "--vram-slot-height=1024",
     "--vram-perm-width=1024", "--vram-perm-height=1024",
     "--debug-port", str(PORT), "--debug-bind", "127.0.0.1", "--debug-print-actors"],
    cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT)

failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", flush=True)
    if not ok:
        failures.append(name)


def actor_index(pattern: str, timeout: float = 12.0) -> int:
    rx = re.compile(pattern)
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = rx.search(LOG.read_text(errors="replace"))
        if m:
            return int(m.group(1))
        time.sleep(0.1)
    raise RuntimeError(f"actor not found in {LOG}: {pattern}")


def value(cli: BridgeClient, idx: int, mailbox: int) -> float | None:
    with cli._lock:
        return cli.mailbox_values.get((idx, mailbox))


def wait_value(cli, idx, mailbox, predicate, timeout=5.0):
    deadline = time.time() + timeout
    cur = value(cli, idx, mailbox)
    while time.time() < deadline:
        cur = value(cli, idx, mailbox)
        if cur is not None and predicate(cur):
            return cur
        time.sleep(0.02)
    return cur


def move(cli, player, x, y, z=16.0, settle=0.6):
    cli.send({"op": "scene:set_transform", "idx": player, "pos": [x, y, z]})
    time.sleep(settle)


def press_b(cli):
    cli.inject_input("joystick1_raw_justpressed", BUTTON_B, duration_frames=1)
    time.sleep(0.12)


def hold(cli, player, bits, until, timeout=8.0):
    """Hold the stick until `until(x, y)` or timeout; returns the settled (x, y, z)."""
    cli.inject_input("joystick1_raw", bits, duration_frames=-1)
    deadline = time.time() + timeout
    while time.time() < deadline:
        x, y = value(cli, player, X_POS), value(cli, player, Y_POS)
        shots_seen.append(value(cli, 1, CAMSHOT))
        if x is not None and y is not None and until(x, y):
            break
        time.sleep(0.03)
    cli.inject_input("joystick1_raw", 0, duration_frames=1)
    time.sleep(0.5)
    # The character glides on (Running Deceleration 0.85) and eases down a step over a few
    # ticks: read z only once it has held still for 0.3 s (a mid-step sample reads short).
    last, still, deadline = None, 0, time.time() + 3.0
    while time.time() < deadline and still < 3:
        time.sleep(0.1)
        z = value(cli, player, Z_POS)
        still = still + 1 if (z is not None and last is not None and abs(z - last) < 5e-4) else 0
        last = z
    return value(cli, player, X_POS), value(cli, player, Y_POS), value(cli, player, Z_POS)


def fmt(p):
    return "(" + ", ".join("None" if v is None else f"{v:.3f}" for v in p) + ")"


try:
    time.sleep(2.0)
    player = actor_index(r"actor idx=(\d+) mesh=player\.iff mobility=Physics")
    slat0 = actor_index(r"actor idx=(\d+) mesh=639_balcony_shade_slat_0\.iff")
    panel0 = actor_index(r"actor idx=(\d+) mesh=639_project_door_panel_0\.iff")
    check("wall switch beside the opening", "mesh=639_balcony_shade_switch.iff" in LOG.read_text(errors="replace"),
          "639_balcony_shade_switch.iff loaded")
    bar = actor_index(r"actor idx=(\d+) mesh=639_balcony_shade_bar\.iff")
    camera = actor_index(r"actor idx=(\d+) mesh=\(none\) mobility=Camera")
    print(f"actors: player={player} slat0={slat0} bar={bar} camera={camera}", flush=True)

    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    for mb in (MB_REACH, MB_TARGET, MB_CLOSEDNESS, MB_DOOR_TARGET, MB_DOOR_CLOSEDNESS, CAMSHOT):
        cli.watch(1, mb)
    cli.watch(panel0, X_POS)
    for idx in (slat0, bar):
        cli.watch(idx, Z_POS)
    for mb in (X_POS, Y_POS, Z_POS):
        cli.watch(player, mb)
    cli.watch(camera, Z_POS)
    cli.watch(1, TIME)
    for idx, mb in ((1, MB_TARGET), (1, MB_CLOSEDNESS), (slat0, Z_POS), (bar, Z_POS), (player, Z_POS), (1, CAMSHOT)):
        wait_value(cli, idx, mb, lambda _v: True, timeout=5.0)
    dollhouse = value(cli, 1, CAMSHOT)          # the engine seeds it with the first CamShot: cs_dollhouse

    s0, b0 = value(cli, slat0, Z_POS), value(cli, bar, Z_POS)
    check("loads open, slats parked in the cassette",
          abs(value(cli, 1, MB_TARGET) or 0) < 1e-3 and abs(value(cli, 1, MB_CLOSEDNESS) or 0) < 1e-3
          and s0 is not None and abs(s0 - (UNIT_Z + PARK0)) < 2e-3 and b0 is not None and abs(b0 - (UNIT_Z + PARK_BAR)) < 2e-3,
          f"target={value(cli, 1, MB_TARGET)} closedness={value(cli, 1, MB_CLOSEDNESS)} "
          f"slat0.z={s0} (want {UNIT_Z + PARK0:.4f}) bar.z={b0} (want {UNIT_Z + PARK_BAR:.4f})")

    # ── Verification 4: step down, step up, walls ──────────────────────────────
    move(cli, player, 4.40, -3.20)
    room = hold(cli, player, 0, lambda x, y: True, timeout=0.1)
    out = hold(cli, player, JOY_UP, lambda x, y: y > -1.20)
    check("steps down 6 cm onto the grass", None not in out and None not in room and out[1] > -1.8
          and abs((room[2] - out[2]) - STEP) < 0.015,
          f"project room {fmt(room)} → balcony {fmt(out)}, drop {((room[2] or 0) - (out[2] or 0)) * 100:.1f} cm")
    wall = hold(cli, player, JOY_UP, lambda x, y: False, timeout=3.0)
    check("pony wall stops the player mid-span", wall[1] is not None and wall[1] < -0.25,
          f"held +Y from the balcony: {fmt(wall)} (pony wall inner face y −0.10)")
    back = hold(cli, player, JOY_DOWN, lambda x, y: y < -2.6)
    check("steps back up 6 cm into the project room", back[1] is not None and back[1] < -2.2
          and abs((back[2] or 0) - (room[2] or 0)) < 0.02,
          f"{fmt(back)} vs room z {room[2]:.3f}")
    for label, x in (("south guide", 2.97), ("north guide", 5.22), ("north jamb", 5.52)):
        move(cli, player, x, -1.0, z=15.9)
        p = hold(cli, player, JOY_UP, lambda _x, _y: False, timeout=2.5)
        check(f"{label} blocks", p[1] is not None and p[1] < -0.25, f"x={x}: {fmt(p)}")

    # ── Verification 7: B within reach toggles, 2 s travel, reversal ───────────
    move(cli, player, 4.40, -3.20)
    press_b(cli)
    time.sleep(0.25)
    check("press in the project room ignored", abs(value(cli, 1, MB_TARGET) or 0) < 1e-3,
          f"target={value(cli, 1, MB_TARGET)} reach={value(cli, 1, MB_REACH)}")
    move(cli, player, 4.10, -1.50, z=15.9)
    press_b(cli)
    time.sleep(0.25)
    check("press on the balcony beyond reach ignored (y −1.50 < −1.00)", abs(value(cli, 1, MB_TARGET) or 0) < 1e-3,
          f"target={value(cli, 1, MB_TARGET)} reach={value(cli, 1, MB_REACH)}")

    move(cli, player, 4.10, -0.60, z=15.9)
    t0 = time.time()
    press_b(cli)
    tgt = wait_value(cli, 1, MB_TARGET, lambda v: v > 0.5, timeout=1.0)
    lt0 = value(cli, 1, TIME)
    mid = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: 0.2 <= v <= 0.8, timeout=3.0)
    closed = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v > 0.995, timeout=6.0)
    lt1 = value(cli, 1, TIME)
    dt = time.time() - t0
    ldt = None if lt0 is None or lt1 is None else lt1 - lt0
    time.sleep(0.15)
    s1, b1 = value(cli, slat0, Z_POS), value(cli, bar, Z_POS)
    check("near press closes", tgt is not None and tgt > 0.5, f"target={tgt} reach={value(cli, 1, MB_REACH)}")
    check("continuous travel", mid is not None and 0.2 <= mid <= 0.8, f"closedness sampled mid-travel={mid}")
    check("full close in about 2 s of level time", closed is not None and closed > 0.995
          and ldt is not None and 1.7 < ldt < 2.4,
          f"closedness={closed} after {ldt if ldt is None else round(ldt, 2)} s level time "
          f"({dt:.2f} s wall clock, incl. bridge polling)")
    check("slats and bar land on their baked positions", s1 is not None and abs(s1 - UNIT_Z) < 2e-3
          and b1 is not None and abs(b1 - UNIT_Z) < 2e-3, f"slat0.z={s1} bar.z={b1} (want {UNIT_Z})")

    press_b(cli)
    before = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: 0.35 < v < 0.75, timeout=3.0)
    press_b(cli)
    after = value(cli, 1, MB_CLOSEDNESS)
    final = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v > 0.995, timeout=4.0)
    check("mid-travel press reverses without a snap",
          before is not None and after is not None and abs(after - before) < 0.15 and final is not None and final > 0.995,
          f"before={before} after={after} final={final}")

    cli.inject_input("joystick1_raw_justpressed", BUTTON_B, duration_frames=30)
    time.sleep(1.0)
    held_target = value(cli, 1, MB_TARGET)
    cli.inject_input("joystick1_raw_justpressed", 0, duration_frames=1)
    time.sleep(0.2)
    check("held press toggles once", held_target is not None and held_target < 0.5, f"target={held_target}")
    opened = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v < 0.005, timeout=4.0)
    s2 = value(cli, slat0, Z_POS)
    check("reopens and parks the slats again", opened is not None and opened < 0.005
          and s2 is not None and abs(s2 - (UNIT_Z + PARK0)) < 2e-3, f"closedness={opened} slat0.z={s2}")

    # ── One B press, one thing: the shade's and the doors' reach bands are disjoint ──
    def both():
        return (value(cli, 1, MB_TARGET), value(cli, 1, MB_DOOR_TARGET))
    for doors_state in ("open", "closed"):
        for label, (x, y), moves in (("shade reach (4.10, −0.60)", (4.10, -0.60), "shade"),
                                     ("door reach from the patio (7.25, −1.35)" if doors_state == "open"
                                      else "door reach from the patio (4.10, −1.30)",
                                      (7.25, -1.35) if doors_state == "open" else (4.10, -1.30), "doors"),
                                     ("between the bands (4.10, −1.02)", (4.10, -1.02), "nothing")):
            move(cli, player, x, y, z=15.9)
            before = both()
            press_b(cli)
            time.sleep(0.3)
            after = both()
            flipped = {"shade": before[0] != after[0], "doors": before[1] != after[1]}
            want = {"shade": moves == "shade", "doors": moves == "doors"}
            check(f"doors {doors_state}: B at {label} moves {moves} only", flipped == want,
                  f"shade target {before[0]}→{after[0]}, door target {before[1]}→{after[1]}")
            if moves != "nothing":           # put it back and let it settle
                press_b(cli)
                mb = MB_CLOSEDNESS if moves == "shade" else MB_DOOR_CLOSEDNESS
                tgt = value(cli, 1, MB_TARGET if moves == "shade" else MB_DOOR_TARGET)
                wait_value(cli, 1, mb, lambda v: abs(v - (tgt or 0)) < 0.005, timeout=6.0)
        if doors_state == "open":            # close the glass doors for the second round
            move(cli, player, 7.25, -1.35, z=15.9)
            press_b(cli)
            wait_value(cli, 1, MB_DOOR_CLOSEDNESS, lambda v: v > 0.995, timeout=6.0)
    move(cli, player, 7.25, -1.35, z=15.9)
    press_b(cli)                             # leave the doors open again
    wait_value(cli, 1, MB_DOOR_CLOSEDNESS, lambda v: v < 0.005, timeout=6.0)

    # ── Verification 6: no automatic camera cut on the patio or at the master window ──
    for state, want in (("open", 0.0), ("closed", 1.0)):
        if abs((value(cli, 1, MB_TARGET) or 0) - want) > 0.5:
            move(cli, player, 4.10, -0.60, z=15.9)
            press_b(cli)
            wait_value(cli, 1, MB_CLOSEDNESS, lambda v: abs(v - want) < 0.005, timeout=4.0)
        for label, (x, y) in (("patio zone entry", (4.10, -1.50)), ("patio", (4.10, -0.60))):
            move(cli, player, x, y, z=15.9, settle=0.0)
            seen, dz = set(), None
            for _ in range(30):
                time.sleep(0.1)
                seen.add(value(cli, 1, CAMSHOT))
            pz, cz = value(cli, player, Z_POS), value(cli, camera, Z_POS)
            dz = None if pz is None or cz is None else cz - pz
            check(f"no camera cut, shade {state}, {label}", seen == {dollhouse}
                  and dz is not None and abs(dz - CAM_DZ) < 0.3,
                  f"camshots seen {sorted(seen)} (doll-house {dollhouse}); camera − player = "
                  f"{dz if dz is None else round(dz, 3)} (authored {CAM_DZ})")
    move(cli, player, -6.90, -4.40, z=15.9, settle=0.0)      # 640's master-window strip (x −8.0…−6.3)
    seen = set()
    for _ in range(30):
        time.sleep(0.1)
        seen.add(value(cli, 1, CAMSHOT))
    check("no camera cut at 640's master window", seen == {dollhouse},
          f"player at ({value(cli, player, X_POS)}, {value(cli, player, Y_POS)}); camshots seen {sorted(seen)}")
    walked = set(shots_seen) - {None}
    check("no camera cut while walking onto the patio and back", walked == {dollhouse},
          f"{len(shots_seen)} samples during the walks, camshots {sorted(walked)}")

    cli.close()
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_fp.close()

print("RESULT:", "PASS" if not failures else f"FAIL {failures}")
sys.exit(1 if failures else 0)
