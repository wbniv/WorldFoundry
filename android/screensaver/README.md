# Android TV screensaver APKs

`android/screensaver` builds three Android TV applications. Aquarium (`org.worldfoundry.screensaver`) renders eight aquarium level variants live. Each tank has an autonomous Player script built from its canonical gameplay export. The app chooses one tank when the Aquarium Dream starts; the default saved `random` preference draws from the eight tank IDs.

**Seahorse Grid** (`org.worldfoundry.seahorsegrid`) has its own DreamService, launcher icon and level bundle. Its World Foundry level has 24 visible seahorses in six columns and four rows against a dark background, alternating the existing female and male models. The level places the actors; each seahorse runs the same autonomous animation script. Build the level with `python3 scripts/build-seahorse-grid-level.py`. This Dream has no tank setting; its one setting is the orientation (see [Orientation](#orientation)). Audio is not yet configured for it.

The player has no phone-controller prompt, QR code, or controller server, and requests no `INTERNET` permission. The native host hides the engine FPS counter and links the existing `wfengine` target through an app-specific CMake project hook. The Planted Tank uses the shared engine launch-override table to apply values to its settings actor before each level load.

All three Dreams and their live previews show only the level render. Each app has its own launcher icon with the approved lower-right World Foundry badge; their TV banners also include it. Regenerate icon resources with `python3 scripts/gen-screensaver-android-icons.py`. The WF Clocks package's art (a clock on brass gears, not any one clock level) is drawn by `scripts/gen-wf-clocks-art.py` into `android/screensaver/art-src/wf-clocks-*.png`; run it first (in the container), then `python3 scripts/gen-screensaver-android-icons.py clocks` (it needs the system fonts for the banner name).

All three Dreams ship as Release builds ([measurements](../../docs/diagnostics/dream-release-2026-11-09/README.md)). The release build type is signed with the debug keystore, like the game app's, so it installs by sideload.

| Dream | Build task | Output | FPS on cast1, Debug → Release |
|---|---|---|---|
| Aquarium | `task build-aquarium-screensaver-apk` | `android/screensaver/build/outputs/apk/aquarium/release/screensaver-aquarium-release.apk` | reef 2.98 → 21.8, clownfish 30 → 59 |
| Seahorse Grid | `task build-seahorse-screensaver-apk` | `android/screensaver/build/outputs/apk/seahorse/release/screensaver-seahorse-release.apk` | 4.2 → 29.6 |
| Planted Tank | `task build-planted-apk` | `android/screensaver/build/outputs/apk/planted/release/screensaver-planted-release.apk` | 6.1 → 40.0 |
| WF Clocks | `task build-clocks-apk` | `android/screensaver/build/outputs/apk/clocks/release/screensaver-clocks-release.apk` | not measured yet |

The Aquarium and Seahorse tasks build the level bundles in the Linux container with `python3 scripts/build-aquarium-screensaver-levels.py`, which also runs `scripts/build-seahorse-grid-level.py`. They then run `./gradlew :screensaver:assemble<Flavor>Release --offline` on the host. The Debug variants (`assemble<Flavor>Debug`) still build, for the coordinator's simpleperf, which needs a debuggable or profileable APK. Freeze copies before submitting coordinator jobs. The Aquarium bundle order in `scripts/build-aquarium-screensaver-levels.py` is the order of `wflevels/aquarium-menu.manifest`, the tank roster; Gradle copies that file into the Dream's assets as `levels.manifest` and `LevelCatalog` reads it, so a tank is added in the manifest only (plus a `SCRIPT_NAMES` line if it needs its own driver); the Seahorse bundle has its sole level at index zero.

The selected Dream advertises `org.worldfoundry.screensaver.settings`. Its shell-only provider answers `getCapabilities` with a base64-encoded schema-1 JSON choice list and accepts `setSetting` with `tank:<id>` or `orientation:<value>`. The coordinator uses a reviewed mapping for this Dream package and authority, validates the response, and offers those choices in the KDE tray. A changed preference takes effect at the next Dream start.

Install, settings, and idle activation checks use the shared coordinator through `task chromecast:*`. See [the implementation plan](../../docs/plans/2026-10-18-aquarium-screensaver-player-and-tray-settings.md). The former video prototype and its evidence are documented in [the investigation](../../docs/investigations/2026-10-17-chromecast-screensaver-from-a-level.md).

## Orientation

All three scenes are wide, so each screensaver starts in landscape by default, also on a portrait phone or tablet. The default is the `default_orientation` string resource in `src/main/res/values/orientation.xml`, shared by all three flavors; a flavor could override it with its own `src/<flavor>/res/values/orientation.xml`, though none does. An invalid resource value falls back to `landscape`. Each app saves its own `orientation` choice (`OrientationSettings`, key `orientation` in the `screensaver` preferences of that app's package); see [the plan](../../docs/plans/2026-10-24-screensaver-landscape-orientation.md):

| Value | Requests | Use |
|---|---|---|
| `landscape` | `SCREEN_ORIENTATION_LANDSCAPE` | Default. Fixed landscape. |
| `sensor-landscape` | `SCREEN_ORIENTATION_SENSOR_LANDSCAPE` | Landscape, flipping when the device is turned 180°. |
| `follow-device` | `SCREEN_ORIENTATION_UNSPECIFIED` | The device's orientation; a portrait screen shows the scene in a 16:9 strip. |

`DreamOrientation.apply` runs in each Dream's `onAttachedToWindow` and in each launcher and preview activity's `onCreate`, before the content view is set. From Android 11 a Dream's window belongs to the system's `DreamActivity`, so it calls `setRequestedOrientation` on it; on Android 10 and earlier it sets the `TYPE_DREAM` window's `screenOrientation` attribute instead (checked in the Android source only, not run on a device). The Chromecasts are landscape already and look as before. `task test-screensaver-orientation` runs the plain-Java `OrientationChoiceTest`.

Each app's shell-only settings provider offers the choice, and a change takes effect at the next Dream start:

| App | Authority | Setting ID |
|---|---|---|
| Aquarium | `org.worldfoundry.screensaver.settings` | `orientation` (schema 1, beside `tank`) |
| Seahorse Grid | `org.worldfoundry.seahorsegrid.settings` (`SeahorseSettingsProvider`) | `orientation` (schema 1, its only setting) |
| Planted Tank | `org.worldfoundry.plantedtank.settings` | `31.orientation` (schema 2: the adapter appends it to the settings actor, currently actor `31`) |
| WF Clocks | `org.worldfoundry.clocks.settings` (`ClocksSettingsProvider`) | `orientation` (schema 1, beside `clock`) |

```sh
task chromecast:screensaver-setting DEVICE=phone-pixel-8-pro SETTING_ID=orientation VALUE=landscape
task chromecast:screensaver-setting DEVICE=phone-pixel-8-pro SETTING_ID=31.orientation VALUE=follow-device  # Planted Tank
```

The coordinator side is not done yet: its Seahorse Grid application entry has no `settings_authority`, so the tray and `screensaver-setting` do not list the Seahorse Grid's orientation until it gets one.

## WF Clocks

**WF Clocks** (`org.worldfoundry.clocks`, flavor `clocks`) holds every World Foundry clock in one app and one `cd.iff`. The roster is `wflevels/clocks-menu.manifest`: Minute Machine (`minute_machine`, level 0) and Tide Harbour (`tide_harbour`, level 1), so the launcher shows the chooser. The built levels and the bundle are committed; `task clocks-check` proves they rebuild identically (`task clocks-regenerate` rewrites them). A clock is added by appending one `level` line; ids are stable and the index is the table-of-contents position, so a saved choice never moves. `task clocks-bundle` packs the manifest with `shell-menu.fth` and its MENU chunk (`scripts/pack-clocks-bundle.py`, which stops naming any id with no built level), and `task build-clocks-apk` builds the Release APK for arm64-v8a and armeabi-v7a and checks both are in it. See [the Tide Harbour plan](../../docs/plans/2026-11-21-tide-harbour-clock.md), "The bundle and the chooser", and [the HOWTO](../../docs/howto/combine-levels-chooser-and-screensaver-launch.md).

- **Launcher** (`ClocksActivity`): with no extra it opens the engine's chooser (`TankPlayer.start(-1)`; the host leaves out the positional level). With one clock in the bundle the engine starts it directly, as it does for any one-entry menu. The remote drives the chooser: up and down move, OK (D-pad centre, Enter, gamepad A) picks (`TankPlayer.buttons` → `nativeButtons` → the engine's `_HALSetJoystickButtons`). Back in a clock picked from the chooser returns to it; Back on the chooser leaves the app.
- **One clock directly**: `adb shell am start -n org.worldfoundry.clocks/org.worldfoundry.screensaver.ClocksActivity --es org.worldfoundry.screensaver.LEVEL minute_machine` (or `random`). An unknown id is logged and shown, and nothing starts. It is one run only; the saved choice is not changed. Back leaves the app (no chooser).
- **Dream** (`ClocksDreamService`): the saved clock, default `random`, resolved once per run; never the chooser, and it never forwards keys (any key wakes it).
- **Chooser test build**: from before the second clock, `task build-clocks-two-entry-apk` builds the same package with Minute Machine listed twice (throwaway manifest and bundle under `android/screensaver/build/clocks-two-entry/`, via `-PwfClocksManifest` and `-PwfClocksAssets`), so the chooser appears. It replaces the shipped app on a device; `task build-clocks-apk` rebuilds the shipped one.
- **Settings** (`ClocksSettingsProvider`, shell only): `getCapabilities`, `getClock`, and `setSetting` with `clock:<id>`, `clock:random` or `orientation:<value>`. Only this provider writes the saved choice, so a preview never overwrites it.

## Planted Tank

**Planted Tank** (`org.worldfoundry.plantedtank`, flavor `planted`) is a third app: the planted tank on its own, plants only, growing from seedlings to a full canopy, shown for a while, then replaced by a new tank. See [the plan](../../docs/plans/2026-10-21-planted-tank-screensaver.md). Parameters are validated once in `PlantedConfig` and saved in the `planted` preferences by `PlantedSettings`:

| Key | Values | Default |
|---|---|---|
| `water` | `freshwater`, `saltwater`, `random` (aliases `fresh`, `salt`) | `random` |
| `seed` | whole number 0 to 2147483647 | random per tank |
| `speed` | 0.25, 0.5, 1, 2, 4, 8 (0 is rejected) | `1` |
| `hold` | seconds, 0 to 86400 | `120` |
| `age`, `textures`, `sway` | developer keys: 0 to 240 s, true or false, true or false | `0`, `true`, `true` |

On the shared TVs, use the coordinator for a launch-only override or to save a value for the Dream. IDs come from the installed app's settings actor and its OAD fields; currently `31.130` is Water type, `31.129` is Seed and `31.131` is Growth speed (`4` means 2×). Check the installed app's capabilities for current IDs. A rejected value changes nothing:

```sh
task chromecast:screensaver-show DEVICE=chromecast-test-01 OVERRIDES='{"31.130":"1","31.129":"713","31.131":"4"}'
task chromecast:screensaver-setting DEVICE=chromecast-test-01 SETTING_ID=31.130 VALUE=1
```

The provider also answers `getCapabilities`, `getSettings` and `resetSettings`. `getCapabilities` serves `assets/planted-settings.json` with saved values filled in. `scripts/gen-settings-capabilities.py` generates that schema-2 file from the actor's OAD during `build_planted()`, omitting the animal fields. The app adapter adds its `random` water policy, removes the unsupported Paused speed choice, and marks the derived Random seed on entry field read-only. It also appends the app-level [Orientation](#orientation) choice. Seed uses `random` as its unset value; previously saved seeds above the current maximum are clamped when read. The generated asset is gitignored, and the provider throws if it is missing. `task test-planted-screensaver` checks the provider metadata and runs `PlantedConfigTest` against a freshly generated asset.

Build and test with tasks, from the repo root: `task build-planted-level` (Blender container, then the bundle `wflevels/planted-screensaver-cd.iff` linked into the flavor), `task build-planted-apk` (runs the level build first, then `./gradlew :screensaver:assemblePlantedRelease --offline` for arm64-v8a and armeabi-v7a; the Chromecasts need armeabi-v7a) and `task test-planted-screensaver` (the C++ container tests, the python tests and `PlantedConfigTest`). The APK is `android/screensaver/build/outputs/apk/planted/release/screensaver-planted-release.apk`. The coordinator also has a declarative package allowlist; its generic Settings reader uses the provider authority and schema, without app-specific field rules. See [the device coordinator guide](../../docs/device-coordinator.md#planted-tank-screensaver) and the plan.
