"""Planted Tank launcher resources: files, sizes and the World Foundry badge.

Checks the committed PNGs under android/screensaver/src/planted/res against the shipping badge code
(scripts/add-wf-logo.py): the badge is stamped where add_logo() puts it, and on the adaptive foreground it
lies inside the 72/108 safe circle. Runs in a plain python + pillow container.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "android/screensaver/src/planted/res"
FOREGROUND = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
INNER = 72 / 108
BANNER_SIZE = (640, 360)


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


badge = _load("add_wf_logo", "scripts/add-wf-logo.py")


def badge_pixels(size, **kwargs):
    """Return {(x, y): (r, g, b)} for every fully opaque pixel add_logo() stamps on a blank image of size."""
    magenta = badge.add_logo(Image.new("RGBA", size, (255, 0, 255, 255)), **kwargs).convert("RGB")
    green = badge.add_logo(Image.new("RGBA", size, (0, 255, 0, 255)), **kwargs).convert("RGB")
    a, b = magenta.load(), green.load()
    return {(x, y): a[x, y] for y in range(size[1]) for x in range(size[0])
            if a[x, y] == b[x, y] and a[x, y] not in ((255, 0, 255), (0, 255, 0))}


def test_banner_has_badge_lower_right():
    banner = Image.open(RES / "drawable/tv_banner.png").convert("RGB")
    assert banner.size == BANNER_SIZE
    expected = badge_pixels(BANNER_SIZE, scale=0.22, margin=0.05)
    assert len(expected) > 2000, "badge should cover a few thousand pixels"
    xs = [x for x, _ in expected]
    ys = [y for _, y in expected]
    # lower-right 22 percent block (the badge side is 0.22 of the short side)
    assert min(xs) > BANNER_SIZE[0] * 0.8 and min(ys) > BANNER_SIZE[1] * 0.6
    px = banner.load()
    wrong = sum(1 for (x, y), rgb in expected.items() if px[x, y] != rgb)
    assert wrong / len(expected) < 0.01, f"{wrong} of {len(expected)} badge pixels differ"


def test_banner_badge_differs_from_art():
    """The badge block is bright white globes and red, unlike the dark tank art next to it."""
    banner = Image.open(RES / "drawable/tv_banner.png").convert("L")
    expected = badge_pixels(BANNER_SIZE, scale=0.22, margin=0.05)
    x0, x1 = min(x for x, _ in expected), max(x for x, _ in expected)
    y0, y1 = min(y for _, y in expected), max(y for _, y in expected)
    badge_mean = sum(banner.getpixel(p) for p in expected) / len(expected)
    # the strip of art just left of the badge, same rows
    left = [banner.getpixel((x, y)) for y in range(y0, y1) for x in range(x0 - 40, x0 - 10)]
    assert badge_mean - sum(left) / len(left) > 60


@pytest.mark.parametrize("density,pixels", FOREGROUND.items())
def test_foreground_size_and_badge_inside_safe_circle(density, pixels):
    path = RES / f"mipmap-{density}/ic_launcher_foreground.png"
    img = Image.open(path).convert("RGBA")
    assert img.size == (pixels, pixels)
    expected = badge_pixels(img.size, scale=0.17, safe_circle=INNER)
    assert expected, "badge not found"
    centre, radius = pixels / 2, pixels * INNER / 2
    far = max(math.hypot(x + 0.5 - centre, y + 0.5 - centre) for x, y in expected)
    assert far <= radius, f"badge reaches {far:.1f}px from centre, safe radius {radius:.1f}px"
    px = img.load()
    wrong = sum(1 for (x, y), rgb in expected.items() if px[x, y][:3] != rgb)
    assert wrong / len(expected) < 0.01, f"{wrong} of {len(expected)} badge pixels differ"


@pytest.mark.parametrize("density,pixels", LEGACY.items())
def test_legacy_icons_exist_with_size(density, pixels):
    square = Image.open(RES / f"mipmap-{density}/ic_launcher.png")
    round_ = Image.open(RES / f"mipmap-{density}/ic_launcher_round.png").convert("RGBA")
    assert square.size == (pixels, pixels)
    assert round_.size == (pixels, pixels)
    assert round_.getpixel((0, 0))[3] == 0, "round icon corner should be transparent"
    assert round_.getpixel((pixels // 2, pixels // 2))[3] == 255


def test_all_files_present():
    names = ["ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png"]
    missing = [f"mipmap-{d}/{n}" for d in FOREGROUND for n in names if not (RES / f"mipmap-{d}/{n}").is_file()]
    assert not missing
    assert (RES / "drawable/tv_banner.png").is_file()
