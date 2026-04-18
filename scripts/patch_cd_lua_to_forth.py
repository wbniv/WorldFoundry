#!/usr/bin/env python3
"""Byte-preserving patch of cd.iff: rewrite the snowgoons Player and Director
scripts from Lua to Forth, padded with trailing spaces so each slot's byte
count stays identical (no chunk size changes, no alignment to repair).

Peer of scripts/patch_snowgoons_forth.py (which patches Fennel → Forth
inside snowgoons.iff). This one handles the case where cd.iff has been
compiled from a snowgoons.iff whose Player/Director were still Lua, which
is what ships today.

Usage:
    python3 scripts/patch_cd_lua_to_forth.py wfsource/source/game/cd.iff

Writes back in place.
"""

import re
import sys
from pathlib import Path


# Fixed by _Common struct offsets; do not change. Matches the slots
# patch_snowgoons_forth.py expects (plus one trailing byte for the
# null terminator — the slot itself is PLAYER_SLOT + 1 wide, but the
# script text occupies PLAYER_SLOT).
DIRECTOR_SLOT = 443
PLAYER_SLOT   = 78


# Director: inline three-block form. The `?cam` helper word would save bytes
# but zForth's minimal bootstrap can't compile it when a user-word definition
# is followed immediately by calls; inline avoids that. Same form produced
# by patch_snowgoons_forth.py.
DIRECTOR_FORTH = (
    b"\\ wf\n"
    b"100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then\n"
    b" 99 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then\n"
    b" 98 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then\n"
)

PLAYER_FORTH = (
    b"\\ wf\n"
    b"INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n"
)

# Lua needles. We match on substrings that are distinctive enough to pin
# the slot's start uniquely.
DIRECTOR_LUA_MARKER = b"-- Director Lua script"
PLAYER_LUA_MARKER   = b"write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))"


def find_slot(data: bytes, marker: bytes) -> tuple[int, int]:
    """Return [start, end) of the null-terminated C string containing marker."""
    idx = data.find(marker)
    if idx < 0:
        raise SystemExit(f"marker not found in cd.iff: {marker!r}")
    if data.find(marker, idx + 1) >= 0:
        raise SystemExit(f"marker matched twice in cd.iff: {marker!r}")
    # Walk back to previous null byte, forward to next null byte.
    start = idx
    while start > 0 and data[start - 1] != 0:
        start -= 1
    end = idx
    while end < len(data) and data[end] != 0:
        end += 1
    return start, end


def pad(replacement: bytes, target_len: int) -> bytes:
    if len(replacement) > target_len:
        raise SystemExit(
            f"Forth replacement {len(replacement)}B > slot {target_len}B")
    if len(replacement) == target_len:
        return replacement
    deficit = target_len - len(replacement)
    # Keep the final newline if the replacement ended in one.
    if replacement.endswith(b"\n"):
        return replacement[:-1] + (b" " * deficit) + b"\n"
    return replacement + (b" " * deficit)


def patch(path: Path) -> None:
    data = bytearray(path.read_bytes())

    ds, de = find_slot(bytes(data), DIRECTOR_LUA_MARKER)
    if de - ds != DIRECTOR_SLOT:
        raise SystemExit(
            f"director slot size mismatch: found {de-ds}, expected {DIRECTOR_SLOT}")
    data[ds:de] = pad(DIRECTOR_FORTH, DIRECTOR_SLOT)
    print(f"director: [{ds}..{de}) → Forth ({len(DIRECTOR_FORTH)}B + padding)")

    ps, pe = find_slot(bytes(data), PLAYER_LUA_MARKER)
    if pe - ps != PLAYER_SLOT:
        raise SystemExit(
            f"player slot size mismatch: found {pe-ps}, expected {PLAYER_SLOT}")
    data[ps:pe] = pad(PLAYER_FORTH, PLAYER_SLOT)
    print(f"player:   [{ps}..{pe}) → Forth ({len(PLAYER_FORTH)}B + padding)")

    path.write_bytes(bytes(data))
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: patch_cd_lua_to_forth.py <cd.iff>", file=sys.stderr)
        sys.exit(2)
    patch(Path(sys.argv[1]))
