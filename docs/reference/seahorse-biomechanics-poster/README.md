# Longsnout seahorse — portrait A3

Open [poster.html](poster.html); print [seahorse-biomechanics-a3.pdf](seahorse-biomechanics-a3.pdf) on matte or uncoated A3 stock. The PDF is one 297 × 420 mm page. [poster.png](poster.png) is a 300 DPI preview rasterised from the PDF.

The subject is the longsnout seahorse, *Hippocampus reidi*. Every claim on the poster comes from [the separate research document](../seahorse-research.md), which was written first and gives each source's DOI, locator, study species and access limits. Each printed claim carries one chip:

- **verified**: the source was read, and it says this about *H. reidi*;
- **other species**: the source was read, but it is about the species named in the text;
- **ours**: a game choice or our own measurement. Device results say **measured (ours)**; interpolated costs say **estimate (ours)**.

Claims the research could not confirm stay in the research document and are never printed. `make_poster.py` refuses to build if one is added. The eight drawings are original. The seahorses are drawn from the game's own 35-ring tail table, so the poster shows the game’s 35-ring control structure.

Regenerate from the repository root:

```sh
python3 docs/reference/seahorse-biomechanics-poster/make_poster.py
python3 docs/reference/seahorse-biomechanics-poster/export_poster.py
python3 -m pytest -q tests/test_poster_seahorse_biomechanics.py
```

`make_poster.py` writes `poster.html` and the eight editable SVG panels (`01-rings.svg` … `08-cost.svg`). `export_poster.py` needs Python Playwright with Chromium and poppler's `pdftoppm`. It writes the PDF, the PNG and `layout-review.json`, which records the page size, the smallest type size, each panel's overflow check and the footer's position. The export fails if anything overflows. The test also checks embedded fonts, type of at least 8 pt, blank 5 mm page edges, one link per source and no other link, and the absence of pending-verification wording.

## Measured population costs — 17 October

Panel 08 now uses the completed [cast1 close-view comparison](../../plans/2026-10-16-saltwater-seahorses/comparison.md#close-idle-and-close-crawl--completed-17-october)
in place of the old 74 ms baseline and estimated one/two-pair costs. Filled
points show the measured None / 1 / 2 / 6 populations; hollow points and dashed
segments show 3 / 4 / 5-pair estimates from frame-time interpolation. The CPU
inset splits the None-to-six increment into update and render; its animation
figure is already inside update. These are CPU `DFRM` workload measurements.

The current game default is six pairs. The separate husbandry citation still
concerns *H. erectus*; it does not establish a six-pair real-aquarium capacity.
All populations allocate twelve residents, and None also hides six posts.
`make_poster.py` reads the committed diagnostic comparison so printed values
come from the same evidence as the full report. The research document records
these measurements and their scope before they are used in the poster.

## From the implemented seahorses

The 17 October revision also updates three panels beyond the cost chart:

- **03 — Grip, hold, release:** authored joint limits beside schematic top
  views of grasping, holding and unwinding. The runtime coil follows the post;
  release precedes swimming and probing for the next grip.
- **06 — Six pairs share six holdfasts:** the greeting uses opposite sides of
  one post and different coil heights. A separate population diagram shows six
  pairs and six posts (not their spatial layout). Greetings rotate through
  visible pairs and check other residents' spot reservations. This choreography
  is marked ours; the biology supports occurrence in pairs, not this greeting.
- **07 — The model we built:** 1,101 triangles, two actors and 693 authored clip
  frames per seahorse; 25 shape controls expand to 105 joint angles. Seven
  exported-rig reference checks are explicitly distinguished from device
  measurements. Their scope and exact results are recorded in the research
  document, including the one-second pose transitions and hold-sway test.

All eight SVGs remain editable original diagrams. The grip and greeting
drawings are explanatory schematics, not engine screenshots or pose-validation
renders. The population chart and the CPU inset use the actual cast1 results;
three-to-five-pair values remain labelled estimates. No GPU-skinning result is
implied by these CPU-deformation measurements.
