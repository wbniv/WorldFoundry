#!/usr/bin/env python3
"""Bake the engine's shared UI glyph atlas, ui-font.wfga (WFGA v1).

    scripts/in-linux-container.sh python3 scripts/bake-ui-font.py [--out PATH] [--fonts DIR] [--json PATH]

Rasterizes Atkinson Hyperlegible Next Regular and SemiBold (wfsource/fonts/atkinson-hyperlegible-next/)
with Pillow + raqm into the WFGA v1 layout that wfsource/source/game/bitmap_text.cc Catalog::Load
validates: a 64-byte header, the variant table, 36-byte glyph records sorted by (variant, code point),
kerning pairs sorted by (variant, left, right), zero text and zero label records, then the 8-bit
coverage atlas. The runtime never sees a TTF. Plan: docs/plans/2026-10-17-settings-editor-font.md.

  * Coverage: printable ASCII, U+00A0-00FF and – — ‘ ’ “ ” • … −, less any code point the fonts lack.
  * Variants (F3, the 1920x1080 logical canvas): small Regular 28, body Regular 36, body-bold
    SemiBold 36, title SemiBold 46, menu Regular 56, menu-bold SemiBold 56, display SemiBold 80.
  * Atlas: 1024 wide, shelf-packed with two clear texels between glyphs, height rounded up to a
    power of two; texel (0,0) is a solid reserved texel, as finding-your-way's glyph_atlas.py has.
  * Deterministic: the same fonts and the same Pillow/FreeType/raqm give the same bytes.

The approach (cmap reader, per-glyph 'ls'-anchored rasterization, kerning from pair lengths) is
copied from ../finding-your-way/game/parmenides-slice/glyph_atlas.py; nothing is imported from it.
Default --out is wfsource/source/game/ui-font.wfga, the file cdpack packs into every cd.iff.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / 'wfsource' / 'fonts' / 'atkinson-hyperlegible-next'
OUT = ROOT / 'wfsource' / 'source' / 'game' / 'ui-font.wfga'
FILES = ('AtkinsonHyperlegibleNext-Regular.ttf', 'AtkinsonHyperlegibleNext-SemiBold.ttf')
SHA256 = {FILES[0]: '88ed5c31a71584c7772963b02d04bef1eb7e3d2e9c8b9cb204339b1f82cf432c',
          FILES[1]: '8e2fff779f35ac25239656bb0f3b2bd35959a2009e3dd21a12141c3b9030362b'}
# (name, face 0=Regular 1=SemiBold, pixels); the index is the variant id the engine uses (wfui::Variant).
VARIANTS = (('small', 0, 28), ('body', 0, 36), ('body-bold', 1, 36), ('title', 1, 46),
            ('menu', 0, 56), ('menu-bold', 1, 56), ('display', 1, 80))
WANT = (list(range(0x20, 0x7F)) + list(range(0xA0, 0x100))
        + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x2212])
WIDTH = 1024
GAP = 2
# Kerning only, no ligatures or contextual alternates: the runtime draws one glyph per code point.
FEATURES = ['kern', '-liga', '-clig', '-dlig', '-calt']


def cmap(path):
    """The font's Unicode coverage (format 4 and 12 subtables), without fontTools."""
    data = path.read_bytes()
    u16 = lambda off: struct.unpack_from('>H', data, off)[0]
    u32 = lambda off: struct.unpack_from('>I', data, off)[0]
    tables = {data[off:off + 4]: u32(off + 8) for off in range(12, 12 + 16 * u16(4), 16)}
    base = tables[b'cmap']
    result = set()
    for off in range(base + 4, base + 4 + 8 * u16(base + 2), 8):
        if u16(off) not in (0, 3):
            continue
        sub = base + u32(off + 4)
        fmt = u16(sub)
        if fmt == 12:
            for group in range(sub + 16, sub + 16 + 12 * u32(sub + 12), 12):
                first, last, glyph = struct.unpack_from('>III', data, group)
                result.update(range(first + (glyph == 0), last + 1))
        elif fmt == 4:
            count = u16(sub + 6) // 2
            ends = sub + 14
            starts = ends + 2 * count + 2
            deltas = starts + 2 * count
            ranges = deltas + 2 * count
            for i in range(count):
                for cp in range(u16(starts + 2 * i), u16(ends + 2 * i) + 1):
                    distance = u16(ranges + 2 * i)
                    glyph = u16(ranges + 2 * i + distance + 2 * (cp - u16(starts + 2 * i))) if distance else cp
                    if glyph and (glyph + u16(deltas + 2 * i)) % 65536:
                        result.add(cp)
    return result


def coverage(fonts):
    """The code points both faces map, in order."""
    have = cmap(fonts / FILES[0]) & cmap(fonts / FILES[1])
    return [cp for cp in WANT if cp in have]


