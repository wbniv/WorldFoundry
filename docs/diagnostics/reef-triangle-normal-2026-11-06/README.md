# Small-triangle normal: preliminary measurements

2026‑11‑06. These are isolated **floating-point prototypes**, not the World Foundry loader, fixed-point implementation, reef geometry, or Android performance. They inform the design discussion; they do not establish the cost or correctness of an engine change.

On an Intel i7-1185G7 (x86-64), GCC 15.2.0, `g++ -O3 -std=c++17 normal-prototype.cpp -o /tmp/reef-normal-prototype`, ran 200,000 deterministic ordinary-sized input pairs five times per sample, two warm-up rounds, then 20 samples of each variant in rotating order. The three variants use identical input. Raw timings and checksums are in [samples.csv](samples.csv). The timing includes loop, branching and checksum overhead; the machine was not isolated and the spread is substantial.

| Prototype | Median ns/triangle | p95 ns/triangle |
|---|---:|---:|
| Baseline-like cross, length and threshold | 17.5674 | 19.1187 |
| Always compute and scale the cross | 29.9443 | 69.0444 |
| Scale only if length is below threshold | 15.7801 | 19.0604 |

The always-scaled prototype is about 70% slower in this run; the conditional prototype's apparent 10% speedup is within noisy, overlapping sample ranges and is not evidence of an improvement. Neither is a game frame-time or load-time result. The benchmark stores no additional per-face data, but it does **not** measure process memory. Arithmetic, data distribution, compiler specialization and hardware may differ from the eventual engine implementation. In particular, neither method solves fixed-point cross-product precision or proves overflow bounds.

The toy right triangle with edge 0.001 has cross magnitude 0.000001: the baseline-like threshold rejects it, the conditional prototype returns +Z, and both reject the zero-area example. See [correctness.txt](correctness.txt). This is a floating-point arithmetic illustration, not a reproduction through export and the actual loader; packed/quantized coordinates and fixed-point results remain to be tested.

## Engine function reproduction

The separate [engine-normal-probe.cpp](engine-normal-probe.cpp) calls the real `CalculateNormal` inline function used by the FACE loader. [Baseline results](engine-normal-baseline.txt): a right triangle with edge `0.001` returns `(0, 0, 0.000001)` instead of `(0, 0, 1)`; edge `0.01` returns the unit normal and the degenerate triangle returns zero. The candidate returns unit +Z for the small face. A fixed-point candidate probe also returns +Z for an edge of 0.001 and zero for an edge smaller than one 16.16 position unit.

The [loader probe](loader-probe.cpp) also loads a MODL file made from a reef export's vertex and material format. Its representable 66/65536-unit small triangle produced z=0.000001014 in the release baseline and z=1 in the candidate; the ordinary triangle produced z=1 and the truly degenerate triangle z=0 in both. The baseline and candidate libraries were rebuilt from the same tree with only `face.hpi` changed. This covers floating-point release loader I/O; the fixed-point probe calls the normal function directly, not a fixed-point loader build.

## Real loader timings on identical geometry

The [loader benchmark](benchmark-loader.py) runs each variant in fresh processes with the same exported `reef_left.iff` per style. Timing covers the `RenderActor3D` constructor, not process startup; peak RSS includes the whole process and its fixed 32 MiB test heap. Two warm-up rounds precede 20 alternating samples, with [raw timings, RSS, and input hashes](loader-samples.csv). This is host-only and does not measure full-level load, game frame time, Android, fixed-point performance, or persistent memory in the application. The machine was not isolated.

| Identical mesh | Baseline median / p95 load | Candidate median / p95 load | Baseline / candidate median peak RSS |
|---|---:|---:|---:|
| Realistic reef | 1.882 / 2.982 ms | 1.792 / 2.567 ms | 44,330 / 44,378 KiB |
| Anime reef | 1.113 / 1.403 ms | 1.080 / 1.672 ms | 44,246 / 44,270 KiB |

The samples do not show a median loader regression on these meshes, but noise and the higher anime candidate p95 prevent a confident tail-latency conclusion. RSS differences are small relative to run-to-run variation. These figures are not the planned device A/B acceptance measurement.

## Android preparation and status

