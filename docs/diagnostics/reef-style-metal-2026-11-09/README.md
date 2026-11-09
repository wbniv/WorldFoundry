# Reef step 14, Metal half: style-shading sweep and GL/Metal scene, 2026‑11‑09

The spec is original step 14 ([plan](../../plans/2026-11-02-gulf-of-thailand-reef-tank.md)). With every new Camera field at 0, a capture sweep of all levels must be pixel-identical to the pre-change captures, on GL and on Metal. The shared shader test scene must match across the two backends within 1/255 per channel.

This record covers the Metal half: the [finishing plan](../../plans/2026-11-08-reef-tanks-finish.md), row 14.

**Run:** Codemagic `macos-style-metal`, build [6af14d475e8a84eec8dac383](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6af14d475e8a84eec8dac383), checkout `1cb09178`. It took 12 Mac minutes. The month's total went from 147 to about 159 of the 400-minute cap. The first attempt ([6af14ba38b1b3718612224de](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6af14ba38b1b3718612224de), about 3 min) stopped at the baseline configure: the worktree had no submodules. That is fixed in `1cb09178`.

| Part | Result |
|---|---|
| CI Metal can render it | **Yes.** Three Debug Metal engines built in about 75 s each, and every capture was written headless. |
| Sweep: baseline `fd9349c8` vs style `b03f5cb5`, 35 levels of the baseline tree | **32 identical, 2 differ by 1/255 on 1–2 pixels, 1 level asserts on both engines.** Strictly this fails "pixel-identical". |
| Shared scene, GL vs Metal (checkout `1cb09178`) | **Shading matches; the strict per-pixel gate fails on raster edges.** 99.97% of pixels are within 1/255. 94 and 96 isolated pixels exceed it, and 82 and 86 of those lie on a geometry edge. |

## Sweep

Both engines render every `*-standalone.iff` of the baseline tree (`fd9349c8`) with the same flags as the GL test: frame 20 of a 30-step, 1-cycle, `-rate20` run, using the VRAM table in `tests/fixtures/renderer/style-scene.json`. Then `tests/compare_renderer_frames.py` compares the pair at tolerance 0. The full per-level list is in [summary.tsv](summary.tsv).

| Level | Verdict | Detail |
|---|---|---|
| 32 others | identical | — |
| `aquarium_arowana` | differs | 1 pixel at (49, 264), channel delta 1 ([log](compare-aquarium_arowana.log)) |
| `snowgoons-blender` | differs | 2 pixels, channel delta 1 ([log](compare-snowgoons-blender.log)) |
| `baseline` | no capture | Both engines assert: `Probably have a polygon which is too small` in `math/vector3.hpi` ([excerpt](sweep-baseline-level-assert.txt)). This is not a style difference. |

The workflow renders each engine once, so it cannot tell whether those 3 pixels are run-to-run noise or a real 1-LSB shader rounding change. That would take a second Metal run of the same engine (about 12 minutes). The GL repeats of the scene below are byte-identical, so Linux GL at least is deterministic.

## Shared style scene

The scene definition is `tests/fixtures/renderer/style-scene.json`:
- Realistic reef (S1 water absorption: `WaterAbsorb` 0.016 / 0.009 / 0.004).
- Anime reef (S3 toon bands: `ToonBands` 3).
- Both use `ReefSettings` Layout = Random with Seed 7, so layout and fish are deterministic, and both capture frame 20.

S2 caustics ship off and are not in the scene; they have their own cast1 gate. GL here is a Debug container build with `-DDESIGNER_CHEATS=1`; without that, `--capture-frame` writes nothing on Linux. Two GL renders of each scene are byte-identical.

| Scene | Exact | Δ = 1 | Δ > 1 | of which on a geometry edge | Max Δ |
|---|---|---|---|---|---|
| reef-realistic-s1 | 260,076 | 47,030 | 94 | 82 | 113 |
| reef-anime-s3 | 303,904 | 3,200 | 96 | 86 | 179 |

There are 307,200 pixels in each frame.

[![Linux GL, Metal and the pixels over 1/255, for both scenes](scene-gl-vs-metal.jpg)](scene-gl-vs-metal.jpg)

The absorption and band math agree to 1/255 across both frames. The 47,030 Δ = 1 pixels in the realistic frame are the absorption blend rounding differently. The pixels beyond 1/255 are single pixels along silhouettes (fins, antennae, coral tips), where the two rasterizers decide coverage differently. The aquarium parity gate meets the same effect; it allows a per-pixel tolerance of 3, with a coverage IoU. The plan's "within 1/255 per channel" does not allow for coverage differences on edges, so as written it cannot pass on any textured scene with fine geometry.

## Decision needed

The strict reading of both checks fails, and only by a handful of pixels. Someone needs to choose one of these:

1. **Gate as now measured:** the sweep allows a channel delta of 1 on at most a few pixels, and the scene is "within 1/255 on all but edge pixels", for example at most 0.05% of pixels beyond 1/255.
2. **Keep the strict gates** and investigate:
    - Rerun the Metal sweep to split noise from rounding.
    - Build a geometry-only scene that has no sub-pixel silhouettes.

## Reproduce

```sh
# Metal: manual workflow (about 12 Mac minutes; check scripts/codemagic-budget.sh first)
python3 ~/.config/claude/will/skills/codemagic-build/codemagic.py build --workflow macos-style-metal --branch 2026-new-level
# GL comparison, with the artifacts' style-metal/ directory and a DESIGNER_CHEATS Debug engine
scripts/in-linux-container.sh bash -c 'Xvfb :9 & export DISPLAY=:9 WF_STYLE_METAL_DIR=<style-metal dir> WF_STYLE_GL_ENGINE=<engine>; python3 -m pytest -q tests/test_style_shading_invariant.py -k metal'
```
