#!/usr/bin/env python3
"""gen-android-icons.py: build every World Foundry game's Android launcher icons and TV banner, in one layout.

The layout is the same for every game on mobile and Chromecast (docs/reference/android-brand-badge.md):
the game's art fills the icon, and the World Foundry logo sits bottom-right. The logo is stamped by the separate
scripts/add-wf-logo.py, which works on any image; this script only prepares the art and calls it.

Per game (a Gradle product flavor) it writes, under android/app/src/<flavor>/res/:

  drawable/tv_banner.png                  640 x 360: the art, the game's name bottom-left, the logo bottom-right
  mipmap-<density>/ic_launcher.png        legacy square icon (pre-API 26), logo bottom-right
  mipmap-<density>/ic_launcher_round.png  legacy round icon: circle-masked, the logo inside the circle at 45 degrees
  mipmap-<density>/ic_launcher_foreground.png
                                          adaptive foreground (API 26+), full bleed; the logo is kept inside the
                                          launcher's safe zone (the inner 72 of 108 dp) so no mask can cut it off

The art, all committed so the output is deterministic (android/app/art-src/ unless noted):
  snowgoons  snowgoons-snowman-1920x1080.png     scripts/render-snowgoon.py (Blender): a menacing three-armed snowman (the icon)
             + snowgoons-level-chromecast-1920x1080.png for the banner: the level itself, screenshotted on the Chromecast HD by
               `scripts/android-device-run.sh --app snowgoons --release --seconds 8 <ip:port>` (adb screencap, no input)
  aquarium   aquarium-icon-2026-10-03/artwork.png   generated promotional illustration: clownfish, tiger barb and betta
             (source and prompts retained beside the artwork)
             + aquarium-school-chromecast-1920x1080.png for the banner (the whole fish school; real Chromecast capture)
  condo      condo-pullback-1920x1080.png        scripts/capture-condo-pullback.py: the camera pulled back and lowered
  smb        smb-w1-1-super-mario-640.png        a copy of tests/screenshots/smb_mushroom_02_super.png (W1-1, the engine's test harness)
  qbert      qbert-pyramid-640x480.png           a copy of docs/plans/2026-09-20-relight-swept-levels/qbert-after.png (an engine render)

Usage:
    scripts/gen-android-icons.py [GAME ...] [-h]        (GAME is snowgoons, aquarium, condo, smb or qbert; default all)
"""
import argparse
import importlib.util
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = REPO_ROOT / "android" / "app" / "art-src"
RES = REPO_ROOT / "android" / "app" / "src"

_spec = importlib.util.spec_from_file_location("addlogo", REPO_ROOT / "scripts" / "add-wf-logo.py")
addlogo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(addlogo)

# per game: icon art + square crop box, banner art + 16:9 crop box, the name shown on the banner
GAMES = {
    # The banner is a real frame of the snowgoons level (the user, 2026-10-01: "use a screenshot from the snowgoons level");
    # the icon stays the snowman. Source: the snowgoons release app on the Chromecast HD, 8 s after launch, no input
    # (docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md, Icons).
    "snowgoons": dict(icon=ART / "snowgoons-snowman-1920x1080.png", icon_crop=(420, 0, 1500, 1080),
                      banner=ART / "snowgoons-level-chromecast-1920x1080.png", banner_crop=(0, 0, 1920, 1080), name="snowgoons"),
    "aquarium": dict(icon=ART / "aquarium-icon-2026-10-03/artwork.png", icon_crop=(0, 0, 1254, 1254),
                     banner=ART / "aquarium-school-chromecast-1920x1080.png",
                     banner_crop=(280, 88, 1640, 853), name="aquarium"),
    "condo": dict(icon=ART / "condo-pullback-1920x1080.png", icon_crop=(1040, 160, 1920, 1040),
                  banner=ART / "condo-pullback-1920x1080.png", banner_crop=(0, 0, 1920, 1080), name="condo"),
    # docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md: real engine frames, 640 px wide (so the big icons are upscaled).
    # The icon crops keep Mario and the ? blocks (the pyramid and Q*bert) inside the middle two thirds, which is
    # all the legacy icon and the launcher's mask show; the banner crops start below the score line.
    "smb": dict(icon=ART / "smb-w1-1-super-mario-640.png", icon_crop=(210, 182, 540, 512),
                banner=ART / "smb-w1-1-super-mario-640.png", banner_crop=(0, 200, 640, 560), name="smb"),
    "qbert": dict(icon=ART / "qbert-pyramid-640x480.png", icon_crop=(90, 20, 550, 480),
                  banner=ART / "qbert-pyramid-640x480.png", banner_crop=(0, 60, 640, 420), name="qbert"),
}

