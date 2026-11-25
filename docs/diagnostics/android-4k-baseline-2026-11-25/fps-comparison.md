# Bamboo pond: cast2 presented-frame comparison

25 November 2026. One profile per build on the same Chromecast and active 4K60 LG output. Both navigated from the Clocks chooser into Bamboo Tipper and Pond using the same timed input script; captures confirm the scene. SurfaceFlinger presentation timestamps were restricted to 30–80 seconds after the input-script anchor, excluding chooser navigation and initial loading. Both runs report no sampling holes. The engine reported the corresponding surface and viewport dimensions.

| Render size | APK SHA-256 | Job | Presented FPS | p95 interval | p99 interval |
| --- | --- | --- | ---: | ---: | ---: |
| 1920×1080 | `25a26ac64c4e74cc1f10b6adca501373d854ce60e1a3da7fc7ed7c128e804054` | J‑14065de23284 | 58.2 | 16.67 ms | 33.33 ms |
| 3840×2160 | `d8b5706d45255e57b1cc0a7d6490415a3cff7e197ec3144895c3bb5b81807ac3` | J‑7218d55edb4a | 22.2 | 66.67 ms | 66.67 ms |

FPS is (number of intervals)/(last presentation minus first presentation). The windows contain 2,910 and 1,111 presentations, respectively, over approximately 50 seconds. Percentiles are nearest-rank-by-index from consecutive presentation intervals. These are display presentations, not isolated GPU time. Each profile's `input-timeline.csv` supplies the monotonic millisecond anchor; `run-1/presents-ns.json` supplies nanosecond presentation timestamps. See [1080p evidence](fps-1080/) and [4K evidence](fps-4k/).

This is a single sequential pair, not a repeated or thermally controlled benchmark. The camera and clock continue moving; captured views show different camera phases, so the workloads are not perfectly matched. The results nevertheless show a large observed drop in this run; repeat with a fixed camera and counterbalanced order before treating the difference as a general performance figure. Physical 4K pixel detail remains unverified.
