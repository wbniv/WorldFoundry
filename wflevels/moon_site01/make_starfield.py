#!/usr/bin/env python3
"""make_starfield.py — emit data/starfield.tga, an equirectangular star map.

Procedurally seeded so the result is byte-stable across re-runs. ~3000 stars
of varying magnitude over a black background. Used by the moon skydome
(see docs/plans/2026-06-01-moon-sky-earth-sun-stars.md).
"""
import os
import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Lives alongside terrain_texture.tga — textile-rs picks textures up from
# the level dir, not data/.
OUT_TGA    = os.path.join(SCRIPT_DIR, 'starfield.tga')

# 512x256 — small enough to fit alongside the 1024² terrain texture in the
# Room0 textile page without forcing the layout to split.
W, H = 512, 256
N_BRIGHT = 50
N_MID    = 300
N_FAINT  = 500

rng = np.random.default_rng(seed=2026_06_01)
img = np.zeros((H, W, 3), dtype=np.uint8)

def put_star(x, y, brightness, halo_radius=0):
    """Paint one star + optional Gaussian-ish halo for the bright ones."""
    if 0 <= x < W and 0 <= y < H:
        b = int(brightness)
        img[y, x] = (b, b, b)
    if halo_radius > 0:
        for dy in range(-halo_radius, halo_radius + 1):
            for dx in range(-halo_radius, halo_radius + 1):
                d2 = dx*dx + dy*dy
                if 0 < d2 <= halo_radius*halo_radius:
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < W and 0 <= yy < H:
                        falloff = max(0, 1.0 - d2 / (halo_radius*halo_radius))
                        b = int(brightness * falloff * 0.35)
                        if b > img[yy, xx, 0]:
                            img[yy, xx] = (b, b, b)

# Faint: single-pixel dim stars (most of them).
for _ in range(N_FAINT):
    x = int(rng.integers(0, W))
    y = int(rng.integers(0, H))
    b = int(rng.integers(40, 100))
    put_star(x, y, b)

# Mid: single-pixel medium stars.
for _ in range(N_MID):
    x = int(rng.integers(0, W))
    y = int(rng.integers(0, H))
    b = int(rng.integers(100, 180))
    put_star(x, y, b)

# Bright: full-white plus small halo, sparse.
for _ in range(N_BRIGHT):
    x = int(rng.integers(0, W))
    y = int(rng.integers(0, H))
    b = int(rng.integers(200, 256))
    halo = int(rng.integers(1, 3))   # 1- or 2-pixel halo
    put_star(x, y, b, halo_radius=halo)

os.makedirs(os.path.dirname(OUT_TGA), exist_ok=True)
Image.fromarray(img).save(OUT_TGA)
print(f"wrote {OUT_TGA} ({W}x{H}, ~{N_BRIGHT+N_MID+N_FAINT} stars)")
