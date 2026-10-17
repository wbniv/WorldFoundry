# Seahorse population cost on cast1

17 October 2026 · Wide-view baseline for the six-pair integration, `9f97f5dd`.

## Measurement

Cast1 is the Chromecast HD (`chromecast-test-01`, Android 14, 32-bit app).
All APKs use the same native libraries and selector contents apart from the
planted tank's authored population settings. Each has twelve allocated
residents, six posts, the same shared mesh/atlas data and a 6 MB permanent
pool. The population setting controls visibility and behavior/deformer calls.
None also hides all six posts. Memory here is whole-process PSS; this comparison
cannot establish allocation cost per seahorse or recover the pre-seahorse app's
memory footprint. None retains the level's resident actor bookkeeping.

The fixture is saltwater, seed 713, plant age 150, growth paused, textures and
sway enabled, random entry disabled and greeting enabled. Gameplay runs in real
time with the normal wide camera, so poses differ between workload samples. Three 60-second release repeats per count follow 15 seconds
of warm-up, with count order varied. CPU sections come from a separate
instrumented repeat per count, whose APK changes only `wf_args.txt` to enable
`--frame-profile`; its presentation numbers are not pooled with release runs.

The analyzer recomputes frame intervals from raw SurfaceFlinger presentation
timestamps and rejects sampling holes, summary disagreement, less than 59 seconds
of observed coverage, wrong plant settings and current-run Forth/assert/allocation
errors. It selects only CPU windows fully contained within that run's device
presentation timestamps. Startup, warm-up and older cumulative-log windows are
excluded. Screenshots establish the scene and visible population.

## Results

Release values are medians of three run means; ranges show the three runs.
P95 is the median of each run's p95 presentation interval, not a CPU percentile.

| Pairs | Mean frame ms (run range) | FPS | p95 interval ms | PSS MiB (run range) |
|---:|---:|---:|---:|---:|
| 0 | 47.14 (47.13–47.24) | 21.22 | 50.05 | 99.0 (98.2–101.6) |
| 1 | 51.58 (51.54–51.90) | 19.39 | 66.73 | 99.3 (97.0–100.7) |
| 2 | 55.10 (55.00–55.66) | 18.15 | 66.73 | 98.2 (97.8–104.8) |
| 6 | 69.26 (69.09–69.28) | 14.44 | 83.42 | 103.6 (100.8–106.2) |

Six pairs add **22.13 ms per presented frame** over None
(**46.9% longer**, **31.9% fewer FPS**).
The extra eight residents from two to six pairs add 14.16 ms in this view.
None-to-one also includes the six posts; it is not an isolated two-fish cost.
All accepted release runs have at least 59 seconds of observed presentation
coverage and post-run thermal status 0. PSS varies by several MiB between runs
with the same population, so these values are not evidence of a precise
per-resident allocation cost.

### Main-thread CPU and rendering counters

Frame-weighted means from fully contained five-second windows in separate
instrumented runs. Each population has 11 selected windows (about 55 seconds).
Total is update + render. Director is inside update; native animation is inside
Director. Do not add overlapping columns. These are main-thread CPU times,
not presented frame times or whole-process CPU times.

| Pairs | Update ms | Director ms | Animation ms | Render ms | Total CPU ms |
|---:|---:|---:|---:|---:|---:|
| 0 | 7.79 | 6.92 | 6.16 | 34.96 | 42.76 |
| 1 | 9.40 | 8.56 | 6.57 | 37.63 | 47.03 |
| 2 | 10.85 | 10.02 | 7.01 | 39.77 | 50.62 |
| 6 | 17.03 | 16.19 | 8.84 | 47.26 | 64.30 |

Six pairs add **21.54 ms main-thread CPU**: +9.24 ms update and
+12.30 ms render. The animation group rises by 2.68 ms, already
included in Director's +9.26 ms. Its grouping includes other deformers;
this is not an isolated `DFRM` evaluator benchmark. Moving vertex placement to
a shader would leave behavior and other Director work to measure separately.

Instrumented frame periods were 1.1–2.0% above their corresponding
release medians. These are separate real-time runs, so that spread includes
run/pose variation and is not a pure instrumentation-overhead measurement.
All accepted CPU runs also have post-run thermal status 0.

| Pairs | Render actors | Draws/frame | Vertex uploads/frame | Vertex MiB/frame | Static index KiB/frame |
|---:|---:|---:|---:|---:|---:|
| 0 | 34 | 27.00 | 9.00 | 5.12 | 9.27 |
| 1 | 44 | 44.01 | 20.01 | 5.37 | 12.45 |
| 2 | 48 | 56.28 | 32.28 | 5.63 | 12.45 |
| 6 | 64 | 79.02 | 55.02 | 6.65 | 12.45 |

Whole-frame streamed vertex traffic grows by 1.53 MiB/frame from None to six pairs.
The baseline already streams 5.12 MiB/frame; opaque seahorse-body skinning cannot
remove all of this traffic. None has 18 static objects; every nonzero count has
24, including all six posts. No static bakes occur in the selected CPU windows.
All variants report 81 level objects, consistent with hiding rather than
removing residents. Full counters and selected window timestamps are in
[comparison.json](../../diagnostics/seahorse-population-cast1-20261017/comparison.json).

## What this establishes

This measures the current CPU `DFRM` seahorse implementation at None, one, two
and six pairs in wide idle. CPU `total` is update plus render on the main thread;
it excludes presentation waits and worker-thread CPU. Director and animation
sections overlap and must not be summed as independent costs. Vertex upload
bytes and static index upload bytes are separate counters. Whole-frame upload
counters also include plants, fins and other streamed geometry; they do not
measure bytes removable by GPU skinning of opaque seahorse bodies.

The six-pair default remains Will's choice. This is the baseline for the
[separate GPU-skinning experiment](../2026-10-16-gpu-skinning-chromecast-experiment.md),
which still needs explicit engine permission. It neither compares a CPU joint
rig with `DFRM` nor measures GPU skinning, hardware GPU time or Metal performance.
Close views, close crawling and cast2 measurements remain outstanding; cast2 is
unavailable on the shared network. This does not complete every Phase 4 check.

## Rejected samples and launch failures

Round two's None capture showed the lionfish scene, not the planted tank. Its
valid timestamp coverage does not make it a usable baseline; it was excluded
and replaced by a separate None run. The original third round failed before
measurement with a coordinator plugin/foreground error. The original CPU
session completed a valid None sample, then ended with a similar failure;
its missing populations were repeated. Failure evidence and replacement
selection are retained. These records do not establish the cause of the launch
failures or certify general lifecycle stability.

## Evidence and reproduction

[Diagnostic bundle](../../diagnostics/seahorse-population-cast1-20261017/README.md)
contains frozen APK/native-library hashes, authored-setting receipts, coordinator
recipes, run summaries, raw timestamps, PSS and thermal snapshots, screenshots,
compressed logs and explicit rejected-sample/replacement records. The coordinator
owns each complete session and restores the release six-pair APK afterward.
Large text artifacts are losslessly gzipped, with uncompressed hashes recorded;
the analyzer reads either form. Temporary build outputs and duplicate downloads
are removed after merge. Service evidence can be downloaded again by job ID.

```sh
python3 scripts/analyze-seahorse-population.py \
  --evidence docs/diagnostics/seahorse-population-cast1-20261017 \
  --out docs/diagnostics/seahorse-population-cast1-20261017/comparison.json
```
