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
