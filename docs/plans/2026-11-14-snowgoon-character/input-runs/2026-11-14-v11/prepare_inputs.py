#!/usr/bin/env python3
"""Recreate the four square Snowgoon view crops and their hash manifest."""

from hashlib import sha256
import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "concept-turnaround-2d-v11-input-layout.png"
GAME_CAPTURE = HERE.parents[3] / "diagnostics/snowgoon-2026-11-14/opening.png"
GAME_CROP = (885, 225, 1020, 375)
VIEWS = ("front", "left-profile", "back", "right-profile")
GUTTER = 4
TOP = 60
BOTTOM = 603


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    source = Image.open(SOURCE).convert("RGB")
    width, height = source.size
    if width % 4 or height < BOTTOM:
        raise ValueError(f"Unexpected source dimensions: {width}x{height}")
    panel_width = width // 4
    crop_height = BOTTOM - TOP
    if crop_height != panel_width:
        raise ValueError("Expected square source panel crops")

    records = []
    for index, label in enumerate(VIEWS):
        x0 = index * panel_width + GUTTER
        x1 = (index + 1) * panel_width - GUTTER
        crop = source.crop((x0, TOP, x1, BOTTOM))
        square = Image.new("RGB", (panel_width, panel_width), "white")
        square.paste(crop, (GUTTER, 0))
        raw_out = HERE / f"{label}.png"
        square.save(raw_out, format="PNG", optimize=False, compress_level=9)
        out = raw_out
        masked_region = None
        if label == "front":
            # Remove one isolated source-art fleck well clear of the twig itself.
            square = square.copy()
            masked_region = [149, 358, 157, 372]
            ImageDraw.Draw(square).rectangle(masked_region, fill="white")
            out = HERE / "front-cleaned.png"
            square.save(out, format="PNG", optimize=False, compress_level=9)
        record = {
            "label": label,
            "file": out.name,
            "sha256": digest(out),
            "source_crop_xyxy": [x0, TOP, x1, BOTTOM],
            "white_padding_px": {"left": GUTTER, "right": GUTTER},
            "dimensions_px": list(square.size),
        }
        if masked_region:
            record["raw_file"] = raw_out.name
            record["raw_sha256"] = digest(raw_out)
            record["masked_region_xyxy_in_crop"] = masked_region
        records.append(record)

    manifest = {
        "source": SOURCE.name,
        "source_sha256": digest(SOURCE),
        "source_dimensions_px": list(source.size),
        "color_mode": "RGB",
        "layout": "four equal, separated orthographic panels, left to right",
        "preprocessing": {
            "panel_split": "four equal-width columns",
            "crop_y_px_exclusive": [TOP, BOTTOM],
            "panel_edge_trim_px": GUTTER,
            "resize": "none",
            "labels_and_panel_dividers": "excluded from crops",
            "canvas": "square RGB white background, no alpha",
        },
        "review_notes": [
            "The detached front-view ink dash was masked in front-cleaned.png; the unmodified front.png crop is retained for traceability."
        ],
        "in_game_comparison": {
            "capture": "docs/diagnostics/snowgoon-2026-11-14/opening.png",
            "capture_sha256": digest(GAME_CAPTURE),
            "capture_dimensions_px": list(Image.open(GAME_CAPTURE).size),
            "snowgoon_crop_xyxy": list(GAME_CROP),
            "crop_file": "in-game-baseline.png",
            "crop_sha256": None,
            "measured_actor_bounds_in_capture_px_approx": [895, 237, 1009, 359],
            "authored_actor_height_m": 2.20,
        },
        "views": records,
    }
    game_capture = Image.open(GAME_CAPTURE).convert("RGB")
    game_crop = game_capture.crop(GAME_CROP)
    game_out = HERE / "in-game-baseline.png"
    game_crop.save(game_out, format="PNG", optimize=False, compress_level=9)
    manifest["in_game_comparison"]["crop_sha256"] = digest(game_out)
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