def bake(fonts):
    from PIL import Image, ImageDraw, ImageFont
    for name in FILES:
        digest = hashlib.sha256((fonts / name).read_bytes()).hexdigest()
        if digest != SHA256[name]:
            raise SystemExit(f'bake-ui-font: {name} is not the pinned file (sha256 {digest})')
    cps = coverage(fonts)
    if ord('?') not in cps:
        raise SystemExit('bake-ui-font: the fonts lack "?", the unmapped-code-point glyph')
    canvas = Image.new('L', (WIDTH, 4096), 0)
    canvas.putpixel((0, 0), 255)          # reserved solid texel
    variants, glyphs, kerns = [], [], []
    x, y, shelf = 1 + GAP, 1, 0
    for index, (_, face, px) in enumerate(VARIANTS):
        font = ImageFont.truetype(str(fonts / FILES[face]), px, layout_engine=ImageFont.Layout.RAQM)
        ascent, descent = font.getmetrics()
        variants.append((index, face, px, ascent, descent, ascent + descent))
        length = lambda s: font.getlength(s, features=FEATURES)
        exact = {cp: length(chr(cp)) for cp in cps}
        advance = {cp: round(exact[cp] * 64) for cp in cps}
        for cp in cps:
            left, top, right, bottom = font.getbbox(chr(cp), anchor='ls', features=FEATURES)
            w, h = right - left, bottom - top
            if x + w + GAP > WIDTH:
                x, y, shelf = 1, y + shelf + GAP, 0
            if y + h + 1 > canvas.height:
                raise SystemExit('bake-ui-font: the glyphs do not fit a 1024x4096 atlas')
            if w and h:
                tile = Image.new('L', (w, h), 0)
                ImageDraw.Draw(tile).text((-left, -top), chr(cp), font=font, anchor='ls', fill=255, features=FEATURES)
                canvas.paste(tile, (x, y))
                glyphs.append((index, cp, x, y, w, h, left, top, advance[cp]))
                x += w + GAP
                shelf = max(shelf, h)
            else:
                glyphs.append((index, cp, 0, 0, 0, 0, 0, 0, advance[cp]))
        for a in cps:
            for b in cps:
                value = round((length(chr(a) + chr(b)) - exact[a] - exact[b]) * 64)
                if value:
                    kerns.append((index, a, b, value))
    used = y + shelf + 1
    height = 1 << (used - 1).bit_length()
    canvas = canvas.crop((0, 0, WIDTH, height))
    glyphs.sort(key=lambda g: (g[0], g[1]))
    kerns.sort(key=lambda k: (k[0], k[1], k[2]))
    return cps, variants, glyphs, kerns, canvas.tobytes(), height, used


def write(out, variants, glyphs, kerns, pixels, height):
    header = b'WFGA' + struct.pack('<15i', 1, WIDTH, height, len(variants), len(glyphs), len(kerns), 0, 0,
                                   0, 0, 0, 0, 0, 0, 0)
    data = bytearray(header)
    for fmt, records in (('<6i', variants), ('<9i', glyphs), ('<4i', kerns)):
        for record in records:
            data.extend(struct.pack(fmt, *record))
    data.extend(pixels)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(data))
    return len(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', type=Path, default=OUT, help=f'the bundle to write (default {OUT.relative_to(ROOT)})')
    ap.add_argument('--fonts', type=Path, default=FONTS, help='the directory holding the two pinned TTFs')
    ap.add_argument('--json', type=Path, help='also write a summary (code points, variants, sizes)')
    args = ap.parse_args()
    cps, variants, glyphs, kerns, pixels, height, used = bake(args.fonts)
    size = write(args.out, variants, glyphs, kerns, pixels, height)
    summary = {'codepoints': len(cps), 'missing': [f'U+{c:04X}' for c in WANT if c not in cps],
               'variants': [dict(zip(('name', 'face', 'pixels', 'ascent', 'descent', 'lineStep'), (n,) + v[1:]))
                            for (n, _, _), v in zip(VARIANTS, variants)],
               'glyphs': len(glyphs), 'kerning': len(kerns), 'atlas': [WIDTH, height], 'rows_used': used,
               'bytes': size, 'sha256': hashlib.sha256(args.out.read_bytes()).hexdigest()}
    if args.json:
        args.json.write_text(json.dumps(summary, indent=1) + '\n')
    print(f"{args.out}: {summary['codepoints']} code points x {len(variants)} variants = {len(glyphs)} glyphs, "
          f"{len(kerns)} kerning pairs, atlas {WIDTH}x{height} ({used} rows used), {size} bytes, sha256 {summary['sha256']}")


if __name__ == '__main__':
    if {'-h', '--help'} & set(sys.argv[1:]):
        print(__doc__.strip())
        sys.exit(0)
    main()
