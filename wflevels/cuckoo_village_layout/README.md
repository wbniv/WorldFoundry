# Cuckoo Village hillside layout prototype

This is a separate, editable 3D layout based on the [revised village plan](../../docs/plans/2026-11-21-cuckoo-village.md) and the existing [reusable asset source](../cuckoo_village_assets/generate.py). It has a rolling terrain and wooden base, winding lanes, thirteen cottages at varied angles and heights, a clock tower with a tiled roof, carved-wood case, four separately pivoted static figures and an exposed chime-and-gear mechanism in its base, a square, conifers, a stream, bridge and garden terrace. The cottages reuse the existing house mesh. The scene is still a stylized prototype: the tower is stylized artwork; its figures and cuckoo are separate meshes, while the chimes and gears are part of the static case, and none are animated yet; the bridge and garden are simple, the terrain does not yet flatten around foundations, and the asset set does not contain the other building and tree varieties in the concept.

- [Blender preview](preview.png) and [tower detail](tower-review.png) are renders. [Desktop engine capture](engine.png) shows the cooked level.
- `village_layout.blend` is the editable assembled scene; keep `village_atlas.tga` beside it.
- `tower_art.py` generates the decorative clock case and figures; `generate.py` regenerates the scene from `../cuckoo_village_assets/village_assets.blend`, so build the asset prototype first if that source is missing.
- `../cuckoo_village_layout-standalone.iff` is the cooked World Foundry prototype.

Build from the repository root with `bash wflevels/cuckoo_village_layout/build.sh`; use `WF_LEVEL_BUILD_HOST=1` with host Blender and built level tools. `blender --background --python-exit-code 1 --python wflevels/cuckoo_village_layout/render_reviews.py` refreshes the Blender reviews. `python3 wflevels/cuckoo_village_layout/check_desktop.py` launches the cooked level and captures `engine.png` using the desktop debug bridge.

This implements the physical layout only. The moving camera route and timed tower view, working clock and animated figures, lighting schedule, sound, screensaver integration, performance measurements and Chromecast acceptance remain future level work. The Blender preview's camera and light are for review; the exported level has a fixed wide camera.

## Tower art cost and texture

The Blender scene contains 21,206 tower triangles including the shell, hands, door, four figure meshes, bird, carved case, chimes and gears. The original village atlas and the dedicated 1024² carved-wood image are packed into a 2048² room texture page (the generated `Room0.tga` is 4,194,322 bytes). The carved image was generated with the imagegen tool; `carved-wood-source.png` is the editable source image and `tower-carved-wood.tga` is the build conversion. The desktop capture uses 2048² room slots. The Android host must provide compatible texture-page options; neither device performance nor the figures' animations have been verified for this layout.
