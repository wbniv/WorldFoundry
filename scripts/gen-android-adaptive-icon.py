#!/usr/bin/env python3
"""Generate Android adaptive-icon foreground rasters from in-repo source art.

World Foundry has no vector master for its launcher mark (wflogo.png / the
mipmap-xxxhdpi/ic_launcher.png it was rendered from are both raster). Rather
than hand-trace a vector approximation, this script derives the adaptive-icon
foreground bitmaps directly from the existing legacy square icon: the square
mark is padded onto a transparent 108dp canvas at each mipmap density, scaled
down so it sits entirely inside the adaptive-icon "safe zone" (the inner ~66dp
of the 108dp canvas that survives every launcher mask shape — circle, squircle,
rounded square, Android 13 themed cutout). The background layer is a flat
color (see res/values/colors.xml) rather than a bitmap, since the source
icon's corners are solid black.

The second launcher entry (WF Log Viewer) gets its own foreground: a plain
document glyph drawn programmatically (no source art exists for it), on a
distinct background color so the two launcher icons read as different at a
glance per docs/plans/2026-04-18-android-launcher-polish.md step 4.

Re-run this whenever the source mipmap-xxxhdpi/ic_launcher.png changes; it
overwrites the generated mipmap-*/ic_launcher_foreground.png and
mipmap-*/ic_launcher_log_foreground.png files deterministically.

Usage:
    scripts/gen-android-adaptive-icon.py [-h]
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageDraw

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RES_DIR = REPO_ROOT / "android" / "app" / "src" / "main" / "res"
SOURCE_ICON = RES_DIR / "mipmap-xxxhdpi" / "ic_launcher.png"

# Android adaptive-icon canvas is 108dp square; only the inner ~66dp survives
# every mask shape, so foreground content is scaled to SAFE_ZONE_SCALE of the
# canvas, centered, leaving transparent padding on all sides.
SAFE_ZONE_SCALE = 0.60

# density -> pixels-per-108dp (108dp * density bucket scale factor), used for
# the adaptive-icon foreground layers (mask-cropped by the launcher at runtime).
DENSITIES = {
    "mdpi": 108,
    "hdpi": 162,
    "xhdpi": 216,
    "xxhdpi": 324,
    "xxxhdpi": 432,
}

# density -> pixels-per-48dp, the classic pre-API-26 legacy icon size (matches
# the existing mipmap-*/ic_launcher.png assets already in the tree).
LEGACY_DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

LOG_VIEWER_BACKGROUND = (27, 39, 51, 255)  # #1B2733 — distinct from the main black


def make_main_foreground(size: int) -> Image.Image:
    """Pad the existing WF mark onto a transparent size x size canvas."""
    source = Image.open(SOURCE_ICON).convert("RGBA")
    mark_size = round(size * SAFE_ZONE_SCALE)
    mark = source.resize((mark_size, mark_size), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - mark_size) // 2, (size - mark_size) // 2)
    canvas.paste(mark, offset, mark)
    return canvas


def _draw_log_glyph(canvas: Image.Image, size: int) -> None:
    """Draw the document glyph onto an existing size x size RGBA canvas."""
    draw = ImageDraw.Draw(canvas)

    mark_size = round(size * SAFE_ZONE_SCALE)
    x0 = (size - mark_size) // 2
    y0 = (size - mark_size) // 2

    # Page body with a folded top-right corner, in the same off-white used by
    # the main mark's text bars so the two icons read as one family.
    page_w = mark_size
    page_h = mark_size
    fold = round(page_w * 0.28)
    page = [
        (x0, y0),
        (x0 + page_w - fold, y0),
        (x0 + page_w, y0 + fold),
        (x0 + page_w, y0 + page_h),
        (x0, y0 + page_h),
    ]
    draw.polygon(page, fill=(238, 238, 238, 255))
    # Folded corner triangle, slightly darker to read as a fold.
    draw.polygon(
        [
            (x0 + page_w - fold, y0),
            (x0 + page_w, y0 + fold),
            (x0 + page_w - fold, y0 + fold),
        ],
        fill=(170, 170, 170, 255),
    )

    # A few horizontal "text lines" in the WF red accent so it visually
    # relates to the main mark's red accent block.
    line_h = max(1, round(page_h * 0.045))
    margin = round(page_w * 0.16)
    for i, frac in enumerate((0.42, 0.55, 0.68, 0.81)):
        y = y0 + round(page_h * frac)
        x_end = x0 + page_w - margin - (fold if i == 0 else 0)
        draw.rectangle(
            [x0 + margin, y, x_end, y + line_h],
            fill=(200, 30, 30, 255),
        )


def make_log_viewer_foreground(size: int) -> Image.Image:
    """Transparent adaptive-icon foreground: document glyph, no source art."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _draw_log_glyph(canvas, size)
    return canvas


