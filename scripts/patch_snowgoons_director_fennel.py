#!/usr/bin/env python3
"""Byte-preserving patch of snowgoons.iff: replace the wasm3 director script
with a Fennel director, padding to the same byte count so no chunk sizes
or alignments change.

The Fennel form starts with `;` (Lua syntax error / Fennel sigil) so the
engine's dispatch in LuaInterpreter::RunScript routes it to fennel.eval.

Usage:
    scripts/patch_snowgoons_director_fennel.py wflevels/snowgoons.iff [out.iff]
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "_lua_patch", SCRIPT_DIR / "patch_snowgoons_lua.py")
_lua = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lua)
pad_to = _lua.pad_to

# Fennel director: reads trigger mailboxes 98/99/100, writes INDEXOF_CAMSHOT.
# Priority: 100 wins over 99 wins over 98 (last write wins, so put lowest
# priority first). Each let-binding is independent; the last truthy one sticks.
DIRECTOR_FENNEL = (
    b';; snowgoons director (Fennel)\n'
    b'(let [v (read_mailbox 98)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))\n'
    b'(let [v (read_mailbox 99)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))\n'
    b'(let [v (read_mailbox 100)] (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))\n'
)

SLOT_SIZE = 439  # byte count of director slot in the iff (excl. null terminator)

def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 1
    in_path  = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) == 3 else in_path

    data = bytearray(in_path.read_bytes())

    # Needle: the #b64 marker that starts the current wasm3 director slot.
    needle_start = b'#b64\n'
    idx = data.find(needle_start)
    if idx < 0:
        print('patch: #b64 marker not found — has the file already been patched?',
              file=sys.stderr)
        return 2
    if data.find(needle_start, idx + 1) >= 0:
        print('patch: #b64 marker found twice — refusing to patch', file=sys.stderr)
        return 3

    needle = bytes(data[idx : idx + SLOT_SIZE])
    if len(DIRECTOR_FENNEL) > SLOT_SIZE:
        print(f'patch: Fennel script ({len(DIRECTOR_FENNEL)}B) '
              f'exceeds slot ({SLOT_SIZE}B)', file=sys.stderr)
        return 4

    padded = pad_to(DIRECTOR_FENNEL, SLOT_SIZE)
    assert len(padded) == SLOT_SIZE
    data[idx : idx + SLOT_SIZE] = padded

    print(f'patched director @0x{idx:06x}: {SLOT_SIZE}B '
          f'(script {len(DIRECTOR_FENNEL)}B + {SLOT_SIZE - len(DIRECTOR_FENNEL)}B padding)',
          file=sys.stderr)

    out_path.write_bytes(bytes(data))
    print(f'wrote {len(data)}B to {out_path}', file=sys.stderr)
    return 0

if __name__ == '__main__':
    sys.exit(main())
