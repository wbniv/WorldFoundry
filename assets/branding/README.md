# World Foundry symbol

`world-foundry-mark.png` is the reusable, text-free symbol from the repository's
`wflogo.png`. It preserves the original 80 × 106 pixels inside the rectangle
`(3, 24, 83, 130)` (Pillow coordinates, right/bottom exclusive). The WORLD and
FOUNDRY lettering and the separate top-right red square are excluded. The
artwork's black, white, grey, and red areas are retained.

`world-foundry-icon-{16,32,48,64,128}.png` are square RGBA versions with transparent
side padding. The symbol keeps its aspect ratio, subject to pixel rounding.
The 128-pixel version is resampled from the original raster, not a vector master.

Regenerate these files and `wfsource/source/gfx/gl/world_foundry_icon.h` with
`python3 scripts/gen-window-icon.py` (requires Pillow), then run `task build`.
Generated files are checked in, so normal builds do not require Pillow.
The Linux game embeds the icon data and publishes it as `_NET_WM_ICON` before
the window appears. A window manager chooses the size used in its decorations.

These are derivatives of the existing World Foundry artwork; no new artwork
or separate license grant is introduced.
