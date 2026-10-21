#!/usr/bin/env python3
"""Prepare the proposed Planted Tank icon, banner and filmstrip crops for the plan mockups.

Writes only into the directory given by --out (default: this plan's scratch area); it never touches
shipping resources. It reuses the shipping pipeline (scripts/add-wf-logo.py and the banner() helper in
scripts/gen-android-icons.py) so the previews match what scripts/gen-screensaver-android-icons.py will
produce once the real art exists. Art here is the retained 2026-10 device evidence, not a final render.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/plans/2026-10-03-aquatic-plant-clumps-and-poster/runtime-evidence/textured-device"
INNER = 72 / 108


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    badge = load("add_wf_logo", "scripts/add-wf-logo.py")
    icons = load("android_icons", "scripts/gen-android-icons.py")

    # Filmstrip crops: the tank only, 1100 x 500 from the 1920 x 1080 device frames.
    for name in ("initial-seedlings", "freshwater-spreading", "freshwater-mature", "saltwater-mature"):
        frame = Image.open(EVIDENCE / f"{name}.png").convert("RGB")
        frame.crop((410, 270, 1510, 770)).resize((440, 200), Image.Resampling.LANCZOS).save(
            out / f"strip-{name}.jpg", quality=82)

    mature = Image.open(EVIDENCE / "freshwater-mature.png").convert("RGB")
    # Icon art: a square on the planted section of the tank, clear of the seed strip and FPS counter.
    art = mature.crop((730, 360, 1170, 800))
    art.save(out / "icon-art.png")
    foreground = art.resize((216, 216), Image.Resampling.LANCZOS).convert("RGBA")
    badge.add_logo(foreground, scale=.17, safe_circle=INNER).save(out / "icon-foreground.png", optimize=True)
    margin = round(art.width * (1 - INNER) / 2)
    legacy = art.crop((margin, margin, art.width - margin, art.height - margin)).resize(
        (96, 96), Image.Resampling.LANCZOS)
    badge.add_logo(legacy, scale=.26, margin=.05).convert("RGB").save(out / "icon-legacy.png", optimize=True)

    # Banner: the whole tank including its stand, 16:9, above the seed strip (y < 900).
    banner = icons.banner({"banner": EVIDENCE / "saltwater-mature.png",
                           "banner_crop": (330, 190, 1590, 898), "name": "Planted Tank"})
    banner.save(out / "banner.png", optimize=True)
    banner.resize((480, 270), Image.Resampling.LANCZOS).convert("RGB").save(out / "banner.jpg", quality=84)

    res = ROOT / "android/screensaver/src"
    for flavor, banner_path, fg_path in (
        ("aquarium", res / "main/res/drawable/tv_banner.png", res / "main/res/mipmap-xhdpi/ic_launcher_foreground.png"),
        ("seahorse", res / "seahorse/res/drawable/tv_banner.png", res / "seahorse/res/mipmap-xhdpi/ic_launcher_foreground.png"),
    ):
        Image.open(banner_path).convert("RGB").resize((480, 270), Image.Resampling.LANCZOS).save(
            out / f"banner-{flavor}.jpg", quality=84)
        Image.open(fg_path).convert("RGBA").save(out / f"icon-foreground-{flavor}.png", optimize=True)
    print(f"wrote previews to {out}")


if __name__ == "__main__":
    main()
