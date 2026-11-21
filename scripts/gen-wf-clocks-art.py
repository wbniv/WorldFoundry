#!/usr/bin/env python3
"""Draw the WF Clocks artwork: a wide frame for the TV banner and a square tile for the launcher icon.

Usage: gen-wf-clocks-art.py [-h]

Writes android/screensaver/art-src/wf-clocks-frame.png (1280 x 720) and
android/screensaver/art-src/wf-clocks-icon.png (720 x 720). scripts/gen-screensaver-android-icons.py clocks
turns them into the launcher icons and the banner. The drawing is deterministic (no random numbers,
no font beyond the repository's Atkinson Hyperlegible Next SemiBold), so a rerun rewrites identical bytes.

The motif is a classic clock face with a gold bezel in front of two meshing brass gears, on a night-blue
ground: it stands for the whole package, not for one clock level. The clock reads 10:10:35.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "android/screensaver/art-src"
FONT = ROOT / "wfsource/fonts/atkinson-hyperlegible-next/AtkinsonHyperlegibleNext-SemiBold.ttf"  # tracked, so it is in the container
SS = 3  # supersampling factor, for smooth edges


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def background(w, h):
    top, bottom = (10, 22, 40), (22, 66, 88)
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        px.line((0, y, w, y), fill=lerp(top, bottom, y / (h - 1)))
    vignette = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vignette).ellipse((-w * .15, -h * .25, w * 1.15, h * 1.25), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(min(w, h) * .12))
    dark = Image.new("RGB", (w, h), (3, 8, 16))
    return Image.composite(img, dark, vignette)


def gear(layer, cx, cy, outer, inner, teeth, hole, body, edge, phase=0.0):
    d = ImageDraw.Draw(layer)
    pts = []
    for i in range(teeth * 4):
        a = phase + i * math.tau / (teeth * 4)
        r = outer if i % 4 in (1, 2) else inner
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=body, outline=edge)
    d.ellipse((cx - inner * .78, cy - inner * .78, cx + inner * .78, cy + inner * .78), outline=edge, width=max(2, round(outer * .03)))
    d.ellipse((cx - hole, cy - hole, cx + hole, cy + hole), fill=(14, 28, 44, 255), outline=edge)


def hand(d, cx, cy, angle, length, width, tail, fill, outline):
    ux, uy = math.sin(angle), -math.cos(angle)
    px, py = -uy, ux
    tip = (cx + ux * length, cy + uy * length)
    base_l = (cx + px * width, cy + py * width)
    base_r = (cx - px * width, cy - py * width)
    back = (cx - ux * tail, cy - uy * tail)
    d.polygon([tip, base_l, back, base_r], fill=fill, outline=outline)


def draw_clock(canvas: Image.Image, cx: float, cy: float, radius: float) -> None:
    w, h = canvas.size
    # soft shadow on the ground
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((cx - radius * 1.02, cy - radius * .92 + radius * .14, cx + radius * 1.02, cy + radius * 1.12 + radius * .14), fill=(0, 0, 0, 150))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(radius * .08)))

    d = ImageDraw.Draw(canvas)
    # bezel: dark outer edge, bright gold, mid gold, thin inner shadow
    rings = [(1.00, (92, 66, 20)), (0.975, (196, 150, 52)), (0.94, (240, 204, 100)), (0.90, (170, 124, 38)), (0.885, (60, 44, 16))]
    for scale, colour in rings:
        r = radius * scale
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour + (255,))
    # face: ivory with a gentle radial shade
    face_r = radius * .87
    steps = 40
    for i in range(steps):
        t = i / (steps - 1)
        r = face_r * (1 - t)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=lerp((226, 214, 184), (252, 247, 232), t) + (255,))
    # minute and hour ticks
    for m in range(60):
        a = math.tau * m / 60
        major = m % 5 == 0
        r0 = face_r * (.80 if major else .90)
        r1 = face_r * .96
        d.line((cx + r0 * math.sin(a), cy - r0 * math.cos(a), cx + r1 * math.sin(a), cy - r1 * math.cos(a)),
               fill=(34, 28, 24, 255), width=max(2, round(radius * (.030 if major else .011))))
    # numerals at the four quarters
    font = ImageFont.truetype(str(FONT), round(radius * .27))
    for label, a in (("12", 0), ("3", 90), ("6", 180), ("9", 270)):
        r = face_r * .60
        x, y = cx + r * math.sin(math.radians(a)), cy - r * math.cos(math.radians(a))
        x0, y0, x1, y1 = d.textbbox((0, 0), label, font=font)
        d.text((x - (x0 + x1) / 2, y - (y0 + y1) / 2), label, font=font, fill=(34, 28, 24, 255))
    # hands at 10:10:35
    sec = 35.0
    minute = 10 + sec / 60
    hour = 10 + minute / 60
    outline = (20, 16, 12, 255)
    hand(d, cx, cy, math.tau * hour / 12, face_r * .50, radius * .045, radius * .08, (30, 26, 24, 255), outline)
    hand(d, cx, cy, math.tau * minute / 60, face_r * .78, radius * .033, radius * .10, (30, 26, 24, 255), outline)
    a = math.tau * sec / 60
    ux, uy = math.sin(a), -math.cos(a)
    d.line((cx - ux * face_r * .22, cy - uy * face_r * .22, cx + ux * face_r * .86, cy + uy * face_r * .86), fill=(196, 40, 36, 255), width=max(2, round(radius * .014)))
    for r, colour in ((radius * .062, (92, 66, 20)), (radius * .046, (240, 204, 100)), (radius * .018, (196, 40, 36))):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour + (255,))
    # glass highlight: a pale crescent on the upper left
    glass = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glass)
    gd.ellipse((cx - face_r * .94, cy - face_r * .94, cx + face_r * .94, cy + face_r * .94), fill=(255, 255, 255, 46))
    gd.ellipse((cx - face_r * .78, cy - face_r * .70, cx + face_r * 1.06, cy + face_r * 1.06), fill=(0, 0, 0, 0))
    canvas.alpha_composite(glass.filter(ImageFilter.GaussianBlur(radius * .012)))


def scene(width: int, height: int, cx: float, cy: float, radius: float, gears_at) -> Image.Image:
    big = (width * SS, height * SS)
    canvas = background(*big).convert("RGBA")
    brass, brass_edge = (150, 108, 46, 255), (70, 48, 18, 255)
    layer = Image.new("RGBA", big, (0, 0, 0, 0))
    for gx, gy, outer, teeth, phase in gears_at:
        gear(layer, gx * SS, gy * SS, outer * SS, outer * SS * .86, teeth, outer * SS * .16, brass, brass_edge, phase)
    layer = Image.alpha_composite(Image.new("RGBA", big, (0, 0, 0, 0)), layer)
    canvas.alpha_composite(layer)
    draw_clock(canvas, cx * SS, cy * SS, radius * SS)
    return canvas.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")


ICON_SIZE, ICON_CLOCK_RADIUS = 720, 232   # Android keeps the inner two thirds: 240 of 360 px


def frame_image() -> Image.Image:
    """Wide frame for the TV banner: the clock a little right of centre so the name sits on the left."""
    return scene(1280, 720, 700, 340, 250,
                 [(330, 250, 130, 14, 0.0), (205, 470, 92, 10, math.pi / 10), (1010, 560, 120, 13, 0.1)])


def icon_image() -> Image.Image:
    """Square tile for the launcher icon. Android keeps the inner two thirds (the adaptive safe circle and
    the legacy crop), so the whole bezel (radius 232 of 360) must sit inside it; the pipeline adds the WF badge."""
    half = ICON_SIZE / 2
    return scene(ICON_SIZE, ICON_SIZE, half, half, ICON_CLOCK_RADIUS,
                 [(120, 150, 120, 12, 0.0), (610, 600, 130, 13, 0.2)])


def main() -> None:
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    frame_image().save(OUT / "wf-clocks-frame.png", optimize=True)
    icon_image().save(OUT / "wf-clocks-icon.png", optimize=True)
    print(f"Wrote {OUT / 'wf-clocks-frame.png'} and {OUT / 'wf-clocks-icon.png'}")


if __name__ == "__main__":
    main()
