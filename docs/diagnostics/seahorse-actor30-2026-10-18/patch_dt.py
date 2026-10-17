#!/usr/bin/env python3
"""Write a copy of a cooked aquarium level whose Director sees every frame delta scaled by
(1 - eps): a device whose frames last 50 ms x (1 - eps) instead of exactly 50 ms, under the
engine's fixed -rate20 clock. The patch is the same length as the original tk-dt@ word, so
no offsets move. Test fixture only; nothing ships with it.

    python3 patch_dt.py IN.iff OUT.iff EPS
"""
import sys

OLD = b': tk-dt@ INDEXOF_DELTA_TIME tk@ dup .2 > if drop 0 else 0 max .05 min then ;'


def main():
    if len(sys.argv) != 4 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0 if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help') else 2
    src, dst, eps = sys.argv[1], sys.argv[2], float(sys.argv[3])
    data = open(src, 'rb').read()
    first = data.find(OLD)                      # the Director's (the Player's comes later)
    assert first > 0, 'tk-dt@ not found'
    new = f': tk-dt@ INDEXOF_DELTA_TIME tk@ 0 max .05 min {1 - eps:.7f} * ;'.encode()
    assert len(new) <= len(OLD), (len(new), len(OLD))
    new = new[:-1] + b' ' * (len(OLD) - len(new)) + b';'
    open(dst, 'wb').write(data[:first] + new + data[first + len(OLD):])
    print(dst, new.decode())
    return 0


if __name__ == '__main__':
    sys.exit(main())
