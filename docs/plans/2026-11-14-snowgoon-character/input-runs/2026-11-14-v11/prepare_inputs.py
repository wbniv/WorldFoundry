#!/usr/bin/env python3
"""Recreate the four square Snowgoon view crops and their hash manifest."""

from hashlib import sha256
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "concept-turnaround-2d-v11-input-layout.png"
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
        out = HERE / f"{label}.png"
        square.save(out, format="PNG", optimize=False, compress_level=9)
        records.append({
            "label": label,
            "file": out.name,
            "sha256": digest(out),
            "source_crop_xyxy": [x0, TOP, x1, BOTTOM],
            "white_padding_px": {"left": GUTTER, "right": GUTTER},
            "dimensions_px": list(square.size),
        })

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
            "The front crop contains a small detached ink dash beside the left arm; review or mask before automated reconstruction."
        ],
        "views": records,
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
