# Candle flicker: Option A against Option B on cast1

27 November 2026. The TODO item "Candle flicker: measure Option B (the deformed flame) against A on cast1". Plan: [2026‑11‑22 candle flicker](../../plans/2026-11-22-cuckoo-village-candle-flicker.md), verification step 0 (result) and "Judging them by eye" (the look).

**Result:** B costs **+1.39 ms of main-thread CPU a frame** over A (23.58 against 22.19 ms, 11 windows of 5 s each, window standard deviation about 0.15 ms). The extra time is in the director (+1.76 ms) and the deformer (+0.44 ms). Both variants hold 30 fps.

| | A (shipped: 4 meshes a tree, swap) | B (1 DFRM mesh a tree, 10 curves) |
|---|---|---|
| FPS / p50 / p95 | 29.84 / 33.37 / 50.05 ms | 29.75 / 33.37 / 50.05 ms |
| missed refreshes | 94.27 % (30 fps on a 60 Hz output) | 92.44 % |
| CPU total, mean (p95 of the median window) | 22.190 ms (23.844) | 23.576 ms (26.223) |
| director / animation / render | 1.883 / 0.000 / 18.810 ms | 3.638 / 0.442 / 18.773 ms |
| draws, deformations, upload bytes a frame | 112, 0, 0 | 100, 12, 116,652 |

## How

| Item | Value |
|---|---|
| Base APK | `3ac985b177624c42…`: WF Clocks Release from `2026-new-level` at `23ee74a4` (Dream host passes `--frame-profile` from `wf_args.txt`) |
| A variant | `01635406657ad99b…`: base, plus `assets/cd.iff` (Cuckoo Village alone), `levels.manifest` and `wf_args.txt` + `--frame-profile` |
| B variant | `de55dc586abb076d…`: the same, B's level |
| Restored | `052292fc80939e9d…`: the Clocks APK cast1 had before (`before_sha256` of the first install), put back by the job's cleanup J‑081f26ab5ec9 and by install J‑aabed797f193 after the clips |
| Levels | built in a scratch worktree from `149b91c9` with [measurement-builds.patch](measurement-builds.patch): `CANDLE_FLAMES=swap` or `deform`, `CANDLE_NIGHT_HOUR=22`, `CANDLE_ALL_YEAR=1`, `CANDLE_CAMERA_STILL=1`. The A level `e3590f7c…` is 8,787,968 B; the B level `fa7d3756…` is 8,740,864 B |
| Benchmark | `variant-benchmark` J‑83080304e587 on chromecast-test-01: 60 s after a 15 s warm-up, A then B, `panel: require-hidden` |
| Clips | `record` J‑cb9ea5a3f79a (A) and J‑26738f3d4732 (B), 12 s, the benchmark builds |

Re-run the figures with `python3 analyse.py pair1`. It reads `summary.json`, `presents-ns.json` and the engine's `frame-profile` windows from `wf.log`, keeping only the windows that lie wholly inside the measured presentation span. Large text files are gzipped; `pair1/compressed-evidence.json` holds their original sizes and SHA-256 hashes. `make_look.py` builds the plan bundle's `near-study-*.png` and `look-real.html/.png` from the desktop study frames. The `cast1-trees-*.mp4` clips are 7 s crops of the record jobs' `capture.mp4`, cut with ffmpeg on the host (`crop=720:405:1180:520`, crf 24).

Re-download a job's evidence with `task chromecast:evidence JOB=… OUT=…`.
