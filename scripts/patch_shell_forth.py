#!/usr/bin/env python3
"""Byte-preserving patch of cd.iff's SHEL chunk: replace the Tcl/Lua shell
script with the Forth equivalent (padded with trailing spaces so the chunk
length doesn't change — no IFF size shifts, no alignment to repair).

Motivation: game.cc + level.cc hardcode the shell / meta script language
to Forth now (was Lua); the Forth-only Android build can't run Lua, and
for consistency we run the same script on desktop Linux too.

Usage:
    python3 scripts/patch_shell_forth.py wfsource/source/game/cd.iff

Writes back in place.
"""

import struct
import sys
from pathlib import Path

# zForth's minimal bootstrap (engine/stubs/scripting_zforth.cc) does not
# define `\` as a line-comment word — only the `\ wf\n` sigil on line 1 is
# stripped by the script router. Any subsequent `\`-prefixed comment inside
# the Forth body would be fed to zForth as a word and error out. So this
# script body is pure code; padding happens as trailing spaces.
FORTH_SHELL = (
    b"\\ wf\n"
    b"6000 read-mailbox  0 <>\n"
    b"if   0 6000                 write-mailbox\n"
    b"else 1 6000                 write-mailbox\n"
    b"     0 INDEXOF_LEVEL_TO_RUN write-mailbox\n"
    b"then\n"
)


def patch(path: Path) -> None:
    data = bytearray(path.read_bytes())

    # SHEL chunk: tag(4) + size(4, little-endian) + payload. Find by scanning
    # — for cd.iff the chunk lives right after the TOC + ALGN header, normally
    # at offset 2048.
    for off in (2048, 2056):
        if data[off:off + 4] == b"SHEL":
            break
    else:
        tag_off = data.find(b"SHEL", 8)
        if tag_off < 0:
            raise SystemExit("SHEL chunk not found in " + str(path))
        off = tag_off

    size = struct.unpack("<I", data[off + 4:off + 8])[0]
    payload_off = off + 8
    print(f"SHEL chunk @ {off}, payload size {size}")

    if len(FORTH_SHELL) > size:
        raise SystemExit(
            f"Forth shell is {len(FORTH_SHELL)}B, SHEL slot is {size}B")

    # Preserve the trailing newline if the original had one. We pad with
    # spaces in the middle so the script is still parseable.
    padded = FORTH_SHELL
    if padded.endswith(b"\n"):
        padded = padded[:-1] + b" " * (size - len(padded)) + b"\n"
    else:
        padded = padded + b" " * (size - len(padded))

    assert len(padded) == size
    data[payload_off:payload_off + size] = padded
    path.write_bytes(bytes(data))
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: patch_shell_forth.py <cd.iff>", file=sys.stderr)
        sys.exit(2)
    patch(Path(sys.argv[1]))
