#!/usr/bin/env python3
"""
dem_to_grid.py — crop the PGDA Site 01 GeoTIFF into a play-area heightfield.

Runs under SYSTEM python3 with rasterio + numpy (not Blender's bundled Python,
which can't see pip --user installs). Output is a small numpy .npy that
blender_create_moon.py reads — same machine, sequential steps in
build_level_binary.sh.

Output schema: float32 array of shape (N, N), elevation in metres relative to
the centre pixel of the crop (so play-area centre = Z=0). Sister .json holds
provenance: source file, crop window, native pixel size.

Run:
  python3 dem_to_grid.py            # default 1km × 1km @ 10m sampling stride
  python3 dem_to_grid.py --side-m 2000 --stride 5    # 2km × 2km @ native 5m
"""

import argparse
import json
import os
import sys

import numpy as np

try:
    import rasterio
except ImportError:
    sys.exit("error: rasterio not installed. `pip install --user rasterio numpy`")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_TIF    = os.path.join(SCRIPT_DIR, 'data', 'Site01_final_adj_5mpp_surf.tif')
OUT_NPY    = os.path.join(SCRIPT_DIR, 'terrain_heights.npy')
OUT_META   = os.path.join(SCRIPT_DIR, 'terrain_heights.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--side-m', type=float, default=1000.0,
                    help='play-area side length in metres (default 1000)')
    ap.add_argument('--stride', type=int, default=2,
                    help='pixel-sampling stride (default 2 → 10m effective res; 1 = native 5m)')
    ap.add_argument('--centre-px', nargs=2, type=int, default=None,
                    help='crop centre in source-pixel (col, row); default = image centre')
    args = ap.parse_args()

    with rasterio.open(SRC_TIF) as src:
        native = src.res[0]                                  # 5.0 m/pix
        cols, rows = src.width, src.height
        cc, cr = args.centre_px or (cols // 2, rows // 2)
        half_px = int(round(args.side_m / native / 2))
        c0, c1 = cc - half_px, cc + half_px
        r0, r1 = cr - half_px, cr + half_px
        if c0 < 0 or r0 < 0 or c1 > cols or r1 > rows:
            sys.exit(f"crop window [{c0}:{c1}, {r0}:{r1}] exceeds image extent {cols}x{rows}")
        window = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
        z = src.read(1, window=window).astype(np.float32)

    # Subsample with stride so the mesh is manageable. Take a regular grid of
    # samples — antialiasing isn't worth it for terrain at this scale.
    z = z[::args.stride, ::args.stride]
    effective_res = native * args.stride
    n = z.shape[0]
    print(f"crop: {n}x{n} samples @ {effective_res} m/sample ({n * effective_res:.0f} m on a side)")

    if not np.all(np.isfinite(z)):
        nan_count = int(np.sum(~np.isfinite(z)))
        print(f"warning: {nan_count} NaN samples — filling with median")
        med = float(np.nanmedian(z))
        z = np.where(np.isfinite(z), z, med)

    centre_z = float(z[n // 2, n // 2])
    z -= centre_z       # play-area centre → Z=0
    print(f"elev range after centring: {z.min():+.1f} to {z.max():+.1f} m (centre subtracted: {centre_z:.1f} m)")

    np.save(OUT_NPY, z)
    meta = {
        'source':         os.path.relpath(SRC_TIF, SCRIPT_DIR),
        'side_m':         args.side_m,
        'samples':        n,
        'cell_size_m':    effective_res,
        'centre_pixel':   [cc, cr],
        'centre_z_m':     centre_z,
        'note':           'Z is metres relative to the centre pixel; centre vertex sits at Z=0',
    }
    with open(OUT_META, 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {OUT_NPY} ({os.path.getsize(OUT_NPY)} bytes) + {OUT_META}")


if __name__ == '__main__':
    main()
