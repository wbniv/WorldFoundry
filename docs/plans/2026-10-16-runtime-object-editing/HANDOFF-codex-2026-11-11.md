# Runtime object editing: working state, 11 November

The migration following `edf5de87` is ready to commit and push. Preserve
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

Remaining work: freeze and test the current APK,
verify held/released directional input on cast2, and commit and push the reviewed
migration paths. The explicit path list is `/tmp/runtime-editing-paths.json`. The queued cast2 recording job
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
