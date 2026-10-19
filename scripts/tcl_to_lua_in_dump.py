#!/usr/bin/env python3
"""
Rewrite TCL mailbox scripts to Lua inside an iffdump -f- output file.

Pipeline:
    iffdump -c<chunks> -f- cd.iff cd.iff.txt
    python3 scripts/tcl_to_lua_in_dump.py cd.iff.txt cd.iff.lua.txt
    iffcomp -binary cd.iff.lua.txt -o=cd.iff

iffdump's -f- format emits each leaf-chunk byte as `$XX` tokens, one group
per line. We find contiguous runs of `$XX` tokens whose ASCII decoding
contains `read-mailbox` or `write-mailbox` and rewrite the payload from
the TCL dialect to Lua. iffcomp recomputes chunk sizes on recompile.

The TCL→Lua translation is minimal and specific to WF's mailbox scripts:

    read-mailbox N      → read_mailbox(N)
    write-mailbox N V   → write_mailbox(N, V)
    $INDEXOF_X          → INDEXOF_X
    if { EXPR } { BODY }→ if (EXPR) ~= 0 then BODY end

It does NOT try to be a general TCL-to-Lua translator. Unhandled TCL
constructs are passed through; run the output past a Lua lint before
trusting it.
"""

import re
import sys
from pathlib import Path

# Matches a line like `\t\t$72 $65 $61 $64` (1-4 bytes per line in practice).
HEX_LINE = re.compile(r'^(\s*)((?:\$[0-9A-Fa-f]{2}\s*)+)\s*$')


def decode_bytes(tokens):
    return bytes(int(tok[1:], 16) for tok in tokens)


def encode_bytes(data, indent):
    """Encode bytes back into $XX lines at 4 bytes per line (matching iffdump)."""
    lines = []
    for i in range(0, len(data), 4):
        chunk = data[i:i + 4]
        lines.append(indent + ' '.join(f'${b:02X}' for b in chunk))
    return lines


TCL_READ = re.compile(r'\[\s*read-mailbox\s+([^\]]+?)\s*\]')
TCL_WRITE = re.compile(r'write-mailbox\s+(\S+)\s+(\S.*?)\s*$', re.MULTILINE)
TCL_IF = re.compile(r'if\s*\{\s*(.+?)\s*\}\s*\{\s*(.+?)\s*\}\s*', re.DOTALL)
TCL_INDEXOF = re.compile(r'\$(INDEXOF_\w+|JOYSTICK_\w+)')


def tcl_to_lua(src: str) -> str:
    """Very small TCL→Lua rewrite for WF mailbox scripts."""
    s = src

    # Strip $ from named integer constants.
    s = TCL_INDEXOF.sub(r'\1', s)

    # `[read-mailbox N]` → `read_mailbox(N)` (applied first so nested calls work).
    prev = None
    while prev != s:
        prev = s
        s = TCL_READ.sub(lambda m: f'read_mailbox({m.group(1).strip()})', s)

    # `write-mailbox N V` (bareword) → `write_mailbox(N, V)`.
    # Done line-by-line so we don't greedily eat subsequent statements.
    out_lines = []
    for line in s.splitlines(keepends=True):
        stripped = line.rstrip('\r\n')
        body, _, eol = line.partition('\n')
        m = re.match(r'^(\s*)write-mailbox\s+(\S+)\s+(.+?)\s*$', stripped)
        if m:
            indent, box, val = m.groups()
            out_lines.append(f'{indent}write_mailbox({box}, {val})' + line[len(stripped):])
        else:
            out_lines.append(line)
    s = ''.join(out_lines)

    # `if { EXPR } { BODY }` → `if (EXPR) ~= 0 then BODY end`.
    # Run repeatedly to catch back-to-back blocks.
    def sub_if(m):
        expr, body = m.group(1).strip(), m.group(2).strip()
        return f'if ({expr}) ~= 0 then {body} end'

    prev = None
    while prev != s:
        prev = s
        s = TCL_IF.sub(sub_if, s)

    return s


def try_rewrite(data: bytes) -> bytes | None:
    """Find each ASCII-printable stretch inside `data` that contains a TCL
    mailbox script and rewrite it to Lua. Non-script bytes (binary payload,
    non-script strings) pass through untouched.
    """
    if b'read-mailbox' not in data and b'write-mailbox' not in data:
        return None

    # Locate runs of printable-ASCII (plus \t \r \n) bytes. Scripts here are
    # always such runs; binary payload is not.
    out = bytearray()
    i = 0
    n = len(data)
    any_rewrite = False
    while i < n:
        b = data[i]
        if 9 <= b <= 13 or 32 <= b <= 126:
            # start of a printable run
            j = i
            while j < n:
                c = data[j]
                if 9 <= c <= 13 or 32 <= c <= 126:
                    j += 1
                else:
                    break
            run = data[i:j]
            if b'read-mailbox' in run or b'write-mailbox' in run:
                new_run = tcl_to_lua(run.decode('ascii')).encode('ascii')
                out.extend(new_run)
                any_rewrite = True
            else:
                out.extend(run)
            i = j
        else:
            out.append(b)
            i += 1
    return bytes(out) if any_rewrite else None


def process(infile: Path, outfile: Path) -> int:
    lines = infile.read_text().splitlines(keepends=True)

    # Walk lines, accumulating contiguous $XX runs.
    out = []
    i = 0
    rewrites = 0
    while i < len(lines):
        m = HEX_LINE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue

        # Start of a hex run. Collect until the run ends.
        start = i
        indent = m.group(1)
        tokens = []
        while i < len(lines):
            m2 = HEX_LINE.match(lines[i])
            if not m2 or m2.group(1) != indent:
                break
            tokens.extend(m2.group(2).split())
            i += 1

        data = decode_bytes(tokens)
        replacement = try_rewrite(data)
        if replacement is None:
            out.extend(lines[start:i])
        else:
            print(
                f'rewrite @{start + 1}: {len(data)}B → {len(replacement)}B',
                file=sys.stderr,
            )
            trailing = lines[i - 1][len(lines[i - 1].rstrip('\r\n')):]
            new_lines = encode_bytes(replacement, indent)
            out.extend(line + trailing for line in new_lines)
            rewrites += 1

    outfile.write_text(''.join(out))
    return rewrites


def main() -> int:
    if len(sys.argv) != 3:
        print('Usage: tcl_to_lua_in_dump.py <in.iff.txt> <out.iff.txt>', file=sys.stderr)
        return 1
    n = process(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f'rewrote {n} script chunk(s)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
