#!/usr/bin/env python3
"""Generate the condo Android app's TV banner and launcher icons from a real capture.

The condo is its own Android app (Gradle product flavor `condo`, see
docs/plans/2026-10-01-condo-chromecast.md); the recipe is scripts/gen-aquarium-android-art.py.
Output under android/app/src/condo/res/ overrides main's resources with the same names/sizes:

  drawable/tv_banner.png                 640 x 360: the doll-house view, "WORLD FOUNDRY" / "condo",
                                         main's navy + blue frame
  mipmap-<density>/ic_launcher.png       legacy square icon (pre-API 26)
  mipmap-<density>/ic_launcher_round.png same bitmap
  mipmap-<density>/ic_launcher_foreground.png  adaptive foreground (API 26+), full bleed

The source is the committed 1920 x 1080 desktop capture of `task run-condo` (its opening
doll-house shot) in android/app/art-src/, so the output is deterministic. Re-run after
re-capturing it.

Usage:
    scripts/gen-condo-android-art.py [-h]
"""
import argparse
import importlib.util
import pathlib
import sys

from PIL import Image, ImageDraw

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FRAME = REPO_ROOT / "android" / "app" / "art-src" / "condo-frame-1920x1080.png"
RES_DIR = REPO_ROOT / "android" / "app" / "src" / "condo" / "res"

# Reuse the aquarium generator's constants and text helpers (one place for the house style).
_spec = importlib.util.spec_from_file_location("aqart", REPO_ROOT / "scripts" / "gen-aquarium-android-art.py")
aq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aq)

# 16:9 box around the doll-house view, and a square on the flat for the icon (set from the capture).
BANNER_CROP = (0, 0, 1920, 1080)
ICON_CROP = (60, 0, 1140, 1080)   # both units: 639 (orange) meets 640 (blue)


def banner():
    im = Image.open(FRAME).convert("RGB").crop(BANNER_CROP).resize(aq.BANNER_SIZE, Image.LANCZOS)
    d = ImageDraw.Draw(im)
    w, h = aq.BANNER_SIZE
    # Dark bands under the words so they read over any part of the floor plan.
    d.rectangle((0, 0, w, 48), fill=aq.NAVY)
    d.rectangle((0, h - 48, w, h), fill=aq.NAVY)
    aq.centred_text(d, 10, "WORLD FOUNDRY", 26, aq.WHITE)
    aq.centred_text(d, h - 40, "condo", 26, aq.SUBTITLE)
    d.rectangle((0, 0, w - 1, h - 1), outline=aq.NAVY, width=2)
    d.rectangle((2, 2, w - 3, h - 3), outline=aq.BORDER_BLUE, width=2)
    return im


def main():
    sys.exit("superseded 2026-10-01 by scripts/gen-android-icons.py condo (one layout for every game, with the logo from scripts/add-wf-logo.py); running this would overwrite the new icons")
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    if not FRAME.exists():
        sys.exit(f"gen-condo-android-art: missing source capture {FRAME}")
    out = RES_DIR / "drawable" / "tv_banner.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    banner().save(out, optimize=True)
    print(f"wrote {out.relative_to(REPO_ROOT)} {aq.BANNER_SIZE[0]}x{aq.BANNER_SIZE[1]}")

    art = Image.open(FRAME).convert("RGB").crop(ICON_CROP)
    for density, px in aq.DENSITIES.items():
        d = RES_DIR / f"mipmap-{density}"
        d.mkdir(parents=True, exist_ok=True)
        art.resize((px, px), Image.LANCZOS).convert("RGBA").save(d / "ic_launcher_foreground.png", optimize=True)
    side = art.size[0]
    m = round(side * (1 - aq.LEGACY_INNER) / 2)
    inner = art.crop((m, m, side - m, side - m))
    for density, px in aq.LEGACY_DENSITIES.items():
        d = RES_DIR / f"mipmap-{density}"
        icon = inner.resize((px, px), Image.LANCZOS)
        icon.save(d / "ic_launcher.png", optimize=True)
        icon.save(d / "ic_launcher_round.png", optimize=True)
    print(f"wrote {len(aq.DENSITIES)} adaptive foregrounds + {2 * len(aq.LEGACY_DENSITIES)} legacy icons under "
          f"{RES_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
