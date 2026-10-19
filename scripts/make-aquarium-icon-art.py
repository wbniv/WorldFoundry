#!/usr/bin/env python3
"""make-aquarium-icon-art.py: the aquarium icon art, just the fish and the anemone's crown, from a camshot B capture.

Input is a 640x480 capture from scripts/capture-aquarium-fish-high.py (the fish resting HIGHER in the crown, as the user asked: "move the fish
up a bit higher ... relative to the anemone"). The frame is cut just under the crown, which drops the brown stalk, its base ring, the rock and the
sand; the water bands are then continued downward (each row repainted with the median water colour at the left edge, where the backdrop is
plain), so the crown and the fish float on the tank's water. Output is a square, ready for scripts/gen-android-icons.py.

Usage: scripts/make-aquarium-icon-art.py IN.png OUT.png [--cut-y N] [-h]
"""
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--cut-y", type=int, default=322, help="keep rows above this (just under the crown's base)")
ap.add_argument("--top-y", type=int, default=42, help="first kept row, just under the tank's rim")
ap.add_argument("--x0", type=int, default=14); ap.add_argument("--x1", type=int, default=594)
ap.add_argument("--centre-y", type=int, default=195, help="the source row of the crown-and-fish's visual centre, put in the middle of the square")
a = ap.parse_args()
im = np.array(Image.open(a.src).convert("RGB"))
side = a.x1 - a.x0
out = np.zeros((side, side, 3), np.uint8)
water = lambda y: np.median(im[min(max(y, a.top_y + 3), 430), 10:70], axis=0).astype(np.uint8)    # the plain left-edge water of source row y
off = side // 2 - (a.centre_y - a.top_y)                        # canvas row of source row top_y
for cy in range(side):
    sy = cy - off + a.top_y                                       # the source row shown at canvas row cy
    if a.top_y <= sy < a.cut_y:
        out[cy] = im[sy, a.x0:a.x1]
    else:
        out[cy] = im[min(max(2 * a.top_y - sy, a.top_y + 3), a.cut_y - 1), 10:70].mean(axis=0).astype(np.uint8) if sy < a.top_y else water(sy)   # above: the water bands mirrored; below the crown: the left-edge water
Image.fromarray(out).save(a.dst, optimize=True)
print(f"wrote {a.dst} {out.shape[1]}x{out.shape[0]}")
