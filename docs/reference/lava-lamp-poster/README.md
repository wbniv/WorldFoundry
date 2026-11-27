# The lava lamp: portrait A3

Open [poster.html](poster.html). [poster.png](poster.png) is a 300 DPI preview rasterised from the PDF. The poster is a **review draft** until Will approves its look: the research document's line "Poster visual review" then changes from pending to approved, and the next build drops the draft mark and exports `lava-lamp-a3.pdf` (one 297 × 420 mm page). Until then the export writes `lava-lamp-review-draft-a3.pdf`, which is not committed.

The subject is the lava lamp: the lamp in the World Foundry clock (a Cycles render), how it moves, what is in the bottle, a short history, six patents, and, in a tall side column, the level's own Forth. Every claim on the poster comes from [the research document](../lava-lamp-research.md), which was written first and gives each source's locator and what could not be found or was corrected. Each claim in `make_poster.py` carries a status, **verified**, **other source** or **ours**, and the statuses are the build gate. The page prints no status tag (Will, 2026‑11‑27: "remove (verify) and (ours) tags"): a sourced sentence ends in its superscript source numbers, which the footer lists with their links. The footer is that list alone: its explanatory and colophon note was removed (Will, 2026‑11‑27).

The Forth column prints three definitions from the shipped director (`ll-env`, `ll-heat0`, `ll-tick`), pretty-printed by `make_poster.pretty()`: one definition per block, `if` opening an indented block, `else` and `then` at its indent, a break after each store, a mailbox kept with its `read-mailbox`. Each level cell number is shown by its name from `wflevels/lava_lamp/lamp.py` (`BLOB0_Y` for 101, `STARTED` for 109, `P1` for 190; Will: "give mailbox numbers actual NAMES"). Mapping the names back gives the shipped code exactly, whitespace aside; the stack effect and a note sit above each block, outside the code, and the test checks each block against the shipped `lava_lamp.lev`.

`make_poster.py` refuses to build if a claim is unverified, if a verified claim has no source, if an ours claim names nothing that computes it, if a source's link or a patent's link is not in the research document, or (without `--draft`) while the visual review is pending. The level's numbers are not typed into the script: the blob count, the model's character over 20 simulated minutes and the Forth words are read from `wflevels/lava_lamp` (`model.py`, `lamp.py`, `forth.py`) at build time, and the test finds each printed Forth word in the shipped `lava_lamp.lev`.

Regenerate from the repository root:

```sh
task poster-lava-lamp-hero        # only after a change to the level's look: CPU Cycles in the Blender container
python3 docs/reference/lava-lamp-poster/make_qr.py                 # only after a change to patents.py (needs segno)
task poster-lava-lamp             # make_poster.py [--draft] and export_poster.py
task test-poster-lava-lamp        # the pytest guard, in the wf-linux-test container
```

- `render_hero.py` renders `hero-cycles.png` (720 × 1080) from `wflevels/lava_lamp/lava_lamp.blend`: each prelit surface becomes an emission of its baked shade times the tint the director writes, the wax is posed as on the engine's first frame (`model.warmed()` through `model.pose()`), Orange lava in Violet water, 16:40 in the base (Will, 2026‑11‑27; the digits shown by their visibility from the hour and minute, as the director's `ll-time` does), the level's camera and the engine's 60° view.
- `patents.py` holds the six patents as Google Patents gave them on 2026‑11‑26; `make_qr.py` writes `qr/<number>.svg` (segno, error level M). The QR SVGs are committed so the build and the tests run where segno is missing; the test regenerates and compares them where it is present.
- `make_poster.py` writes `poster.html` and the two editable drawings, `01-moves.svg` (the globe's cross-section on the model's own profile) and `02-bottle.svg` (a schematic density crossing).
- `export_poster.py` needs Python Playwright with Chromium and poppler's `pdftoppm`; it reuses the seahorse poster's exporter, changing only the PDF name, and writes the PDF, the PNG and `layout-review.json` (page size, smallest type 8.25 pt, no panel overflowing).
