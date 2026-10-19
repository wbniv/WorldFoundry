#!/usr/bin/env python3
"""Byte-preserving patch of snowgoons.iff: rewrite the player and director
scripts from Lua to Fennel, padding with trailing spaces so each script's
total byte count stays identical (no chunk size changes, no IFF size shifts,
no alignment to repair).

Runs AFTER patch_snowgoons_lua.py — the needles are the current Lua forms
(padded to the original TCL length), and the replacements are Fennel (padded
to the same length). Each Fennel script begins with `;` so the embedded
Fennel dispatcher in LuaInterpreter::RunScript routes it to `fennel.eval`.

Usage:
    scripts/patch_snowgoons_fennel.py wflevels/snowgoons.iff [out.iff]
"""

import importlib.util
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# Reuse pad_to + the (TCL needle, Lua replacement) pairs from the Lua patcher,
# so the Fennel needles track changes to the Lua patcher automatically.
_spec = importlib.util.spec_from_file_location(
    "_lua_patch", SCRIPT_DIR / "patch_snowgoons_lua.py")
_lua = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lua)
pad_to = _lua.pad_to

# Fennel replacements. Each starts with `;` (Lisp comment / Lua syntax error)
# so the engine's sigil sniff routes through fennel.eval. Writing whitespace
# at the end of a Fennel expression is benign, so the pad-to-length trick
# still applies.
# Bare `;` line-comment is the Fennel sigil; the form follows on the next
# line. Player is tight (77B to hit); skip the trailing newline after the
# form and leave a bare `;` header so we fit exactly.
PLAYER_FENNEL = (
    b';\n'
    b'(write_mailbox INDEXOF_INPUT (read_mailbox INDEXOF_HARDWARE_JOYSTICK1_RAW))'
)

DIRECTOR_FENNEL = (
    b';; snowgoons director\n'
    b'(let [v (read_mailbox 100)] (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))\n'
    b'(let [v (read_mailbox 99)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))\n'
    b'(let [v (read_mailbox 98)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))\n'
)

_FENNEL_REPLACEMENTS = [PLAYER_FENNEL, DIRECTOR_FENNEL]

# Build (current-iff-bytes, fennel-bytes) pairs. Needle = Lua replacement
# padded to the TCL original's byte count, which is exactly what the Lua
# patcher wrote into the file last.
PATCHES: list[tuple[bytes, bytes]] = []
for (tcl_needle, lua_repl), fennel in zip(_lua.PATCHES, _FENNEL_REPLACEMENTS):
    current_in_iff = pad_to(lua_repl, len(tcl_needle))
    PATCHES.append((current_in_iff, fennel))


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
            print(f'patch_snowgoons_fennel: needle not found '
                  f'(has this file been Lua-patched?):\n  {needle!r}',
                  file=sys.stderr)
            return 2
        if data.find(needle, idx + 1) >= 0:
            print(f'patch_snowgoons_fennel: needle matched twice '
                  f'(refusing to patch):\n  {needle!r}', file=sys.stderr)
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
