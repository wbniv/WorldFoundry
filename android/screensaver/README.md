# Android TV screensaver APKs

`android/screensaver` builds three Android TV applications. Aquarium (`org.worldfoundry.screensaver`) renders eight aquarium level variants live. Each tank has an autonomous Player script built from its canonical gameplay export. The app chooses one tank when the Aquarium Dream starts; the default saved `random` preference draws from the eight tank IDs.

**Seahorse Grid** (`org.worldfoundry.seahorsegrid`) has its own DreamService, launcher icon and level bundle. Its World Foundry level has 24 visible seahorses in six columns and four rows against a dark background, alternating the existing female and male models. The level places the actors; each seahorse runs the same autonomous animation script. Build the level with `python3 scripts/build-seahorse-grid-level.py`. This Dream has no tank setting. Audio is not yet configured for it.

The player has no phone-controller prompt, QR code, or controller server, and requests no `INTERNET` permission. The native host hides the engine FPS counter and links the existing `wfengine` target through an app-specific CMake project hook. The Planted Tank uses the shared engine launch-override table to apply its Settings catalog before each level load.

All three Dreams and their live previews retain the cropped World Foundry graphic in the lower-right corner. Each app also has its own launcher icon with the approved badge; their TV banners include it. Regenerate icon resources with `python3 scripts/gen-screensaver-android-icons.py`.

Build the Aquarium and Seahorse level bundles and debug APKs with:

```sh
cargo build --release --offline --manifest-path wftools/cdpack-rs/Cargo.toml
python3 scripts/build-aquarium-screensaver-levels.py
cd android
./gradlew :screensaver:assembleAquariumDebug :screensaver:assembleSeahorseDebug --offline
```

The outputs are `android/screensaver/build/outputs/apk/aquarium/debug/screensaver-aquarium-debug.apk` and `android/screensaver/build/outputs/apk/seahorse/debug/screensaver-seahorse-debug.apk`. Freeze copies before submitting coordinator jobs. The Aquarium bundle order in `scripts/build-aquarium-screensaver-levels.py` must match `TankChoice.IDS`; the Seahorse bundle has its sole level at index zero.

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

On the shared TVs, use the coordinator for a launch-only override or to save a value for the Dream. The IDs come from the installed app's Settings catalog; here `4.2` is the Director's Water type, `4.1` its Seed and `4.3` its Growth speed (`4` means 2×). A rejected value changes nothing:

```sh
task chromecast:screensaver-show DEVICE=chromecast-test-01 OVERRIDES='{"4.2":"1","4.1":"713","4.3":"4"}'
task chromecast:screensaver-setting DEVICE=chromecast-test-01 SETTING_ID=4.2 VALUE=1
```

The provider also answers `getCapabilities`, `getSettings` and `resetSettings`. `getCapabilities` serves `assets/planted-settings.json` with the saved values filled in. `scripts/gen-settings-capabilities.py` generates that schema-2 file from the level's OAD-derived `settings.rprp` during `build_planted()`. It preserves the catalog owner and includes all eight fields; its show-as modifiers choose the UI type. The app adapter adds its `random` water policy, removes the unsupported Paused speed choice, and marks the derived Random seed on entry field read-only. Seed uses `random` as its unset value. The generated asset is gitignored, and the provider throws if it is missing. `task test-planted-screensaver` checks the catalog and runs `PlantedConfigTest` against a freshly generated asset.

Build and test with tasks, from the repo root: `task build-planted-level` (Blender container, then the bundle `wflevels/planted-screensaver-cd.iff` linked into the flavor), `task build-planted-apk` (runs the level build first, then `./gradlew :screensaver:assemblePlantedDebug --offline` for arm64-v8a and armeabi-v7a; the Chromecasts need armeabi-v7a) and `task test-planted-screensaver` (the C++ container tests, the python tests and `PlantedConfigTest`). The APK is `android/screensaver/build/outputs/apk/planted/debug/screensaver-planted-debug.apk`. The coordinator also has a declarative package allowlist; its generic Settings reader uses the provider authority and schema, without app-specific field rules. See [the device coordinator guide](../../docs/device-coordinator.md#planted-tank-screensaver) and the plan.
