# WorldFoundry — Android build

This directory is the Android Gradle project that packages `libwf_game.so`
(built from the repo-root `CMakeLists.txt`) into an APK.

## One-time setup

```
task dev-setup            # NDK + JDK + adb (from repo root)
task android-sdk-install  # cmdline-tools + platforms;android-34 + build-tools;34.0.0 + Gradle 8.7
```

`android-sdk-install` is idempotent — re-runs skip already-installed pieces.
Needs sudo to write under `/usr/lib/android-sdk/` and `/opt/`. It also writes
`android/local.properties` pointing Gradle at the SDK.

After it finishes, add the env-var lines it prints to `~/.bashrc` /
`~/.zshrc` so Gradle + adb are always on PATH.

## Build + install

```
task build-apk        # → android/app/build/outputs/apk/<app>/release/worldfoundry-<app>-release.apk
task build-apk-debug  # → android/app/build/outputs/apk/<app>/debug/worldfoundry-<app>-debug.apk
task install-apk      # APP=aquarium|snowgoons: install + start the release APK (scripts/android-device-run.sh)
task chromecast-aquarium -- <ip>   # network ADB: install, launch, screenshot, logcat, frame pacing → ~/tmp
adb logcat -s wf_game # stream engine logs
```

Without sudo, the SDK + NDK in `~/android-sdk-local` also build it (`task build-apk` stops at its `android-sdk-install` step, which wants `sudo`):
`cd android && ANDROID_HOME=~/android-sdk-local ./gradlew :app:assembleCondoRelease` (or `AquariumRelease`; the `snowgoons` release also needs the gitignored
soundfont, or `-x lintVitalAnalyzeSnowgoonsRelease -x lintVitalReportSnowgoonsRelease -x lintVitalSnowgoonsRelease`).

**One app per game.** Gradle product flavors (`android/app/build.gradle.kts`) build the same
`libwf_game.so` and Java glue into separate apps that install side by side
(`docs/plans/2026-09-30-aquarium-chromecast.md`):

| Flavor (`<app>`) | applicationId | Label / banner | `assets/cd.iff` |
|---|---|---|---|
| `snowgoons` | `org.worldfoundry.wf_game` | World Foundry (`src/main/res`) | `wfsource/source/game/cd.iff` (task `build-cd-iff`; boots TOC level 0), plus `level0.mid` + soundfont |
| `aquarium` | `org.worldfoundry.wf_game.aquarium` | WF Aquarium (`src/aquarium/res`) | `wflevels/aquarium-cd.iff` (task `build-cd-iff-aquarium`) |
| `condo` | `org.worldfoundry.wf_game.condo` | WF Condo (`src/condo/res`) | `wflevels/condo-cd.iff` (task `build-cd-iff-condo`), plus `wf_args.txt` (the engine flags the level needs) |

Each flavor's `cd.iff` is a symlink in `android/app/src/<app>/assets/`; the AAssetAccessor reads
it directly from the APK at runtime. The aquarium's banner and icons come from
`scripts/gen-aquarium-android-art.py`.

Gradle calls the repo-root CMake (via `externalNativeBuild`) for arm64-v8a **and armeabi-v7a** (the Chromecast HD is 32-bit only)
with `-DCMAKE_BUILD_TYPE=RelWithDebInfo` and packages the resulting
`libwf_game.so` under `lib/arm64-v8a/` in the APK.

## Status

Phases 1–3 complete. Playable APK on arm64; port is closed pending launcher
icons + light polish.

- **Phase 3 step 1**: `libwf_game.so` builds ✅
- **Phase 3 step 2**: `android_main` + EGL context ✅
- **Phase 3 step 3**: Gradle project ✅
- **Phase 3 step 4**: touch + gamepad input (TV-mode detection) ✅
- **Phase 3 step 5**: `AAssetManager` asset accessor (reads `cd.iff` from APK) ✅
- **Phase 3 step 6**: audio (miniaudio + TinySoundFont, `level0.mid` + soundfont bundled) ✅
- **Phase 3 step 7**: on-device smoke test on arm64 phone ✅
- **Post-boot polish**: viewport/projection aspect, pause/resume EGL context
  preservation, zForth `if/else/then` director fix, on-screen touch HUD ✅

Remaining before full closure: adaptive-icon XML (`res/mipmap-anydpi-v26/`)
layered on top of the legacy mipmap PNGs just landed, and the
audio-assets-from-iff remediation (`docs/plans/2026-04-18-audio-assets-from-iff.md`)
that collapses the three-symlink transitional `assets/` layout to a single
bundled `cd.iff`. See `docs/investigations/2026-04-18-android-port-closure.md`.

See `docs/plans/2026-04-16-android-port.md` for the full plan.

## Playing on a Chromecast with Google TV

Plans: [the Chromecast plan](../docs/plans/2026-09-30-aquarium-chromecast.md) (Phase E, the phone), [the OK button](../docs/plans/2026-10-01-chromecast-ok-button.md).

- **The remote.** The D-pad walks (the aquarium: moves the fish) and **OK is button A**. In the condo, A toggles the project-room glass doors and the balcony zip screen
  when you stand near them (there is no hop; B does nothing). Back hides the phone panel below. The remote has no other buttons the game can use.
- **The phone as a gamepad** (aquarium and condo only; snowgoons starts no server). The app shows a panel on the TV with a QR code, a URL (for example `192.168.4.38:8765`) and a PIN.
  Join the **same Wi-Fi as the TV** (a guest network, the other band, mobile data or a VPN looks like a page that never loads), scan the QR, and the phone becomes the controller:
  aquarium = stick, A, B; condo = stick, doors/shade (A), teleport (C), orbit (hold D, then the stick), zoom in/out (E/F). Nothing is installed on the phone; the page is served by the TV app
  over the local network only, behind a fresh PIN each launch, and the TV releases every button if the phone stops sending for 1 s. The PIN changes every time the app starts.
- **Logs.** `adb logcat -s wf_game` shows one line per remote key (`key code=23 …`), per accepted phone connection and per button change.
- **Not built yet:** tilt steering (needs an https page and a certificate) and game-driven vibration; both are parked in `TODO.md`.
