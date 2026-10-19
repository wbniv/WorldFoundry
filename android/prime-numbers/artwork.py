#!/usr/bin/env python3
"""Generate the numbered-grid launcher icon and TV banner, without external assets."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
BOLD = FONT.with_name('DejaVuSans-Bold.ttf')
BG, CARD, PRIME, INK, MUTED = '#101e25', '#263e48', '#a6e3c4', '#f2f4e8', '#a5bcc5'
SCALE = 4


def font(size, bold=False):
    return ImageFont.truetype(str(BOLD if bold else FONT), round(size * SCALE))


def box(draw, bounds, radius, fill):
    draw.rounded_rectangle(tuple(round(v * SCALE) for v in bounds), round(radius * SCALE), fill=fill)


def text(draw, xy, content, size, fill=INK, bold=False, anchor=None):
    draw.text(tuple(round(v * SCALE) for v in xy), content, font=font(size, bold), fill=fill, anchor=anchor)


def grid(draw, x, y, cell, gap):
    for n in range(1, 10):
        left = x + (n - 1) % 3 * (cell + gap)
        top = y + (n - 1) // 3 * (cell + gap)
        prime = n in (2, 3, 5, 7)
        box(draw, (left, top, left + cell, top + cell), cell * .15, PRIME if prime else CARD)
        text(draw, (left + cell / 2, top + cell / 2 - cell * .025), str(n), cell * .56,
             BG if prime else INK, True, 'mm')


def main():
    out = ROOT / 'res/drawable-nodpi'
    out.mkdir(parents=True, exist_ok=True)
    icon = Image.new('RGB', (512 * SCALE, 512 * SCALE), BG)
    grid(ImageDraw.Draw(icon), 66, 66, 116, 16)
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(out / 'icon.png')
    banner = Image.new('RGB', (320 * SCALE, 180 * SCALE), BG)
    draw = ImageDraw.Draw(banner)
    grid(draw, 18, 36, 32, 5)
    text(draw, (140, 33), 'Prime', 27, bold=True)
    text(draw, (140, 65), 'Numbers', 27, bold=True)
    text(draw, (142, 107), '1–100', 23, PRIME)
    text(draw, (142, 143), 'STUDY & RECALL', 9, MUTED, True)
    banner.resize((320, 180), Image.Resampling.LANCZOS).save(out / 'banner.png')
    print('Artwork:', out)


if __name__ == '__main__':
    main()
