# Planted Tank soak with continuous sampling, 13 November 2026

Repeat of plan step 9 (50 tanks at 8× with hold 5; same PID, no crash, PSS spread
under 4 MiB after warm-up) on **chromecast-test-02**, as Will asked after
[J‑c21e98845289](../runtime-editing-followups-2026-11-13/README.md): repeat with
continuous sampling and keep the 4 MiB limit. **Result: FAIL on genuine memory
spread.** The sampling was continuous this time, and the PSS spread in the final ten
minutes was 11,848 KiB, against a limit below 4,096 KiB.

## Why the last run had a 914.8-second gap

The gap was on the host side; the coordinator and the device were not the cause. This
laptop suspended from 09:30:24 to 09:45:17 +0700 (`systemd-logind: The system will
suspend now!`, kernel `PM: suspend entry (s2idle)`). The soak kept running on the
Chromecast, but the host-side sampler loop was frozen. Samples 71 and 72 carry
coordinator timestamps of 09:30:06 and 09:45:21. The old loop timed itself with
`time.monotonic()`, which does not advance during suspend. Its `elapsed` column
therefore shows a 26-second step where 914.8 seconds really passed, and its
`duration + 600` guard never fired.

The fix changes only how samples are taken ([`run-soak.py`](run-soak.py)):

- the whole run holds a `systemd-inhibit --what=sleep:idle --mode=block` lock;
- elapsed time and gaps use the wall clock;
- a gap over 60 seconds between sample attempts aborts the run as invalid instead of being absorbed.

Everything goes through coordinator `task chromecast:*` commands. The Planted values
and the original selection are read before the run, then restored and read back
afterwards.

## Run

| | |
|---|---|
| Job | J‑bf9150654784 (`record`, no video, `PANEL=require-hidden`), 14:57–15:22 +0700 |
| APK | Release `planted-release-followups.apk`, SHA‑256 `2d8f70c1…fdfd90`: the same build as the last run, with no Planted source change since. Frozen at `~/tmp/planted-soak-2026-11-13/` |
| Settings during the run | Growth speed 6 (8×), Hold seconds 5 |
| Process | PID 30527 in all 81 samples, every one `stable` |
| Tank starts | 51 `PLANTS settings-source=OAD` markers, so 50 reloads (a lower bound) |
| Sampling | 81 samples over 1,467.3 s; median interval 17.9 s, largest gap 24.1 s |
| Crash markers | none (`FATAL EXCEPTION`, `Fatal signal`, `ASSERTION FAILED`, `ANR in`, tombstone) |

## Memory gate (strict)

| Final ten minutes | Value |
|---|---|
| Samples | 34 over 587.5 s, largest gap 20.6 s |
| PSS min / median / max | 73,859 / 83,417.5 / 85,707 KiB |
| **Spread** | **11,848 KiB** (limit below 4,096): **FAIL** |
| Spread with the lowest sample dropped | 10,388 KiB |
| Every 10-minute rolling window in the run | spread 11,848 to 29,991 KiB |

Across the whole run, PSS ranged from 73,859 to 110,623 KiB, falling from about
100–110 MiB early on to 80–85 MiB, so it does not grow. Comparing the highest and lowest
final-window samples (`input-sample-048` against `-056` meminfo), the difference is
almost all **GL mtrack**: 44,900 against 34,900 KiB, −10,000. Native Heap differs by
−893 and Dalvik by nothing. Over the whole final window, GL mtrack spans 10,288 KiB,
Native Heap 5,907 KiB, Dalvik Heap 15 KiB, and PSS without GL mtrack 5,915 KiB. Each of
the first two is over the limit on its own.

The samples land at arbitrary points in each tank's grow-and-hold cycle, so part of the
spread may follow plant growth inside a cycle, not reload to reload. Nobody has
established that yet, and as before, no engine investigation was authorized.

## Restoration

Readback after the run: Growth speed 3 and Hold seconds 120. The selection is Seahorse
Grid again. `enabled`, `activate_on_sleep`, idle 600,000 ms, sleep 3,600,000 ms and
stay-on 3 match the values read before the run; the screensaver is not running.
`readback_verified: true`, and the job completed with health `ready`. cast1 was not
touched.

Files: [verdict](soak/verdict.json), [samples](soak/sample-values.json),
[markers](soak/markers.json), [restoration](soak/restoration.json),
[analysis](analyse.py), meminfo [max](soak/input-sample-048-meminfo.txt) /
[min](soak/input-sample-056-meminfo.txt).
