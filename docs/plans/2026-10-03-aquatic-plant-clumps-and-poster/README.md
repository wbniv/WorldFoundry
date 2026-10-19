# Aquatic plants A3 poster

Original botanical vector schematics; bibliography and design rationale are in the adjacent plan. `aquatic-plants-a3.pdf` is one A3 portrait page (297 × 420 mm), with no page margins. Print at actual size on A3.

Regenerate SVG diagrams and print HTML:

```sh
python3 docs/plans/2026-10-03-aquatic-plant-clumps-and-poster/generate-poster.py
```

Render `poster-print.html` with Chrome headless using `--no-pdf-header-footer --print-to-pdf=<absolute PDF path>` and its file URL. Use a separate temporary user-data directory. `pdftoppm -scale-to 1680 -png -singlefile` creates the review PNG. `pdfinfo` verifies one page at A3 portrait dimensions. The SVG is the editable vector master; the PDF preserves vector paths and text.

`plant-helpers.fth` contains illustrative arithmetic helpers, not a complete growth simulator. `forth-verification.json` records real zForth execution of nine arithmetic and boundary cases.
