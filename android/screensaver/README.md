# Aquarium screensaver APK

`android/screensaver` is a separate Android TV application (`org.worldfoundry.screensaver`). Its DreamService and launcher preview render the eight aquarium level variants live. Each tank has an autonomous Player script built from its canonical gameplay export. The app chooses one tank when the Dream starts; the saved `random` preference draws from the eight tank IDs.

The player has no phone-controller prompt, QR code, or controller server, and requests no `INTERNET` permission. The native host hides the engine FPS counter and links the existing `wfengine` target through an app-specific CMake project hook; shared engine code and its CMake file are unchanged. The planted tank currently retains its level-supplied seed/settings strip.

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
