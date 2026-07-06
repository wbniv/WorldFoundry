#!/usr/bin/env python3
"""Minify a Lua source file: strip `--` line comments and `--[[...]]` block
comments (any bracket level), collapse runs of blank lines. Preserves all
string literals byte-for-byte. Output remains valid Lua.

Used by build_game.sh to shrink the embedded fennel.lua before xxd-i'ing
it into the binary.

Usage: minify_lua.py <input.lua> <output.lua>
"""

import re
import sys
from pathlib import Path


def _long_bracket_level(src: str, pos: int) -> int:
    """If src[pos:] starts with `[`, optional `=`s, `[`, return the level
    (count of `=`). Otherwise -1."""
    if pos >= len(src) or src[pos] != '[':
        return -1
    j = pos + 1
    level = 0
    while j < len(src) and src[j] == '=':
        level += 1
        j += 1
    if j < len(src) and src[j] == '[':
        return level
    return -1


def minify(src: str) -> str:
    out: list[str] = []
    i, n = 0, len(src)

    while i < n:
        c = src[i]

        # Short-string literals "..." / '...' (with backslash escapes).
        if c == '"' or c == "'":
            out.append(c)
            i += 1
            while i < n:
                ch = src[i]
                if ch == '\\' and i + 1 < n:
                    out.append(ch); out.append(src[i + 1])
                    i += 2
                    continue
                out.append(ch)
                i += 1
                if ch == c or ch == '\n':  # closed, or unterminated at newline
                    break
            continue

        # Long-string literals [[...]], [=[...]=], etc.
        if c == '[':
            lvl = _long_bracket_level(src, i)
            if lvl >= 0:
                closer = ']' + ('=' * lvl) + ']'
                open_len = 2 + lvl
                end = src.find(closer, i + open_len)
                if end < 0:
                    out.append(src[i:])
                    break
                out.append(src[i:end + len(closer)])
                i = end + len(closer)
                continue

        # Comments: `--` optionally followed by a long bracket = block comment.
        if c == '-' and i + 1 < n and src[i + 1] == '-':
            lvl = _long_bracket_level(src, i + 2)
            if lvl >= 0:
                closer = ']' + ('=' * lvl) + ']'
                open_len = 2 + 2 + lvl  # `--` + `[` + `=`*lvl + `[`
                end = src.find(closer, i + open_len)
                i = n if end < 0 else end + len(closer)
                continue
            # Line comment: drop through end of line; leave the `\n`.
            while i < n and src[i] != '\n':
                i += 1
            continue

        out.append(c)
        i += 1

    result = ''.join(out)
    # Trim trailing whitespace on each line, then collapse blank-line runs.
    result = re.sub(r'[ \t]+\n', '\n', result)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 1
    src = Path(sys.argv[1]).read_text()
    out = minify(src)
    Path(sys.argv[2]).write_text(out)
    print(f'minify_lua: {len(src)} -> {len(out)} bytes '
          f'({100 * (1 - len(out) / len(src)):.1f}% smaller)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
