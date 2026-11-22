# One Aquarium APK: retire the standalone playable app

**Status: decided by Will 2026‑11‑22, not started.** Will: "i only want 1 apk with combined app and screensaver (with the good icon)". The combined app, `org.worldfoundry.screensaver`, already is that APK. This plan retires the second one, `org.worldfoundry.wf_game.aquarium`, and lists what goes with it. It closes the `[T4]` question in [the One Aquarium app plan](2026-11-21-one-aquarium-app.md) (decision 2 there kept the old package "for now").

## Where it stands

| | Combined app (keep) | Standalone playable app (retire) |
|---|---|---|
| Package | `org.worldfoundry.screensaver` | `org.worldfoundry.wf_game.aquarium` |
| Built by | `android/screensaver`, flavor `aquarium` | `android/app`, product flavor `aquarium` (and its `diagnostic` build type) |
| Icon and banner | the approved clownfish, tiger barb and betta art (`585d590f`) | the old clownfish tank banner |
| Normal launch | the tank menu; a tank from it is the playable one (steered on cast1, 2026‑11‑22, `J‑08baa5d0ca23`) | the same menu |
| As a screensaver | `AquariumDreamService`, preview, `LEVEL` and `DREAM` extras, settings provider | none |
| Phone as a controller | no | yes (`controller.html`, `layout.json`) |
| Installed on | cast1, the Pixel | cast1, the Pixel |

## What retiring removes

These are the real costs, found by inventory on 2026‑11‑22, not guesses:

1. **The phone-pad controller for the Aquarium** (the phone as a gamepad over the LAN). The combined app has none; the TV remote's d-pad steers the fish. The condo flavor keeps its own phone pad.
2. **The `diagnostic` build of the Aquarium** (`assembleAquariumDiagnostic`) and, with it, the coordinator's `aquarium` registry entry (`native`, eight scenes) that `record`, `profile` and `check` use for runtime-diagnostics, settings and plant checks.
3. **Ten scripts and harnesses that start the old package by name:** `scripts/check-arowana-device.py`, `check-growing-plants-device.py`, `check-growing-plants-lifetime.py`, `check-lionfish-feeding-device.py`, `check-menu-back-device.py`, `check-species-device.py`, `profile-growing-plants-device.py`, `profile-growing-plants-trace.py`, plus `scripts/android-device-run.sh`, `wflevels/aquarium_tanks/check_chromecast_menu.py`.
4. **`android/app/src/aquarium/assets/wf_args.txt`**, which the desktop `task run-aquarium-menu` and a comment in `CMakeLists.txt` read: it moves, it is not deleted.
5. **Tests that guard the flavor:** `tests/test_aquarium_android.py` (14 tests; the TODO records that its Taskfile asset checks already fail on origin), `tests/phonepad_harness.py`'s aquarium layout, and checks in `test_game_apps_android.py`, `test_launcher_parity.py`, `test_dream_host_vram.py` and others that name the package.

Left alone: the historical device logs and plan evidence that name the package (about 2 000 files), which are a record, and the Homeboard and coordinator repositories until their own steps below.

```mermaid
flowchart LR
    A["Phase 0<br/>devices: one Aquarium tile"] --> B["Phase 1<br/>stop building the old APK"]
    B --> C["Phase 2<br/>re-home what hung off it"]
    C --> D["Phase 3<br/>coordinator and Homeboard"]
    B -.->|"git revert restores it"| X["old flavor"]
```

## Phases

0. **Devices.** Remove `org.worldfoundry.wf_game.aquarium` from cast1 and the Pixel. The coordinator has no uninstall workflow (checked: `capability-describe uninstall` finds nothing), so this is a manual step on each device (Pixel: long-press the icon, Uninstall; Chromecast: Settings, Apps). Nothing else on the devices changes.
1. **Stop building it.** Remove the `aquarium` flavor from `android/app/build.gradle.kts`, `android/app/src/aquarium/`, the `build-apk` and `build-apk-diagnostic` and `install-apk` defaults that name it, and the `chromecast-aquarium` alias; rewrite `tests/test_aquarium_android.py` to the snowgoons and condo flavors that remain.
2. **Re-home what hung off it.** Move `wf_args.txt` next to the menu bundle for `run-aquarium-menu` and CMake; decide for each device script in item 3: port to the combined app (`AquariumActivity`, `LEVEL`), or archive it under `docs/reference/device-harnesses/` where eleven already have a `.txt` copy.
3. **Coordinator and Homeboard.** Remove or re-point the registry's `aquarium` entry (a protected registry edit, with Will's approval at that step); update Homeboard's directory and investigation notes.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | The end state is one Aquarium package. | Will, 2026‑11‑22. |
| D2 | The old flavor is removed in Phase 1, not kept as a hidden dev build. | A second APK that nobody installs still gets built, tested and named in scripts. `git revert` restores it. |
| D3 | The phone-pad controller and the diagnostic build are given up. | The combined app has neither; the d-pad steers. If either is wanted back it becomes a feature of the combined app, not a second package. |
| D4 | Phase 0 is manual. | There is no uninstall in the coordinator; adding one is a protected capability and not worth building for this. |

## Open

| # | Question | Recommendation |
|---|---|---|
| Q1 | Give up the Aquarium phone-pad controller and the diagnostic build (D3)? | Yes. The remote steers the fish, and the diagnostics can be rebuilt on the combined app if a validator needs them. |
| Q2 | For each of the ten scripts in item 3: port or archive? | Archive the one-off investigations (arowana, growing plants, species, lionfish feeding); port `check-menu-back-device.py`, which now belongs to the combined app's menu. |

## Verification

1. `task chromecast:devices` then an `inspect` job on cast1 and the Pixel: `packages.txt` has `org.worldfoundry.screensaver` and not `org.worldfoundry.wf_game.aquarium`.
2. `git grep -l "wf_game\.aquarium" -- . ':!docs/diagnostics' ':!docs/transcripts' ':!docs/plans'` lists only files this plan names as kept.
3. `scripts/in-linux-container.sh python3 -m pytest tests -q -k "aquarium or launcher or android"` passes.
4. `cd android && ./gradlew :app:tasks --offline` lists no `Aquarium` variant, and `./gradlew :screensaver:assembleAquariumRelease --offline` still builds.
5. `task run-aquarium-menu` still starts the menu on the desktop.
6. On cast1 and the Pixel: one Aquarium tile, with the approved icon, that opens the menu; the Dream still starts from the lock screen while charging.
