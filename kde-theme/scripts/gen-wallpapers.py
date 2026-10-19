#!/usr/bin/env python3
"""Generate three WorldFoundry KDE wallpapers using wflogo.png.

Outputs to ../wallpapers/ relative to this script:
  FoundryLinux-IronMark      logo as dark embossed stamp, lower-right, red glow
  FoundryLinux-RedFoundry    logo centred; red bleeds outward from it
  FoundryLinux-GlobeField    giant ghost logo + horizon line + small crisp logo
"""

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR.parent / "wallpapers"
LOGO_PATH  = SCRIPT_DIR.parent.parent / "wflogo.png"

FULL  = (1920, 1080)
HI    = (3840, 2160)
THUMB = (400, 225)

# ---------------------------------------------------------------------------
# WorldFoundry brand colours (worldfoundry.org/src/styles/global.css)
# ---------------------------------------------------------------------------
C_BG          = (26, 23, 20)       # #1a1714 — warm near-black
C_RAISED      = (36, 31, 27)       # #241f1b
C_ACCENT      = (248, 0, 0)        # #f80000 — molten red
C_ACCENT_DARK = (180, 0, 0)        # #b40000
C_BORDER      = (58, 50, 44)       # #3a322c

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(clamp(lerp(c1[i], c2[i], t)) for i in range(3))

def radial_t(x, y, cx, cy, inner_r, outer_r):
    """1.0 at/inside inner_r, 0.0 at/outside outer_r."""
    d = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    if d <= inner_r:
        return 1.0
    if d >= outer_r:
        return 0.0
    return 1.0 - (d - inner_r) / (outer_r - inner_r)

def warm_noise(img_rgba, seed=0, strength=3):
    """Add 0–strength warm noise in-place (red channel slightly boosted)."""
    rng = random.Random(seed)
    px  = img_rgba.load()
    w, h = img_rgba.size
    for y in range(h):
        for x in range(w):
            n = rng.randint(0, strength)
            r, g, b, a = px[x, y]
            px[x, y] = (clamp(r + n), clamp(g + max(0, n - 1)), clamp(b + max(0, n - 2)), a)
    return img_rgba

# ---------------------------------------------------------------------------
# Wallpaper 1 — Iron Mark
#
# Warm near-black surface. The WF logo sits large in the lower-right corner,
# rendered as a recessed dark-monochrome manufacturer's stamp (~22% opacity).
# A faint red radial glow radiates from behind the logo.
# ---------------------------------------------------------------------------

def make_iron_mark(w, h, logo):
    base = Image.new("RGBA", (w, h), (C_BG[0], C_BG[1], C_BG[2], 255))
    warm_noise(base, seed=11)

    # Logo size: 38% of screen height
    logo_h = int(h * 0.38)
    logo_w = int(logo_h * logo.width / logo.height)
    logo_r = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # Lower-right position with ~4% margin
    lx = w - logo_w - int(w * 0.04)
    ly = h - logo_h - int(h * 0.05)
    lcx, lcy = lx + logo_w // 2, ly + logo_h // 2

    # Red glow behind the logo
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd   = glow.load()
    inner = logo_w * 0.3
    outer = logo_w * 1.45
    y0, y1 = max(0, ly - logo_h),     min(h, ly + logo_h * 2)
    x0, x1 = max(0, lx - logo_w),     min(w, lx + logo_w * 2)
    for y in range(y0, y1):
        for x in range(x0, x1):
            t = radial_t(x, y, lcx, lcy, inner, outer)
            if t > 0:
                gd[x, y] = (clamp(C_ACCENT[0] * t), 0, 0, clamp(t * t * 85))

    base = Image.alpha_composite(base, glow)

    # Dark stamp: desaturate logo, map light→bg, dark→slightly-raised
    grey  = ImageOps.grayscale(logo_r)
    stamp = Image.new("RGBA", (logo_w, logo_h), (0, 0, 0, 0))
    sp    = stamp.load()
    gp    = grey.load()
    for y in range(logo_h):
        for x in range(logo_w):
            t = gp[x, y] / 255.0           # 0=black, 1=white in original
            # dark orig pixels → raised colour; light → bg (invisible)
            r = clamp(lerp(C_RAISED[0] + 14, C_BG[0], t))
            g = clamp(lerp(C_RAISED[1] + 9,  C_BG[1], t))
            b = clamp(lerp(C_RAISED[2] + 7,  C_BG[2], t))
            sp[x, y] = (r, g, b, clamp(215 * (1.0 - t * 0.65)))

    base.paste(stamp, (lx, ly), stamp)
    return base.convert("RGB")


