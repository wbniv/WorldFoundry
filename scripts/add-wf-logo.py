#!/usr/bin/env python3
"""add-wf-logo.py: stamp the World Foundry logo in the bottom-right corner of any existing icon or banner.

The logo is the favicon of the World Foundry website (../worldfoundry.org/public/favicon.svg: a red square with a
dark square inside). The same layout is used for every World Foundry game on mobile and Chromecast: the game's art
fills the icon and the logo sits bottom-right. This script is the only place that knows the logo, so it can be run on
any PNG, whatever made it, and is used by scripts/gen-android-icons.py for every launcher icon and TV banner.

Usage:
  scripts/add-wf-logo.py ICON.png                    # write ICON.png in place
  scripts/add-wf-logo.py ICON.png -o OUT.png         # leave the input alone
  scripts/add-wf-logo.py a.png b.png c.png           # several, each in place

Options:
  --logo SVG          the logo (default ../worldfoundry.org/public/favicon.svg next to this repository); only <rect>
                      shapes are supported, which is all the favicon has
  --scale F           logo side as a fraction of the shorter image side (default 0.26)
  --margin F          gap to the edges, as a fraction of the shorter side (default 0.05)
  --safe-inset F      keep the logo this fraction of each side away from the edge; adaptive-icon foregrounds need 1/6
                      so the launcher's mask does not cut it off (default 0)
  --circle            the image is a round icon: mask it to a circle and put the logo inside it, at 45 degrees
  -h, --help
"""
import argparse
import math
import pathlib
import re
import sys

from PIL import Image, ImageDraw

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_LOGO = REPO_ROOT.parent / "worldfoundry.org" / "public" / "favicon.svg"


def _attrs(tag):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag))


def render_svg_rects(path, size):
    """Rasterise an SVG made only of <rect> elements (the favicon) at size x size, with transparency."""
    text = pathlib.Path(path).read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', text).group(1).replace(",", " ").split()]
    ss = 4                                                    # supersample, then reduce: smooth edges without a dependency
    im = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rects = re.findall(r"<rect\b[^>]*>", text)
    if not rects or re.search(r"<(path|circle|ellipse|polygon|polyline|line|text|image|use|g)\b", text):
        sys.exit(f"add-wf-logo: {path} has shapes other than <rect>; only rect-only logos are supported")
    for tag in rects:
        a = _attrs(tag)
        x, y = float(a.get("x", 0)), float(a.get("y", 0))
        w, h = float(a["width"]), float(a["height"])
        fill = a.get("fill", "#000000").lstrip("#")
        if len(fill) == 3:
            fill = "".join(c * 2 for c in fill)
        col = tuple(int(fill[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
        sx, sy = size * ss / vb[2], size * ss / vb[3]
        d.rectangle(((x - vb[0]) * sx, (y - vb[1]) * sy, (x - vb[0] + w) * sx - 1, (y - vb[1] + h) * sy - 1), fill=col)
    return im.resize((size, size), Image.LANCZOS)


def add_logo(img, logo_svg=DEFAULT_LOGO, scale=0.26, margin=0.05, safe_inset=0.0, circle=False):
    """Return img (RGBA) with the logo stamped bottom-right (and masked to a circle if circle=True)."""
    img = img.convert("RGBA")
    w, h = img.size
    short = min(w, h)
    side = max(8, round(short * scale))
    logo = render_svg_rects(logo_svg, side)
    border = max(1, round(side * 0.07))                       # a thin white keyline so the mark reads on any art
    framed = Image.new("RGBA", (side + 2 * border, side + 2 * border), (255, 255, 255, 255))
    framed.alpha_composite(logo, (border, border))
    fw = framed.size[0]
    if circle:
        r = short / 2
        # the logo's own bottom-right corner must lie inside the circle: centre it on the 45 degree radius
        reach = (r - fw * math.sqrt(2) / 2) - short * margin * 0.5
        cx, cy = w / 2 + reach * math.cos(math.radians(45)), h / 2 + reach * math.sin(math.radians(45))
        pos = (round(cx - fw / 2), round(cy - fw / 2))
        mask = Image.new("L", (w * 4, h * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, w * 4 - 1, h * 4 - 1), fill=255)
        img.putalpha(mask.resize((w, h), Image.LANCZOS))
    else:
        inset = round(short * max(margin, safe_inset))
        pos = (w - inset - fw, h - inset - fw)
    img.alpha_composite(framed, pos)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+")
    ap.add_argument("-o", "--output")
    ap.add_argument("--logo", default=str(DEFAULT_LOGO))
    ap.add_argument("--scale", type=float, default=0.26)
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--safe-inset", type=float, default=0.0)
    ap.add_argument("--circle", action="store_true")
    a = ap.parse_args()
    if a.output and len(a.images) != 1:
        sys.exit("add-wf-logo: -o takes exactly one input image")
    if not pathlib.Path(a.logo).exists():
        sys.exit(f"add-wf-logo: logo not found: {a.logo} (the website repository is expected at ../worldfoundry.org)")
    for p in a.images:
        out = add_logo(Image.open(p), a.logo, a.scale, a.margin, a.safe_inset, a.circle)
        dest = a.output or p
        out.save(dest, optimize=True)
        print(f"wrote {dest} ({out.size[0]}x{out.size[1]})")


if __name__ == "__main__":
    main()
