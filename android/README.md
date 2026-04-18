# WorldFoundry — Android build

This directory is the Android Gradle project that packages `libwf_game.so`
(built from the repo-root `CMakeLists.txt`) into an APK.

## One-time setup

The repo's `task dev-setup` installs the NDK. You additionally need:

- **Java 17** (`openjdk-17-jdk` on Debian/Ubuntu — already in `dev-setup`).
- **Android SDK platforms + build-tools**. One way:

  ```
  sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"
  ```

  (If `sdkmanager` isn't on your PATH, install `cmdline-tools;latest` from an
  Android Studio install or from the Android SDK command-line tools zip.)

- **Gradle 8.x**. Easiest: drop a gradle wrapper in this directory. Until
  then, install the package (`apt install gradle`, Homebrew `brew install
  gradle`, or `sdk install gradle 8.7` via sdkman).

Set `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) to your SDK install, e.g. in
`~/.bashrc`:

```sh
export ANDROID_HOME=/usr/lib/android-sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
```

A `local.properties` in this directory pointing Gradle at the SDK also works
and is git-ignored (`sdk.dir=/usr/lib/android-sdk`).

## Build

From this directory:

```
gradle assembleRelease
```

The APK lands in `app/build/outputs/apk/release/app-release.apk`.

Gradle calls the repo-root CMake (via `externalNativeBuild`) for arm64-v8a
with `-DCMAKE_BUILD_TYPE=RelWithDebInfo` and packages the resulting
`libwf_game.so` under `lib/arm64-v8a/` in the APK.

## Sideload + run

```
adb install -r app/build/outputs/apk/release/app-release.apk
adb shell am start -n org.worldfoundry.wf_game/android.app.NativeActivity
adb logcat -s wf_game
```

For the assets (`cd.iff`), until the APK asset pipeline lands (Phase 3 step
5), push the file to the device's working directory:

```
adb push /home/will/WorldFoundry/wfsource/source/game/cd.iff /data/local/tmp/wf/cd.iff
```

## Status

- **Phase 3 step 1**: `libwf_game.so` builds ✅
- **Phase 3 step 2**: `android_main` + EGL context ✅
- **Phase 3 step 3**: this Gradle project ✅
- **Phase 3 step 4**: touch / gamepad input wiring — pending
- **Phase 3 step 5**: `AAssetManager` asset accessor — pending
- **Phase 3 step 7**: first device / emulator smoke test — pending

See `docs/plans/2026-04-16-android-port.md` for the full plan.