# ---------------------------------------------------------------------------
# Wallpaper 2 — Red Foundry
#
# The WF logo centred at full opacity. Its own red (`#f80000`) bleeds
# outward as a radial gradient fading to `#1a1714` at the screen edges —
# the logo is the heat source.
# ---------------------------------------------------------------------------

def make_red_foundry(w, h, logo):
    base = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    px   = base.load()

    logo_h = int(h * 0.55)
    logo_w = int(logo_h * logo.width / logo.height)
    lx = (w - logo_w) // 2
    ly = (h - logo_h) // 2
    lcx, lcy = w // 2, h // 2

    corner_dist = math.sqrt((w / 2) ** 2 + (h / 2) ** 2)
    inner = min(logo_w, logo_h) * 0.30
    outer = corner_dist * 0.97

    for y in range(h):
        for x in range(w):
            t     = radial_t(x, y, lcx, lcy, inner, outer)   # 1=centre, 0=edge
            blend = 1.0 - t                                    # 0=centre, 1=edge
            c = lerp_color(C_ACCENT, C_BG, blend ** 1.7)
            px[x, y] = (c[0], c[1], c[2], 255)

    logo_r    = logo.resize((logo_w, logo_h), Image.LANCZOS).convert("RGBA")
    base.paste(logo_r, (lx, ly), logo_r)
    return base.convert("RGB")


# ---------------------------------------------------------------------------
# Wallpaper 3 — Globe Field
#
# The WF logo scaled to ~92% of screen height and ghosted (~12% opacity)
# centred-right. A thin red Forge-Horizon line cuts across at 55%. A small
# crisp logo instance sits in the lower-left corner.
# ---------------------------------------------------------------------------

