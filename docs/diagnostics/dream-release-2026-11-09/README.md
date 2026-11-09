# Aquarium Dream: Debug against Release on cast1, 9 November 2026

This is the TODO item "Ship the Aquarium Dream as a Release build" (Will, 2026‑11‑09: "Investigate Release"). The [cast1 acceptance run](../reef-cast1-acceptance-2026-11-09/README.md#step-12-dream-with-each-reef) found the reef Dream running at about 3 FPS, because the screensaver APK was built as Debug.

**Result:** a Release build of the Aquarium Dream renders the reef about **7× faster** than Debug: 21.8 FPS against 2.98, which is about what the game app holds. Nothing broke. The Aquarium Dream now builds and ships as Release.

## Numbers

Device: cast1 (`chromecast-test-01`, Chromecast HD, Android 14, armeabi‑v7a). Every action went through the coordinator. Both APKs were built from the same HEAD Dream bundle. The tank was set through the Dream's own settings provider, and Layout is Random, the shipped default.

| Tank | Debug FPS (3 runs) | Release FPS (3 runs) | Debug frame p50 | Release frame p50 |
|---|---|---|---|---|
| Gulf of Thailand Reef | **2.98** (2.98, 2.98, 2.97) | **21.80** (21.54, 21.80, 22.13) | 333.7 ms | 50.1 ms |
| Gulf of Thailand Reef — Anime | **2.72** (2.74, 2.72, 2.68) | **19.98** (19.81, 20.12, 19.98) | 367.0 ms | 50.1 ms |
| Clownfish & Sea Anemone (non-reef) | **29.97** (44.31, 29.97, 29.97) | **59.45** (29.97, 59.45, 59.45) | 33.4 ms | 16.7 ms |

- **How it was measured:** the coordinator's `profile` workflow, run three times per cell (`task chromecast:profile`, `APP=screensaver`). It counts the frames SurfaceFlinger presents for the Dream app's own player, `AquariumActivity`, which is the same native `TankPlayer` as the Dream.
- **Why not the engine log:** the engine logs frame deltas only when a frame takes longer than 0.2 s (`delta too large`, in `gfx/gl/display.cc`). That shows the slow Debug frames, as the acceptance run read them, but says nothing about a Release build that never drops below 5 FPS.
- **Agreement with the acceptance run:** the Debug reef matches it: 2.98 FPS here, and a 0.338 s median delta there.
- **The Release Dream itself:** `screensaver-show` (J‑13f237b69178) ran the reef in the Dream's preview path for 75 s. `screensaver-status` (J‑d865fa46af7a) then found the preview running, the settings provider `ready` with `tank = aquarium_thai_reef`, and no assertion. One slow frame, 0.85 s, came at level load, and none followed ([status](release-dream-reef-status.json), [engine log tail](release-dream-reef-engine-log-tail.txt)).
- **Evidence:** the per-run numbers are in [`results.json`](results.json), with the job IDs. The screenshots show each tank as profiled:

| | Reef | Anime reef | Clownfish |
|---|---|---|---|
| Debug | ![](debug-aquarium_thai_reef.jpg) | ![](debug-aquarium_thai_reef_anime.jpg) | ![](debug-aquarium.jpg) |
| Release | ![](release-aquarium_thai_reef.jpg) | ![](release-aquarium_thai_reef_anime.jpg) | ![](release-aquarium.jpg) |

## Why it was Debug

Nothing in the git log or the plans chose Debug on purpose. The screensaver's `release` build type had no `signingConfig`, so a release APK came out unsigned and could not be sideloaded. Every README, plan and task therefore used `assemble…Debug`, from the first live screensaver (`54f44b51`, 2026‑10‑18) and the flavor split (`d4b4070a`, 2026‑10‑23) onwards. Nothing that ships depends on Debug.

The coordinator's `simpleperf` workflow needs a profileable or debuggable APK. Anyone who wants to profile the Dream can still build the Debug variant.

## What changed

- `android/screensaver/build.gradle.kts` (`a39d33c8`): the `release` build type now matches the game app's release. It is signed with the debug keystore for sideload, `isDebuggable = false`, and passes `-DCMAKE_BUILD_TYPE=Release`, which gives `wfengine`, Jolt and zforth -O3 and thin LTO. `libwf_dream.so` for armeabi‑v7a shrinks from 5.9 MB to 3.2 MB.
- `Taskfile.yml`: a new `build-aquarium-screensaver-apk` task.
    - It builds the Dream levels and bundle in the Linux container, then runs `./gradlew :screensaver:assembleAquariumRelease --offline` on the host, as `task build-apk` does.
    - It has no `android-sdk-install` dependency, like `build-planted-apk`, because that step runs `sudo` for the SDK licences.
- `android/screensaver/README.md`: the Aquarium Dream ships as Release. The Seahorse Grid and Planted Tank Dreams still build as Debug; their Release builds work but have not been measured.
- `tests/test_screensaver_release_build.py` (new): the task must assemble the Release variant, and the release build type must stay signed, not debuggable, and CMake Release.

## cast1 afterwards

| | Before | After |
|---|---|---|
| Selected Dream | Seahorse Grid | Seahorse Grid (J‑14b6eec60eb4) |
| Aquarium Dream `tank` | `random` | `random` (J‑4449c311eee7) |
| Aquarium screensaver package | `5dfdba1f…` (the acceptance run's VRAM fix) | `5dfdba1f…` reinstalled (J‑07dbc6b02d14; before it, the Release `ecf5e860…`) |
| Game APK | `30554973…` | unchanged: no job here installed it; every installation recorded was `org.worldfoundry.screensaver` |
| Running | nothing | nothing (status at 14:07 UTC; 21:07 in Bangkok) |

The press job (Home) relaunches the foreground it found, so it brought the Aquarium preview back. A `sleep` job was needed to end the preview before the package could be reinstalled. cast1 was left asleep; it wakes on its remote.