Release APKs were built from the same sources with the baseline and candidate `face.hpi`. The unmodified aquarium APKs both contain the same `assets/cd.iff` SHA-256 `d962630886ebf648b6e65a99881739c098dceb96c7a80c3c511e8a225b301b39`. For profiling, [make-profile-apks.py](make-profile-apks.py) creates a two-entry menu pointing to the same reef level and puts the same asset in both variants for that style. This preserves geometry and native libraries and makes the existing coordinator scene alias for menu index zero select the real reef; receipts use that alias even though the menu and level are reef. An earlier one-entry menu automatically started the level, so the coordinator could not confirm a menu cursor.

| Style | Identical paired asset SHA-256 |
|---|---|
| Realistic | `3937e2b7b71f681aac91249f4e471d691b63f7a250194a9802640229a944ba28` |
| Anime | `c1e7c8f1ad5bef0026ac284510885f4e8b5a146f40206ee42b481df76f5beeb9` |

The first realistic baseline profile J‑add7120f138d failed with the device locked. Original-APK installation J‑f11d1273d673 reported a transport error, but its recovery journal verified SHA-256 `91fd64499085fffc86161f8547c0d3216f6b544c15f145fb71326517bf01b8f5`. Retry J‑189c5d0925e7 installed the first benchmark APK and failed to confirm the one-entry menu cursor. Subsequent two-entry attempts J‑a5bd778fd66c and J‑ddb6260be9a9 did not complete; the latter reported that the target left the foreground. Original-APK installation J‑1b7e20a1e67d was refused because the app was foreground; a later attempt succeeded as described below.

Correction after inspecting the downloaded evidence: J‑a5bd778fd66c completed its **first** realistic baseline run before the overall job failed on a later run. Its frame capture shows the reef; over that 20-second run the coordinator reported 59.89 FPS, median frame interval 16.67 ms, p95 16.95 ms, worst 33.36 ms, and 0.16% missed refreshes. The process memory sample reported 180,536 KiB PSS and 317,320 KiB RSS. These are single-run baseline observations, not a paired result or acceptance. The same job's final scene-selection file reflects the subsequent attempt and does not negate the captured first run. J‑2f896e30a3df subsequently restored and launcher-verified the original APK. Will reported concurrently using the Pixel; a foreground change can result from that normal use and should not be attributed to an application crash without further evidence. Complete an uninterrupted paired comparison when an authorized device is available for the workload.

### Pixel paired wide-idle profiles, 2026‑11‑07

Four coordinator jobs completed on the Pixel 8 Pro: realistic baseline J‑246829891d23, realistic candidate J‑399fe3f2383c, anime baseline J‑67793d9a9661 and anime candidate J‑1b92e72d2a8a. Each used three 20-second measurements with a 10-second warm-up per run. The coordinator scene label `clownfish` selects menu index zero in the benchmark-only APKs; screenshots confirm that the selected level is the corresponding reef. Matching variants have identical packed level assets, and outside signing metadata the original two APKs differ only in their two native engine libraries.

| Reef | Variant | Median FPS | Median of run p95 frame intervals | Worst frame across runs | Median sampled PSS | Median sampled RSS |
|---|---|---:|---:|---:|---:|---:|
| Realistic | baseline | 59.995 | 16.893 ms | 33.510 ms | 177,422 KiB | 308,896 KiB |
| Realistic | candidate | 59.996 | 16.923 ms | 33.637 ms | 181,976 KiB | 313,224 KiB |
| Anime | baseline | 59.939 | 16.919 ms | 33.383 ms | 188,601 KiB | 320,240 KiB |
| Anime | candidate | 59.994 | 16.931 ms | 33.438 ms | 186,268 KiB | 318,124 KiB |

The [per-run results](pixel-results.csv) include median and p95 frame intervals, worst frame, missed-refresh rate and memory. The realistic p95 increased 0.030 ms and anime 0.012 ms; these short idle runs do not establish a reproducible frame-time regression. Median PSS changed by +4,554 KiB and −2,333 KiB respectively; the three realistic baseline samples span 8,899 KiB, so the apparent difference is not conclusive evidence of intrinsic memory growth. Measurements were grouped baseline then candidate, rather than alternated, and process PSS/RSS samples are not peak or isolated allocator measurements. Load-time and fixed-point performance were not measured by these jobs, so the full proposed performance gate remains open. No additional geometry was included for these comparisons.

The coordinator completed original APK restoration J‑8035fad0a67e with launcher verification after the profiles. Its intended APK SHA-256 is `91fd64499085fffc86161f8547c0d3216f6b544c15f145fb71326517bf01b8f5`.

### Pixel movement workload, 2026‑11‑07

