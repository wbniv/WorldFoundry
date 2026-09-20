#!/usr/bin/env python3
"""Compare deterministic renderer captures (8-bit RGB/RGBA PNG; no dependencies).

Use the same backend frame, level and -rate20 on both platforms. A tolerance
allows small rasterizer rounding differences, but never a changed solid face.
"""
import argparse
from collections import Counter
import struct
import zlib


def read_png(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', f'{path}: not a PNG'
    pos, idat, w, h, chan = 8, b'', 0, 0, 0
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos+4])[0]
        typ = d[pos+4:pos+8]
        body = d[pos+8:pos+8+ln]
        if typ == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', body[:10])
            assert depth == 8 and body[12] == 0, f'{path}: requires non-interlaced 8-bit PNG'
            chan = {2: 3, 6: 4}[ctype]
        elif typ == b'IDAT':
            idat += body
        elif typ == b'IEND':
            break
        pos += 12 + ln
    raw = zlib.decompress(idat)
    stride = w * chan
    out = bytearray(w * h * 3)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        assert 0 <= f <= 4, f"invalid PNG filter {f}"
        line = bytearray(raw[p:p+stride]); p += stride
        for i in range(stride):                       # undo PNG filtering
            a = line[i-chan] if i >= chan else 0
            b = prev[i]
            c = prev[i-chan] if i >= chan else 0
            if f == 1:   line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a+b)//2) & 255
            elif f == 4:
                pa, pb, pc = abs(b-c), abs(a-c), abs(a+b-2*c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        for x in range(w):
            out[(y*w+x)*3:(y*w+x)*3+3] = line[x*chan:x*chan+3]
        prev = line
    return w, h, out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("actual")
    parser.add_argument("--tolerance", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.tolerance <= 255:
        parser.error("tolerance must be in [0,255]")
    w, h, a = read_png(args.reference)
    wb, hb, b = read_png(args.actual)
    if (w, h) != (wb, hb):
        print(f"FAIL: dimensions {w}x{h} != {wb}x{hb}")
        return 1
    differences = Counter()
    bad = []
    both = union = 0
    for i in range(w*h):
        ca, cb = a[3*i:3*i+3], b[3*i:3*i+3]
        delta = max(abs(x-y) for x, y in zip(ca, cb))
        differences[delta] += 1
        if delta > args.tolerance:
            bad.append((i % w, i // w))
        both += bool(any(ca) and any(cb))
        union += bool(any(ca) or any(cb))
    print(f"{w}x{h}: exact={differences[0]}/{w*h} ({100*differences[0]/(w*h):.6f}%)")
    print(f"max channel delta histogram: {dict(sorted(differences.items()))}")
    print(f"coverage IoU={both}/{union} ({100*both/max(union,1):.6f}%)")
    print(f"pixels exceeding tolerance {args.tolerance}: {len(bad)}")
    if bad:
        xs, ys = zip(*bad)
        print(f"difference bbox (inclusive): {min(xs)},{min(ys)}–{max(xs)},{max(ys)}")
    print("FAIL" if bad else "PASS")
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
