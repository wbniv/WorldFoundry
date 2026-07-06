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
task build-apk        # → android/app/build/outputs/apk/debug/worldfoundry-debug.apk
task install-apk      # adb install + start NativeActivity
adb logcat -s wf_game # stream engine logs
```

`cd.iff` is bundled in the APK under `assets/` via a symlink
(`android/app/src/main/assets/cd.iff → ../../../../../wfsource/source/game/cd.iff`);
the AAssetAccessor reads it directly from the APK at runtime.

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