One 30-second profile per variant followed a 10-second warm-up and the same two eight-second directional holds, with 3 seconds between holds. Coordinator evidence verifies all four touch edges per run; the realistic baseline captures show the player fish moved across the scene. This is a movement/animation workload, not proof that every species reaction triggered. Realistic baseline/candidate jobs were J‑1f2cdc9ed490 and J‑116b76825d9c; anime baseline/candidate were J‑ada0661f2e1d and J‑a0c45d82c399. All completed successfully with `device-edges-verified`. [Raw per-run metrics](pixel-reaction-results.csv):

| Reef | Variant | FPS | p95 frame interval | Worst frame | Sampled PSS | Sampled RSS |
|---|---|---:|---:|---:|---:|---:|
| Realistic | baseline | 59.925 | 16.927 ms | 33.624 ms | 182,771 KiB | 312,616 KiB |
| Realistic | candidate | 59.967 | 16.923 ms | 32.607 ms | 185,126 KiB | 313,548 KiB |
| Anime | baseline | 59.988 | 16.915 ms | 17.361 ms | 188,300 KiB | 316,772 KiB |
| Anime | candidate | 59.995 | 16.925 ms | 17.390 ms | 189,440 KiB | 317,160 KiB |

These single samples show no clear frame-time regression and cannot establish a reproducible memory delta. They include the coordinator touch/capture workload, which was the same for both variants. Device load time is measured separately below; peak memory and fixed-point performance remain unmeasured. The original APK was restored again by J‑1d2aa943ff6a, with launcher verification.

### Pixel level-construction timing, 2026‑11‑07

The existing `--frame-profile` flag was added equally to the matched baseline and candidate benchmark APKs using [make-load-profile-apks.py](make-load-profile-apks.py); the reef level assets did not change. For each style and variant, the coordinator launched the reef three times and captured the engine's `level-load` start/end timestamps. The [individual timestamps and durations](pixel-level-load-results.csv) were matched to the next measurement anchor to distinguish them from older appended log entries. Jobs: realistic baseline J‑45b4300901b3, realistic candidate J‑362452b6cec2, anime baseline J‑21d3f52270f0, and anime candidate J‑f8d9455d0452.

| Reef | Baseline level construction (ms) | Candidate level construction (ms) |
|---|---|---|
| Realistic | 82.751, 85.820, 80.145 | 78.322, 77.965, 131.129 |
| Anime | 117.416, 100.639, 119.315 | 83.940, 83.388, 124.129 |

Medians are 82.751 → 78.322 ms for realistic and 117.416 → 83.940 ms for anime. Three sequentially grouped samples, including the slower candidate outliers, do not establish the p95, cold/warm behavior or a causal speedup; the opt-in profiler also adds the same instrumentation to both variants. The timing covers `WFGame::LoadLevel`, including construction and optional prewarm, rather than APK startup or menu selection. It does not measure peak memory. After the jobs, restoration J‑b4a59ff27812 reported a plugin error; its recovery journal verified the original installed APK SHA-256 `91fd64499085fffc86161f8547c0d3216f6b544c15f145fb71326517bf01b8f5`. A follow-up install/launcher verification was submitted separately.

The [18-page catalogue audit](catalogue-survival-audit.md) maps every explicitly export-survival entry to the current source. No restoration has been made by that audit.

The follow-up installation J‑31a4a398b1c0 timed out while running `adb install -r` even though its recorded pre-install hash was already the original APK hash. Its cleanup and automatic readd J‑61e6bdc8e060 left the Pixel fenced with `cleanup-requires-restart`. The coordinator explains that an interrupted installer can have a delayed commit, so the matching pre-install hash alone does not establish that it is safe to clear the fence. After Will requested recovery, reboot-and-readd J‑7f0fdd1debd8 verified a completed boot, the original APK hash and safe cleanup; the Pixel returned ready. This follow-up was unnecessary after the prior journal had already verified the original APK hash. A [separate plan](../../plans/2026-11-07-coordinator-installer-self-recovery.md) proposes automatic recovery without a routine reboot; that change is not implemented or deployed.

An attempt to compile the original fixed-point vector/scalar sources for the current x86-64 host as a baseline benchmark failed before linking: `Vector3::Length` and `RLength` have ambiguous conversions from `unsigned long` to `Scalar`, and the legacy Linux scalar source produced additional compile errors under that configuration. The candidate's header-level fixed-point correctness regression passes; it is not a fixed-point engine performance benchmark. A supported fixed-point build configuration is still needed for that comparison.