BANNER = (640, 360)
NAVY, BLUE, WHITE = (26, 26, 46), (74, 122, 181), (255, 255, 255)           # main's banner frame colours
DENSITIES = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}          # adaptive foreground
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
SAFE = (108 - 72) / 2 / 108                       # the launcher keeps the inner 72 of 108 dp: 1/6 on every side
LEGACY_INNER = 72 / 108

FONT_DIRS = ("/usr/share/fonts/truetype/ibm-plex", "/usr/share/fonts/truetype/dejavu")
FONT_NAMES = ("IBMPlexSans-SemiBold.ttf", "IBMPlexSans-Regular.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf")


def font(size):
    for d in FONT_DIRS:
        for n in FONT_NAMES:
            p = pathlib.Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    sys.exit("gen-android-icons: no IBM Plex Sans or DejaVu Sans font found")


def banner(g):
    im = Image.open(g["banner"]).convert("RGB").crop(g["banner_crop"]).resize(BANNER, Image.LANCZOS).convert("RGBA")
    w, h = BANNER
    shade = Image.new("RGBA", BANNER, (0, 0, 0, 0))                          # a soft dark gradient under the name, blended
    sd = ImageDraw.Draw(shade)
    for i in range(70):
        sd.line((0, h - 1 - i, w, h - 1 - i), fill=(0, 0, 0, int(150 * (1 - i / 70) ** 1.6)))
    im = Image.alpha_composite(im, shade)
    d = ImageDraw.Draw(im)
    f = font(34)
    x0, y0, x1, y1 = d.textbbox((0, 0), g["name"], font=f)
    d.text((22 - x0 + 1, h - 22 - (y1 - y0) - y0 + 2), g["name"], font=f, fill=(0, 0, 0, 160))
    d.text((22 - x0, h - 22 - (y1 - y0) - y0), g["name"], font=f, fill=WHITE + (255,))
    im = addlogo.add_logo(im, scale=0.22, margin=0.05)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=NAVY, width=2)
    d.rectangle((2, 2, w - 3, h - 3), outline=BLUE, width=2)
    return im.convert("RGB")


def build(game):
    g = GAMES[game]
    for src in (g["icon"], g["banner"]):
        if not pathlib.Path(src).exists():
            sys.exit(f"gen-android-icons: missing art {src}")
    res = RES / game / "res"
    (res / "drawable").mkdir(parents=True, exist_ok=True)
    banner(g).save(res / "drawable" / "tv_banner.png", optimize=True)

    art = Image.open(g["icon"]).convert("RGB").crop(g["icon_crop"])
    for density, px in DENSITIES.items():
        d = res / f"mipmap-{density}"
        d.mkdir(parents=True, exist_ok=True)
        fg = art.resize((px, px), Image.LANCZOS).convert("RGBA")
        addlogo.add_logo(fg, scale=0.17, safe_circle=LEGACY_INNER).save(d / "ic_launcher_foreground.png", optimize=True)
    side = art.size[0]
    m = round(side * (1 - LEGACY_INNER) / 2)
    inner = art.crop((m, m, side - m, side - m))
    for density, px in LEGACY.items():
        d = res / f"mipmap-{density}"
        sq = inner.resize((px, px), Image.LANCZOS)
        addlogo.add_logo(sq, scale=0.26, margin=0.05).convert("RGB").save(d / "ic_launcher.png", optimize=True)
        addlogo.add_logo(sq, scale=0.24, margin=0.05, circle=True).save(d / "ic_launcher_round.png", optimize=True)
    print(f"{game}: wrote tv_banner.png, {len(DENSITIES)} foregrounds, {len(LEGACY)} legacy and {len(LEGACY)} round icons under "
          f"{res.relative_to(REPO_ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("games", nargs="*", help="snowgoons, aquarium, condo, smb and/or qbert (default: all)")
    a = ap.parse_args()
    bad = [g for g in a.games if g not in GAMES]
    if bad:
        sys.exit(f"gen-android-icons: unknown game {bad[0]} (choose from {', '.join(GAMES)})")
    for game in a.games or GAMES:
        build(game)


if __name__ == "__main__":
    main()
