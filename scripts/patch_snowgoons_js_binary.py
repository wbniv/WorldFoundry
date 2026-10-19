#!/usr/bin/env python3
"""Directly patch snowgoons.iff with JavaScript scripts (in-place, no IFF recompile).

Finds each script slot in the binary by its known opening bytes, then overwrites
the slot content with the new JS script null-padded to the original slot length.
The IFF chunk structure (sizes, TOC offsets) is untouched, so the engine loads
correctly.

Usage:
    python3 scripts/patch_snowgoons_js_binary.py [iff_in] [iff_out]

Defaults: wflevels/snowgoons.iff → wflevels/snowgoons.iff  (in-place)
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Original slot needles — used to locate each slot in the binary.
# These are the first bytes of the script currently stored in the IFF.
DIRECTOR_NEEDLE = b';; snowgoons director'   # Fennel director in feb6ac2
PLAYER_NEEDLE   = b';\n(write_mailbox '       # TCL/Scheme player

# Replacement JS scripts.
PLAYER_JS = (
    b'//\n'
    b'write_mailbox(INDEXOF_INPUT,read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))'
)

DIRECTOR_JS = (
    b'// snowgoons director\n'
    b'var v;\n'
    b'v=read_mailbox(100);if(v!==0)write_mailbox(INDEXOF_CAMSHOT,v);\n'
    b'v=read_mailbox(99); if(v!==0)write_mailbox(INDEXOF_CAMSHOT,v);\n'
    b'v=read_mailbox(98); if(v!==0)write_mailbox(INDEXOF_CAMSHOT,v);\n'
)


def find_slot(data: bytes, needle: bytes) -> tuple[int, int]:
    """Return (slot_start, slot_len) by finding needle and reading to first NUL."""
    pos = data.find(needle)
    if pos == -1:
        raise ValueError(f'Needle not found: {needle[:20]!r}')
    null_off = data.index(b'\x00', pos)
    return pos, null_off - pos


def patch_slot(data: bytearray, needle: bytes, new_script: bytes, label: str) -> None:
    slot_start, slot_len = find_slot(data, needle)
    assert len(new_script) <= slot_len, (
        f'{label}: new script {len(new_script)} B exceeds slot {slot_len} B'
    )
    padded = new_script + b'\x00' * (slot_len - len(new_script))
    data[slot_start:slot_start + slot_len] = padded
    print(f'  {label}: offset={slot_start} slot={slot_len}B '
          f'script={len(new_script)}B', file=sys.stderr)


def main() -> int:
    iff_in  = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / 'wflevels/snowgoons.iff'
    iff_out = Path(sys.argv[2]) if len(sys.argv) > 2 else iff_in

    data = bytearray(iff_in.read_bytes())
    patch_slot(data, DIRECTOR_NEEDLE, DIRECTOR_JS, 'DIRECTOR')
    patch_slot(data, PLAYER_NEEDLE,   PLAYER_JS,   'PLAYER')
    iff_out.write_bytes(data)
    print(f'  Wrote {iff_out} ({len(data)} B)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
