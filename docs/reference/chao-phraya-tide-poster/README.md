# The tide at Bangkok — portrait A3

Open [poster.html](poster.html); print [chao-phraya-tide-a3.pdf](chao-phraya-tide-a3.pdf) on matte or uncoated A3 stock (the 2026‑10‑06 print was too glossy). The PDF is one 297 × 420 mm page. [poster.png](poster.png) is a 300 DPI preview rasterised from the PDF.

The subject is the tide of the Chao Phraya at Bangkok, as the Royal Thai Navy Hydrographic Department predicts it at station HD (Royal Thai Navy Headquarters), and how a computer adds it up from harmonic waves. Every claim on the poster comes from [the research document](../chao-phraya-tide-research.md), which was written first and gives each source's locator and what could not be found. Each printed claim wears one chip:

- **verified**: the source was read, and it says this about this station or river;
- **other source**: the source was read, but it is about a numerical model or another place;
- **ours (measured)**: computed by us from the sources, by a script in `wflevels/tide_harbour/tide_fit/`. The two statements that are not measurements say **design (ours)** or **limit (ours)**.

Claims the research could not confirm stay in the research document and are never printed. `make_poster.py` refuses to build if one is added, if a verified claim has no source, or if an ours claim does not name what computes it. The numbers are not typed into the script: it reads them from `wflevels/tide_harbour/tide_constants.json` and `time_zone_check.json` (written by the fit scripts) and from the Navy's printed table. The eight drawings are original.

Regenerate from the repository root:

```sh
bash wflevels/tide_harbour/tide_fit/fetch_sources.sh      # once: one request per file, a pause between
python3 -I wflevels/tide_harbour/tide_fit/make_constants.py
python3 -I wflevels/tide_harbour/tide_fit/count_turns.py --json wflevels/tide_harbour/turning_points.json
python3 -I wflevels/tide_harbour/tide_fit/check_time_zone.py --json wflevels/tide_harbour/time_zone_check.json
python3 docs/reference/chao-phraya-tide-poster/make_poster.py
python3 docs/reference/chao-phraya-tide-poster/export_poster.py
python3 -m pytest -q tests/test_poster_chao_phraya_tide.py
```

`make_poster.py` writes `poster.html` and the eight editable SVG panels (`01-days.svg` … `08-harbour.svg`; panel 08 embeds `08-harbour-engine.png`). `export_poster.py` needs Python Playwright with Chromium and poppler's `pdftoppm`; it reuses the seahorse poster's exporter, changing only the PDF name, and writes the PDF, the PNG and `layout-review.json`, which records the page size, the smallest type (8.25 pt) and that no panel overflows.

The harbour picture in panel 08 is the engine's own drawing of the finished level, with its river panel (`08-harbour-engine.png`, 2026‑11‑22), not a sketch. Redo it after a change to the level's look:

```sh
scripts/in-linux-container.sh bash -c 'xvfb-run -a -s "-screen 0 1280x720x24" python3 scripts/check-tide-harbour.py \
    --capture build/poster-capture --no-fps --times 2026-01-08T17:51:00'      # the engine built as the script's header says
cp build/poster-capture/20260108T175100.png docs/reference/chao-phraya-tide-poster/08-harbour-engine.png
```

The moment, 8 January 17:51 Thai time, is the "now" dot on panel 08's tide curve; if you change one, change the other, and the readings quoted in the panel's first claim (`turns.py --at` computes them).
