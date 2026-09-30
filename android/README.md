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

Without sudo, the SDK + NDK in `~/android-sdk-local` also build it:
`cd android && ANDROID_HOME=~/android-sdk-local ./gradlew :app:assembleDebug`.

**One app per game.** Gradle product flavors (`android/app/build.gradle.kts`) build the same
`libwf_game.so` and Java glue into separate apps that install side by side
(`docs/plans/2026-09-30-aquarium-chromecast.md`):

| Flavor (`<app>`) | applicationId | Label / banner | `assets/cd.iff` |
|---|---|---|---|
| `snowgoons` | `org.worldfoundry.wf_game` | World Foundry (`src/main/res`) | `wfsource/source/game/cd.iff` (task `build-cd-iff`; boots TOC level 0), plus `level0.mid` + soundfont |
| `aquarium` | `org.worldfoundry.wf_game.aquarium` | WF Aquarium (`src/aquarium/res`) | `wflevels/aquarium-cd.iff` (task `build-cd-iff-aquarium`) |

Each flavor's `cd.iff` is a symlink in `android/app/src/<app>/assets/`; the AAssetAccessor reads
it directly from the APK at runtime. The aquarium's banner and icons come from
`scripts/gen-aquarium-android-art.py`.

Gradle calls the repo-root CMake (via `externalNativeBuild`) for arm64-v8a
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
