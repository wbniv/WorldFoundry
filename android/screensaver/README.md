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
