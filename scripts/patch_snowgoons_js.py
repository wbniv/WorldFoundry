#!/usr/bin/env python3
"""Patch wflevels/snowgoons.iff.txt with JavaScript (// sigil) scripts.

Edits the PLAYER SCRIPT and DIRECTOR SCRIPT hex blocks in snowgoons.iff.txt
in-place, then recompiles with iffcomp-rs to produce snowgoons.iff.

Usage:
    python3 scripts/patch_snowgoons_js.py [iff.txt] [iff.out]

Defaults: wflevels/snowgoons.iff.txt → wflevels/snowgoons.iff

The script uses the 5 KB slots introduced by make_snowgoons_iff_txt.py.
Both scripts start with '//' so ScriptRouter dispatches them to js_engine.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IFFCOMP   = REPO_ROOT / "wftools/iffcomp-rs/target/release/iffcomp"
SLOT_SIZE = 5000

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
    # The section comment looks like:
    #   \t// ===…\n\t// LABEL SCRIPT …\n…\n\t// ===…\n
    # followed immediately by lines of $XX tokens, ending at the next
    # non-hex line (closing brace or next comment).
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

    assert len(PLAYER_JS)   <= SLOT_SIZE, "player script too long"
    assert len(DIRECTOR_JS) <= SLOT_SIZE, "director script too long"

    text = txt_path.read_text()
    text = replace_script_block(text, 'DIRECTOR', DIRECTOR_JS)
    text = replace_script_block(text, 'PLAYER',   PLAYER_JS)
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
