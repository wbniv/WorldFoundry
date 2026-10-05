# Lionfish: measured performance and deltas

Final normal APK SHA-256: `ddeeeb889eac5201527c9129e4b8f653901ebe76f16b3c84e367eabe0e191d77`.
Both final benchmark jobs completed and restored that exact APK. All measurements
below come from coordinator evidence; CPU means use the last complete window,
presentation figures use separate uninstrumented runs. Baseline windows are
12 seconds; final windows are 30 seconds, each after 15 seconds of warmup.

## Presentation pacing

| Device / prey | Baseline FPS, all 3 runs | Final FPS, all 3 runs | Median FPS delta | Baseline → final p95 range (ms) | Final p99 range (ms) |
| --- | --- | --- | ---: | --- | --- |
| chromecast-test-01 / 0 | 29.97 / 29.97 / 29.97 | 29.99 / 29.99 / 29.97 | +0.1% | 33.37–33.37 → 33.37–33.37 | 33.37–33.37 |
| chromecast-test-01 / 3 | 29.97 / 29.97 / 29.97 | 29.99 / 29.99 / 29.99 | +0.1% | 33.37–33.37 → 33.37–33.37 | 33.37–33.37 |
| chromecast-test-02 / 0 | 59.94 / 59.94 / 59.94 | 40.02 / 39.87 / 39.92 | -33.4% | 16.70–16.70 → 33.39–33.39 | 33.40–33.41 |
| chromecast-test-02 / 3 | 59.94 / 59.94 / 59.94 | 39.70 / 39.84 / 39.85 | -33.5% | 16.70–16.70 → 33.38–33.39 | 33.40–33.40 |

Cast1 retains its approximately 30 FPS presentation cadence. Cast2 falls from
the controlled baseline’s 60 FPS to about 40 FPS with the richer asset. Earlier
stock cast2 runs included 30 FPS cadence; these are retained separately and
are not averaged into the controlled baseline. No 60 FPS claim is made for
the final asset. The increase from 844 to 4,068 triangles per complete fish
is +382%; reducing actor count does not erase that rendering cost.

## CPU sections and actor cost

Values are **baseline → final** CPU milliseconds per frame. Sections overlap;
do not add actor, Director, pose and animation columns to infer total time.

| Device / prey | Actor update | Director | Pose (includes native animation) | Native animation | Render submission / waits | Total update + render | Total delta |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| chromecast-test-01 / 0 | 1.692 → 1.123 | 1.053 → 1.021 | 0.652 → 0.734 | 0.000 → 0.595 | 3.103 → 17.699 | 5.917 → 19.902 | +236.3% |
| chromecast-test-01 / 3 | 1.524 → 1.129 | 2.027 → 1.950 | 0.577 → 0.735 | 0.019 → 0.611 | 3.334 → 18.252 | 6.948 → 21.389 | +207.9% |
| chromecast-test-02 / 0 | 1.615 → 1.032 | 0.928 → 0.821 | 0.565 → 0.572 | 0.000 → 0.454 | 2.908 → 14.760 | 5.518 → 16.669 | +202.1% |
| chromecast-test-02 / 3 | 1.518 → 1.038 | 1.921 → 1.580 | 0.534 → 0.576 | 0.023 → 0.476 | 3.404 → 15.468 | 6.909 → 18.144 | +162.6% |

Actor update is lower in the new build; the additional native deformation is
under 1 ms per frame in these windows. Rendering is the principal added cost.
The sampled counters, rather than FPS alone, establish reduced actor/mailbox
work. Script flow/sensing remains included in Director/school time.

## Per-frame counters

Values are **baseline → final**. Rendered triangles vary with pose and culling;
the exported model count is exactly 4,068 per fish.

