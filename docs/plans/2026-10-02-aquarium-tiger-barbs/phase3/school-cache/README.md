# Schooling cache measurements

Implemented on the phase 3 worktree and integrated into the seven-tank release. Native libraries, mesh/texture, 29 followers and five behavior updates/frame are identical in both measurements. Only repeated invariant reads and address calculations are cached.

| Build | Median FPS (3 runs) | p95 ms | p99 ms | Missed refresh % |
|---|---:|---:|---:|---:|
| Before cache | 35.458 | 50.050 | 50.050 | 60.298 |
| With cache | 37.426 | 50.050 | 50.050 | 53.618 |

Presentation FPS: +1.967 (+5.55%). Missed-refresh delta: -6.680 percentage points.

480 fixed-step follower comparisons produced exactly the same state and accumulation outputs as the preserved original Forth. Total mailbox bridge calls in that trace fell by 21.34% for 30 fish and 14.15% for 11 fish. These are VM call counts, not device timings. 73 final integrated checks and 8 existing schooling regressions passed.

The candidate CPU trace was interrupted when the foreground switched to the FPS-check app. It is excluded under profiles/school-cache/P3-cache-cpu-interrupted-excluded. Candidate CPU timing, late baseline control and final device installation await exclusive Chromecast access. The complete optimized seven-tank APK is built and verified; SHA-256: d6f536248f1f8ad534083fa8c794ed3dcee9c3e2caac7047fa96ea0d8a52484d.
