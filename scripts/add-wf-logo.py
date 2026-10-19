#!/usr/bin/env python3
"""add-wf-logo.py: stamp the World Foundry logo in the bottom-right corner of any existing icon or banner.

The approved badge is the graphic panel of the repository's wflogo.png, retaining its grey globes and white
background, with no outer border or side padding. See docs/reference/android-brand-badge.md. This shared script
stamps every game's launcher icons and TV banners, and can also stamp any existing PNG.

Usage:
  scripts/add-wf-logo.py ICON.png                    # write ICON.png in place
  scripts/add-wf-logo.py ICON.png -o OUT.png         # leave the input alone
  scripts/add-wf-logo.py a.png b.png c.png           # several, each in place

Options:
  --logo PNG          an already cropped graphic (default wflogo.png is cropped automatically)
  --scale F           logo longer side as a fraction of the shorter image side (default 0.26)
  --margin F          gap to the edges, as a fraction of the shorter side (default 0.05)
  --safe-inset F      keep the logo this fraction of each side away from the edge; adaptive-icon foregrounds need 1/6
                      so the launcher's mask does not cut it off (default 0)
  --circle            the image is a round icon: mask it to a circle and put the logo inside it, at 45 degrees
  --safe-circle F     do not mask, but put the logo inside the circle of diameter F x the short side (an adaptive foreground: the launcher shows
                      the inner 72 of 108 dp, which a round mask clips to a circle of 0.667, so a corner logo would be cut off)
  -h, --help
"""
import argparse
import math
import pathlib
import sys

from PIL import Image, ImageDraw, ImageOps

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_LOGO = REPO_ROOT / "wflogo.png"
LOGO_CROP = (4, 25, 82, 129)  # interior: no lettering or black frame borders


def render_logo(path, size):
    """Resize the rectangular graphic without padding, borders, or distortion."""
    path = pathlib.Path(path)
    with Image.open(path) as source:
        logo = source.convert("RGBA")
    if path.resolve() == DEFAULT_LOGO.resolve():
        logo = logo.crop(LOGO_CROP)
    return ImageOps.contain(logo, (size, size), Image.LANCZOS)


def add_logo(img, logo_path=DEFAULT_LOGO, scale=0.26, margin=0.05, safe_inset=0.0, circle=False, safe_circle=0.0):
    """Return img (RGBA) with the logo stamped bottom-right (and masked to a circle if circle=True)."""
    img = img.convert("RGBA")
    w, h = img.size
    short = min(w, h)
    side = max(8, round(short * scale))
    logo = render_logo(logo_path, side)
    fw, fh = logo.size
    if circle or safe_circle:
        r = short * (safe_circle or 1.0) / 2
        # the logo's own bottom-right corner must lie inside the circle: centre it on the 45 degree radius
        reach = (r - math.hypot(fw, fh) / 2) - short * margin * 0.5
        cx, cy = w / 2 + reach * math.cos(math.radians(45)), h / 2 + reach * math.sin(math.radians(45))
        pos = (round(cx - fw / 2), round(cy - fh / 2))
        if circle:
            mask = Image.new("L", (w * 4, h * 4), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, w * 4 - 1, h * 4 - 1), fill=255)
            img.putalpha(mask.resize((w, h), Image.LANCZOS))
    else:
        inset = round(short * max(margin, safe_inset))
        pos = (w - inset - fw, h - inset - fh)
    img.alpha_composite(logo, pos)
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
    ap.add_argument("--safe-circle", type=float, default=0.0)
    a = ap.parse_args()
    if a.output and len(a.images) != 1:
        sys.exit("add-wf-logo: -o takes exactly one input image")
    if not pathlib.Path(a.logo).exists():
        sys.exit(f"add-wf-logo: logo not found: {a.logo}")
    for p in a.images:
        out = add_logo(Image.open(p), a.logo, a.scale, a.margin, a.safe_inset, a.circle, a.safe_circle)
        dest = a.output or p
        out.save(dest, optimize=True)
        print(f"wrote {dest} ({out.size[0]}x{out.size[1]})")


if __name__ == "__main__":
    main()