def make_log_viewer_legacy(size: int) -> Image.Image:
    """Flattened pre-API-26 icon: glyph over an opaque background fill."""
    canvas = Image.new("RGBA", (size, size), LOG_VIEWER_BACKGROUND)
    _draw_log_glyph(canvas, size)
    return canvas


PREVIEW_DIR = (
    REPO_ROOT / "docs" / "plans" / "2026-04-18-android-launcher-polish"
)
PREVIEW_SIZE = 432  # xxxhdpi (108dp @ 4x) — matches the highest-res mipmap


def write_previews() -> None:
    """Composite foreground-over-background at 108dp for reviewer sign-off.

    Not shipped in the APK — this is a rendered reference so a reviewer can
    see what the launcher will draw without installing on a device. Written
    into the plan's bundle dir per docs/plans/2026-04-18-android-launcher-polish.md.
    """
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    main_bg = Image.new("RGBA", (PREVIEW_SIZE, PREVIEW_SIZE), (0, 0, 0, 255))
    main_bg.alpha_composite(make_main_foreground(PREVIEW_SIZE))
    main_path = PREVIEW_DIR / "ic_launcher_preview.png"
    main_bg.convert("RGB").save(main_path)
    print(f"wrote {main_path.relative_to(REPO_ROOT)}")

    log_bg = Image.new("RGBA", (PREVIEW_SIZE, PREVIEW_SIZE), LOG_VIEWER_BACKGROUND)
    log_bg.alpha_composite(make_log_viewer_foreground(PREVIEW_SIZE))
    log_path = PREVIEW_DIR / "ic_launcher_log_preview.png"
    log_bg.convert("RGB").save(log_path)
    print(f"wrote {log_path.relative_to(REPO_ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help=(
            "Only (re)render the composited 108dp preview PNGs into the "
            "plan's bundle dir; skip regenerating the shipped mipmap assets."
        ),
    )
    args = parser.parse_args()

    if not SOURCE_ICON.exists():
        print(f"error: source icon not found: {SOURCE_ICON}", file=sys.stderr)
        return 1

    if args.preview_only:
        write_previews()
        return 0

    if not SOURCE_ICON.exists():
        print(f"error: source icon not found: {SOURCE_ICON}", file=sys.stderr)
        return 1

    for density, size in DENSITIES.items():
        density_dir = RES_DIR / f"mipmap-{density}"
        density_dir.mkdir(parents=True, exist_ok=True)

        main_fg = make_main_foreground(size)
        main_path = density_dir / "ic_launcher_foreground.png"
        main_fg.save(main_path)
        print(f"wrote {main_path.relative_to(REPO_ROOT)} ({size}x{size})")

        log_fg = make_log_viewer_foreground(size)
        log_path = density_dir / "ic_launcher_log_foreground.png"
        log_fg.save(log_path)
        print(f"wrote {log_path.relative_to(REPO_ROOT)} ({size}x{size})")

    for density, size in LEGACY_DENSITIES.items():
        density_dir = RES_DIR / f"mipmap-{density}"
        density_dir.mkdir(parents=True, exist_ok=True)

        legacy = make_log_viewer_legacy(size).convert("RGB")
        # Square and round variants are identical, matching the existing
        # mipmap-*/ic_launcher.png / ic_launcher_round.png convention (the
        # launcher applies its own mask; both files carry the same bitmap).
        square_path = density_dir / "ic_launcher_log.png"
        round_path = density_dir / "ic_launcher_log_round.png"
        legacy.save(square_path)
        legacy.save(round_path)
        print(f"wrote {square_path.relative_to(REPO_ROOT)} ({size}x{size})")
        print(f"wrote {round_path.relative_to(REPO_ROOT)} ({size}x{size})")

    write_previews()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
