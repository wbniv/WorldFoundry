# Android / Chromecast teleport verification

Status: standalone assertions and repeated chapter tours passed on both Chromecasts.

Engine implementation commit: [`c92ca353`](https://github.com/wbniv/WorldFoundry/commit/c92ca353). Review updated 2026-10-09, Asia/Bangkok.

The audited `teleport-audit` source was built with NDK 26.2.11394342 for `armeabi-v7a`, Android API 21, Release (`-O3`, thin LTO), Jolt and zForth. Engine assertions and UBSan were off. This tests the shipping-style configuration rather than relying on assertions to mask release failures. Debug-bridge support was compiled in, with no subscribed client during the device runs.

Both APKs reuse the existing Parmenides Android manifest and Java glue, with the audited native library substituted. Only the four-room variant substitutes the level. The chapter variant keeps its existing scene9 `cd.iff` bytes. Both store the level archive uncompressed, add `--frame-profile`, and retain the existing development signing identity. They are diagnostic APKs, not production releases. Debug sections were removed from the device library to fit the coordinator's 32 MiB upload limit; the original library is retained for symbolization.

## Standalone regression

Batch `B-885c3c12bc09`, APK SHA-256 `0fa01b422c335947272912906c9817d1899eb5eb0756a63b4687d7aed57c6303`.

| Device | Android / ABI | Coordinator job | Recorded arrivals | Complete seven-step tours | Largest camera X error | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Chromecast 01, HD | 14 / armeabi-v7a | `J-c24317f2ceae` | 151 | 21 | 0 | PASS |
| Chromecast 02 | 12 / armeabi-v7a | `J-eadb0ef85fcd` | 146 | 20 | 0 | PASS |

The autonomous Forth fixture cycles the desktop regression's seven commands every 0.5 game seconds. It reports on the next actor update, after teleport completion. Every record includes a monotonic step, command, actual Player X, actual camera X, cached unloaded-marker scale and a boolean assertion. The host validator checks every expected destination, camera position, scale 0.25, command sequence and contiguous record count. It also rejects runtime/script/pointer diagnostics.

The sequence includes adjacent-room jumps, disconnected-room jumps, retained rooms, complete active-set replacement, slot reuse and three X writes within one script with final destination C. Neither a running process nor a successful coordinator job alone constitutes the assertion result.

The coordinator owned installation, launch, recording, capture, transfer and cleanup. Downloaded artifacts were hash-verified by `task chromecast:evidence`; both jobs reached `completed`. Screen captures show the Player and room mesh present after repeated slot reuse. The 1920×1080 recordings were approximately 47.64 s and 49.77 s; screenrecord's frame rate is not an engine FPS measurement.

See [raw batch evidence](android/regression/batch.json), [arrival validation](android/regression/validation.json), [offline validator](android/validate-device.py), [APK receipts](android/inputs/receipts.json) and the per-device logs/videos beneath `android/regression/`.

## Chapter integration

Batch `B-7a616ae227c9`, APK SHA-256 `dcd09d9ac4eb55d80398e1850e6f47e373f0f39de0366c073f90962c6b1dec1e`.

The existing scene9 g1/view1 loop runs the chapter's own `fy-teleport` through Truth, God and Being and returns to repeat. Requested coordinator recordings are 135 seconds on each device. Jobs: `J-e01b28ace7cd` (01), `J-819e6fd27240` (02).

- [x] Both chapter jobs complete with clean coordinator cleanup and captured logs.
- [x] Decode both recordings and inspect realm changes and repeat visits.

The retained log tails contain 243 pose samples and 9 realm transitions on 01, and 283 samples and 10 transitions on 02. Both show repeated Truth → God → Being → Truth cycles in the correct order. These are counts evidenced by the downloaded log tails, not an estimate of transitions omitted earlier in the session. Both logs pass runtime/script/pointer checks.

Recordings decode and were visually inspected via frames sampled every 18 seconds. Actual durations are 132.06 s (01) and 134.76 s (02), at 1920×1080. The views show the three realms rendering through repeat visits. Their changing frame content and live pose records establish that the tour continues after return/slot reuse.

See [chapter batch](android/chapter/batch.json), [chapter validation](android/chapter/validation.json), [offline chapter validator](android/validate-chapter.py), and [01 contact sheet](android/chapter-01-sheet.png) / [02 contact sheet](android/chapter-02-sheet.png). Contact sheets are sampled evidence, not a frame-by-frame visual review.

## Scope

This verifies scripted Player teleports and following-camera arrival on both dedicated 32-bit Chromecasts. The transform API is verified by desktop CTest; no transform bridge was used outside coordinator ownership on devices. The phone/arm64 build, invalid/overlapping destinations, arbitrary unloaded actors, and systematic contact/terrain cases remain outside these runs. No new gameplay policy is implied.

The autonomous fixture was first checked on desktop (28 successful arrivals). Its authoring uses the existing Forth `EMIT`/`PRINT` host syscalls; it does not require a new engine diagnostic API. The default command-driven desktop fixture remains unchanged.
