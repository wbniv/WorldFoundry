#!/usr/bin/env python3
"""Build the screensaver launcher icons and TV banners with the approved WF badge.

Usage: gen-screensaver-android-icons.py [-h] [{all,aquarium,seahorse,planted}]

The aquarium crop excludes its banner title and badge. Seahorse and Planted Tank
artwork comes from local renders of the levels. All use the shared Android icon
treatment. With no argument every flavor is rebuilt; name one to rewrite only
that flavor's files (aquarium: src/main/res, seahorse: src/seahorse/res,
planted: src/planted/res).
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "android/screensaver/src/main/res"
BANNER = RES / "drawable/tv_banner.png"
SEAHORSE_FRAME = ROOT / "android/screensaver/art-src/seahorse-grid-frame.png"
SEAHORSE_RES = ROOT / "android/screensaver/src/seahorse/res"
PLANTED_FRAME = ROOT / "android/screensaver/art-src/planted-tank-frame.png"
PLANTED_RES = ROOT / "android/screensaver/src/planted/res"
DENSITIES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
INNER = 72 / 108

spec = importlib.util.spec_from_file_location("add_wf_logo", ROOT / "scripts/add-wf-logo.py")
assert spec and spec.loader
badge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(badge)
banner_spec = importlib.util.spec_from_file_location(
    "android_icons", ROOT / "scripts/gen-android-icons.py")
assert banner_spec and banner_spec.loader
android_icons = importlib.util.module_from_spec(banner_spec)
banner_spec.loader.exec_module(android_icons)


def write_icons(art: Image.Image, res: Path) -> None:
    margin = round(art.width * (1 - INNER) / 2)
    legacy_art = art.crop((margin, margin, art.width - margin, art.height - margin))
    for density, pixels in DENSITIES.items():
        target = res / f"mipmap-{density}"
        target.mkdir(parents=True, exist_ok=True)
        foreground = art.resize((pixels, pixels), Image.Resampling.LANCZOS).convert("RGBA")
        badge.add_logo(foreground, scale=.17, safe_circle=INNER).save(
            target / "ic_launcher_foreground.png", optimize=True)
    for density, pixels in LEGACY.items():
        target = res / f"mipmap-{density}"
        square = legacy_art.resize((pixels, pixels), Image.Resampling.LANCZOS)
        badge.add_logo(square, scale=.26, margin=.05).convert("RGB").save(
            target / "ic_launcher.png", optimize=True)
        badge.add_logo(square, scale=.24, margin=.05, circle=True).save(
            target / "ic_launcher_round.png", optimize=True)
    print(f"Wrote screensaver launcher icons under {res}")


def build_aquarium() -> None:
    # The badge already on the aquarium banner is at x=563..622; its title ends before x=175.
    aquarium_art = Image.open(BANNER).convert("RGB").crop((175, 0, 535, 360))
    write_icons(aquarium_art, RES)


def build_seahorse() -> None:
    frame = Image.open(SEAHORSE_FRAME).convert("RGB")
    if frame.size != (1280, 720):
        raise ValueError(f"unexpected Seahorse render size: {frame.size}")
    write_icons(frame.crop((475, 190, 655, 370)), SEAHORSE_RES)
    banner = android_icons.banner({
        "banner": SEAHORSE_FRAME,
        "banner_crop": (0, 0, 1280, 720),
        "name": "seahorse grid",
    })
    target = SEAHORSE_RES / "drawable/tv_banner.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    banner.save(target, optimize=True)
    print(f"Wrote {target}")


def build_planted() -> None:
    frame = Image.open(PLANTED_FRAME).convert("RGB")
    if frame.size != (1280, 720):
        raise ValueError(f"unexpected Planted Tank frame size: {frame.size}")
    # A 360 x 360 square inside the tank on the planted section: no glass, stand, seed strip or FPS counter.
    write_icons(frame.crop((430, 200, 790, 560)), PLANTED_RES)
    banner = android_icons.banner({
        "banner": PLANTED_FRAME,
        "banner_crop": (0, 0, 1280, 720),
        "name": "Planted Tank",
    })
    target = PLANTED_RES / "drawable/tv_banner.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    banner.save(target, optimize=True)
    print(f"Wrote {target}")


FLAVORS = {"aquarium": build_aquarium, "seahorse": build_seahorse, "planted": build_planted}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build screensaver launcher icons and TV banners with the WF badge.")
    parser.add_argument("flavor", nargs="?", default="all", choices=["all", *FLAVORS],
                        help="flavor to rebuild (default: all); other flavors' files are left untouched")
    args = parser.parse_args()
    for name, build in FLAVORS.items():
        if args.flavor in ("all", name):
            build()


if __name__ == "__main__":
    main()
