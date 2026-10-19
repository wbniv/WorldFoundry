# Multi-APK implementation validation — 2026-10-19

Implemented for install, check, profile, simpleperf and non-interactive record.
The installed service advertises `multi_apk_batches: 1`; the live feature arrived
in a concurrent reviewed coordinator deployment after the source patch was
applied. No additional deployment was performed by this session. Its earlier
`/tmp/coordinator-multi-apk-release` bundle/review is stale and must not be used.
The installed batching, client, manifest parser, app registration and tray
changes match the tested snapshot. Installed service/store also contain separate
remote-control and screensaver updates; their multi-APK code is retained.

## Automated checks

- 104 focused coordinator tests passed against frozen source. Coverage includes
  APK package resolution, preflight rejection before upload/admission, bounded
  requests, profileable requirements, recipes, migration, exact retry tokens,
  restart, ordering, child failure isolation, evidence, cancellation, personal
  reservations, install/launcher continuation, and existing scalar commands.
- Eight World Foundry consumer tests passed, including loading the installed
  coordinator dependency bundle through the producer namespace shim.
- Broad coordinator run: 1,401 passed, 22 skipped, six failures. Two packaging
  failures disappeared in the actual repository. Four existing failures remain:
  two drilldown fixtures lack `close_video_observer`; two release fixtures consult
  the host's protected plugin index instead of an isolated config directory.
  Representative failures reproduce in the untouched pre-change snapshot.
- An additional run against the shared repository encountered hash drift while
  another session edited `interactive_input.py`. The final focused run used
  frozen source and passed.
- Task forwarding preserved spaces, commas and literal `$(...)` text in APK paths.
- All six previously frozen production APKs parsed with the expected package and
  both Android ABIs. None advertises simpleperf profiling; profiling acceptance
  must use actual profileable builds.
- `INTERACTIVE=true` with an APK list was rejected before upload/admission.

## Live admission and recovery

```sh
task chromecast:submit WORKFLOW=install DEVICE=chromecast-test-01,chromecast-test-02 -- build/apk-font-refresh-2026-10-19/aquarium-b88535fe5fc780f5.apk build/apk-font-refresh-2026-10-19/baseline-aee5cd2f6f4e082b.apk
task chromecast:watch BATCH=B-d4837bbd7336 STAGE=install
task chromecast:evidence BATCH=B-d4837bbd7336 OUT=docs/diagnostics/multi-apk-2026-10-19/batch
```

Batch `B-d4837bbd7336` atomically created four app/device children. Both TVs were
already unavailable under coordinator recovery policy, so every child ended
`needs-local-setup` before a grant. Stage watching returned failure with
`Installed 0/4; launcher verified 0/4`. These counts describe this acceptance
attempt, not the successful APK refresh performed earlier.

[Batch manifest](batch/batch.json) records app, item, target, immutable APK hash,
child status and separate installation totals. Evidence download created distinct
item/device/job directories, with zero device artifacts as expected for jobs that
never ran. No acceptance jobs remain queued.

Before submitting the batch, the owned cast1 readd J‑904183154623 failed
`recovery-preparation-failed`: shared transport readiness was false. Its
[receipt](readd-cast1/receipt.json) shows `connected: false`, `work_started: false`
and no device journal effects. No direct ADB or reservation changes were used.

Successful physical installation, artwork/font/gameplay checks, heterogeneous
validators and profiling/recording batches remain pending until recovery succeeds.
