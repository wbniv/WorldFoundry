# Atkinson Hyperlegible Next (build-time UI font)

Unmodified Atkinson Hyperlegible Next Regular and SemiBold from the pinned Google Fonts project commit [7925f50](https://github.com/googlefonts/atkinson-hyperlegible-next/tree/7925f50f649b3813257faf2f4c0b381011f434f1/fonts/ttf), byte-identical to the copies in `../finding-your-way/game/parmenides-slice/fonts/`. Redistributed under the [SIL Open Font License 1.1](Atkinson-OFL.txt).

`scripts/bake-ui-font.py` rasterizes them in the Linux test container into `ui-font.wfga`, the engine's shared UI glyph atlas (`docs/plans/2026-10-17-settings-editor-font.md`). The engine never reads these TTF files at runtime; it only reads the baked pixels and metrics. The phone controller page (`wfsource/source/hal/phonepad/controller.html`) embeds a WOFF2 subset of the same two files.

| File | SHA-256 |
| --- | --- |
| AtkinsonHyperlegibleNext-Regular.ttf | `88ed5c31a71584c7772963b02d04bef1eb7e3d2e9c8b9cb204339b1f82cf432c` |
| AtkinsonHyperlegibleNext-SemiBold.ttf | `8e2fff779f35ac25239656bb0f3b2bd35959a2009e3dd21a12141c3b9030362b` |
