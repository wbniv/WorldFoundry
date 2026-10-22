# Aquarium screensaver APK

`android/screensaver` is a separate Android TV application (`org.worldfoundry.screensaver`). Its Aquarium DreamService and launcher preview render the eight aquarium level variants live. Each tank has an autonomous Player script built from its canonical gameplay export. The app chooses one tank when the Aquarium Dream starts; the saved `random` preference draws from the eight tank IDs.

The app also offers a separate **Seahorse Grid** DreamService. Its own World Foundry level has only 24 visible seahorses in six columns and four rows against a dark background, alternating the existing female and male models. Its Director starts each pair at a staggered phase of the three-second `rest_coil` idle clip, then gives each pair hovering, probing and greeting motions with gentle crossfades and quiet rests. Fins keep moving continuously. Build it with `python3 scripts/build-seahorse-grid-level.py`; the complete aquarium bundle build includes it as TOC index 8. This Dream has no tank setting. Audio is not yet configured for it.

The player has no phone-controller prompt, QR code, or controller server, and requests no `INTERNET` permission. The native host hides the engine FPS counter and links the existing `wfengine` target through an app-specific CMake project hook; shared engine code and its CMake file are unchanged. The planted tank currently retains its level-supplied seed/settings strip.

Both Dreams and their live previews show the cropped World Foundry graphic in the lower-right corner. The overlay is part of the screensaver app view, above the level render surface.

Build the level bundle and debug APK with:

```sh
cargo build --release --offline --manifest-path wftools/cdpack-rs/Cargo.toml
python3 scripts/build-aquarium-screensaver-levels.py
cd android
./gradlew :screensaver:assembleDebug --offline
```

The output is `android/screensaver/build/outputs/apk/debug/screensaver-debug.apk`. Freeze a copy before submitting coordinator jobs. The native bundle order in `scripts/build-aquarium-screensaver-levels.py` must match `TankChoice.IDS`.

The selected Dream advertises `org.worldfoundry.screensaver.settings`. Its shell-only provider answers `getCapabilities` with a base64-encoded schema-1 JSON choice list and accepts `setSetting` with `tank:<id>`. The coordinator uses a reviewed mapping for this Dream package and authority, validates the response, and offers those choices in the KDE tray. A changed preference takes effect at the next Dream start.

Install, settings, and idle activation checks use the shared coordinator through `task chromecast:*`. See [the implementation plan](../../docs/plans/2026-10-18-aquarium-screensaver-player-and-tray-settings.md). The former video prototype and its evidence are documented in [the investigation](../../docs/investigations/2026-10-17-chromecast-screensaver-from-a-level.md).

## Planted Tank

**Planted Tank** (`org.worldfoundry.plantedtank`, flavor `planted`) is a third app: the planted tank on its own, plants only, growing from seedlings to a full canopy, shown for a while, then replaced by a new tank. See [the plan](../../docs/plans/2026-10-21-planted-tank-screensaver.md). Parameters are validated once in `PlantedConfig` and saved in the `planted` preferences by `PlantedSettings`:

| Key | Values | Default |
|---|---|---|
| `water` | `freshwater`, `saltwater`, `random` (aliases `fresh`, `salt`) | `random` |
| `seed` | whole number 0 to 4294967295 | random per tank |
| `speed` | 0.25, 0.5, 1, 2, 4, 8 (0 is rejected) | `1` |
| `hold` | seconds, 0 to 86400 | `120` |
| `age`, `textures`, `sway` | developer keys: 0 to 240 s, true or false, true or false | `0`, `true`, `true` |

Run now with activity extras (used for this run only, never saved), or save values for the Dream through the shell-only settings provider; a bad value is rejected with a message and changes nothing:

```sh
adb shell am start -n org.worldfoundry.plantedtank/.PlantedTankActivity \
    --es water saltwater --el seed 713 --ef speed 2
adb shell content call --uri content://org.worldfoundry.plantedtank.settings \
    --method setSetting --arg water:saltwater
```

The provider also answers `getCapabilities`, `getSettings` and `resetSettings`. `getCapabilities` serves `assets/planted-settings.json` with the saved values filled in. `scripts/gen-settings-capabilities.py` generates that schema-2 file from the level's OAD-derived `settings.rprp` during `build_planted()`. It preserves the catalog owner and includes all eight fields; its show-as modifiers choose the UI type. The app adapter adds its `random` water policy, removes the unsupported Paused speed choice, and marks the derived Random seed on entry field read-only. Seed uses `random` as its unset value. The generated asset is gitignored, and the provider throws if it is missing. `task test-planted-screensaver` checks the catalog and runs `PlantedConfigTest` against a freshly generated asset.

Build and test with tasks, from the repo root: `task build-planted-level` (Blender container, then the bundle `wflevels/planted-screensaver-cd.iff` linked into the flavor), `task build-planted-apk` (runs the level build first, then `./gradlew :screensaver:assemblePlantedDebug --offline` for arm64-v8a and armeabi-v7a; the Chromecasts need armeabi-v7a) and `task test-planted-screensaver` (the C++ container tests, the python tests and `PlantedConfigTest`). The APK is `android/screensaver/build/outputs/apk/planted/debug/screensaver-planted-debug.apk`. The coordinator also has a declarative package allowlist; its generic Settings reader uses the provider authority and schema, without app-specific field rules. See [the device coordinator guide](../../docs/device-coordinator.md#planted-tank-screensaver) and the plan.
