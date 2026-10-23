# Multi-APK install acceptance attempt — 2026-10-23

Batch `B-94c7f0f5366e`: Aquarium and Baseline on chromecast-test-01 and chromecast-test-02.

```sh
task chromecast:submit WORKFLOW=install DEVICE=chromecast-test-01,chromecast-test-02 -- build/apk-font-refresh-2026-10-19/aquarium-b88535fe5fc780f5.apk build/apk-font-refresh-2026-10-19/baseline-aee5cd2f6f4e082b.apk
task chromecast:evidence BATCH=B-94c7f0f5366e OUT=docs/diagnostics/multi-apk-2026-10-23/batch
```

Results and analysis are in the plan's
[Acceptance attempt 2026-10-23](../../plans/2026-10-19-chromecast-multiple-apk-commands.md#acceptance-attempt-2026-10-23).
Aquarium installed and hash-verified on both casts, then both jobs ended `recovery-required`
(`transport-unavailable` on cast1, `plugin-error` on cast2). Baseline was refused on both with
`INSTALL_FAILED_VERSION_DOWNGRADE` (cast1 receipt: `batch/item-02/chromecast-test-01/J-6cd31246d60b/adb-failure-5.json`).
