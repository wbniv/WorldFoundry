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

The [per-run results](pixel-results.csv) include median and p95 frame intervals, worst frame, missed-refresh rate and memory. The realistic p95 increased 0.030 ms and anime 0.012 ms; these short idle runs do not establish a reproducible frame-time regression. Median PSS changed by +4,554 KiB and −2,333 KiB respectively; the three realistic baseline samples span 8,899 KiB, so the apparent difference is not conclusive evidence of intrinsic memory growth. Measurements were grouped baseline then candidate, rather than alternated, and process PSS/RSS samples are not peak or isolated allocator measurements. Load-time, fixed-point performance, and a reaction/input workload were not measured by these jobs, so the full proposed performance gate remains open. No additional geometry was included for these comparisons.

The coordinator completed original APK restoration J‑8035fad0a67e with launcher verification after the profiles. Its intended APK SHA-256 is `91fd64499085fffc86161f8547c0d3216f6b544c15f145fb71326517bf01b8f5`.

Reference hashes for later identical-input comparisons:

| Input | SHA-256 |
|---|---|
| `wflevels/aquarium_thai_reef-standalone.iff` | `02984fe20a3d89963049a6f0b53768a9708022e14d3244af9ccf5f24a808b863` |
| `wflevels/aquarium_thai_reef_anime-standalone.iff` | `5e6cc5ce4bb76b666c5f372b2afa00ed345ea3dfac13baea475366f5bd75b888` |
| Existing aquarium release APK | `6c9867ba061159806e6b864fc3d5a7eb62076390372831a48f6c843abfccb91f` |

Those hashes identify files present during the measurement; the APK predates the listed levels and is not established to contain them. Neither a baseline device profile nor an engine-candidate A/B comparison has been performed.
