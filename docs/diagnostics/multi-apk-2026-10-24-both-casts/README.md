# Multi-APK install on both casts — 2026‑10‑24

Batch `B-a29c022860da`: Aquarium and Baseline (version code 4) on `chromecast-test-01` and `chromecast-test-02`, one command.
Queue state at submit: cast1 busy with another session's recording (children waited, nothing cancelled); cast2 under Will's
personal-use reservation (`kde-tray`, YouTube in the foreground).

```sh
task chromecast:submit WORKFLOW=install DEVICE=chromecast-test-01,chromecast-test-02 ASYNC=1 -- build/apk-font-refresh-2026-10-19/aquarium-b88535fe5fc780f5.apk wflevels/baseline/build/baseline-86e195b804408271.apk
task chromecast:watch BATCH=B-a29c022860da STAGE=install
task chromecast:evidence BATCH=B-a29c022860da OUT=docs/diagnostics/multi-apk-2026-10-24-both-casts/batch
```

| Item | App | Device | Job | Install | Foreground | Launcher verification |
|---|---|---|---|---|---|---|
| 1 | aquarium | cast1 | J‑6cdd3d5c1b8d | hash `b88535fe5fc7` | unchanged (launcher) | `verified`, completed |
| 1 | aquarium | cast2 | J‑a8b194e44173 | hash `b88535fe5fc7` | unchanged (YouTube) | `verified`, completed |
| 2 | baseline | cast1 | J‑74bb8a611fe6 | hash `86e195b80440` | unchanged (launcher) | `verified`, completed |
| 2 | baseline | cast2 | J‑575e673b1e22 | hash `86e195b80440` | unchanged (YouTube) | `verified`, completed |

- `STAGE=install` followed the batch to "Installed 4/4; launcher verified 3/4" and exited cleanly; the fourth child verified
  seconds later. Evidence downloaded as `item-NN/device/job` with 15–24 verified artifacts per job.
- Cast2's installs ran in the background while the personal-use reservation held YouTube in the foreground
  (`background-install.json`: `foreground_unchanged: true` for all four). Launcher verification on cast2 ran after the
  reservation ended; no agent created or released it.
- **Finding:** on cast2 both jobs recorded `adb-failure-4.json`: the post-verification attempt to return YouTube to the
  foreground (`am start -W -n com.google.android.youtube.tv/...MainActivity`) failed with `SecurityException … not exported`.
  The jobs still succeeded. Not investigated further.
- **Not exercised:** the screensaver wake (`4b23847`) and the `device-command-timeout` probe (`8bc97ab`) — both casts had the
  launcher or YouTube on top and neither was dreaming.
