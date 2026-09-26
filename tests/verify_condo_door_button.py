#!/usr/bin/env python3
"""In-engine verification for the 639 project-room glass-door button.

Checks that B is ignored away from the glass panels, toggles the door while the
player is within reach, drives a continuous two-second slide, and reverses an
in-flight slide without snapping. It also walks the player into the gathered
glass stack and all three fully-extended bays to prove that every visible part
of the door remains impassable.

Run after ``task condo-level``:

    python3 tests/verify_condo_door_button.py
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
PORT = int(os.environ.get("WF_BRIDGE_PORT", "7796"))
LOG = Path("/tmp/wfgame_condo_door_button.log")

X_POS = 3009
Y_POS = 3010
MB_ZONE = 92
MB_TARGET = 93
MB_CLOSEDNESS = 94
BUTTON_B = 1 << 1
JOY_UP = 1 << 11

env = os.environ.copy()
env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
env.setdefault("DISPLAY", ":0")
env["vblank_mode"] = "0"
env["__GL_SYNC_TO_VBLANK"] = "0"
# LeakSanitizer cannot inspect the process under Codex's ptrace sandbox. The
# runtime test is about level behavior, not a leak pass.
env["LSAN_OPTIONS"] = "detect_leaks=0"

log_fp = LOG.open("w")
proc = subprocess.Popen(
    [
        str(WF),
        f"-L{LEVEL}",
        "--vram-width=4096",
        "--vram-height=2048",
        "--vram-slot-width=1024",
        "--vram-slot-height=1024",
        "--vram-perm-width=1024",
        "--vram-perm-height=1024",
        "--debug-port",
        str(PORT),
        "--debug-bind",
        "127.0.0.1",
        "--debug-print-actors",
    ],
    cwd=str(CWD),
    env=env,
    stdout=log_fp,
    stderr=subprocess.STDOUT,
)

failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    if not ok:
        failures.append(name)


def actor_index(pattern: str, timeout: float = 12.0) -> int:
    rx = re.compile(pattern)
    deadline = time.time() + timeout
    while time.time() < deadline:
        match = rx.search(LOG.read_text(errors="replace"))
        if match:
            return int(match.group(1))
        time.sleep(0.1)
    raise RuntimeError(f"actor not found in {LOG}: {pattern}")


def value(cli: BridgeClient, idx: int, mailbox: int) -> float | None:
    with cli._lock:
        return cli.mailbox_values.get((idx, mailbox))


def wait_value(cli: BridgeClient, idx: int, mailbox: int, predicate, timeout: float = 5.0):
    deadline = time.time() + timeout
    current = value(cli, idx, mailbox)
    while time.time() < deadline:
        current = value(cli, idx, mailbox)
        if current is not None and predicate(current):
            return current
        time.sleep(0.03)
    return current


def move(cli: BridgeClient, player: int, x: float, y: float, z: float = 16.0) -> None:
    cli.send({"op": "scene:set_transform", "idx": player, "pos": [x, y, z]})
    time.sleep(0.5)


def press_b(cli: BridgeClient) -> None:
    cli.inject_input("joystick1_raw_justpressed", BUTTON_B, duration_frames=1)
    time.sleep(0.12)


def walk_toward_patio(cli: BridgeClient, player: int, timeout: float = 8.0) -> float | None:
    """Hold +Y long enough to cross the y=-2 door plane if no collider stops us."""
    cli.inject_input("joystick1_raw", JOY_UP, duration_frames=-1)
    deadline = time.time() + timeout
    current = value(cli, player, Y_POS)
    while time.time() < deadline:
        current = value(cli, player, Y_POS)
        if current is not None and current > -1.60:
            break
        time.sleep(0.04)
    cli.inject_input("joystick1_raw", 0, duration_frames=1)
    time.sleep(0.35)
    return value(cli, player, Y_POS)


try:
    time.sleep(2.0)
    player = actor_index(r"actor idx=(\d+) mesh=player\.iff mobility=Physics")
    panel0 = actor_index(r"actor idx=(\d+) mesh=639_project_door_panel_0\.iff")
    check("physical button removed", "mesh=639_project_door_button.iff" not in LOG.read_text(), "no wall switch actor")
    print(f"actors: player={player} panel0={panel0}")

    cli = BridgeClient("127.0.0.1", PORT, timeout=15.0)
    for mailbox in (MB_ZONE, MB_TARGET, MB_CLOSEDNESS):
        cli.watch(1, mailbox)
    cli.watch(panel0, X_POS)
    cli.watch(player, Y_POS)
    wait_value(cli, 1, MB_TARGET, lambda _v: True, timeout=5.0)
    wait_value(cli, 1, MB_CLOSEDNESS, lambda _v: True, timeout=5.0)
    wait_value(cli, panel0, X_POS, lambda _v: True, timeout=5.0)

    initial_target = value(cli, 1, MB_TARGET)
    initial_closedness = value(cli, 1, MB_CLOSEDNESS)
    initial_panel_x = value(cli, panel0, X_POS)
    check(
        "default open",
        initial_target is not None
        and initial_closedness is not None
        and initial_panel_x is not None
        and abs(initial_target) < 0.001
        and abs(initial_closedness) < 0.001
        and abs(initial_panel_x) < 0.001,
        f"target={initial_target} closedness={initial_closedness} panel0.x={initial_panel_x}",
    )

    move(cli, player, 5.8, -5.0)
    press_b(cli)
    time.sleep(0.25)
    check(
        "far press ignored",
        abs(value(cli, 1, MB_TARGET) or 0.0) < 0.001,
        f"target={value(cli, 1, MB_TARGET)}",
    )

    # Within reach of the gathered glass stack.
    move(cli, player, 7.25, -2.55)
    press_b(cli)
    target = wait_value(cli, 1, MB_TARGET, lambda v: v > 0.5, timeout=1.0)
    mid = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: 0.10 <= v <= 0.90, timeout=3.0)
    check("near press toggles closed", target is not None and target > 0.5, f"target={target}")
    check("continuous close", mid is not None and 0.10 <= mid <= 0.90, f"closedness={mid}")

    closed = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v > 0.995, timeout=12.0)
    panel_x = value(cli, panel0, X_POS)
    check(
        "settles closed",
        closed is not None and closed > 0.995 and panel_x is not None and abs(panel_x + 2.6667) < 0.02,
        f"closedness={closed} panel0.x={panel_x}",
    )

    # Each closed leaf can be reached from the room and the patio. Reclose
    # immediately after each opening request, also exercising moving-panel reach.
    for x in (4.45, 5.80, 7.10):
        for y in (-2.65, -1.35):
            move(cli, player, x, y)
            press_b(cli)
            target = wait_value(cli, 1, MB_TARGET, lambda v: v < .5, timeout=1)
            check(f"panel at {x} from side {y} opens", target is not None and target < .5, str(target))
            press_b(cli)
            wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v > .995, timeout=12)
    move(cli, player, 7.25, -2.55)

    press_b(cli)
    reopened = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v < 0.005, timeout=18.0)
    check("second press opens", reopened is not None and reopened < 0.005, f"closedness={reopened}")

    move(cli, player, 4.45, -2.65)
    press_b(cli)
    check("empty open bay ignores press", value(cli, 1, MB_TARGET) == 0, str(value(cli, 1, MB_TARGET)))
    move(cli, player, 7.25, -2.55)
    cli.inject_input("joystick1_raw_justpressed", BUTTON_B, duration_frames=30)
    time.sleep(1)
    check("held press toggles once", value(cli, 1, MB_TARGET) == 1, str(value(cli, 1, MB_TARGET)))
    cli.inject_input("joystick1_raw_justpressed", 0, duration_frames=1)
    time.sleep(.2)
    press_b(cli)
    wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v < .005, timeout=12)

    # Start closing, reverse around one-quarter travel, and require the next sample
    # to remain near that position rather than snap to an endpoint.
    press_b(cli)
    before_reverse = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: 0.20 < v < 0.45, timeout=5.0)
    press_b(cli)
    after_reverse = value(cli, 1, MB_CLOSEDNESS)
    returned_open = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v < 0.005, timeout=8.0)
    check(
        "mid-slide reversal has no snap",
        before_reverse is not None
        and after_reverse is not None
        and abs(after_reverse - before_reverse) < 0.20
        and returned_open is not None
        and returned_open < 0.005,
        f"before={before_reverse} after={after_reverse} final={returned_open}",
    )

    # Open state: x=7.10 is through the gathered one-third stack, not the open
    # two-thirds threshold. All three leaves occupy this bay on adjacent tracks.
    move(cli, player, 7.10, -3.20)
    gathered_y = walk_toward_patio(cli, player)
    check(
        "gathered one-third blocks passage",
        gathered_y is not None and gathered_y < -2.05,
        f"final y={gathered_y} vs door plane -2.00",
    )

    # Close from beside the gathered glass, then test the centre of each extended bay.
    move(cli, player, 7.25, -2.55)
    press_b(cli)
    closed = wait_value(cli, 1, MB_CLOSEDNESS, lambda v: v > 0.995, timeout=12.0)
    check("collision test door closed", closed is not None and closed > 0.995,
          f"closedness={closed}")
    # Include both joints: separate mesh bodies that only meet at an edge are
    # the spots most likely to regress into a collision crack.
    for label, x in (
        ("left", 4.45),
        ("left/middle seam", 5.13),
        ("middle", 5.80),
        ("middle/right seam", 6.47),
        ("right/fixed", 7.10),
    ):
        move(cli, player, x, -3.20)
        final_y = walk_toward_patio(cli, player)
        check(
            f"closed {label} third blocks passage",
            final_y is not None and final_y < -2.05,
            f"x={x} final y={final_y} vs door plane -2.00",
        )

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
