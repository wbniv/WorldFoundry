#!/usr/bin/env python3
"""Patch wflevels/snowgoons.iff.txt with Forth (\\ sigil) scripts.

Edits the PLAYER SCRIPT and DIRECTOR SCRIPT hex blocks in snowgoons.iff.txt
in-place, then recompiles with iffcomp-rs to produce snowgoons.iff.

Usage:
    python3 scripts/patch_snowgoons_forth.py [iff.txt] [iff.out]

Defaults: wflevels/snowgoons.iff.txt → wflevels/snowgoons.iff

Scripts use the `\\` sigil (Forth line-comment); ScriptRouter dispatches to
forth_engine.  The same source runs on every backend (zForth, ficl, Atlast,
embed, libforth, pForth) — backend selection is compile-time only via
WF_FORTH_ENGINE.

Word signatures:
    read-mailbox  ( idx -- val )
    write-mailbox ( val idx -- )
INDEXOF_* constants are loaded into the dictionary at forth_engine::Init.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IFFCOMP   = REPO_ROOT / "wftools/iffcomp-rs/target/release/iffcomp"
SLOT_SIZE = 5000

# Player: read joystick raw mailbox, write to input mailbox.
# Stack effect: ( -- )
PLAYER_FORTH = (
    b'\\ snowgoons player\n'
    b'INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox\n'
)

# Director: for each of mailboxes 100, 99, 98 — if non-zero, write to camshot.
# Uses a helper word ?cam ( idx -- ) defined in the same script.
DIRECTOR_FORTH = (
    b'\\ snowgoons director\n'
    b': ?cam ( idx -- ) read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then ;\n'
    b'100 ?cam   99 ?cam   98 ?cam\n'
)


def make_hex_block(script: bytes, slot: int = SLOT_SIZE,
                   indent: str = '\t', width: int = 16) -> str:
    data = script + b' ' * (slot - len(script))
    assert len(data) == slot
    lines = []
    for i in range(0, len(data), width):
        row = data[i:i+width]
        lines.append(indent + ' '.join(f'${b:02X}' for b in row))
    return '\n'.join(lines) + '\n'


def replace_script_block(text: str, label: str, new_script: bytes) -> str:
    """Replace the hex block following the '// LABEL SCRIPT' comment."""
    pattern = re.compile(
        r'(// =+\n\t// ' + label + r' SCRIPT.*?// =+\n)'  # comment block
        r'(\t(?:\$[0-9A-Fa-f]{2} ?)+\n)+',               # hex lines
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        raise ValueError(f"{label} SCRIPT block not found in iff.txt")
    new_block = m.group(1) + make_hex_block(new_script)
    result = text[:m.start()] + new_block + text[m.end():]
    old_bytes = (m.end() - m.start() - len(m.group(1)))
    print(f"  {label}: replaced ~{old_bytes} chars of hex "
          f"({len(new_script)} B script → {SLOT_SIZE} B slot)", file=sys.stderr)
    return result


def main() -> int:
    txt_path = (Path(sys.argv[1]) if len(sys.argv) > 1
                else REPO_ROOT / 'wflevels/snowgoons.iff.txt')
    iff_out  = (Path(sys.argv[2]) if len(sys.argv) > 2
                else txt_path.with_suffix(''))  # strips .txt

    assert len(PLAYER_FORTH)   <= SLOT_SIZE, "player script too long"
    assert len(DIRECTOR_FORTH) <= SLOT_SIZE, "director script too long"

    text = txt_path.read_text()
    text = replace_script_block(text, 'DIRECTOR', DIRECTOR_FORTH)
    text = replace_script_block(text, 'PLAYER',   PLAYER_FORTH)
    txt_path.write_text(text)
    print(f"  Updated {txt_path}", file=sys.stderr)

    print(f"  Compiling → {iff_out}", file=sys.stderr)
    r = subprocess.run(
        [str(IFFCOMP), f'-o={iff_out}', '-binary', str(txt_path)],
        capture_output=True, text=True,
    )
    if r.returncode:
        print(r.stderr, file=sys.stderr)
        return r.returncode
    print(f"  Done ({iff_out.stat().st_size} B)", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
