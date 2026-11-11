# Runtime object editing: working state, 11 November

The migration following `edf5de87` is committed and pushed as `cd6b9e9e`. Preserve
all unrelated staged and unstaged work; do not use a blanket add, reset, clean,
or commit. The previous handoff and the parent plan explain the authorized scope.
The user chose the existing `PlantedTankSettings` actor with `Hold seconds` in a
Screensaver section, and chose to preserve baseline runtime diagnostics in a
separate form.

The actor-backed planted, jellyfish, reef and baseline paths, selector preview,
Android capabilities, and separate diagnostics form have been implemented.
`LevelRenderSettings` has also been migrated. The runtime RPRP reader was removed;
old-format decoding is retained only in test fixtures. The level-designer and
command-line documentation has been updated. Generated tracked levels were
rebuilt in `build-docker/runtime-editing-engine/src`; the main CD was repacked
with every original level preserved except the migrated baseline. The shared
screensaver builder and its test include another session's saltwater change;
that behavior has been preserved. Do not overwrite foreign changes in those files
or the modified `scripts/build-object-properties.py`.

The current container engine build and C++ adapter, preview and diagnostics
checks pass. An isolated compiled LevelRenderSettings level ran with
`ROOM-RENDER scope=current-only source=actor` (`build-docker/runtime-render-smoke/engine.log`). The rebuilt engine smoke test loaded actor settings and applied
seed 713 (`build-docker/runtime-editing-engine/final-actor-smoke.log`). Focused
plant, jellyfish, reef and screensaver checks reported 28 passed; presentation
and touch fixtures reported 42 passed. A broad run reported 66 passed and one
skipped, with four failures: Playwright is unavailable in the test container,
and three assertions read stale ignored Dream bundles in the shared workspace.
Fresh Dream bundles were built in the isolated checkout; verify them there and
avoid overwriting shared ignored outputs without checking ownership. The isolated baseline and screensaver suite passed all 69 tests against the freshly built outputs.

Catalog cleanup is complete: obsolete production tools and per-level catalog sources
were removed; synthetic UI fixtures retain the presentation examples and the prior
docstring edit. The final engine cleanup builds successfully. Playwright and its
headless browser and desktop libraries are now available under
`build-docker/runtime-browser-*`; phone tests are being run in the container.

Phone/browser verification passed: all 12 tests across plant phone, generic host
and property core suites passed with fonts configured.

Remaining work: finish device verification, including held/released directional
input on cast2, and record the results. The migration is already pushed. The queued cast2 recording job
`J‑897f46fd7891` is held by Will's personal reservation; do not release it or
bypass the coordinator. The old production catalog files are removed; tests use synthetic fixtures. The normal
shared-workspace Dream bundles are stale and should not be treated as evidence
of the new build.

Browser environment follow-up: Chromium initially could not edit text because the
Linux test image has no fonts or fontconfig configuration. Supplying DejaVu fonts
and `FONTCONFIG_FILE=/build/runtime-browser-fonts.conf` restored native edits.
No controller change was needed. The test environment uses
`LD_LIBRARY_PATH=/build/runtime-browser-libs/root/usr/lib/x86_64-linux-gnu`,
`PYTHONPATH=/build/runtime-browser-python`, and
`PLAYWRIGHT_BROWSERS_PATH=/build/runtime-browser-cache` inside the standard
project container. Playwright 1.62 and its headless Chromium are staged there.

Final verification: the configured browser run passed all 12 tests; the Android
launch bridge passed 114 checks. Fresh Aquarium and Planted debug APKs built successfully for both ABIs in `/build/runtime-editing-android/source` using both rebuilt Dream bundles
and the actor-derived provider metadata. The build log is
`build-docker/runtime-editing-android/final-apk-build.log`.

The frozen APKs are `build-docker/runtime-editing-android/{aquarium,planted}-actor-settings-cd6b9e9e.apk`.
Both include arm64-v8a and armeabi-v7a, no RPRP catalog, and the Planted asset
advertises owner 31 and OAD field IDs with the signed seed limit. Both were
signed using the normal host development key after the isolated Gradle key was
refused by the installed apps. The signed Aquarium APK installed successfully
in job J‑42d53ac43d6d. Its idle-Dream wait and queued Planted idle check
J‑1aa21c7b657a were cancelled by this session to avoid the eight-minute-per-app
idle wait. Explicit coordinator preview job J‑a79dd85c2c6d succeeded but showed the original
Seahorse selection. Aquarium was then temporarily selected in J‑49af9c04c328,
and its explicit preview is J‑12e3e5261a75. Restore the original Seahorse selection
after the preview capture. The missing `chromecast:screensaver-select` Task
alias was added, forwarding the existing coordinator command and COMPONENT field.
The earlier signature refusal evidence is saved under
`docs/diagnostics/runtime-object-editing-2026-11-11/aquarium/`.

The first isolated Android APKs produced a black Aquarium preview. An audit found
that the isolated checkout's `wftools/wf_attr_edit/src/lib.rs` lacked the current
`OadField.storage_width` member, creating a C++/Rust ABI mismatch. All engine and
Rust sources now match the repository, and rebuilding both ABIs completed in 37s.
Use only the `*-cd6b9e9e-r2.apk` files for further tests. The signed hashes are:

- Aquarium: `aa48c4fbb52a96d5b25b91e33b4af7445d9041be53ad9e99a1d8d885e2f01b43`
- Planted: `bc8332cc3ae93ff80e111e4f1ebb8ce5a1e159c6e578c011703bfb0dd096f528`

Coordinator installations J‑1f93459fa110 and J‑61a443c5a9a0 use these corrected
APKs. Their preview/capture sequence writes logs to
`docs/diagnostics/runtime-object-editing-2026-11-11/{aquarium,planted}-*.log`
and restores the original Seahorse selection in a finally block.

Cast1 verification passed with the corrected R2 APKs. Aquarium preview
J‑555991fca153 rendered the Arowana tank in capture J‑2e49a67b67d7.
Planted preview J‑d78c3c08836d rendered growing plants in capture
J‑2d7a042e367d. Both images were inspected. Planted provider metadata reports
owner 31, Seed field 129 with maximum 2147483647, and Hold seconds.
The original Seahorse selection was restored successfully in J‑5043c0906162.
Only the reserved cast2 held/released-input verification remains pending;
J‑897f46fd7891 is still queued and its reservation must be respected.
