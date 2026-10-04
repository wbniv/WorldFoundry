# Quilt Night icon draft

Created with the built-in image-generation tool on 2026-10-04. The replacement
icon uses connected square-grid patches with exclusively horizontal/vertical
boundaries, replacing the rejected diagonal design. The matching banner uses
only this original icon as its reference, without publisher/community artwork.
Both prompts are archived alongside their generated raster sources.

- quilt-night-source.png: full-resolution generated raster source.
- quilt-night-icon.png: 512 px application icon.
- apple-touch-icon.png: 180 px phone browser home-screen artwork.
- favicon.png: 48 px browser favicon.
- quilt-night-banner-source.png: generated landscape banner source.
- quilt-night-banner.png: 320×180 Android TV launcher tile, including title.

Exports use ImageMagick resizing only; artwork is preserved. Android TV
packages quilt-night-icon.png as res/drawable-nodpi/app_icon.png. The platform
uses the game-specific favicon and touch icon on both web shells.

The TV banner is packaged in res/drawable-xhdpi/banner.png. Adaptive
foreground/background, monochrome artwork, production store assets and physical
launcher checks remain pending. Sources are raster, not layered design files.
