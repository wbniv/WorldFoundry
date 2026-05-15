#!/usr/bin/env python3
"""Build a single side-by-side comparison PNG: MAME vs WF, all 16 rounds.

Layout: 4 columns × 16 rows.
  col 0: MAME state-0 (apex pristine)
  col 1: MAME state-1 (cube (1,1) flipped)
  col 2: WF   state-0 (apex pristine)
  col 3: WF   state-1 (cube (1,0) flipped)

Each cell is annotated with the sampled-pixel colour swatch + hex.
Output: docs/investigations/wf-screenshots/walker_composite.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[3]
MAME_DIR  = REPO_ROOT / "docs/investigations/mame-screenshots"
WF_DIR    = REPO_ROOT / "docs/investigations/wf-screenshots"
OUT_PATH  = REPO_ROOT / "docs/investigations/wf-screenshots/walker_composite.png"

# Sample coords (mirrors qbert_walker_diff.py).
MAME_APEX     = (120, 56)
MAME_CUBE11   = (137, 80)
WF_APEX_TOP   = (320, 240)
WF_CUBE10_TOP = (290, 285)

CELL_W = 220
CELL_H = 220
LABEL_H = 22
SWATCH = 14
ROW_LABEL_W = 50
HEADER_H = 28


def load_or_blank(path: Path) -> Image.Image:
    if path.exists():
        return Image.open(path).convert("RGB")
    img = Image.new("RGB", (640, 640), (40, 40, 40))
    d = ImageDraw.Draw(img)
    d.text((220, 300), "missing", fill=(200, 200, 200))
    return img


def sample(img: Image.Image, xy):
    if not (0 <= xy[0] < img.width and 0 <= xy[1] < img.height):
        return (0, 0, 0)
    p = img.getpixel(xy)
    return p[:3] if isinstance(p, tuple) else (p, p, p)


def hex_color(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def draw_cell(canvas: Image.Image, x: int, y: int, src: Image.Image,
              sample_xy, font: ImageFont.ImageFont):
    # Crosshair on the source so the sample point is visible.
    annotated = src.copy()
    d = ImageDraw.Draw(annotated)
    sx, sy = sample_xy
    d.line([(sx - 8, sy), (sx + 8, sy)], fill=(255, 0, 0), width=1)
    d.line([(sx, sy - 8), (sx, sy + 8)], fill=(255, 0, 0), width=1)
    annotated.thumbnail((CELL_W, CELL_W), Image.Resampling.LANCZOS)
    canvas.paste(annotated, (x, y))

    rgb = sample(src, sample_xy)
    label = hex_color(rgb)
    d2 = ImageDraw.Draw(canvas)
    sw_y = y + CELL_W + 3
    d2.rectangle([x, sw_y, x + SWATCH, sw_y + SWATCH], fill=rgb,
                 outline=(180, 180, 180))
    d2.text((x + SWATCH + 4, sw_y - 1), label, fill=(220, 220, 220), font=font)


def main():
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        font_h = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
        font_h = font

    rounds = [(L, R) for L in (1, 2, 3, 4) for R in (1, 2, 3, 4)]
    n_rows = len(rounds)

    total_w = ROW_LABEL_W + 4 * CELL_W + 30
    total_h = HEADER_H + n_rows * (CELL_W + LABEL_H + 6) + 10
    canvas = Image.new("RGB", (total_w, total_h), (12, 12, 14))
    d = ImageDraw.Draw(canvas)

    # Column headers.
    headers = ["MAME state-0", "MAME state-1", "WF state-0", "WF state-1"]
    for i, h in enumerate(headers):
        d.text((ROW_LABEL_W + i * CELL_W + 4, 6), h,
               fill=(230, 230, 230), font=font_h)

    for row_i, (L, R) in enumerate(rounds):
        cell_y = HEADER_H + row_i * (CELL_W + LABEL_H + 6)
        d.text((6, cell_y + CELL_W // 2 - 6), f"L{L}R{R}",
               fill=(220, 220, 100), font=font_h)

        cells = [
            (MAME_DIR / f"qbert_L{L}R{R}.png",        MAME_APEX),
            (MAME_DIR / f"qbert_hop_L{L}R{R}.png",    MAME_CUBE11),
            (WF_DIR   / f"wf_walker_L{L}R{R}_state0.png", WF_APEX_TOP),
            (WF_DIR   / f"wf_walker_L{L}R{R}_state1.png", WF_CUBE10_TOP),
        ]
        for col_i, (path, xy) in enumerate(cells):
            cell_x = ROW_LABEL_W + col_i * CELL_W
            src = load_or_blank(path)
            draw_cell(canvas, cell_x + 2, cell_y, src, xy, font)

    canvas.save(OUT_PATH)
    print(f"wrote {OUT_PATH} ({total_w}x{total_h}, {OUT_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
