# Planted Tank soak with continuous sampling, 13 November 2026

Repeat of plan step 9 (50 tanks at 8× with hold 5; same PID, no crash, PSS spread
under 4 MiB after warm-up) on **chromecast-test-02**, as Will asked after
[J‑c21e98845289](../runtime-editing-followups-2026-11-13/README.md): repeat with
continuous sampling and keep the 4 MiB limit. **Result: FAIL on genuine memory
spread.** The sampling was continuous this time, and the PSS spread in the final ten
minutes was 11,848 KiB, against a limit below 4,096 KiB.

A phase-locked repeat (J‑dadba4fb4900, one sample per tank at 20 s) also **fails**, with
a spread of 6,784 KiB. At a fixed phase, GL mtrack is flat; most of the spread is one
−4,552 KiB step in Code PSS. See the last two sections.

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

## Phase-binned re-analysis of J‑bf9150654784 (no device time)

Will's follow-up question: does the spread come from within each grow-and-hold cycle?
[`phase.py`](phase.py) bins every sample by seconds since the latest tank start.
Everything is timed on the device clock: the tank-start markers, and, for each sample,
the one `Explicit … GC` line that `dumpsys meminfo` forces in the app. Every sample has
exactly one such new line. The 51 starts are 29.32–29.40 s apart, and the grow phase
lasts 24.4 s ([output](soak/phase-analysis.txt)).

| Phase bin (final 10 min) | n | PSS spread | GL mtrack spread | Native Heap spread |
|---|---|---|---|---|
| 0–6 s (just after load) | 5 | 6,133 | 2,364 | 5,536 |
| 6–12 s | 8 | 3,520 | 2,384 | 1,568 |
| 12–18 s | 7 | 4,040 | 2,336 | 960 |
| 18–24.4 s (late grow) | 7 | 2,529 | 1,540 | 1,600 |
| hold, 24.4 s and later | 7 | **11,848** | **10,236** | 3,219 |

- **The two −10 MiB GL mtrack dips are both in the hold** (phase 25.2 and 27.4 s, GL mtrack about 34.8 MiB against about 44.9 MiB). They do not happen in every hold.
- Outside the hold, GL mtrack takes one of two values, about 44.9 or about 42.6 MiB, in every bin. Neither value lines up with water type or plant geometry.
- Native Heap rises within a cycle (correlation with phase +0.41) and is lowest just after a load.
- Within-cycle phase explains the large excursions, so I sampled at one fixed phase in late grow.

## Phase-locked soak (J‑dadba4fb4900): FAIL, 6,784 KiB

[`run-phase-soak.py`](run-phase-soak.py) takes one sample per tank, 20 s after its
start. The host fires each sample at the predicted start plus 20 s minus the measured
delay from request to GC, and re-anchors on the latest marker after every sample.
Everything else is the same as the continuous run: Release 2d8f70c1, cast2, speed 6
(8×), hold 5, sleep inhibitor, abort on any gap over 60 s, restore and read back.
Judged by [`analyse-phase.py`](analyse-phase.py): one sample per tank within 3 s of the
target, final ten minutes ([verdict](soak-phase/verdict.json)).

| | |
|---|---|
| Process | PID 1221, all 47 samples stable; 51 starts (50 reloads); no crash marker |
| Phase lock | 32 of 47 samples within ±3 s. In the final ten minutes: 21 samples, tanks 31–51, over 587 s; phase 18.81–22.28 s, median 20.21, sd 0.84 |
| Jitter cause | `task chromecast:input:sample` took 0.2–23 s before the coordinator created the request. The host load average was 29–42 from other sessions. The coordinator's own pickup plus run was about 1.3 s |
| PSS, final 10 min | 112,896 / 113,804 / 119,680 KiB (min/median/max): **spread 6,784 KiB, FAIL** |
| GL mtrack spread | 180 KiB (phase-locking removes it) |
| Native Heap spread | 2,611 KiB |
| **Code** (mapped .so/.dex) | **one step of −4,552 KiB** between samples 33 and 34 (tank 38): 26,208 → 21,676, flat on both sides |
| PSS minus Code spread | 2,630 KiB |
| Last 14 locked samples (tanks 38–51, about 6.9 min, after the step) | spread 2,172 KiB (does not cover the 10 minutes the gate needs) |

At a fixed phase, GL mtrack is flat and Native Heap moves by 2.6 MiB. Most of the
remaining spread is a single drop in file-backed Code PSS, which is page-cache or
shared-mapping accounting, not an allocation by the app. Nobody has established why
it happened. The gate stays strict and fails. Restore: speed 3, hold 120, Seahorse
Grid, `enabled`/`activate_on_sleep` 1, idle 600,000 ms, sleep 3,600,000 ms,
stay-on 3, not running, `readback_verified: true` ([restoration](soak-phase/restoration.json)).
Meminfo either side of the step: [033](soak-phase/input-sample-033-meminfo.txt),
[034](soak-phase/input-sample-034-meminfo.txt).
