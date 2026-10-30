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
| 15 | Exited on scene entry | J‑8aec7f96f1f5 |
| 26 | Exited on scene entry | J‑0028543728d7 |
| 50 | Exited on scene entry | J‑c008ddda67f8 |

The 30 fps point was not measured because the 15-companion build exited. The
0-companion build was close to the 60 Hz refresh ceiling, at 59.8 fps. The
settings check [shows integer endpoints and a 5→7 adjustment](final-settings-cast1/input-frame-004.png);
the [7-companion tank capture](final-settings-cast1/input-frame-005.png)
shows the added animals spread across the tank. The final APK was
[installed on cast1](final-install-cast1/apk-installations.json) and
[hash verified on Pixel 8 Pro](final-install-pixel-locked/apk-installations.json).
Pixel launcher verification could not run because the device was locked.
