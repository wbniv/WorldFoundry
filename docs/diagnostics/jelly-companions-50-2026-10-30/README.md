# Full-detail jellyfish companion sweep — 2026-10-30

Chromecast HD (`chromecast-test-01`), 8-second profile after 3-second warmup,
one run per count. Each test APK set the indicated initial count. All extra
jellyfish retained the full 341-face bell and arms geometry combined in one
actor. The shipped default remains 5, and the integer slider spans 0–50.

| Companions | Result | Evidence |
| ---: | ---: | --- |
| 0 | 59.8 fps | [profile](zero-visible-full-mesh/summary.json), J‑c0469928325a |
| 5 | 50.2 fps | [profile](five-visible-full-mesh/summary.json), J‑53e1d023d592 |
| 8 | 47.1 fps | [profile](eight-visible-full-mesh/summary.json), J‑f8708f7c6ecf |
| 10 | 42.5 fps | [profile](ten-visible-full-mesh/summary.json), J‑6f73d2417ba4 |
| 12 | 39.2 fps | [profile](twelve-visible-full-mesh/summary.json), J‑6521b5da5eac |
| 15 | Foreground lost; cause unknown | J‑8aec7f96f1f5 |
| 26 | Foreground lost; cause unknown | J‑0028543728d7 |
| 50 | Foreground lost; cause unknown | J‑c008ddda67f8 |

Subsequent tests of the shipped APK changed the count through Settings and
remained in the tank at [15](../jelly-live-count-2026-10-30/cast1-15/input-frame-006.png),
[30](../jelly-live-count-2026-10-30/cast1-30/input-frame-005.png), and
[50](../jelly-live-count-2026-10-30/cast1-50/input-frame-005.png). Their
instantaneous counters read 32.7, 17.0, and 10.5 fps respectively. The cause
of the earlier profile job failures remains unknown; they do not establish a
count limit. The 30 fps threshold has not been measured with a timed profile.
The 0-companion build was close to the 60 Hz refresh ceiling, at 59.8 fps. The
settings check [shows integer endpoints and a 5→7 adjustment](final-settings-cast1/input-frame-004.png);
the [7-companion tank capture](final-settings-cast1/input-frame-005.png)
shows the added animals spread across the tank. The final APK was
[installed on cast1](final-install-cast1/apk-installations.json) and
[hash verified on Pixel 8 Pro](final-install-pixel-locked/apk-installations.json).
Pixel launcher verification could not run because the device was locked.
