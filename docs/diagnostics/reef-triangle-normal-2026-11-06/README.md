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

The first realistic baseline profile J‑add7120f138d failed with the device locked. Original-APK installation J‑f11d1273d673 reported a transport error, but its recovery journal verified SHA-256 `91fd64499085fffc86161f8547c0d3216f6b544c15f145fb71326517bf01b8f5`. Retry J‑189c5d0925e7 installed the first benchmark APK and failed to confirm the one-entry menu cursor. Subsequent two-entry attempts J‑a5bd778fd66c and J‑ddb6260be9a9 failed; the latter reported that the target left the foreground. No Android profile measurements were collected. Original-APK installation J‑1b7e20a1e67d is queued following those attempts and needs verification.

Reference hashes for later identical-input comparisons:

| Input | SHA-256 |
|---|---|
| `wflevels/aquarium_thai_reef-standalone.iff` | `02984fe20a3d89963049a6f0b53768a9708022e14d3244af9ccf5f24a808b863` |
| `wflevels/aquarium_thai_reef_anime-standalone.iff` | `5e6cc5ce4bb76b666c5f372b2afa00ed345ea3dfac13baea475366f5bd75b888` |
| Existing aquarium release APK | `6c9867ba061159806e6b864fc3d5a7eb62076390372831a48f6c843abfccb91f` |

Those hashes identify files present during the measurement; the APK predates the listed levels and is not established to contain them. Neither a baseline device profile nor an engine-candidate A/B comparison has been performed.