| Device / prey | Tank actors | Render actors | Draw calls | Submitted triangles | Pose mailbox writes | Deformed fish |
| --- | --- | --- | --- | --- | --- | --- |
| chromecast-test-01 / 0 | 41.0 → 31.0 | 25.0 → 15.0 | 24.0 → 18.0 | 956.2 → 6431.6 | 108.0 → 18.0 | 0.0 → 2.0 |
| chromecast-test-01 / 3 | 41.0 → 31.0 | 28.0 → 18.0 | 27.0 → 21.0 | 1112.8 → 6622.3 | 126.0 → 36.0 | 3.0 → 5.0 |
| chromecast-test-02 / 0 | 41.0 → 31.0 | 25.0 → 15.0 | 24.0 → 18.0 | 955.3 → 6430.9 | 108.0 → 18.0 | 0.0 → 2.0 |
| chromecast-test-02 / 3 | 41.0 → 31.0 | 28.0 → 18.0 | 27.0 → 21.0 | 1113.5 → 6613.9 | 126.0 → 36.0 | 3.0 → 5.0 |

Two lionfish lose ten visible actors overall (12 → 2); tank objects fall
41 → 31 (−24.4%). Reported pose writes fall 108 → 18 with no prey (−83.3%)
and 126 → 36 with three prey (−71.4%). The counter counts actor-mailbox pose
writes; it is not every local Forth mailbox read/write.

## Batching diagnosis

The asset and textures are unchanged between the full implementation trials.
The first used palette uniforms; the intermediate moved endpoints into vertices
but still replayed unchanged lighting/fog on palette changes. The final build
also skips that replay, allowing globally sorted fins to share draws.

| Device / prey | First trial FPS median | Attribute-only trial FPS median | Final FPS median | First → final draws/frame | First → final render ms |
| --- | ---: | ---: | ---: | --- | --- |
| chromecast-test-01 / 0 | 8.10 | 9.31 | 29.99 | 1023.4 → 18.0 | 138.49 → 17.70 |
| chromecast-test-01 / 3 | 6.63 | 9.03 | 29.99 | 1142.5 → 21.0 | 164.14 → 18.25 |
| chromecast-test-02 / 0 | 9.06 | 10.41 | 39.92 | 1019.2 → 18.0 | 110.45 → 14.76 |
| chromecast-test-02 / 3 | 7.54 | 10.15 | 39.84 | 1094.3 → 21.0 | 132.32 → 15.47 |

## Process memory and texture capacity

PSS values are the median of three uninstrumented run-end process snapshots,
in MiB (Android reports KiB). These do not isolate GPU residency or texture
allocation. Shader vertex payload, model data, page buffers and driver state
all contribute.

| Device / prey | Baseline PSS MiB | Final PSS MiB | Delta MiB |
| --- | ---: | ---: | ---: |
| chromecast-test-01 / 0 | 49.16 | 59.32 | +10.16 |
| chromecast-test-01 / 3 | 49.01 | 59.04 | +10.03 |
| chromecast-test-02 / 0 | 20.23 | 30.88 | +10.64 |
| chromecast-test-02 / 3 | 20.25 | 31.04 | +10.80 |

Source maps stay 256² each (512 KiB RGBA8 combined). Packed room/permanent
pages use 512² slots (1 MiB RGBA8 per full upload). Configured pixel-buffer
capacity is 2048 × 1024, using existing engine arguments. Actual driver/GPU
texture residency and separate GPU execution time were not measured.

## Reproduction and raw records

- [Controlled baseline / first trial](profiles-first-trial/batch.json): B-0f8d52c91422.
- [Attribute-only trial](profiles-palette-attributes/batch.json): B-edf562de0055.
- [Final batch](profiles-final/batch.json): B-483e17a947be.
- [All run summaries and CPU counters](profile-summary.json).
- [Preparation and summary script](../../../scripts/profile-lionfish-realism.py).

Use `prepare --baseline-root ... --baseline-apk ... --apk ... --out ...`
with an isolated baseline checkout and archived APK, then submit the frozen
recipe using `task chromecast:submit DEVICE=all RECIPE=...`. The benchmark
restores and verifies the normal APK before releasing its managed sessions.
Baseline source is commit `bcec65ac`; the archived original APK hash is
recorded in the implementation report. Input hashes remain in each batch’s
request. Fixed three-prey benchmark variants suppress auto-capture; normal
gameplay retains it.

These are fixed initial camera/population comparisons, not a complete strike
GPU benchmark. Actual feeding is verified separately in the desktop runtime
and Forth cadence/generation/occlusion tests. No coordinator feeding-input
trace was added, and no unsupported device control bypass was used.
