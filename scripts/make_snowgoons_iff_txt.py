#!/usr/bin/env python3
"""Generate wflevels/snowgoons.iff.txt from the binary iff.

The binary iff has script slots sized to match the original TCL scripts (77 B
player, 439 B director). This tool:

  1. Dumps the binary with iffdump-rs (-f- format).
  2. Finds the two script slots in the flat $XX token stream.
  3. Replaces each with a 5 KB padded slot (spaces after the script content).
  4. Writes wflevels/snowgoons.iff.txt (iffcomp source, round-trippable).

After this file exists, the workflow for testing a different scripting language:

    # 1. Edit the script section in wflevels/snowgoons.iff.txt
    # 2. Recompile:
    wftools/iffcomp-rs/target/release/iffcomp \\
        -o=wflevels/snowgoons.iff -binary wflevels/snowgoons.iff.txt

No byte-preserving patching required.

Usage:
    python3 scripts/make_snowgoons_iff_txt.py [iff] [out.iff.txt]

Defaults: wflevels/snowgoons.iff → wflevels/snowgoons.iff.txt
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IFFDUMP   = REPO_ROOT / "wftools/iffdump-rs/target/release/iffdump"
SLOT_SIZE = 5000  # bytes per script slot

# Script content as currently in the binary (used as search needles).
PLAYER_SCRIPT = (
    b';\n(write_mailbox INDEXOF_INPUT (read_mailbox INDEXOF_HARDWARE_JOYSTICK1_RAW))'
)
DIRECTOR_SCRIPT_START = b';; snowgoons director'


def run_iffdump(iff_path: Path) -> str:
    r = subprocess.run([str(IFFDUMP), '-f-', str(iff_path)],
                       capture_output=True, text=True, check=True)
    return r.stdout


def make_slot_bytes(script: bytes, slot_size: int = SLOT_SIZE) -> bytes:
    """Pad script to slot_size with spaces."""
    assert len(script) <= slot_size, f"{len(script)} > {slot_size}"
    return script + b' ' * (slot_size - len(script))


def hex_block(data: bytes, indent: str = '\t', width: int = 16) -> str:
    """Render bytes as lines of $XX tokens."""
    lines = []
    for i in range(0, len(data), width):
        row = data[i:i+width]
        lines.append(indent + ' '.join(f'${b:02X}' for b in row))
    return '\n'.join(lines) + '\n'


def find_and_replace_tokens(dump: str, needle: bytes, replacement: bytes,
                             label: str) -> str:
    """Replace `needle` bytes (as $XX tokens) in dump with `replacement` bytes.

    Handles the case where the needle starts mid-line — we find the first
    $XX token matching needle[0], verify the subsequent tokens match the
    rest of the needle, then do a text-level substitution of the exact
    character span.
    """
    # Build the needle as a list of uppercase $XX strings
    ndl = [f'${b:02X}' for b in needle]
    n = len(ndl)

    # Find all $XX token positions (char index in dump, token value)
    tok_re = re.compile(r'\$[0-9A-Fa-f]{2}')
    all_toks = [(m.start(), m.end(), m.group().upper()) for m in tok_re.finditer(dump)]

    # Search for needle
    vals = [v for _, _, v in all_toks]
    ndl_up = [x.upper() for x in ndl]
    idx = None
    for i in range(len(vals) - n + 1):
        if vals[i:i+n] == ndl_up:
            idx = i
            break
    if idx is None:
        raise ValueError(f"Needle for {label} not found: {needle[:16]!r}…")

    char_start = all_toks[idx][0]
    char_end   = all_toks[idx + n - 1][1]

    comment = (
        f'\n\t// {"=" * 60}\n'
        f'\t// {label} SCRIPT — {SLOT_SIZE}-byte slot\n'
        f'\t// Edit the hex below, then recompile:\n'
        f'\t//   iffcomp-rs -o=snowgoons.iff -binary snowgoons.iff.txt\n'
        f'\t// Current content: {needle.decode("ascii", "replace")[:60]!r}'
        f'{"…" if len(needle) > 60 else ""}\n'
        f'\t// {"=" * 60}\n'
    )

    new_hex = hex_block(make_slot_bytes(needle))
    replacement_text = comment + new_hex

    print(f"  {label}: replaced {n} tokens ({n} B → {SLOT_SIZE} B)", file=sys.stderr)
    return dump[:char_start] + replacement_text + dump[char_end:]


def main() -> int:
    iff_path = (Path(sys.argv[1]) if len(sys.argv) > 1
                else REPO_ROOT / 'wflevels/snowgoons.iff')
    out_path = (Path(sys.argv[2]) if len(sys.argv) > 2
                else iff_path.with_suffix('.iff.txt'))

    print(f"Dumping {iff_path} …", file=sys.stderr)
    dump = run_iffdump(iff_path)

    # Read binary to locate director script bytes.
    # The script is a C string (null-terminated); use the first NUL as the end.
    data = iff_path.read_bytes()
    dir_off = data.find(DIRECTOR_SCRIPT_START)
    if dir_off < 0:
        print("error: director script start not found", file=sys.stderr)
        return 1
    null_off = data.index(b'\x00', dir_off)
    dir_content = data[dir_off:null_off]
    print(f"Director script: {len(dir_content)} B (null-terminated)", file=sys.stderr)
    print(f"Player script:   {len(PLAYER_SCRIPT)} B", file=sys.stderr)

    # Replace director first (it comes earlier in the file)
    dump = find_and_replace_tokens(dump, dir_content, dir_content,
                                   'DIRECTOR')
    dump = find_and_replace_tokens(dump, PLAYER_SCRIPT, PLAYER_SCRIPT,
                                   'PLAYER')

    out_path.write_text(dump)
    kb = out_path.stat().st_size // 1024
    print(f"Wrote {out_path} ({kb} KB)", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
