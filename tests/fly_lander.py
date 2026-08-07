#!/usr/bin/env python3
"""Fly the Site 01 lander from the terminal — no window focus required.

Sends input straight into the running engine over the debug bridge (TCP,
port 7777 by default), writing the exact same raw-joystick mailbox a real
keypress would. Since this bypasses X11 entirely, it works even if the
game window itself isn't receiving keyboard focus (the WSLg/Weston issue
we hit) — the window still renders live as you fly, you just don't type
into it directly.

Usage:
    1. In one terminal: task run-moon      (or run engine/wf_game directly —
       must be built with --debug-port 7777, which run-moon/run-level do NOT
       pass by default; use `task run-debug -- wflevels/moon_site01-standalone.iff`
       instead, or add --debug-port 7777 --debug-bind 127.0.0.1 yourself)
    2. In a second terminal: python3 tests/fly_lander.py

Controls (single keypress, no Enter needed):
    SPACE        main engine (thrust up)
    Up/Down/Left/Right arrows   RCS thrusters
    2            retry after a crash/landing
    q            quit this script (the game keeps running)

Limitation: each press is a short pulse (duration_frames below), not a
held key — a plain terminal has no key-release event to detect "still
held," so this can't combine two buttons at once (e.g. thrust + RCS
simultaneously). Tap repeatedly instead of holding; lunar gravity is slow
enough (free-fall from spawn takes ~19s) that this is a completely
workable way to fly it.
"""
import os
import select
import sys
import termios
import tty

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from debug_bridge_client import BridgeClient  # noqa: E402

# Pulse length in frames. ~0.2s at a typical 60fps tick.
PULSE_FRAMES = 12

# Bit values match wfsource/source/hal/sjoystic.h (EJ_BUTTONF_*), the same
# ones blender_create_moon.py's flight-model script tests via LBTN.
BUTTON_BITS = {
    " ": (1, "main engine"),
    "2": (2, "retry"),
    "UP": (2048, "+Y RCS"),
    "DOWN": (4096, "-Y RCS"),
    "RIGHT": (8192, "+X RCS"),
    "LEFT": (16384, "-X RCS"),
}


def read_key(fd) -> str:
    """Read one logical keypress, resolving arrow-key escape sequences."""
    ch = os.read(fd, 1).decode("utf-8", errors="replace")
    if ch == "\x1b":
        rest = os.read(fd, 2).decode("utf-8", errors="replace")
        return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}.get(rest, "")
    return ch


def main() -> int:
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7777

    try:
        client = BridgeClient(host=host, port=port)
    except Exception as e:  # noqa: BLE001 - top-level CLI, want a clean message
        print(f"Could not connect to debug bridge at {host}:{port}: {e}")
        print("Is the game running with --debug-port 7777 --debug-bind 127.0.0.1?")
        print("(task run-moon does NOT pass this by default — see this script's")
        print(" docstring for the exact command.)")
        return 1
    client.ping()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        sys.stdout.write(
            "\r\nConnected. SPACE=thrust  arrows=RCS  2=retry  q=quit\r\n"
        )
        sys.stdout.flush()
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not ready:
                continue
            key = read_key(fd)
            if key == "q":
                break
            entry = BUTTON_BITS.get(key)
            if entry is None:
                continue
            bit, label = entry
            client.inject_input(
                slot="joystick1_raw", value=bit, duration_frames=PULSE_FRAMES
            )
            sys.stdout.write(f"\r{label:<14}")
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\r\nDisconnected (game keeps running).\r\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
