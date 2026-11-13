# Snowgoons one-acre yard — implementation evidence

Implemented 2026-11-13/14 from the [arena plan](../../plans/2026-11-13-snowgoons-one-acre-arena.md).
The classic Android/web level has a level 60 × 68 m lawn: **4,080 m²**, 1.008 acre.
The house, trees, rooms, lighting and player horizontal spawn are retained.
The player starts at Z −0.60; the lawn is Z −0.62. Fog distances are 40 / 100 m.

## Implemented assets and build

`wflevels/snowgoons-blender/make_yard.py --lev` writes `yard01.iff` and patches
only the classic `snowgoons.lev`. The yard has **808 vertices / 1,070 triangles**.
Its MATL bytes equal the original arena's; lawn, hedge-side and hedge-top textures
are retained. Mirrored adjacent UVs share hedge vertices. UVs stay inside each
32² texture's edge texels to avoid atlas colour bleeding under filtering.

`task snowgoons-yard` generates; `task snowgoons-level` builds all three classic
bundles through the Linux container and cdpack. `WF_LEVEL_DIR` selects the existing
source directory; `WF_TEXTILE_OUT_DIR=classic-atlas` separates the classic atlases.
Room assignment uses the world bounding-box centre, so the larger yard belongs
to Room0. Reusing shared atlas filenames changed the Blender intermediates;
isolating them avoids that. `unchanged-scaffold.json` verifies byte equality
against the pre-change shared mesh, source level, atlases and Blender bundles.

## Physics checks and corrections

The first proposed slab used local Z −1…0 with the actor on the lawn. GDB contact
evidence (`contacts.log`) found its collision surface **0.5 m above the lawn**:
existing box-body position updates discard the local centre offset. All five
colliders now have symmetric local boxes centred on their actors, retaining the
planned world bounds. This is a level-data correction; no engine source changed.

The tiled two-sided trimesh and slab together also produced seam hops. The yard
therefore uses the existing **anchored Platform** class for rendering, while the
slab and four walls exclusively provide collision. Its authored name remains
`statplat_2`; no new actor type is introduced.

`verify_desktop.py` holds normal forward input with explicit headings, samples
position every simulated second, and releases input between segments. Its full
route covers 166 simulated seconds: south wall, east wall, west wall, north wall,
then across the rear of the house. All 167 samples stay between
**−0.621842 and −0.621841 m** in Z. Wall stops are Y −45.64777, X ±29.64777,
and Y 21.64777. See `walk-positions.json`, `validation.json` and the desktop PNGs.
These physics results precede the UV/vertex-sharing adjustment; collision geometry
and authored collider bounds are identical in the final build.

The pre-change observation (`baseline-positions.json`) showed a stable original
player Z around −0.01659 over ten wall-clock seconds; falling was not observed.
The baseline script was run before overwriting the classic bundle.

## Memory and tests

The original proposal used 260,576 / 300,000 room bytes at load, below the plan's
25% free-headroom requirement. The classic standalone ROOM budget is now 400,000.
`inspect-final.log` records a GDB reading after 20 frames with the final mesh.
These readings describe occupied storage at those boundaries, not continuous
measurement of every transient allocation. The standalone wrapper is embedded in
the Snowgoons CD bundle; legacy CD copies retain their existing configuration.

- `geometry-tests.txt`: **8 passed**, including shipped-model equality in the
  inner, standalone and CD bundles, measured area, winding, UVs, centred colliders,
  deterministic generation, idempotent patching and shared-atlas preservation.
- `reference-check.txt`: **2 passed**, Snowgoons Blender and aquarium frames,
  without regenerating either reference.
- Plan rendering completed with no Mermaid failure warning.

The broad Android suites returned 39 passed, 14 failed, 1 skipped. Failures include
older tests rejecting the newer UIFT TOC chunk and common APK assets, stale
unrelated built APKs, and a test still expecting direct device-launch tasks.
The focused yard tests independently verify the current three bundles. The
test APK's embedded CD bytes equal the current CD bundle.

## Desktop reproduction

All gameplay ran in `wf-linux-test:local`, using Xvfb. The acceptance binary is
`build-docker/snowgoons-acceptance/wf_game`, built from the existing isolated engine
source snapshot (used by the lifetime work), with lifetime diagnostics and ASan
off, Jolt/zforth, debug symbols and `DESIGNER_CHEATS=1` for frame capture. This
avoids unrelated unfinished engine edits in the shared worktree; no engine source
was edited for the arena.

