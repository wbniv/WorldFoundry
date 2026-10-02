# World Foundry app badge standard

Status: set D approved by the user on 2026-10-02.

Applies to every current and future World Foundry game icon and TV banner. The game artwork fills the tile; the World Foundry graphic is stamped at bottom-right. TV banners also carry the game name bottom-left.

## Source and crop

Use the repository's [wflogo.png](../../wflogo.png), never the website favicon. Preserve the original source file. Its size is 108 × 133 pixels; the graphic panel is the Pillow crop box **(4, 25, 82, 129)**, with right and bottom exclusive. This removes the top WORLD and right FOUNDRY lettering and all black frame borders, and retains the globe/diagonal/red-square graphic. Keep that 78 × 104 graphic rectangular, preserving aspect ratio, with no square tile or extra side padding. Retain the light grey globes and original white background. Use Lanczos resizing. Add no outer border (white or black) and no side padding.

## Shared implementation

Use [scripts/add-wf-logo.py](../../scripts/add-wf-logo.py) for every stamp. The default reads and crops the original logo automatically; `--logo` accepts an already cropped alternate PNG. Always stamp clean source artwork rather than stamping over a previously badged image.

```bash
scripts/add-wf-logo.py clean-icon.png -o branded-icon.png
scripts/gen-android-icons.py  # regenerate all Android games from clean art
```

| Asset | Badge longer side / shorter canvas side | Placement |
|---|---:|---|
| Legacy square | 0.26 | 0.05 edge margin |
| Legacy round | 0.24 | Inside circle, along bottom-right 45° radius |
| Adaptive foreground | 0.17 | Inside visible circle of diameter 72/108 of canvas |
| TV banner | 0.22 | 0.05 edge margin |

For round and adaptive assets, the entire rectangular badge must stay inside the visible circle. Keep the shared generator's scale and placement parameters for future games. Inspect both square and circular previews before shipping; use fresh APKs and verify the installed resources, since Google TV caches tile art.

This standard supersedes the favicon choice in the [2026-10-01 icons plan](../plans/2026-10-01-android-icons.md).
