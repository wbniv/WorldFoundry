#!/usr/bin/env python3
"""Byte-preserving patch of snowgoons.iff: rewrite the director script from
its current form to a WAMR wasm module (base64-wrapped under the `#b64\\n`
subtype tag), padding with trailing spaces so the script's total byte count
stays identical.

Uses the WAMR-specific global-import wasm (compiled from snowgoons_director.wat
via wabt; INDEXOF_CAMSHOT resolved at instantiation time via host global import).
The player slot (77 B) is too small for any base64-wrapped wasm module; it
is not patched.

Usage:
    scripts/patch_snowgoons_wamr.py wflevels/snowgoons.iff [out.iff]
"""

import base64
import importlib.util
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT  = SCRIPT_DIR.parent

# Wasm binary embedded directly (158 bytes; compiled from snowgoons_director.wat
# with INDEXOF_CAMSHOT as a host-supplied global import).
_DIRECTOR_WASM_B64 = (
    "AGFzbQEAAAABEgRgAX8BfWACf30AYAF/AGAAAAJCAwZjb25zdHMPSU5ERVhPRl9DQU1TSE9U"
    "A38AA2VudgxyZWFkX21haWxib3gAAANlbnYNd3JpdGVfbWFpbGJveAABAwMCAgMHCAEEbWFp"
    "bgADCi0CGQEBfSAAEAAiAUMAAAAAXARAIwAgARABCwsRAEHkABACQeMAEAJB4gAQAgs="
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_current_director_bytes(data: bytearray) -> bytes | None:
    """Return the current director script bytes from the IFF, padded slot."""
    # Try each known director form in priority order:
    # wasm3/wamr b64, Wren, Fennel, Lua — whichever is in the file now.
    _lua    = _load('_lua_patch',    SCRIPT_DIR / 'patch_snowgoons_lua.py')
    _fennel = _load('_fennel_patch', SCRIPT_DIR / 'patch_snowgoons_fennel.py')
    pad_to  = _lua.pad_to

    _DIR_TCL_NEEDLE, _DIR_LUA = _lua.PATCHES[1]
    _DIR_FENNEL_PADDED = pad_to(_fennel.DIRECTOR_FENNEL, len(_DIR_TCL_NEEDLE))

    # Walk through candidates and find whichever is present.
    for needle in [
        _DIR_FENNEL_PADDED,
        _DIR_TCL_NEEDLE,
    ]:
        if needle in data:
            return needle

    # Try searching for the #b64 or //wren prefix within the slot-sized window.
    # (The iff may already be wasm3- or Wren-patched.)
    slot_len = len(_DIR_TCL_NEEDLE)
    b64_prefix = b'#b64\n'
    wren_prefix = b'//wren\n'
    for prefix in (b64_prefix, wren_prefix):
        idx = data.find(prefix)
        if idx >= 0:
            # Return the slot_len bytes starting at idx.
            return bytes(data[idx:idx + slot_len])

    return None


def build_replacement() -> bytes:
    wasm = base64.b64decode(_DIRECTOR_WASM_B64)
    b64  = base64.b64encode(wasm)
    return b'#b64\n' + b64


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 1

    in_path  = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) == 3 else in_path

    data = bytearray(in_path.read_bytes())
    n    = len(data)

    try:
        replacement = build_replacement()
    except FileNotFoundError as e:
        print(f'patch_snowgoons_wamr: {e}', file=sys.stderr)
        return 6

    needle = _find_current_director_bytes(data)
    if needle is None:
        print('patch_snowgoons_wamr: could not locate director script slot '
              'in the IFF', file=sys.stderr)
        return 2

    _lua   = _load('_lua_patch', SCRIPT_DIR / 'patch_snowgoons_lua.py')
    pad_to = _lua.pad_to

    if len(replacement) > len(needle):
        print(f'patch_snowgoons_wamr: replacement ({len(replacement)}B) '
              f"won't fit in slot ({len(needle)}B)", file=sys.stderr)
        return 5

    idx = data.find(needle)
    assert idx >= 0
    if data.find(needle, idx + 1) >= 0:
        print('patch_snowgoons_wamr: needle matched twice '
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
