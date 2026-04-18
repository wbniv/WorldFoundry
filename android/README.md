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
task build-apk        # → android/app/build/outputs/apk/debug/app-debug.apk
task push-assets      # adb push cd.iff to /data/local/tmp/wf/ (pre-AAssetManager)
task install-apk      # adb install + start NativeActivity
adb logcat -s wf_game # stream engine logs
```

Gradle calls the repo-root CMake (via `externalNativeBuild`) for arm64-v8a
with `-DCMAKE_BUILD_TYPE=RelWithDebInfo` and packages the resulting
`libwf_game.so` under `lib/arm64-v8a/` in the APK.

## Status

- **Phase 3 step 1**: `libwf_game.so` builds ✅
- **Phase 3 step 2**: `android_main` + EGL context ✅
- **Phase 3 step 3**: this Gradle project ✅
- **Phase 3 step 4**: touch / gamepad input wiring — pending
- **Phase 3 step 5**: `AAssetManager` asset accessor — pending
- **Phase 3 step 7**: first device / emulator smoke test — pending

See `docs/plans/2026-04-16-android-port.md` for the full plan.
