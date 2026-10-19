#!/usr/bin/env python3
"""Generate the aquarium Android app's TV banner and launcher icons from real captures.

The aquarium is its own Android app (Gradle product flavor `aquarium`, see
docs/plans/2026-09-30-aquarium-chromecast.md). Its launcher art overrides the
shared `main` resources from the flavor source set android/app/src/aquarium/res/:

  drawable/tv_banner.png                 640 x 360, the same size and frame as
                                         main's snowgoons banner (a 2 px blue border
                                         inside a 2 px navy one), the tank from
                                         camshot A with "WORLD FOUNDRY" / "aquarium"
  mipmap-<density>/ic_launcher.png       legacy square icon (pre-API 26)
  mipmap-<density>/ic_launcher_round.png same bitmap (main's round icons are square too)
  mipmap-<density>/ic_launcher_foreground.png
                                         adaptive-icon foreground (API 26+), full bleed:
                                         the launcher mask keeps the inner ~66 dp of the
                                         108 dp canvas, where the fish and crown sit

Sources are the committed 1920 x 1080 desktop captures in the plan's bundle directory
(frame A: whole tank; frame B: camshot B, the fish in the anemone), so the output is
deterministic and the art is what the game renders. Re-run after re-capturing them.

Usage:
    scripts/gen-aquarium-android-art.py [-h]
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BUNDLE = REPO_ROOT / "docs" / "plans" / "2026-09-30-aquarium-chromecast"
FRAME_A = BUNDLE / "frame-a-1920x1080.png"
FRAME_B = BUNDLE / "frame-b-1920x1080.png"
RES_DIR = REPO_ROOT / "android" / "app" / "src" / "aquarium" / "res"

BANNER_SIZE = (640, 360)
# Camshot A at 1920 x 1080 puts the tank at x 340..1580, y 190..730; this 16:9 box keeps it
# whole with the room above (title) and the stand below (subtitle).
BANNER_CROP = (280, 88, 1640, 853)
# Camshot B at 1920 x 1080: the crown spans x 420..1570, the fish sits at about (930, 440).
ICON_CROP = (470, 40, 1390, 960)

# main's banner (android/app/src/main/res/drawable/tv_banner.png) colours.
NAVY = (26, 26, 46)
BORDER_BLUE = (74, 122, 181)
SUBTITLE = (136, 170, 204)
WHITE = (255, 255, 255)

FONT_DIRS = ("/usr/share/fonts/truetype/ibm-plex", "/usr/share/fonts/truetype/dejavu")
FONT_NAMES = ("IBMPlexSans-Regular.ttf", "DejaVuSans.ttf")

# Same density tables as scripts/gen-android-adaptive-icon.py.
DENSITIES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
LEGACY_DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# The legacy icon shows what the adaptive mask keeps: the inner 72 of 108 dp.
LEGACY_INNER = 72 / 108


def font(size):
    for d in FONT_DIRS:
        for n in FONT_NAMES:
            p = pathlib.Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    sys.exit("gen-aquarium-android-art: no IBM Plex Sans or DejaVu Sans font found")


def centred_text(draw, y, text, size, fill):
    f = font(size)
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=f)
    draw.text(((BANNER_SIZE[0] - (x1 - x0)) / 2 - x0, y - y0), text, font=f, fill=fill)


def banner():
    im = Image.open(FRAME_A).convert("RGB").crop(BANNER_CROP).resize(BANNER_SIZE, Image.LANCZOS)
    d = ImageDraw.Draw(im)
    centred_text(d, 12, "WORLD FOUNDRY", 26, WHITE)     # over the dark room above the tank
    centred_text(d, 318, "aquarium", 26, SUBTITLE)      # over the stand
    w, h = BANNER_SIZE
    d.rectangle((0, 0, w - 1, h - 1), outline=NAVY, width=2)
    d.rectangle((2, 2, w - 3, h - 3), outline=BORDER_BLUE, width=2)
    return im


def main():
    sys.exit("superseded 2026-10-01 by scripts/gen-android-icons.py aquarium (one layout for every game, with the logo from scripts/add-wf-logo.py); running this would overwrite the new icons")
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    for src in (FRAME_A, FRAME_B):
        if not src.exists():
            sys.exit(f"gen-aquarium-android-art: missing source capture {src}")

    out = RES_DIR / "drawable" / "tv_banner.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    banner().save(out, optimize=True)
    print(f"wrote {out.relative_to(REPO_ROOT)} {BANNER_SIZE[0]}x{BANNER_SIZE[1]}")

    art = Image.open(FRAME_B).convert("RGB").crop(ICON_CROP)
    for density, px in DENSITIES.items():
        d = RES_DIR / f"mipmap-{density}"
        d.mkdir(parents=True, exist_ok=True)
        art.resize((px, px), Image.LANCZOS).convert("RGBA").save(d / "ic_launcher_foreground.png", optimize=True)
    side = art.size[0]
    m = round(side * (1 - LEGACY_INNER) / 2)
    inner = art.crop((m, m, side - m, side - m))
    for density, px in LEGACY_DENSITIES.items():
        d = RES_DIR / f"mipmap-{density}"
        icon = inner.resize((px, px), Image.LANCZOS)
        icon.save(d / "ic_launcher.png", optimize=True)
        icon.save(d / "ic_launcher_round.png", optimize=True)
    print(f"wrote {len(DENSITIES)} adaptive foregrounds + {2 * len(LEGACY_DENSITIES)} legacy icons under "
          f"{RES_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
