#!/usr/bin/env python3
"""make_pane_texture.py — deterministic textures for the aquarium Phase 0 translucency spike.

Writes, next to this script:

  pane.tga     16×16, **16-bit BGR555** uncompressed TGA, every texel = bit 15 | light cyan.
               textile-rs copies 16-bit TGAs verbatim (bitmap.rs `try_load_tga_bgr555`), so
               bit 15 survives to the engine, where gfx/pixelmap.cc turns a bit-15 texel into
               alpha 128 and gfx/material.cc flags the material HALF_BACK_HALF_PRIMITIVE.
  checker.tga  64×64, 24-bit RGB, 8×8 cells of CHECK_A / CHECK_B (the backdrop).

Why 16-bit written by hand: a 32-bit RGBA TGA is a trap — textile's `rgba_555` maps an opaque
texel to 0x0000, i.e. a cut-out (docs/level-design-troubleshooting.md). Every channel value here
is a multiple of 8 so the 8→5→8-bit round trip is exact and the pixel maths in the plan is clean.

Plan: docs/plans/2026-09-30-aquarium-level.md § Phase 0.
Usage: python3 make_pane_texture.py [--check]    (--check verifies the files instead of writing)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PANE_TGA = os.path.join(HERE, 'pane.tga')
CHECKER_TGA = os.path.join(HERE, 'checker.tga')

PANE_RGB = (160, 224, 240)        # light cyan, 8-bit; multiples of 8
CHECK_A = (224, 64, 48)           # red-orange
CHECK_B = (200, 200, 200)         # light grey
PANE_SIZE = 16
CHECK_SIZE = 64
CHECK_CELL = 8
TRANSLUCENT_BIT = 0x8000


def bgr555(rgb, translucent):
    r, g, b = (c >> 3 for c in rgb)
    return (TRANSLUCENT_BIT if translucent else 0) | (r << 10) | (g << 5) | b


PANE_TEXEL = bgr555(PANE_RGB, True)


def tga_header(w, h, bpp):
    # id_len, cmap_type, img_type=2 (uncompressed truecolour), cmap spec (5 bytes),
    # x/y origin, w, h, bpp, descriptor (0x20 = top-left origin; alpha bits = 1 for 16-bit).
    desc = 0x20 | (1 if bpp == 16 else 0)
    return struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, w, h, bpp, desc)


def pane_bytes():
    return tga_header(PANE_SIZE, PANE_SIZE, 16) + struct.pack('<H', PANE_TEXEL) * (PANE_SIZE * PANE_SIZE)


def checker_bytes():
    out = bytearray(tga_header(CHECK_SIZE, CHECK_SIZE, 24))
    for y in range(CHECK_SIZE):
        for x in range(CHECK_SIZE):
            r, g, b = CHECK_A if ((x // CHECK_CELL) + (y // CHECK_CELL)) % 2 == 0 else CHECK_B
            out += bytes((b, g, r))                      # TGA stores BGR
    return bytes(out)


def check():
    data = open(PANE_TGA, 'rb').read()
    assert data[2] == 2 and data[16] == 16, f'{PANE_TGA}: not an uncompressed 16-bit TGA'
    texels = struct.unpack(f'<{PANE_SIZE * PANE_SIZE}H', data[18:18 + 2 * PANE_SIZE * PANE_SIZE])
    assert all(t & TRANSLUCENT_BIT for t in texels), 'a pane texel lacks bit 15'
    assert data == pane_bytes() and open(CHECKER_TGA, 'rb').read() == checker_bytes(), 'textures drifted'
    print(f'ok: pane texel 0x{PANE_TEXEL:04X} (bit 15 set), 16-bit; checker 24-bit')


if __name__ == '__main__':
    if '--check' in sys.argv[1:]:
        check()
    else:
        with open(PANE_TGA, 'wb') as f:
            f.write(pane_bytes())
        with open(CHECKER_TGA, 'wb') as f:
            f.write(checker_bytes())
        print(f'wrote {PANE_TGA} (texel 0x{PANE_TEXEL:04X}) and {CHECKER_TGA}')
