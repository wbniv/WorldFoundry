#!/usr/bin/env python3
"""Write a copy of a cooked aquarium level with the seahorse_behaviour.fth fix applied to its
Director script in place: sh-valid also requires progress x (35 - start) >= 1. The script
keeps its length (a following comment line gives up the bytes the fix adds), so no offsets
move. For checking the fix on frozen levels only; the shipped level is re-cooked from source.

--reverse does the opposite on a level cooked with the fix: it puts the old sh-valid line
back, padded with trailing spaces to the same length, so the result is the shipped level with
only the bug restored. Test fixture only (the Debug assertion check of 2026-11-14).

    python3 patch_fix.py [--reverse] IN.iff OUT.iff
"""
import sys

OLD = b'24 sh@ 0 > 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!'
NEW = b'24 sh@ 35 22 sh@ - * 1 >= 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!'
DONOR = b'\\ Greeting (shared, once a frame before the seahorses): pair p\'s female and male take\n'


def reverse(data):
    i = data.find(NEW)
    assert i > 0 and data.find(NEW, i + 1) < 0 and data.find(OLD) < 0, i
    return bytes(data[:i]) + OLD + b' ' * (len(NEW) - len(OLD)) + bytes(data[i + len(NEW):]), i


def forward(data):
    i = data.find(OLD)
    j = data.find(DONOR, i)
    assert i > 0 and j > i and data.find(OLD, i + 1) < 0, (i, j)
    extra = len(NEW) - len(OLD)
    donor = DONOR[:len(DONOR) - 1 - extra] + b'\n'
    return bytes(data[:i]) + NEW + bytes(data[i + len(OLD):j]) + donor + bytes(data[j + len(DONOR):]), i


def main():
    args = sys.argv[1:]
    if args and args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    rev = bool(args) and args[0] == '--reverse'
    if rev:
        args = args[1:]
    if len(args) != 2:
        print(__doc__)
        return 2
    data = bytearray(open(args[0], 'rb').read())
    out, i = (reverse if rev else forward)(data)
    assert len(out) == len(data)
    open(args[1], 'wb').write(out)
    print(args[1], 'unpatched' if rev else 'patched', 'at', i)
    return 0


if __name__ == '__main__':
    sys.exit(main())
