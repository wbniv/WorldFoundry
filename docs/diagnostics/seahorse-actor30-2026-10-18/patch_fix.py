#!/usr/bin/env python3
"""Write a copy of a cooked aquarium level with the seahorse_behaviour.fth fix applied to its
Director script in place: sh-valid also requires progress x (35 - start) >= 1. The script
keeps its length (a following comment line gives up the bytes the fix adds), so no offsets
move. For checking the fix on frozen levels only; the shipped level is re-cooked from source.

    python3 patch_fix.py IN.iff OUT.iff
"""
import sys

OLD = b'24 sh@ 0 > 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!'
NEW = b'24 sh@ 35 22 sh@ - * 1 >= 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!'
DONOR = b'\\ Greeting (shared, once a frame before the seahorses): pair p\'s female and male take\n'


def main():
    if len(sys.argv) != 3 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0 if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help') else 2
    data = bytearray(open(sys.argv[1], 'rb').read())
    i = data.find(OLD)
    j = data.find(DONOR, i)
    assert i > 0 and j > i and data.find(OLD, i + 1) < 0, (i, j)
    extra = len(NEW) - len(OLD)
    donor = DONOR[:len(DONOR) - 1 - extra] + b'\n'
    out = bytes(data[:i]) + NEW + bytes(data[i + len(OLD):j]) + donor + bytes(data[j + len(DONOR):])
    assert len(out) == len(data)
    open(sys.argv[2], 'wb').write(out)
    print(sys.argv[2], 'patched at', i)
    return 0


if __name__ == '__main__':
    sys.exit(main())
