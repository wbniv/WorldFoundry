# Multi-APK install re-run on cast1 — 2026-10-24

Batch `B-8b28ca1044b8`: Aquarium and Baseline (version code 4) on chromecast-test-01 only. Cast2 was
`needs-local-setup` (Wireless debugging not advertising), so it was left out.

```sh
task chromecast:submit WORKFLOW=install DEVICE=chromecast-test-01 -- build/apk-font-refresh-2026-10-19/aquarium-b88535fe5fc780f5.apk wflevels/baseline/build/baseline-86e195b804408271.apk
task chromecast:watch BATCH=B-8b28ca1044b8 STAGE=install
task chromecast:evidence BATCH=B-8b28ca1044b8 OUT=docs/diagnostics/multi-apk-2026-10-24-cast1/batch
```

| Item | App | Job | Install | Launcher verification |
|---|---|---|---|---|
| 1 | aquarium | `batch/item-01/chromecast-test-01/J-c5f65cd6c59e` | installed, hash `b88535fe5fc7` | `verified`, adaptive icon, MAE 8.4 |
| 2 | baseline | `batch/item-02/chromecast-test-01/J-2cfcdd43c04c` | installed, hash `86e195b80440` | `verified`, icon, MAE 0.32 |

- `STAGE=install` now follows the batch to "Installed 2/2; launcher verified 1/2" without raising (fix `e37dd6f`).
- Both children ended `completed`; Baseline was not refused (version code 4 matches the installed build).
- The launcher was already on top before each job (`item-*/…/background-install.json`), so this run does **not**
  exercise the screensaver wake (`4b23847`). That still needs a cast that is dreaming.
