# Runtime object editing: verification handoff, 11 November

Implementation is committed and pushed as `cd6b9e9e`; documentation and the
screensaver selection Task are `11744a1b`. The main plan's dated closeout status
and [cast2 evidence](../../diagnostics/runtime-object-editing-2026-11-11/cast2/README.md)
are the current status. Preserve unrelated staged and unstaged work in this
shared tree. The real-OAD Editor Label and fixed-size string follow-ups remain
separate; the baseline Pixel/runtime-options and Planted soak/timing gates also
retain their own TODO items.

All catalog-user migrations, the selector preview, separate RuntimeDiagnostics
form, Android capabilities, labels and pure text IFF/Blender authoring paths are
implemented. The production RP01 reader and catalog tools are removed; synthetic
UI fixtures remain under tests. Native checks, the 69-test isolated level suite,
42 presentation/touch tests, 12 phone/host/property checks and 114 Android bridge
checks passed. Both APK ABIs build. Current Aquarium and Planted previews rendered
on cast1 and cast2, and both devices' original Seahorse selections were restored.

## One final check remains

J‑2a9de06204d9 is the fresh cast2 gameplay held/released-input recording. It is
queued because coordinator control became unavailable for every device before
execution. Follow it through `task chromecast:watch JOB=J-2a9de06204d9`, download
evidence through the coordinator, and inspect the four directions plus the 40s
and 46s released-scene captures. Only then close the runtime-editing verification
TODO. J‑897f46fd7891 completed but used pre-migration RPRP code; it is historical
evidence, not final acceptance. No raw-device fallback is authorized.

Current gameplay APK:
`build-docker/runtime-editing-android/aquarium-game-actor-settings-cd6b9e9e.apk`,
SHA-256 `635980d9a540581f6812d420226373694147ae6f01f46ffec43138200fa03a81`.
It contains both ABIs and the current catalog-free menu bundle. The exact recipe
and APK identity are committed with the cast2 evidence summary.

## Build and test environment

Use the isolated Android source under `build-docker/runtime-editing-android/source`.
The first isolated screensaver builds had an outdated Rust `OadField` definition,
which caused a black preview. Both C++ and Rust source trees now match the repo.
Use only `*-cd6b9e9e-r2.apk` screensaver builds, signed with the normal host
development key:

- Aquarium: `aa48c4fbb52a96d5b25b91e33b4af7445d9041be53ad9e99a1d8d885e2f01b43`
- Planted: `bc8332cc3ae93ff80e111e4f1ebb8ce5a1e159c6e578c011703bfb0dd096f528`

The container browser needs fonts. Phone tests passed with these settings inside
`scripts/in-linux-container.sh`:

```sh
FONTCONFIG_FILE=/build/runtime-browser-fonts.conf
LD_LIBRARY_PATH=/build/runtime-browser-libs/root/usr/lib/x86_64-linux-gnu
PYTHONPATH=/build/runtime-browser-python
PLAYWRIGHT_BROWSERS_PATH=/build/runtime-browser-cache
```

The standard shared-workspace ignored Dream bundles may still be stale. The
isolated level build under `build-docker/runtime-editing-engine/src` contains the
validated rebuilt bundles. Do not overwrite other sessions' ignored outputs.
