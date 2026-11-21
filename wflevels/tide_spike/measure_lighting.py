#!/usr/bin/env python3
"""Lit factor of four faces of known normal from the spike's sun-sweep captures.

    python3 wflevels/tide_spike/measure_lighting.py DIR      (DIR holds sun-<B>_<C>.png; a minus sign is written m)

The pier deck is one colour (wood_hi) and the tower another (stone), so rendered / authored colour, least squares over the
channels, is how lit a face is: ambient alone gives the ambient value (0.50 here). Boxes: pier top +z, pier front -y, tower
front -y, tower left -x, at the camera and framing of the spike (1280 x 720).
"""
import json
import sys
from pathlib import Path

from PIL import Image

WOOD, STONE = (0.58, 0.40, 0.22), (0.80, 0.77, 0.68)
FACES = {"pier top (+z)": ((200, 428, 700, 452), WOOD), "pier front (-y)": ((200, 463, 700, 469), WOOD),
         "tower front (-y)": ((935, 240, 1010, 370), STONE), "tower left (-x)": ((884, 240, 906, 360), STONE)}
SETTINGS = ["m50_m70", "40_90", "m50_110", "50_m70", "50_110"]


def lit(im, box, base):
    px = [im.getpixel((x, y))[:3] for x in range(box[0], box[2]) for y in range(box[1], box[3])]
    rgb = [sum(p[i] for p in px) / len(px) / 255 for i in range(3)]
    return sum(r * b for r, b in zip(rgb, base)) / sum(b * b for b in base)


def main(d):
    out = {}
    for tag in SETTINGS:
        im = Image.open(Path(d) / f"sun-{tag}.png").convert("RGB")
        b, c = (float(x.replace("m", "-")) for x in tag.split("_"))
        out[tag] = {"B_deg": b, "C_deg": c, **{k: round(lit(im, box, base), 2) for k, (box, base) in FACES.items()}}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