```sh
task snowgoons-level
scripts/in-linux-container.sh python3 -m pytest tests/test_snowgoons_one_acre_yard.py tests/test_snowgoons_arena_faces_up.py -v -s
scripts/in-linux-container.sh python3 tests/run_lifetime_headless.py python3 docs/diagnostics/snowgoons-one-acre-2026-11-13/verify_desktop.py
scripts/in-linux-container.sh python3 tests/run_lifetime_headless.py env WF_GAME=/build/snowgoons-acceptance/wf_game python3 -m pytest tests/test_renderer_references_fresh.py -v
```

## Chromecast verification

The frozen APK is an **asset-only rebuild** of the existing Snowgoons release:
`scripts/swap-apk-assets.py` replaces `assets/cd.iff`, aligns and signs the result.
All native libraries and Java payload entries remain byte-identical. The final
candidate is `build-docker/snowgoons-one-acre/snowgoons-shared-vertices.apk`.
`validation.json` records its identity and coordinator jobs.

Baseline recording J‑3bcbf7bda27c and inset-UV recording J‑6cb91628968d both
completed on Chromecast HD using the same 60-second input score. The first
baseline submission required automatic transport recovery; the coordinator
retried it under ownership. The intermediate acre recording J‑804808b51b85
also completed. Device screenshots show the house retained, tiled lawn and
the player reaching a far hedge. The inset-UV capture removes the coloured grid
visible in the first acre recording. No fatal exception/signal or FatalError
appeared in the final inset-UV session's logcat.

`wf.log` contains historical FPS CHECK rows shared by the runs; they are not
current-session performance evidence. `fps_ocr.py` samples the visible FPS
counter and retains crops, but coverage is incomplete and the numbers are noisy.
The recording's encoded FPS is also not gameplay FPS. Use the coordinator's
separate SurfaceFlinger profile comparison for the performance verdict below.


### Final device results

The shipping shared-vertex mesh completed its 60-second held-input recording,
J‑0707cd5a14a5 (`device-shipping/`), reaching the far hedge with no fatal error.
Its screenshots retain the clean inset-UV seams. The APK/native payload check
and bundle equality checks pass.

SurfaceFlinger profiling used the same Chromecast HD, three runs per APK,
10-second warm-up and 12-second measurement windows, without recording overhead.
Both traces have no sampling holes:

| Build | Run 1 FPS | Run 2 FPS | Run 3 FPS | Median FPS |
|---|---:|---:|---:|---:|
| Original (J‑2e6d001dd38b) | 59.0441 | 59.3612 | 59.3612 | 59.3612 |
| Acre (J‑849e50e3e5f0) | 29.9700 | 59.4432 | 59.5266 | 59.4432 |

The median meets the parity target, but the acre's first run held half refresh.
Do not erase that outlier or describe all runs as equivalent. The 30-second warm-up confirmations were:


| Build | Confirmation run 1 FPS | Confirmation run 2 FPS |
|---|---:|---:|
| Original (J‑f07e4ef2d3aa) | 51.6838 | 59.0429 |
| Acre (J‑ddc5d83b5573) | 45.7073 | 59.1121 |

Across all five runs per build, median presented FPS is **59.0441 original /
59.1121 acre**. Thus typical/median parity is measured. Both builds have dips;
the acre's 29.97 FPS run is a real low result, not excluded as bad data. This
sample does **not** establish worst-case or startup parity, and the cause remains
unexplained. Raw summaries and per-present timestamps are retained in the four
`profile-*` evidence directories. No culling default was changed to force a pass.

Implementation and functional/device checks are complete. Keep the performance
variability as an open acceptance concern rather than claiming every run passed
the plan's broad “no lower frame rate” wording. The source, assets and evidence are committed together.


### Install everywhere — 2026-11-14

Will requested installation everywhere. Coordinator `DEVICE=all`, install-only
batch `B-4ba9216c45f7`, verified the shipping APK hash on both Chromecasts,
Pixel 8 Pro and Lenovo Tab P11 Pro. See
[installation receipts](install-everywhere/summary.json).