def make_globe_field(w, h, logo):
    base = Image.new("RGBA", (w, h), (C_BG[0], C_BG[1], C_BG[2], 255))
    warm_noise(base, seed=99)

    aspect = logo.width / logo.height

    # Giant ghost logo
    ghost_h = int(h * 0.92)
    ghost_w = int(ghost_h * aspect)
    ghost   = logo.resize((ghost_w, ghost_h), Image.LANCZOS).convert("RGBA")
    gd      = ghost.load()
    for y in range(ghost_h):
        for x in range(ghost_w):
            r, g, b, a = gd[x, y]
            gd[x, y] = (r, g, b, clamp(a * 0.12))
    gx = int(w * 0.52) - ghost_w // 2
    gy = (h - ghost_h) // 2
    base.paste(ghost, (gx, gy), ghost)

    # Red horizon line + bloom at 55%
    horizon_y  = int(h * 0.55)
    bloom_down = int(h * 0.14)
    bloom_up   = int(h * 0.05)
    hotspot_x  = int(w * 0.35)

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gld  = glow.load()
    for y in range(h):
        dy = y - horizon_y
        if dy >= 0:
            t = dy / bloom_down
            if t > 1.0:
                continue
            base_a = (1.0 - t * t) * 130
            deep   = (55, 8, 8)
        else:
            t = (-dy) / bloom_up
            if t > 1.0:
                continue
            base_a = (1.0 - t * t) * 170
            deep   = C_ACCENT_DARK

        for x in range(w):
            dx    = (x - hotspot_x) / (w * 0.4)
            boost = math.exp(-dx * dx * 0.5) * 0.5
            alpha = clamp(base_a * (1.0 + boost))
            tt    = min(abs(dy) / (bloom_down if dy >= 0 else bloom_up), 1.0)
            color = lerp_color(C_ACCENT, deep, tt)
            gld[x, y] = (color[0], color[1], color[2], alpha)

    base = Image.alpha_composite(base, glow)

    # Core line
    core   = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd     = core.load()
    lthick = max(1, h // 540)
    for y in range(horizon_y - lthick, horizon_y + lthick + 1):
        if 0 <= y < h:
            for x in range(w):
                dx = (x - hotspot_x) / (w * 0.45)
                b  = 0.45 + 0.55 * math.exp(-dx * dx * 0.3)
                cd[x, y] = (255, clamp(30 * b), clamp(20 * b), clamp(218 * b))
    base = Image.alpha_composite(base, core)

    # Small crisp logo — lower-left
    small_h = int(h * 0.18)
    small_w = int(small_h * aspect)
    small   = logo.resize((small_w, small_h), Image.LANCZOS).convert("RGBA")
    margin  = int(h * 0.04)
    base.paste(small, (margin, h - small_h - margin), small)

    return base.convert("RGB")


# ---------------------------------------------------------------------------
# Metadata + dispatch
# ---------------------------------------------------------------------------

METADATA = {
    "FoundryLinux-IronMark": {
        "KPlugin": {
            "Authors": [{"Name": "World Foundry"}],
            "Description": "WF logo as a dark iron stamp in the lower-right, with a faint red heat glow.",
            "Id": "FoundryLinux-IronMark",
            "License": "CC-BY-SA-4.0",
            "Name": "Iron Mark",
        }
    },
    "FoundryLinux-RedFoundry": {
        "KPlugin": {
            "Authors": [{"Name": "World Foundry"}],
            "Description": "WF logo centred; molten red radiates outward from it into darkness.",
            "Id": "FoundryLinux-RedFoundry",
            "License": "CC-BY-SA-4.0",
            "Name": "Red Foundry",
        }
    },
    "FoundryLinux-GlobeField": {
        "KPlugin": {
            "Authors": [{"Name": "World Foundry"}],
            "Description": "Giant ghost logo behind a red horizon line; small crisp logo lower-left.",
            "Id": "FoundryLinux-GlobeField",
            "License": "CC-BY-SA-4.0",
            "Name": "Globe Field",
        }
    },
}

GENERATORS = {
    "FoundryLinux-IronMark":   make_iron_mark,
    "FoundryLinux-RedFoundry": make_red_foundry,
    "FoundryLinux-GlobeField": make_globe_field,
}

# ---------------------------------------------------------------------------
# Save + main
# ---------------------------------------------------------------------------

def save_wallpaper(name, img_full):
    base_dir   = DATA_DIR / name
    images_dir = base_dir / "contents" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    img_full.save(images_dir / "1920x1080.png", optimize=True)
    print(f"  {name}/contents/images/1920x1080.png")

    img_full.resize(HI, Image.LANCZOS).save(images_dir / "3840x2160.png", optimize=True)
    print(f"  {name}/contents/images/3840x2160.png")

    img_full.resize(THUMB, Image.LANCZOS).save(base_dir / "contents" / "screenshot.png", optimize=True)
    print(f"  {name}/contents/screenshot.png")

    with open(base_dir / "metadata.json", "w") as f:
        json.dump(METADATA[name], f, indent=2)
        f.write("\n")
    print(f"  {name}/metadata.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--logo", default=str(LOGO_PATH),
                        help="Path to wflogo.png")
    args = parser.parse_args()

    logo_path = Path(args.logo)
    if not logo_path.exists():
        raise FileNotFoundError(f"Logo not found: {logo_path}")

    logo = Image.open(logo_path).convert("RGBA")
    print(f"Logo: {logo_path} ({logo.width}×{logo.height})")

    for name, gen in GENERATORS.items():
        print(f"\n{name} …")
        save_wallpaper(name, gen(*FULL, logo))

    print("\nDone.")


if __name__ == "__main__":
    main()
