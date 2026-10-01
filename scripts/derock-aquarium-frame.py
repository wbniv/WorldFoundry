#!/usr/bin/env python3
"""derock-aquarium-frame.py: leave only the fish and the anemone in the aquarium's camshot B capture (no rock, no sand, no brown stalk), with the fish lifted a little.

The aquarium icon is just the fish and the anemone (the user's words: "keep the same except remove the rock", then "just the fish and anemone"). The rock is a flat-shaded grey
low-poly shape under the anemone's base ring. It is masked by colour (neutral grey; the sand is tan, the water teal, the
base ring red-brown) inside a window around it, and each masked run is repainted with the pixels of the same row
shifted sideways, so the sand keeps its tile pattern and the water its bands. The sand floor is then painted over with the water behind it (the lowest water band, extended down), so the anemone and its base ring float on the water backdrop and only the fish and anemone remain.

This edits a capture, it does not re-render the level (the rock is part of the level, and rebuilding it was not needed for
a launcher icon); the result is committed beside its source so the icon is deterministic.

Usage: scripts/derock-aquarium-frame.py IN.png OUT.png [-h]
"""
import argparse
import sys

import numpy as np
from PIL import Image

WINDOW = (560, 850, 1380, 1080)          # x0, y0, x1, y1 of the 1920x1080 camshot B around the rock


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--keep-sand", action="store_true", help="remove the rock only")
    ap.add_argument("--keep-stalk", action="store_true", help="keep the brown stalk and base ring")
    ap.add_argument("--fish-up", type=int, default=0, help="lift the fish this many pixels (0 = leave it)")
    a = ap.parse_args()
    im = np.array(Image.open(a.src).convert("RGB")).astype(int)
    x0, y0, x1, y1 = WINDOW
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    grey = (abs(r - g) < 16) & (abs(g - b) < 16) & (r > 60) & (r < 200)
    mask = np.zeros(grey.shape, bool)
    mask[y0:y1, x0:x1] = grey[y0:y1, x0:x1]
    # grow by 3 px so the rock's anti-aliased edge goes too
    grown = mask.copy()
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            grown |= np.roll(np.roll(mask, dy, 0), dx, 1)
    grown[:y0] = False; grown[y1:] = False; grown[:, :x0] = False; grown[:, x1:] = False
    out = im.copy()
    if a.fish_up:
        # the fish: orange body/fins, white bands, dark outline and grey belly, inside a box around it (the tentacles are pink-magenta,
        # the water teal, so the colours do not clash). Lift it, repainting where it was from the same row beside it.
        fx0, fy0, fx1, fy1 = 750, 330, 1110, 545
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        orange = (r > 190) & (g > 80) & (g < 185) & (b < 110)
        white = (r > 225) & (g > 225) & (b > 225)
        dark = (r < 45) & (g < 45) & (b < 55)
        belly = (abs(r - g) < 14) & (abs(g - b) < 14) & (r > 110) & (r < 175)
        fm = np.zeros(r.shape, bool); fm[fy0:fy1, fx0:fx1] = (orange | white | dark | belly)[fy0:fy1, fx0:fx1]
        for _ in range(2):                                              # close pinholes and take the anti-aliased edge
            fm |= np.roll(fm, 1, 0) & np.roll(fm, -1, 0) | np.roll(fm, 1, 1) & np.roll(fm, -1, 1)
        fm2 = fm.copy()
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                fm2 |= np.roll(np.roll(fm, dy, 0), dx, 1)
        fm2[:fy0] = False; fm2[fy1:] = False; fm2[:, :fx0] = False; fm2[:, fx1:] = False
        fish = im.copy()
        for y in range(fy0, fy1):
            xs = np.flatnonzero(fm2[y])
            if xs.size == 0:
                continue
            s0, e0 = xs[0], xs[-1] + 1; n = e0 - s0
            if s0 - n >= 0 and not fm2[y, s0 - n:s0].any():
                out[y, s0:e0] = im[y, s0 - n:s0]
            elif e0 + n <= im.shape[1] and not fm2[y, e0:e0 + n].any():
                out[y, s0:e0] = im[y, e0:e0 + n]
            else:
                out[y, s0:e0] = im[y, max(0, s0 - 1)]
        up = a.fish_up
        sel = fm2.copy(); sel[:up] = False
        dst = np.zeros_like(sel); dst[:-up] = sel[up:]                  # destination rows: source row minus `up`
        ys, xs = np.nonzero(dst)
        out[ys, xs] = fish[ys + up, xs]
        print(f"fish lifted {up} px ({int(fm2.sum())} px)")
    for y in range(y0, y1):
        xs = np.flatnonzero(grown[y])
        if xs.size == 0:
            continue
        run_start = xs[0]
        for i in range(1, xs.size + 1):
            if i == xs.size or xs[i] != xs[i - 1] + 1:
                s, e = run_start, xs[i - 1] + 1                          # run [s, e)
                n = e - s
                def clean(a0, a1):                                     # a source span: in the image, not masked, no red-brown ring
                    if a0 < 0 or a1 > im.shape[1] or grown[y, a0:a1].any():
                        return False
                    seg = im[y, a0:a1]
                    return not (((seg[:, 0] - seg[:, 2]) > 40) & ((seg[:, 0] - seg[:, 1]) > 25) & (seg[:, 0] < 200)).any()
                for k in (1, 2, 3):                                    # try the same row one, two, three run-widths away on either side
                    if clean(s - k * n, s - (k - 1) * n):
                        out[y, s:e] = im[y, s - k * n:s - (k - 1) * n]; break
                    if clean(e + (k - 1) * n, e + k * n):
                        out[y, s:e] = im[y, e + (k - 1) * n:e + k * n]; break
                else:
                    out[y, s:e] = im[y, max(0, s - 1)]
                if i < xs.size:
                    run_start = xs[i]
    if not a.keep_sand:
        def tan(px):                                                     # sand: warm, light, r > g > b
            return (px[..., 0] > 150) & (px[..., 1] > 130) & ((px[..., 0] - px[..., 2]) > 40) & (px[..., 0] >= px[..., 1])
        col = out[:, 600]
        horizon = next(y for y in range(800, 1000) if tan(col[y]))     # first sand row on a clean column left of the base
        water = out[horizon - 3, 600].copy()                            # the lowest water band
        sand = tan(out); sand[:horizon - 1] = False
        out[sand] = water
        print(f"sand floor from row {horizon} replaced with water colour {tuple(int(v) for v in water)}")
    if not a.keep_stalk and not a.keep_sand:
        # the brown "sleeve": the stalk column, its base ring and the dark disc under the crown (warm browns with g >= b; the
        # magenta tentacles have g < b and the orange fish is far above this window)
        wx0, wy0, wx1, wy1 = 700, 612, 1260, 1000
        r, g, b = out[..., 0], out[..., 1], out[..., 2]
        brown = (r - b > 22) & (g >= b) & (r < 215)
        sm = np.zeros(brown.shape, bool); sm[wy0:wy1, wx0:wx1] = brown[wy0:wy1, wx0:wx1]
        grown2 = sm.copy()
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                grown2 |= np.roll(np.roll(sm, dy, 0), dx, 1)
        grown2[:wy0] = False; grown2[wy1:] = False
        # repaint with the water of the same row, sampled just left of the window (the rows are plain horizontal bands down here)
        for y in range(wy0, wy1):
            xs = np.flatnonzero(grown2[y])
            if xs.size:
                row = out[y, 640:700]
                out[y, xs.min():xs.max() + 1] = np.median(row, axis=0).astype(out.dtype)
        print(f"brown stalk removed: {int(grown2.sum())} px")
    Image.fromarray(out.astype(np.uint8)).save(a.dst, optimize=True)
    print(f"wrote {a.dst}: repainted {int(grown.sum())} px")


if __name__ == "__main__":
    main()
