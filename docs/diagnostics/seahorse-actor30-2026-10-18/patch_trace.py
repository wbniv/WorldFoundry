#!/usr/bin/env python3
"""Write a copy of a cooked planted level, or of a cd.iff that bundles it, whose Director
prints one line per seahorse per frame for level time 6 to 8 s, to stderr (the engine log,
wf.log on Android):

    777 <seahorse id> <level time> <raw frame delta> <wrap progress> <reported centre y> <body x> <body y>

The trace line goes in sh-tick right after the sh-valid line. The script keeps its length:
the comment lines that follow sh-tick give up the bytes the trace adds (each keeps at least
"\\ ."; the code lines between them move up), so no offsets move. Diagnostic fixture only; nothing ships with it.

    python3 patch_trace.py IN OUT
"""
import sys

ANCHOR = b'24 sh@ 35 22 sh@ - * 1 >= 39 sh@ 1 <> & 39 sh@ 2 <> & sh-valid sh!\n'
# The engine's zForth bootstrap has no '.' or 'emit': 1 sys prints a cell, 0 sys a character.
TRACE = (b'  INDEXOF_TIME tk@ dup 6 > over 8 < & if 777 1 sys sh-id sh@ 1 sys 1 sys INDEXOF_DELTA_TIME tk@'
         b' 1 sys 24 sh@ 1 sys 34 sh@ 1 sys sh-x sh@ 1 sys sh-y sh@ 1 sys 10 0 sys else drop then\n')
TAIL = b'  sh-fin sh@ .022 0 1 sh-fins sh@ fin-deform ;\n'


def main():
    if len(sys.argv) != 3 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0 if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help') else 2
    data = open(sys.argv[1], 'rb').read()
    i = data.find(ANCHOR)
    assert i > 0 and data.find(ANCHOR, i + 1) < 0, 'expected one fixed sh-valid line'
    cut = i + len(ANCHOR)
    end = data.find(TAIL, cut)
    assert end > cut and end - cut < 400, 'sh-tick tail not found'
    end += len(TAIL)
    need, pos, lines = len(TRACE), end, []
    while need > 0:                     # shrink the comment lines after sh-tick; code lines move up
        nl = data.find(b'\n', pos)
        line = data[pos:nl + 1]
        assert nl > 0 and pos - end < 6000 and b'\0' not in line, 'ran out of comment lines'
        if line.startswith(b'\\ '):
            keep = max(4, len(line) - need)              # '\ .' + newline at least
            need -= len(line) - keep
            line = line[:keep - 1] + b'\n'
        lines.append(line)
        pos = nl + 1
    out = data[:cut] + TRACE + data[cut:end] + b''.join(lines) + data[pos:]
    assert len(out) == len(data)
    open(sys.argv[2], 'wb').write(out)
    print(sys.argv[2], 'trace at', cut, 'lines rewritten:', len(lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())
