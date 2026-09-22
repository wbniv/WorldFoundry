#!/usr/bin/env python3
"""Render a decoded Marble Madness course JSON in the arcade's own 2:1 isometric
projection (screen_x = Y - X, screen_y = (X + Y)/2 - h) so it can be compared
pixel-for-pixel against MAME captures.  Cells are drawn back-to-front with
flat shading from the triangle normal; cliff faces (corner-height jumps between
neighbours, or edges onto void) are drawn as dark side walls.

Usage: mm_render_iso.py course.json out.png [--scale 2] [--ref stitched.png --scroll-base 0xC0F0]
"""
import argparse
import json
import math
from PIL import Image, ImageDraw

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('course'); ap.add_argument('out')
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--ref', help='stitched MAME capture to place side by side')
    a = ap.parse_args()
    d = json.load(open(a.course))
    cells = {(c['i'], c['j']): c['h'] for c in d['cells']}
    U = 8
    def proj(X, Y, h):
        return (Y - X + 0x88) * a.scale, ((X + Y) / 2 - h + 0x54 - 0xF0 + 16) * a.scale   # +0x54 as in the sprite code; scroll base 0xC0F0
    xs = []; ys = []
    for (i, j), h in cells.items():
        for k, (dx, dy) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
            x, y = proj((i + dx) * U, (j + dy) * U, h[k]); xs.append(x); ys.append(y)
    W = int(max(xs) - min(xs)) + 20; H = int(max(ys) - min(ys)) + 60
    ox = -min(xs) + 10; oy = -min(ys) + 10
    img = Image.new('RGB', (W, H), (0, 0, 0)); dr = ImageDraw.Draw(img)
    def P(X, Y, h):
        x, y = proj(X, Y, h); return (x + ox, y + oy)
    light = (-0.4, -0.5, 0.77)
    for (i, j) in sorted(cells, key=lambda c: c[0] + c[1]):
        h = cells[(i, j)]
        corners = [((i + dx) * U, (j + dy) * U, h[k]) for k, (dx, dy) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1)))]
        # walls to lower neighbours / void first (behind the floor)
        for (k0, k1, ni, nj, nk0, nk1) in ((1, 2, i + 1, j, 0, 3), (2, 3, i, j + 1, 1, 0)):   # +X edge, +Y edge (front-facing)
            nb = cells.get((ni, nj))
            top0, top1 = corners[k0], corners[k1]
            if nb is None:
                bot = -60
                b0 = (top0[0], top0[1], bot); b1 = (top1[0], top1[1], bot)
                col = (60, 30, 10)
            else:
                b0 = (top0[0], top0[1], nb[nk0]); b1 = (top1[0], top1[1], nb[nk1])
                if b0[2] >= top0[2] - 0.5 and b1[2] >= top1[2] - 0.5:
                    continue
                col = (150, 70, 20)
            dr.polygon([P(*top0), P(*top1), P(*b1), P(*b0)], fill=col)
        for tri in (((0, 1, 2)), ((0, 2, 3))):
            p = [corners[t] for t in tri]
            ux, uy, uz = p[1][0] - p[0][0], p[1][1] - p[0][1], (p[1][2] - p[0][2]) * 0.8165
            vx, vy, vz = p[2][0] - p[0][0], p[2][1] - p[0][1], (p[2][2] - p[0][2]) * 0.8165
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            lam = max(0.15, (nx * light[0] + ny * light[1] + nz * light[2]) / n)
            g = int(60 + 190 * lam)
            chk = 20 if (i + j) % 2 else 0
            dr.polygon([P(*q) for q in p], fill=(g - chk, g - chk, g - chk))
    if a.ref:
        ref = Image.open(a.ref).convert('RGB')
        ref = ref.resize((int(ref.width * a.scale), int(ref.height * a.scale)), Image.NEAREST)
        canvas = Image.new('RGB', (ref.width + img.width + 10, max(ref.height, img.height)), (30, 30, 30))
        canvas.paste(ref, (0, 0)); canvas.paste(img, (ref.width + 10, 0)); img = canvas
    img.save(a.out); print(img.size)

if __name__ == '__main__':
    main()
