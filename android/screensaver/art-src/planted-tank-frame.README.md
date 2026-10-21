# planted-tank-frame.png

**PROVISIONAL.** This is a placeholder until a capture of the plants-only Planted Tank level
(`wflevels/planted_tank_screensaver`, no animals, no HUD) replaces it. Replace the PNG at the same
size (1280 x 720) and re-run `python3 scripts/gen-screensaver-android-icons.py planted`.

- **Source frame:** `docs/plans/2026-10-03-aquatic-plant-clumps-and-poster/runtime-evidence/textured-device/saltwater-mature.png`
  (1920 x 1080 device capture, seed 713, saltwater, mature planting).
- **Crop box:** `(320, 184, 1600, 904)` in source pixels, giving 1280 x 720 (16:9). It contains the whole
  tank and its stand and stops above the seed strip (source y >= 984, bottom-left) and the FPS counter
  (source x >= 1800, y >= 1015, bottom-right).
- **Icon crop** (in `gen-screensaver-android-icons.py`): `(690, 201, 1050, 561)` of this file, a 360 x 360
  square on the planted section, equal to `(1010, 385, 1370, 745)` of the source frame. It lies inside the tank
  (no glass edge, stand or HUD) and right of the urchin. The plan's `make_art.py` used a 440 x 440 square
  of `freshwater-mature.png` instead, which also takes in the dark stand and glass.
- **Known defect:** the retained frame still shows the **sea urchin** (centre, near the sand; the icon crop avoids it, the banner does not). The final
  plants-only level has no animals, so the final art will not.
