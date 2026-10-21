# planted-tank-frame.png

A real capture of the plants-only Planted Tank level (`wflevels/planted-screensaver-cd.iff`, built from
`wflevels/planted_tank_screensaver`): no animals, no HUD. It is the source of the launcher icon and the TV banner
of the `planted` flavor. Re-run `python3 scripts/gen-screensaver-android-icons.py planted` after replacing it; the
file must stay 1280 x 720.

- **Source:** desktop engine (`wf_game`, Debug build without ASan) running the bundle through the cd.iff meta-loop in
  `wf-linux-test:local`, under Xvfb at 1920 x 1080 (`-width=1920 -height=1080`), with the VRAM switches of
  `scripts/planted-cycle-desktop-run.sh` and these overrides:
  `--property='PlantedTankSettings.Initial age=194'` (fully grown), `Water type=1` (**saltwater**), `Seed=713`,
  `Random seed on entry=0`, `Growth speed=1`. The frame is the X display read from Xvfb's framebuffer file
  (`-fbdir`) 42 s after launch. The engine's `--capture-frame` switch wrote nothing under the meta-loop, so it was not used.
- **Why saltwater 713:** of freshwater and saltwater at seeds 713, 48 and 1254 it filled the tank most evenly,
  from tall grass at the left to dense leaf bushes at the right, with no bare patches. Freshwater 713 (rosettes
  under grass) was the runner-up.
- **Seed strip and FPS counter:** a desktop run draws the seed strip (bottom-left, from y = 984 of the 1920 x 1080 frame)
  and an FPS counter (bottom-right). The Dream host hides the strip, the desktop does not. Both lie on the flat
  dark tank stand, so rows 978 to 1079 were overwritten with the clean row 960 (the stand and background colours are
  constant down each column), then the frame was resized to 1280 x 720 (Lanczos). Nothing of the tank is cropped: the
  whole tank, its stand and the dark background are in view, and no urchin, goby or seahorse is in the level.
- **Icon crop** (in `gen-screensaver-android-icons.py`): `(430, 200, 790, 560)` of this file, a 360 x 360 square
  on the grass-to-leaf transition. It excludes the glass, the top rail, the stand and the right-hand bushes' edge, and
  shows only a thin strip of sand at the bottom.
