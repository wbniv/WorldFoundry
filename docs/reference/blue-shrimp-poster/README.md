# Blue shrimp A3 poster

One-page A3 portrait poster for the [mixed shrimp content plan](../../plans/2026-10-03-aquarium-blue-shrimp-varieties.md). Both varieties have Blender and in-game panels; anatomy/motion diagrams and sourced biology remain alongside the game choices.

Open [poster.html](poster.html); print [blue-shrimp-a3.pdf](blue-shrimp-a3.pdf) at actual size. The rebuilt PDF was rasterized and visually checked: one 297 × 420 mm page, with all captions and footer inside the page.

Blender panels use the actual exported Jelly/Dream meshes, shared camera and studio checker backdrop. Regenerate with `blender --background --python-exit-code 1 --python docs/reference/blue-shrimp-poster/render_models.py`. Blender 5.0.1 / Cycles, 48 samples, Standard view transform, 1200 × 650 pixels; Jelly shell 0.28, appendages 0.18, eyes 1.0; original Dream 1.0.

In-game panels are unretouched crops of [the initial Chromecast HD game capture](../../plans/2026-10-03-aquarium-blue-shrimp-varieties/device/blue-shrimp-screen.png), 1920 × 1080, Android release / GLES. Crop rectangles (left, top, right, bottom): Jelly (420, 470, 965, 765); Dream (890, 505, 1370, 765). They show the native tank backdrop rather than an isolated studio model. The [optimized release capture](../../plans/2026-10-03-aquarium-blue-shrimp-varieties/device/blue-shrimp-optimized.png) is additional runtime evidence; the batching optimization preserves the visual material settings.