The coordinator profiles collected end-of-run `dumpsys meminfo` snapshots, not a process peak. The existing interactive sample also reads a point-in-time `meminfo` snapshot after startup. Neither can establish a peak during level construction, so the table above does not relabel the largest snapshot as a peak.

## First restoration and in-game review

The generator now retains small valid triangles and writes a per-object, per-face `triangle-diagnostics.json`; the original 0.010 leather-polyp radius has been restored with the later deflation rig intact. Both pinned level builds and all 34 reef tests passed. The [catalogue](../reef-refinement-catalogue-2026-11-04/reef-refinement-catalogue.pdf) has the source-mesh before/after on page 49 and realistic/anime Pixel close-ups on page 50. The full menu APK was reinstalled and hash-verified on the Pixel after the diagnostic captures. The [catalogue audit](catalogue-survival-audit.md) records the source evidence, exact face counts, loader checks, capture job IDs and remaining restoration work.

Reference hashes for later identical-input comparisons:

| Input | SHA-256 |
|---|---|
| `wflevels/aquarium_thai_reef-standalone.iff` | `02984fe20a3d89963049a6f0b53768a9708022e14d3244af9ccf5f24a808b863` |
| `wflevels/aquarium_thai_reef_anime-standalone.iff` | `5e6cc5ce4bb76b666c5f372b2afa00ed345ea3dfac13baea475366f5bd75b888` |
| Existing aquarium release APK | `6c9867ba061159806e6b864fc3d5a7eb62076390372831a48f6c843abfccb91f` |

Those hashes identify files present during the measurement; the APK predates the listed levels and is not established to contain them. Neither a baseline device profile nor an engine-candidate A/B comparison has been performed.

## Fixed-point normal microbenchmark and peak RSS, 2026‑11‑07

A host benchmark now compiles the actual baseline and corrected `CalculateNormal` fixed-point branches against the same 12,372 triangles extracted from the realistic and anime `reef_left` exports. The 36-byte-per-triangle [fixture](fixed-normal-triangles.bin) has SHA-256 `5613f68eaafe7c100e1075c12e139860bcf049d9ca90b20eccf87d2e62a017a7`. Both programs use the same input and [harness](fixed-normal-host-bench.cpp), which incorporates the engine's `Vector3::CrossProduct`, fixed-point `Vector3::Length`, and `Sqrt64`; the latter two require an explicit unsigned-to-long cast for this host compiler. The baseline uses [the original face header](fixed-normal-baseline-face.hpi). These are host-compatibility changes in the diagnostic harness, not engine modifications. The source meshes have SHA-256 `e2de86c7331fe35a21ba36ba1924a7175a7daea7bc3bc7370e831c5501d5b46f` and `5e21e3f2370b72ec0da1085beec599552253ee9098ab0351e5016e4029954469` respectively.

On x86-64 Intel i7-1185G7 with GCC 15.2, two warm-up rounds and 20 alternating fresh-process samples each evaluated 25 passes (309,300 face normals per sample). Median elapsed time was **41.081 ms baseline and 15.791 ms corrected**; ranges were 38.906–46.410 and 14.880–18.487 ms. [Raw samples](fixed-normal-host-samples.csv) include checksums, which differ because the corrected normal intentionally produces different results. The host was not isolated. This measures the normal calculation in a fixed-point host harness, including loop and checksum overhead; it is not a fixed-point loader, full game, or device benchmark and cannot prove performance on another fixed-point target.

Twenty alternating fresh-process measurements of `wait4` high-water RSS gave a median **13,080 KiB for both**; [raw results](fixed-normal-host-peak-rss.csv). The Python parent process is approximately this size and can set a high-water floor before `exec`, so these values do not bound a small intrinsic memory difference. The earlier real-loader host measurements on identical meshes remain the more relevant measured peak-RSS comparison. Android process peak memory remains unmeasured: existing coordinator captures provide snapshots, not a process high-water measurement.

A second peak-RSS run avoided the Python-parent floor: a shell launched 20 fresh processes of each variant, using the same fixed-point fixture and the same harness with `getrusage(RUSAGE_SELF)` added. Baseline median peak was **4,576 KiB** (4,464–4,668), and corrected median peak was **4,582 KiB** (4,508–4,648). [Raw paired results](fixed-normal-host-peak-rss-direct.txt) and [peak harness](fixed-normal-host-peak-bench.cpp) are saved. The 6 KiB median difference is smaller than the observed spread; whole-process RSS and page granularity do not establish a small per-function memory delta. This supplements the real-loader host peak measurements and does not substitute for Android peak memory.
