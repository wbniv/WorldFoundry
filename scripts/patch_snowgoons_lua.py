#!/usr/bin/env python3
"""
Byte-preserving patch of snowgoons.iff: rewrite the player and director
scripts from TCL to Lua, padding with trailing spaces so each script's
total byte count stays identical (no chunk size changes, no IFF size
shifts, no alignment to repair).

Usage:
    scripts/patch_snowgoons_lua.py wflevels/snowgoons.iff [out.iff]

If `out.iff` is omitted, writes back to the input.
"""

import sys
from pathlib import Path

# (TCL needle, Lua replacement). Each replacement must be <= len(needle).
# Pad the difference with trailing spaces so the script keeps the same
# byte count and surrounding chunk structure stays valid.
PATCHES: list[tuple[bytes, bytes]] = [
    # Player input-forwarding script.
    (
        b'\twrite-mailbox $INDEXOF_INPUT [read-mailbox $INDEXOF_HARDWARE_JOYSTICK1_RAW]\n',
        b'\twrite_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))\n',
    ),
    # Director script: three identical-shape forwards from mailbox 100/99/98 → CAMSHOT.
    # We keep the leading `#` banner as Lua line comments by converting `#` → `--`,
    # but `--` is two chars; pad each comment line accordingly.
    (
        b'#===========================================================================\n'
        b'# Director tcl script\n'
        b'#===========================================================================\n'
        b'\n'
        b'\n'
        b'\tif { [read-mailbox 100] } {\n'
        b'\t\twrite-mailbox $INDEXOF_CAMSHOT [ read-mailbox 100 ]\n'
        b'\t}\n'
        b'\tif { [read-mailbox 99] } {\n'
        b'\t\twrite-mailbox $INDEXOF_CAMSHOT [ read-mailbox 99 ]\n'
        b'\t} \n'
        b'\tif { [read-mailbox 98] } {\n'
        b'\t\twrite-mailbox $INDEXOF_CAMSHOT [ read-mailbox 98 ]\n'
        b'\t} \n'
        b' \n'
        b'\n'
        b'\n'
        b'\n',
        b'-- =========================================================================\n'
        b'-- Director Lua script\n'
        b'-- =========================================================================\n'
        b'local v\n'
        b'v = read_mailbox(100); if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end\n'
        b'v = read_mailbox(99);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end\n'
        b'v = read_mailbox(98);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end\n',
    ),
]


def pad_to(replacement: bytes, target_len: int) -> bytes:
    """Pad replacement out to target_len with trailing spaces (Lua ignores them).
    The very last byte is preserved as a newline if present so the script ends
    on a line break (some readers care)."""
    if len(replacement) > target_len:
        raise ValueError(
            f'replacement ({len(replacement)}B) longer than original ({target_len}B):\n'
            f'  {replacement!r}'
        )
    deficit = target_len - len(replacement)
    if deficit == 0:
        return replacement
    # If the original ended in \n, preserve a trailing \n in the padded form.
    if replacement.endswith(b'\n'):
        return replacement[:-1] + (b' ' * deficit) + b'\n'
    return replacement + (b' ' * deficit)


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 1
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) == 3 else in_path

    data = bytearray(in_path.read_bytes())
    n = len(data)

    for needle, replacement in PATCHES:
        idx = data.find(needle)
        if idx < 0:
            print(f'patch_snowgoons_lua: needle not found:\n  {needle!r}', file=sys.stderr)
            return 2
        if data.find(needle, idx + 1) >= 0:
            print(f'patch_snowgoons_lua: needle matched twice (refusing to patch):\n  {needle!r}', file=sys.stderr)
            return 3
        padded = pad_to(replacement, len(needle))
        assert len(padded) == len(needle)
        data[idx:idx + len(needle)] = padded
        print(f'patched @0x{idx:06x}: {len(needle)}B (padded {len(needle) - len(replacement)}B)', file=sys.stderr)

    if len(data) != n:
        print('internal error: data length changed', file=sys.stderr)
        return 4

    out_path.write_bytes(bytes(data))
    print(f'wrote {len(data)}B to {out_path}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
