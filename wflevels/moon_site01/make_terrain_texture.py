#!/usr/bin/env python3
"""
make_terrain_texture.py — bake a terrain texture from the source data.

Two modes, gated by --source:

  --source dem  (default)  — synthesise a hillshade from the PGDA DEM. Geometry
                             and shading agree exactly. Use when no NAC is
                             handy (Phase 3a).

  --source nac             — composite the LROC NAC orthorectified frame
                             (NAC_DTM_SHACKRDGE02_M139797542_120CM.IMG, 1.2 m/px,
                             native south polar stereographic) over a DEM-
                             hillshade fallback for shadowed/nodata regions.
                             Real lunar imagery on the lit half; hillshade on
                             the shadowed half (Phase 3b).

Run:
  python3 make_terrain_texture.py                       # DEM hillshade
  python3 make_terrain_texture.py --source nac          # NAC + hillshade fallback
  python3 make_terrain_texture.py --source nac --size 512
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
NAC_IMG    = os.path.join(SCRIPT_DIR, 'data', 'nac',
                          'NAC_DTM_SHACKRDGE02_M139797542_120CM.IMG')
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


def _read_dem_window_metres(meta):
    """Return (z float32, lunar_X0, lunar_Y0, native_cell_m) for the heightfield crop."""
    side_m = float(meta['side_m'])
    cc, cr = meta['centre_pixel']
    native = 5.0
    half_px = int(round(side_m / native / 2))
    c0, c1 = cc - half_px, cc + half_px
    r0, r1 = cr - half_px, cr + half_px

    with rasterio.open(SRC_TIF) as src:
        window = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
        z = src.read(1, window=window).astype(np.float32)
        # GeoTIFF transform: world_x = a*col + b*row + c, world_y = d*col + e*row + f
        # For a north-up image we have: pixel (c0, r0) → world (lunar_X0, lunar_Y0_top)
        t = src.transform
        lunar_X0 = t.c + t.a * c0                 # west edge of crop
        lunar_Y_top = t.f + t.e * r0              # north edge (top, larger Y)
    z = np.where(np.isfinite(z), z, np.nanmedian(z))
    return z, lunar_X0, lunar_Y_top, native


def bake_dem_hillshade(meta, size, sun_az_deg, sun_alt_deg):
    """Synthetic hillshade for fallback in shadowed / out-of-NAC regions.

    Output is **neutral grayscale** matching the LROC NAC's panchromatic
    palette — no warm tint, no elevation hue shift. Earlier versions had a
    `val * 0.98 / val * 0.94` "regolith warm bias" plus a `0.12*(nz-0.5)`
    elevation tint that read as alien pink/peach next to the real NAC half;
    the moon is famously graphite-grey (Apollo crew reports). Dropped.
    """
    z, _, _, native = _read_dem_window_metres(meta)
    shade = hillshade(z, native, az_deg=sun_az_deg, alt_deg=sun_alt_deg)
    val = np.clip(shade, 0.0, 1.0)
    rgb = np.stack([val, val, val], axis=-1)
    img = Image.fromarray((rgb * 255).astype(np.uint8))
    return img.resize((size, size), Image.Resampling.LANCZOS)


def bake_nac_composite(meta, size, sun_az_deg, sun_alt_deg):
    """Composite NAC orthoimage over a DEM hillshade fallback.

    Both products are in the same south polar stereographic frame (MOON_ME),
    so cropping by world coords directly is exact — no gdalwarp needed.
    """
    side_m = float(meta['side_m'])
    cc, cr = meta['centre_pixel']
    native = 5.0
    # Same crop window as the DEM, in polar-stereo X/Y metres.
    half_px = int(round(side_m / native / 2))
    c0 = cc - half_px
    r0 = cr - half_px
    with rasterio.open(SRC_TIF) as src:
        t = src.transform
        play_x0 = t.c + t.a * c0
        play_y_top = t.f + t.e * r0
        play_x1 = play_x0 + side_m
        play_y_bottom = play_y_top - side_m
    print(f"crop window (polar stereo metres): "
          f"X[{play_x0:.0f}, {play_x1:.0f}] Y[{play_y_bottom:.0f}, {play_y_top:.0f}]")

    # Read the NAC at the target output resolution directly — rasterio resamples
    # via the dataset's `out_shape` parameter (default = nearest; we want
    # bilinear for a smoother texture).
    from rasterio.enums import Resampling
    with rasterio.open(NAC_IMG) as nac:
        window = rasterio.windows.from_bounds(
            play_x0, play_y_bottom, play_x1, play_y_top, transform=nac.transform)
        nac_arr = nac.read(1, window=window,
                           out_shape=(size, size),
                           resampling=Resampling.bilinear).astype(np.float32)
        nac_nodata = nac.nodata or 0

    # nodata=0 in the NAC = shadowed / outside-strip → use hillshade there.
    nac_valid = nac_arr > nac_nodata
    valid_frac = float(np.mean(nac_valid))
    print(f"NAC coverage of play area: {100*valid_frac:.1f}% lit / valid")

    # Stretch the NAC's valid pixels into [0, 1] with a percentile clip so
    # specular hot-spots don't blow the texture out.
    if np.any(nac_valid):
        lo, hi = np.percentile(nac_arr[nac_valid], (2, 99))
        nac_norm = np.clip((nac_arr - lo) / max(hi - lo, 1.0), 0.0, 1.0)
    else:
        nac_norm = np.zeros_like(nac_arr)

    # Build the hillshade fallback at the same output size.
    hill = np.asarray(bake_dem_hillshade(meta, size, sun_az_deg, sun_alt_deg)) / 255.0

    # Match hillshade brightness to NAC's percentile-stretched range so the
    # seam between "real NAC" and "synthetic hillshade fallback" disappears.
    # Both are already normalised into [0, 1]; the issue is that the NAC's
    # mean tone (after percentile stretch) ≠ the hillshade's. Compute both
    # means and shift the hillshade to land on the NAC's mean while keeping
    # its contrast.
    hill_gray = hill[..., 0]
    if np.any(nac_valid):
        nac_mean = float(nac_norm[nac_valid].mean())
        nac_std  = float(nac_norm[nac_valid].std())
        h_mean = float(hill_gray.mean())
        h_std  = float(hill_gray.std()) or 1e-6
        # z-score the hillshade then re-fit to NAC's mean and std
        hill_gray = np.clip((hill_gray - h_mean) * (nac_std / h_std) + nac_mean, 0, 1)
    hill_rgb = np.stack([hill_gray, hill_gray, hill_gray], axis=-1)

    # Composite: NAC (neutral) where valid, matched hillshade elsewhere.
    nac_rgb = np.stack([nac_norm, nac_norm, nac_norm], axis=-1)
    mask3 = np.repeat(nac_valid[..., None], 3, axis=-1)
    out = np.where(mask3, nac_rgb, hill_rgb)
    return Image.fromarray((out * 255).astype(np.uint8))


def overlay_grid(img, side_m, minor_m=10.0, major_m=100.0,
                 minor_rgba=(255, 255, 255, 60),
                 major_rgba=(255, 255, 0, 160)):
    """Draw a metric grid on top of the texture so distance is readable in-game.

    side_m is the world span the texture covers (1 km for the current level).
    Minor lines every minor_m metres in white; major lines every major_m
    metres in yellow. Drawn pixel-aligned with alpha blending.
    """
    arr = np.asarray(img).astype(np.float32) / 255.0
    h, w = arr.shape[:2]
    px_per_m = w / side_m
    out = arr.copy()

    def blend_line(mask, rgba):
        rgb = np.array(rgba[:3], dtype=np.float32) / 255.0
        a   = rgba[3] / 255.0
        for c in range(3):
            out[..., c] = np.where(mask, out[..., c] * (1 - a) + rgb[c] * a, out[..., c])

    # Minor gridlines
    xs_minor = np.round(np.arange(0, side_m + 1e-6, minor_m) * px_per_m).astype(int)
    ys_minor = xs_minor.copy()
    col_mask = np.zeros((h, w), dtype=bool)
    col_mask[:, xs_minor[xs_minor < w]] = True
    col_mask[ys_minor[ys_minor < h], :] = True
    blend_line(col_mask, minor_rgba)

    # Major gridlines (over the minor lines)
    xs_major = np.round(np.arange(0, side_m + 1e-6, major_m) * px_per_m).astype(int)
    maj_mask = np.zeros((h, w), dtype=bool)
    maj_mask[:, xs_major[xs_major < w]] = True
    maj_mask[xs_major[xs_major < h], :] = True
    blend_line(maj_mask, major_rgba)

    return Image.fromarray((out * 255).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['dem', 'nac'], default='dem',
                    help='texture source (default dem hillshade)')
    ap.add_argument('--size', type=int, default=256,
                    help='output texture edge in pixels (default 256 — fits WF texture page budget)')
    ap.add_argument('--sun-azimuth', type=float, default=20.0,
                    help='solar azimuth degrees (Site 01 lunar south pole: ~20°)')
    ap.add_argument('--sun-alt', type=float, default=2.0,
                    help='solar altitude degrees (south pole sun stays low: ~2°)')
    ap.add_argument('--grid', action='store_true',
                    help='overlay metric gridlines (10 m minor white, 100 m major yellow)')
    ap.add_argument('--grid-minor-m', type=float, default=10.0,
                    help='minor gridline spacing in metres (default 10)')
    ap.add_argument('--grid-major-m', type=float, default=100.0,
                    help='major gridline spacing in metres (default 100)')
    args = ap.parse_args()

    import json
    with open(META_JSON) as f:
        meta = json.load(f)

    if args.source == 'dem':
        img = bake_dem_hillshade(meta, args.size, args.sun_azimuth, args.sun_alt)
        kind = f"DEM hillshade (sun az={args.sun_azimuth}° alt={args.sun_alt}°)"
    else:
        if not os.path.isfile(NAC_IMG):
            sys.exit(f"NAC image missing: {NAC_IMG} — fetch from PDS first.")
        img = bake_nac_composite(meta, args.size, args.sun_azimuth, args.sun_alt)
        kind = "NAC orthoimage + hillshade fallback"

    if args.grid:
        side_m = float(meta['side_m'])
        img = overlay_grid(img, side_m,
                           minor_m=args.grid_minor_m,
                           major_m=args.grid_major_m)
        kind += f" + grid {args.grid_minor_m:.0f}/{args.grid_major_m:.0f} m"

    img.save(OUT_TGA)
    print(f"wrote {OUT_TGA} ({args.size}x{args.size}, {kind})")


if __name__ == '__main__':
    main()
