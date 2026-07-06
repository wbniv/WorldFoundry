#!/usr/bin/env python3
"""Byte-preserving patch of snowgoons.iff: rewrite the player and director
scripts from Fennel to Forth (backslash sigil) for forth_engine dispatch,
padding with trailing spaces so each script's total byte count stays identical
(no chunk size changes, no IFF size shifts, no alignment to repair).

Works directly on the binary snowgoons.iff — no iff.txt recompile needed.
The same script source runs on every backend (zForth, ficl, Atlast, embed,
libforth, pForth); backend selection is compile-time only via WF_FORTH_ENGINE.

Usage:
    python3 scripts/patch_snowgoons_forth.py wflevels/snowgoons.iff [out.iff]

If out.iff is omitted, writes back to the input.

Word signatures:
    read-mailbox  ( idx -- val )
    write-mailbox ( val idx -- )
INDEXOF_* constants are loaded into the dictionary at forth_engine::Init.

Slot sizes (fixed by _Common struct offsets; must not change):
    Player:   77 bytes (null-terminated C string)
    Director: 439 bytes (null-terminated C string)
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT  = SCRIPT_DIR.parent


def pad_to(replacement: bytes, target_len: int) -> bytes:
    """Pad replacement to target_len with trailing spaces.
    If replacement ends in \\n, the \\n is preserved as the final byte."""
    if len(replacement) > target_len:
        raise ValueError(
            f'replacement ({len(replacement)}B) longer than original ({target_len}B):\n'
            f'  {replacement!r}'
        )
    deficit = target_len - len(replacement)
    if deficit == 0:
        return replacement
    if replacement.endswith(b'\n'):
        return replacement[:-1] + (b' ' * deficit) + b'\n'
    return replacement + (b' ' * deficit)


# ---------------------------------------------------------------------------
# Slot sizes (bytes of script text, excluding the null terminator)
# ---------------------------------------------------------------------------
PLAYER_SLOT   = 77   # ;\n(write_mailbox ...) — 77 bytes of text
DIRECTOR_SLOT = 439  # ;; snowgoons director ... — 439 bytes including trailing \n

# ---------------------------------------------------------------------------
# Current content needles (Fennel state written by patch_snowgoons_fennel.py)
# ---------------------------------------------------------------------------
PLAYER_FENNEL_NEEDLE = (
    b';\n'
    b'(write_mailbox INDEXOF_INPUT (read_mailbox INDEXOF_HARDWARE_JOYSTICK1_RAW))'
)  # exactly PLAYER_SLOT bytes

# Accept both the wflevels/ form (compiled from iff.txt, has "(Fennel)" label)
# and the cd.iff form (patched by patch_snowgoons_fennel.py, no label suffix).
_DIRECTOR_FENNEL_PREFIX_OPTS = (
    b';; snowgoons director (Fennel)\n',  # wflevels/snowgoons.iff
    b';; snowgoons director\n',           # cd.iff after patch_snowgoons_fennel.py
)
DIRECTOR_FENNEL_PREFIX = None  # resolved at patch time

# ---------------------------------------------------------------------------
# Forth replacements
# ---------------------------------------------------------------------------
# Player: \ sigil (Forth line-comment) + one-liner. 76 bytes → padded to 77.
PLAYER_FORTH = (
    b'\\ wf\n'
    b'INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n'
)

# Director: inline if/else/fi for mailboxes 100/99/98.
# Avoids defining a word per tick (zForth dict is append-only).
# Uses zForth `then` (= `fi` alias defined in bootstrap) for readability.
# 225 bytes → padded to 439.
DIRECTOR_FORTH = (
    b'\\ wf\n'
    b'100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then\n'
    b' 99 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then\n'
    b' 98 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then\n'
)

assert len(PLAYER_FENNEL_NEEDLE) == PLAYER_SLOT,   "player needle length mismatch"
assert len(PLAYER_FORTH)         <= PLAYER_SLOT,   "player Forth script too long"
assert len(DIRECTOR_FORTH)       <= DIRECTOR_SLOT, "director Forth script too long"


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 1

    in_path  = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) == 3 else in_path

    data = bytearray(in_path.read_bytes())
    n    = len(data)

    # ------------------------------------------------------------------
    # Patch player
    # ------------------------------------------------------------------
    idx = data.find(PLAYER_FENNEL_NEEDLE)
    if idx < 0:
        print('patch_snowgoons_forth: player Fennel needle not found '
              '(has the file already been Forth-patched, or not Fennel-patched?)',
              file=sys.stderr)
        return 2
    if data.find(PLAYER_FENNEL_NEEDLE, idx + 1) >= 0:
        print('patch_snowgoons_forth: player needle matched twice (refusing)',
              file=sys.stderr)
        return 3

    padded_player = pad_to(PLAYER_FORTH, PLAYER_SLOT)
    assert len(padded_player) == PLAYER_SLOT
    data[idx:idx + PLAYER_SLOT] = padded_player
    print(f'player:   patched @0x{idx:06x}: {PLAYER_SLOT}B '
          f'(script {len(PLAYER_FORTH)}B, padded {PLAYER_SLOT - len(PLAYER_FORTH)}B)',
          file=sys.stderr)

    # ------------------------------------------------------------------
    # Patch director (try each known prefix variant)
    # ------------------------------------------------------------------
    dir_idx = -1
    matched_prefix = None
    for pfx in _DIRECTOR_FENNEL_PREFIX_OPTS:
        i = data.find(pfx)
        if i >= 0:
            dir_idx = i
            matched_prefix = pfx
            break
    if dir_idx < 0:
        print('patch_snowgoons_forth: director Fennel prefix not found '
              '(has the file already been Forth-patched, or not Fennel-patched?)',
              file=sys.stderr)
        return 4
    if data.find(matched_prefix, dir_idx + 1) >= 0:
        print('patch_snowgoons_forth: director prefix matched twice (refusing)',
              file=sys.stderr)
        return 5

    padded_director = pad_to(DIRECTOR_FORTH, DIRECTOR_SLOT)
    assert len(padded_director) == DIRECTOR_SLOT
    data[dir_idx:dir_idx + DIRECTOR_SLOT] = padded_director
    print(f'director: patched @0x{dir_idx:06x}: {DIRECTOR_SLOT}B '
          f'(script {len(DIRECTOR_FORTH)}B, padded {DIRECTOR_SLOT - len(DIRECTOR_FORTH)}B)',
          file=sys.stderr)

    # ------------------------------------------------------------------
    # Verify no size change and write
    # ------------------------------------------------------------------
    if len(data) != n:
        print('internal error: data length changed', file=sys.stderr)
        return 6

    out_path.write_bytes(bytes(data))
    print(f'wrote {len(data)}B to {out_path}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
