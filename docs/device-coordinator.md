# Chromecast coordinator client for World Foundry

The shared service now belongs to the independent private repository
[wbniv/chromecast-coordinator](https://github.com/wbniv/chromecast-coordinator),
checked out at `/home/will/chromecast-coordinator`. It owns service code,
reviewed validators, capture helper, deployment, host policy and shared tests.
World Foundry owns APK builds, level/variant preparation and thin producer shims.

The existing installation was upgraded in place. Operational paths remain
`/opt/wf-device-coordinator`, `/etc/wf-device-coordinator`,
`/var/lib/wf-device-coordinator` and `/run/wf-device-coordinator`. Database,
client credentials, enrollment, ADB keys, queue, reservations and evidence are
retained. No second scheduler or device identity is introduced.

## Device sessions

Build/freeze the APK locally, then use the familiar Task commands:

```sh
task chromecast:devices
task chromecast:queue
task chromecast:check DEVICE=chromecast-test-01 APP=aquarium APK=/path/frozen.apk
task chromecast:submit DEVICE=chromecast-test-02 APP=bomberman WORKFLOW=install APK=/path/frozen.apk ASYNC=true
task chromecast:watch JOB=J-example
task chromecast:evidence JOB=J-example OUT=docs/diagnostics/example
task chromecast:message JOB=J-example TEXT='Please finish when convenient'
```

DEVICE may select multiple IDs or `all`, or use POOL instead. Multi-device
submissions create batches; watch/status/evidence/cancel accept BATCH. Closing
a watcher does not cancel a job. Cancel only your own submitted jobs.
Use `ASYNC=true` to submit without waiting. Check/profile/record/capture/readd
retain their existing Task names, variables, evidence locations and literal
message handling. Pairing codes belong only in secure interactive prompts.

APK defaults remain here: Aquarium/other game flavor release outputs and verified
Bomberman/Prime Numbers build receipts. Explicit APKs or recipes override them.
The standalone client requires explicit artifacts and does not infer game paths.
App installers check advertised protocol/workflow/validator capabilities before
submitting; they never copy adapters or run sudo to upgrade the shared service.
Legacy profile and Android routing scripts use the installed client API through
`scripts/wf_device`, retaining only World Foundry producer helpers there.

## Aquarium screensaver

The separate `android/screensaver` APK runs a live aquarium level Dream and a
fullscreen launcher activity. It selects one of eight tanks at Dream startup,
using the tank choice exposed by the selected Dream to the coordinator tray.
It has no phone-controller prompt, QR code, or phone server. Build and freeze
its APK locally, then use the
reviewed coordinator workflow to check natural idle activation on each TV:

As of 2026‑10‑18, the live screensaver APK with SHA-256
`99fdfce1cde44b45f6037aa4048dfb348b18929847feb4bf567acf9490317a94`
is installed and its Dream selected on both test Chromecasts. The
[implementation plan](plans/2026-10-18-aquarium-screensaver-player-and-tray-settings.md)
records the tank, tray and motion checks. The
[one-minute video archive](diagnostics/aquarium-screensaver-video-archive-2026-10-18/index.html)
covers all eight tanks, including both Planted Tank water types. The earlier
[investigation](investigations/2026-10-17-chromecast-screensaver-from-a-level.md)
records the video predecessor's deployment.

To test cast1 by eye, press Home on its remote and leave the TV idle. Its
recorded `screen_off_timeout` is 600,000 ms (10 minutes), Dreams are enabled,
and the aquarium Dream is selected. The aquarium should appear during that idle
period. Press a remote key to wake it. Opening **World Foundry Aquarium Screensaver** from
the Apps row tests its fullscreen launcher, not automatic Dream activation.
For a repeatable Dream capture through the coordinator, run:

```sh
task chromecast:queue
task chromecast:submit DEVICE=chromecast-test-01 APP=screensaver WORKFLOW=dream-check APK=/path/frozen-screensaver.apk ASYNC=true
task chromecast:watch JOB=J-example
task chromecast:evidence JOB=J-example OUT=docs/diagnostics/screensaver-cast1-check
```

Replace `J-example` with the submitted job ID. Review `dream.png` and the
receipt in the evidence directory. The workflow uses a temporary six minute
idle timeout and restores the prior settings and foreground when it finishes.
It does not remove cast1's persistent aquarium Dream selection.

```sh
task chromecast:submit DEVICE=chromecast-test-01,chromecast-test-02 APP=screensaver WORKFLOW=dream-check APK=/path/frozen-screensaver.apk ASYNC=true
task chromecast:watch BATCH=B-example
task chromecast:evidence BATCH=B-example OUT=docs/diagnostics/screensaver-dream
```

`dream-check` temporarily selects the Dream and restores each device's original
screensaver settings afterward. After reviewing its screenshot and the device's
original component, persistent selection uses
`task chromecast:configure DEVICE=chromecast-test-01 CHANGE=aquarium-screensaver`.
For a device whose recorded original was Google Backdrop, use
`CHANGE=google-tv-ambient` to undo that selection. Device 01 also required
`CHANGE=allow-standby` because its previous powered setting kept the display
awake; `CHANGE=stay-awake-while-powered` reverses that specific change.
See [the investigation](investigations/2026-10-17-chromecast-screensaver-from-a-level.md)
for build isolation, evidence and distribution limits.

## Planted Tank screensaver

A third `android/screensaver` app (`org.worldfoundry.plantedtank`, flavor
`planted`): the planted tank alone, growing from seedlings to a full canopy,
then replaced by a new tank. See the
[plan](plans/2026-10-21-planted-tank-screensaver.md) and the
[app README](../android/screensaver/README.md#planted-tank).

```sh
task build-planted-level   # level + bundle, linked into the flavor
task build-planted-apk     # build-planted-level, then both ABIs
task test-planted-screensaver
```

The APK lands at
`android/screensaver/build/outputs/apk/planted/debug/screensaver-planted-debug.apk`.
The Chromecasts need its armeabi-v7a library; the build includes it.

Parameters (`water`, `seed`, `speed`, `hold`) take two command shapes. Activity
extras apply to that run only; the settings provider saves values for the Dream. On the dedicated TVs, use the coordinator's owned Settings workflows:

```sh
task chromecast:screensaver-setting DEVICE=chromecast-test-01 SETTING_ID=4.2 VALUE=1
task chromecast:screensaver-show DEVICE=chromecast-test-01 OVERRIDES='{"4.2":"1"}'
```

Here `4.2` identifies owner 4 (Director), field 2 (Water type), and `1` is
Saltwater. The owner/field IDs and labels come from the app's `getCapabilities`
document, generated from the OAD-derived `RP01` catalog by
`scripts/gen-settings-capabilities.py`. The provider authority is declared in
the APK manifest. The coordinator has a separate package allowlist for APK
admission; Settings fields are discovered from the provider rather than copied
into that list. The `screensaver-show` override applies to one launch and does
not change the saved Dream setting.

## Reservations and recovery

Will's terminal owns personal reservations. Use `task cast1:reserve` /
`task cast1:release`, or cast2, with optional REASON. Agents must never create or
release these on his behalf. Interactive workflows wait behind reservations.
`WORKFLOW=install` alone may install in the background: retain the reservation,
reject updates to the foreground app, never launch or send input.

Use `task chromecast:readd DEVICE=id` for recovery. Verified discovery hints may
be supplied with ADDRESS when needed. Device 01 uses native wireless debugging;
device 02 uses USB debugging with verified TCP/IP ADB. Respect ownership and
recovery gates. No raw Chromecast ADB, parallel locks, copied harnesses or direct
phone control outside coordinator ownership; downtime grants no fallback.
Factory reset, account changes, unrelated deletion and security disabling require
separate authorization.

## Service administration

Prepare and review releases in the standalone project. Its deployment runner
saves a transcript and uses the root-owned upgrade helper, draining complete
sessions, taking SQLite/configuration backups, verifying readiness and retaining
safe rollback/maintenance state on failure. See the standalone
[deployment guide](https://github.com/wbniv/chromecast-coordinator/blob/main/docs/deployment.md)
and [operations guide](https://github.com/wbniv/chromecast-coordinator/blob/main/docs/operations.md).

`task chromecast:install` is a compatibility alias for that project's reviewed
upgrade runner; pass `--source RELEASE --review REVIEW` via CLI arguments after
preparing the review. Fresh provisioning is separate and belongs to the new repo.
Historical Bomberman deployment paths/reviews in older plans are archival.

See [migration plan](plans/2026-10-06-standalone-chromecast-coordinator.md) and
[extraction evidence](diagnostics/coordinator-extraction-20261006/receipt.json).
Host bypass verification remains pending; do not claim enforcement until those
checks pass. The GitHub repository stays private through the full acceptance and
publication review.
### Multiple APKs in one command

`submit WORKFLOW=install`, `check`, `profile`, `simpleperf` and non-interactive
`record` accept complete APK paths after `--`. Each distinct app and selected
device gets an ordinary owned job within one durable batch. Package names come
from APK manifests and must match the coordinator's registered applications.
This requires client and service capability `multi_apk_batches: 1`; older
services reject the request before uploading inputs or creating jobs.

```sh
task chromecast:submit WORKFLOW=install DEVICE=chromecast-test-01,chromecast-test-02 -- /build/aquarium.apk '/build/baseline release.apk'
task chromecast:watch BATCH=B-example STAGE=install
task chromecast:watch BATCH=B-example
task chromecast:evidence BATCH=B-example OUT=docs/diagnostics/app-batch

task chromecast:check DEVICE=chromecast-test-01 VALIDATOR=poke-resume -- /build/condo.apk /build/qbert.apk
task chromecast:profile DEVICE=chromecast-test-01 RUNS=3 -- /build/condo.apk /build/qbert.apk
task chromecast:simpleperf DEVICE=chromecast-test-01 DURATION=10 -- /build/condo-profileable.apk /build/qbert-profileable.apk
task chromecast:record DEVICE=chromecast-test-01 DURATION=10 -- /build/condo.apk /build/qbert.apk
```

Use an explicit `DEVICE` or device list. `DEVICE=all` resolves once and prints
the enrolled targets, including phones; `POOL` is unsupported for APK lists.
Do not combine positional paths with scalar `APK`, `RECIPE`, or a global `APP`
for several apps. Existing `APP=... APK=...` commands retain their behavior.
In World Foundry, `chromecast:install` remains the host-coordinator deployment
alias; app installation uses `chromecast:submit WORKFLOW=install`.

For different per-app options, save a recipe and use
`task chromecast:check DEVICE=chromecast-test-01 RECIPE=/path/checks.json`:

```json
{
  "workflow": "check",
  "items": [
    {"app": "aquarium", "apk": "/build/aquarium.apk", "validator": "menu-back"},
    {"app": "baseline", "apk": "/build/baseline.apk", "validator": "baseline-settings"}
  ]
}
```

Items inherit the workflow and common options. Allowed item fields are `app`,
`apk`, `validator`, `scene`, `duration`, `warmup`, `runs`, `trace`, `frequency`,
`callgraph`, `record`, `reinstall`, `require_abi` and `input_script`; each workflow
still enforces its schema. Item targets/workflows and unknown fields are rejected.
`menu-back` requires Aquarium; Baseline diagnostic checks require a diagnostic
APK, and simpleperf requires a profileable or debuggable APK.

The bounds are 32 items, 128 app/device jobs, 32 MiB per APK and 256 MiB of unique
APK bytes. All files are frozen and validated before admission; no child is
accepted if any item fails. Split APKs and duplicate packages are rejected.
Use `variant-benchmark` for labelled builds of one app plus its restoration APK.
Interactive recording/input, capture, reconnect and configuration do not accept
APK lists.

Installation and launcher verification have separate results. A reservation can
hold launcher verification while later background installs continue.
`STAGE=install` returns when all installations succeed or fail and prints the
installed and launcher-verified totals; default watching waits for complete
workflows. A failed child does not cancel unrelated children. Recovery and
cleanup gates still apply, and there is no cross-app rollback.

Use `BATCH` with status/watch/evidence/cancel. Evidence is stored under
`item-NN/device/job`, with a batch manifest. Cancellation affects only your
unfinished jobs and preserves completed installs. Closing a watcher never
cancels work; messages still require an explicit `JOB`.

See the [implementation plan](plans/2026-10-19-chromecast-multiple-apk-commands.md) for rollout status.

