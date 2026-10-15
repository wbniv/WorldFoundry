# Longsnout seahorse — portrait A3

Open [poster.html](poster.html); print [seahorse-biomechanics-a3.pdf](seahorse-biomechanics-a3.pdf) on matte or uncoated A3 stock. The PDF is one 297 × 420 mm page. [poster.png](poster.png) is a 300 DPI preview rasterised from the PDF.

The subject is the longsnout seahorse, *Hippocampus reidi*. Every claim on the poster comes from [the separate research document](../seahorse-research.md), which was written first and gives each source's DOI, locator, study species and access limits. Each printed claim carries one chip:

- **verified**: the source was read, and it says this about *H. reidi*;
- **other species**: the source was read, but it is about the species named in the text;
- **ours**: a game choice. The frame costs, which have not been measured yet, say **estimate (ours)**.

Claims the research could not confirm stay in the research document and are never printed. `make_poster.py` refuses to build if one is added. The eight drawings are original. The seahorses are drawn from the game's own 35-ring tail table, so the poster shows the rig the game will use.

Regenerate from the repository root:

```sh
python3 docs/reference/seahorse-biomechanics-poster/make_poster.py
python3 docs/reference/seahorse-biomechanics-poster/export_poster.py
python3 -m pytest -q tests/test_poster_seahorse_biomechanics.py
```

`make_poster.py` writes `poster.html` and the eight editable SVG panels (`01-rings.svg` … `08-cost.svg`). `export_poster.py` needs Python Playwright with Chromium and poppler's `pdftoppm`. It writes the PDF, the PNG and `layout-review.json`, which records the page size, the smallest type size, each panel's overflow check and the footer's position. The export fails if anything overflows. The test also checks embedded fonts, type of at least 8 pt, blank 5 mm page edges, one link per source and no other link, and the absence of pending-verification wording.
