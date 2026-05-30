#!/usr/bin/env python3
"""
make_terrain_texture.py — bake a terrain texture from the source DEM.

Phase 3 first pass: synthesise a hillshaded + elevation-tinted RGB texture
from the same PGDA GeoTIFF the heightfield came from. Texture pixels line up
1:1 with the heightfield's geographic extent, so geometry and shading agree.

A future iteration will swap this for an LROC NAC + WAC composite (Phase 3b)
— the script writes to terrain_texture.tga and blender_create_moon.py
consumes it by name, so the upgrade is a one-line dem-to-NAC switch.

Run:
  python3 make_terrain_texture.py
  python3 make_terrain_texture.py --size 4096 --sun-azimuth 45 --sun-alt 5
"""

import argparse
import os
import sys

import numpy as np

try:
    import rasterio
except ImportError:
    sys.exit("error: rasterio not installed (pip install --user rasterio)")
from PIL import Image


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_TIF    = os.path.join(SCRIPT_DIR, 'data', 'Site01_final_adj_5mpp_surf.tif')
META_JSON  = os.path.join(SCRIPT_DIR, 'terrain_heights.json')
OUT_TGA    = os.path.join(SCRIPT_DIR, 'terrain_texture.tga')


def hillshade(z, cell_m, az_deg=315.0, alt_deg=45.0):
    """Standard GDAL-style hillshade. Returns float array in [0, 1]."""
    az_rad = np.deg2rad(az_deg); alt_rad = np.deg2rad(alt_deg)
    dy, dx = np.gradient(z, cell_m)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(dx, -dy)
    return np.clip(
        np.cos(alt_rad) * np.cos(slope) +
        np.sin(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect),
        0.0, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--size', type=int, default=2048,
                    help='output texture edge in pixels (default 2048)')
    ap.add_argument('--sun-azimuth', type=float, default=20.0,
                    help='solar azimuth degrees (Site 01 lunar south pole: ~20°)')
    ap.add_argument('--sun-alt', type=float, default=2.0,
                    help='solar altitude degrees (south pole sun stays low: ~2°)')
    args = ap.parse_args()

    # Match the heightfield's crop window from terrain_heights.json so the
    # texture aligns perfectly with mesh UVs.
    import json
    with open(META_JSON) as f:
        meta = json.load(f)
    side_m = float(meta['side_m'])
    cc, cr = meta['centre_pixel']
    native = 5.0
    half_px = int(round(side_m / native / 2))
    c0, c1 = cc - half_px, cc + half_px
    r0, r1 = cr - half_px, cr + half_px

    with rasterio.open(SRC_TIF) as src:
        window = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
        z = src.read(1, window=window).astype(np.float32)
    z = np.where(np.isfinite(z), z, np.nanmedian(z))

    shade = hillshade(z, native,
                      az_deg=args.sun_azimuth,
                      alt_deg=args.sun_alt)
    nz = (z - z.min()) / (z.max() - z.min() + 1e-9)

    # Composite: regolith grey × hillshade, with a faint elevation tint so
    # higher ridges read warmer / lighter (and crater shadows colder).
    base = np.full_like(shade, 0.55)              # mid-grey lunar regolith
    tint = 0.12 * (nz - 0.5)                      # ±0.06 around mid-grey
    val = np.clip((base + tint) * (0.20 + 0.80 * shade), 0.0, 1.0)

    rgb = np.stack([val, val * 0.98, val * 0.94], axis=-1)   # warm bias
    img = Image.fromarray((rgb * 255).astype(np.uint8))
    img = img.resize((args.size, args.size), Image.Resampling.LANCZOS)
    img.save(OUT_TGA)
    print(f"wrote {OUT_TGA} ({args.size}x{args.size}, "
          f"sun az={args.sun_azimuth}° alt={args.sun_alt}°)")


if __name__ == '__main__':
    main()
