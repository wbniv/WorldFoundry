"""The baseline level's launcher icon and TV banner carry the World Foundry logo at bottom-right.

docs/reference/android-brand-badge.md stamps the logo bottom-right on every game's icon and banner. The art is
committed under android/app/art-src/baseline-icon-2026-10-11/ (made by scripts/gen-baseline-icon.py) and
wflevels/baseline/build.py ships it, so this checks the art and the wiring. The logo is a light badge on dark
navy art, so its corner has many near-white pixels and the clean art's corner has none.
"""

from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "android/app/art-src/baseline-icon-2026-10-11"
# shipped file, clean art, shipped size, corner as (x0, x1, y0, y1) fractions of width and height
CASES = [
    ("icon.png", "icon-art.png", (256, 256), (0.78, 0.92, 0.78, 0.93)),
    ("tv_banner.png", "banner-art.png", (640, 360), (0.89, 0.96, 0.75, 0.93)),
]


def bright_fraction(image, corner):
    width, height = image.size
    x0, x1, y0, y1 = corner
    grey = image.convert("L").crop((int(width * x0), int(height * y0), int(width * x1), int(height * y1)))
    histogram = grey.histogram()
    return sum(histogram[201:]) / sum(histogram)


@pytest.mark.parametrize("shipped,clean,size,corner", CASES)
def test_shipped_art_has_the_logo_in_the_corner(shipped, clean, size, corner):
    image = Image.open(ART / shipped).convert("RGB")
    assert image.size == size
    # Measured 0.28 (icon) and 0.48 (banner); the clean art measures 0.
    assert bright_fraction(image, corner) >= 0.15, f"{shipped} has no logo at bottom-right"
    clean_art = Image.open(ART / clean).convert("RGB").resize(size, Image.LANCZOS)
    assert bright_fraction(clean_art, corner) <= 0.01, f"{clean} is not clean art: it already has a logo"


def test_build_ships_the_stamped_art():
    build = (ROOT / "wflevels/baseline/build.py").read_text()
    assert "ICON_ART=ROOT/'android/app/art-src/baseline-icon-2026-10-11'" in build
    assert "shutil.copyfile(ICON_ART/(name+'.png')" in build
    assert "ImageDraw" not in build, "build.py draws its own icon again instead of shipping the stamped art"
