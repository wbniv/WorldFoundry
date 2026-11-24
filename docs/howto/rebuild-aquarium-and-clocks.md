# Rebuilding Aquarium and 3D Clocks

This source snapshot contains the 2026-11-24 development build inputs for the
Aquarium and 3D Clocks Android packages. It includes work in progress from the
shared checkout; it is not a statement that the levels have passed release
acceptance.

On Linux, install Docker, Task, Rust, Python 3, Java 21 and the Android SDK
(including the CMake and NDK versions required by `android/screensaver`). Build
the project's Blender and Linux test container images using the instructions in
`docker/` and `docs/level-building.md`. Point `ANDROID_HOME` at the SDK, then:

```sh
export ANDROID_HOME=/path/to/android-sdk
task build-clocks-apk
task build-aquarium-screensaver-apk
```

The tasks unpack the bundled Jolt archive when necessary. Gradle can download
dependencies on its first run; set `WF_GRADLE_OFFLINE=--offline` only when its
dependencies are already cached. APKs land under
`android/screensaver/build/outputs/apk/{clocks,aquarium}/release/`. Signing uses
the local debug keystore, so another computer's APK signatures and byte hashes
can differ. Freeze and hash the APKs before device installation.

The Clocks package task rebuilds Minute Machine and Tide Harbour and packages
the checked-in standalone outputs for the rest of the roster. For reauthoring
all levels rather than packaging those outputs, consult `task clocks-regenerate`
and each level's build instructions and assets. Do not confuse package build
success with visual, performance or device acceptance.
