#!/usr/bin/env python3
"""Byte-preserving patch of snowgoons.iff: rewrite the director script from
Fennel to a wasm module (base64-wrapped under the `#b64\\n` subtype tag),
padding with trailing spaces so the script's total byte count stays
identical.

Runs AFTER patch_snowgoons_fennel.py — the director needle is the current
Fennel form padded to the original TCL length, and the replacement is the
base64-wrapped wasm. The player is NOT patched: its 77 B slot in the iff
cannot hold any valid wasm module's base64 form (minimum ~108 B).

Usage:
    scripts/patch_snowgoons_wasm.py wflevels/snowgoons.iff [out.iff]
"""

import base64
import importlib.util
import sys
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent
REPO_ROOT    = SCRIPT_DIR.parent
DIRECTOR_WASM = REPO_ROOT / 'wftools/vendor/wasm3-v0.5.0-wf/snowgoons_director.wasm'

# Reuse pad_to + TCL needles from the Lua patcher, and the Fennel forms
# that are currently in the iff from the Fennel patcher.
def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_lua    = _load('_lua_patch',    SCRIPT_DIR / 'patch_snowgoons_lua.py')
_fennel = _load('_fennel_patch', SCRIPT_DIR / 'patch_snowgoons_fennel.py')
pad_to  = _lua.pad_to

# Target: rewrite the director only. Needle = current iff state for the
# director = DIRECTOR_FENNEL padded to the original TCL length.
_DIR_TCL_NEEDLE,    _DIR_LUA     = _lua.PATCHES[1]
_DIR_FENNEL_PADDED                = pad_to(_fennel.DIRECTOR_FENNEL, len(_DIR_TCL_NEEDLE))

def build_wasm_replacement() -> bytes:
    wasm = DIRECTOR_WASM.read_bytes()
    b64  = base64.b64encode(wasm)
    return b'#b64\n' + b64

PATCHES: list[tuple[bytes, bytes]] = [
    (_DIR_FENNEL_PADDED, build_wasm_replacement()),
]


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 1
    in_path  = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) == 3 else in_path

    data = bytearray(in_path.read_bytes())
    n    = len(data)

    for needle, replacement in PATCHES:
        if len(replacement) > len(needle):
            print(f'patch_snowgoons_wasm: replacement ({len(replacement)}B) '
                  f"won't fit in slot ({len(needle)}B)", file=sys.stderr)
            return 5
        idx = data.find(needle)
        if idx < 0:
            print(f'patch_snowgoons_wasm: needle not found '
                  f'(has this file been Fennel-patched?)',
                  file=sys.stderr)
            return 2
        if data.find(needle, idx + 1) >= 0:
            print('patch_snowgoons_wasm: needle matched twice '
                  '(refusing to patch)', file=sys.stderr)
            return 3
        padded = pad_to(replacement, len(needle))
        assert len(padded) == len(needle)
        data[idx:idx + len(needle)] = padded
        print(f'patched @0x{idx:06x}: {len(needle)}B '
              f'(padded {len(needle) - len(replacement)}B)', file=sys.stderr)

    if len(data) != n:
        print('internal error: data length changed', file=sys.stderr)
        return 4

    out_path.write_bytes(bytes(data))
    print(f'wrote {len(data)}B to {out_path}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
