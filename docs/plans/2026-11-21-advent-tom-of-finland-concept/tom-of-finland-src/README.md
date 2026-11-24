# Tom of Finland-inspired Advent concept: how to rebuild it

Two steps, both from the repo root. The scene is built and rendered headless in the `blender` container ([`docker/Dockerfile.blender`](../../../../docker/Dockerfile.blender), listed in the container registry); the ink pass is plain Python with numpy and Pillow.

```bash
mkdir -p build-docker/advent
WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender -b \
  -P docs/plans/2026-11-21-advent-tom-of-finland-concept/tom-of-finland-src/build_scene.py -- \
  --out /build/advent/raw.png --width 1920 --samples 64        # about 12 min on CPU
python3 -I docs/plans/2026-11-21-advent-tom-of-finland-concept/tom-of-finland-src/ink_post.py \
  build-docker/advent/raw.png docs/plans/2026-11-21-advent-tom-of-finland-concept/tom-of-finland-concept.png
```

- `build_scene.py`: four townhouses with 24 numbered advent doors (shuffled by a fixed seed, days 1 to 6 open), four clothed adult men, lamps, garlands, a fir and a snowman, Cycles on CPU, Freestyle outlines.
- `ink_post.py`: converts tone to diagonal and cross hatching, keeps the door numerals un-hatched, adds a thin colour wash and paper grain.
- Use `--width 960 --samples 24` for a quick preview.

## Plain renders from other cameras

`build_scene.py --views` takes `poster` (the hatched drawing's framing), `men_left`, `men_close`, `doors` and `high`; `--ink 0` turns Freestyle outlines off. `{view}` in `--out` becomes the view name. Clean the grain afterwards with Intel OIDN, which the container carries (its Blender has no denoiser of its own); `denoise.py` falls back to a bilateral filter where `oidnDenoise` is missing:

```bash
WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender -b \
  -P docs/plans/2026-11-21-advent-tom-of-finland-concept/tom-of-finland-src/build_scene.py -- \
  --out "/build/advent/real-{view}.png" --views men_left,men_close,doors,high --ink 0 --width 1600 --samples 128
WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh python3 -I \
  /src/docs/plans/2026-11-21-advent-tom-of-finland-concept/tom-of-finland-src/denoise.py \
  /build/advent/real-men_left.png /build/advent/dn-men_left.png   # then copy to renders/men-left.png
```

`--views none` builds the scene and prints its statistics without rendering.
