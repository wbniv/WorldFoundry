# Two-APK install on a dreaming cast: attempt (2026‑11‑13)

Goal: install Aquarium and Baseline in one command on a cast that is dreaming a
different app (the selected Dream is Seahorse Grid on both casts).

## Starting state (`pre-state/`)

At 00:30 local (17:30 UTC on 2026‑11‑12) both casts were `ready`, unreserved and the queue was empty.

| Cast | `screensaver-list` | `capture` | Readings |
|---|---|---|---|
| cast1 | J‑5cf6202a65a8: `running_state: not-running` | J‑8cfffaf97a21: launcher, Netflix details page | Dream Seahorse Grid, enabled, `idle_timeout_ms` 600000, `sleep_timeout_ms` 7200000, `stay_on_while_plugged_in` 3 |
| cast2 | J‑eaeffa1abfc9: `running_state: not-running` | J‑fe82b2ea65e1: black frame | same, `sleep_timeout_ms` 3600000, `stay_on_while_plugged_in` 3 |

Neither cast was dreaming.

## Attempt 1 (cast1)

- `task chromecast:screensaver-trigger DEVICE=chromecast-test-01` (J‑1e405fd3d122) presses
  HOME and waits up to 12 minutes for the Dream to start by itself. It does not force a
  Dream. It ended `failed: dream-not-observed`: `last_running_state: not-running` for the
  whole wait (`attempt1-trigger-J-1e405fd3d122/`).
- The two-APK install queued behind it, batch `B-d367ee9b4620`, therefore ran on an
  **awake** launcher: Aquarium J‑a183b50a2c80 (`e2ac53f5…` reinstalled, already
  current) and Baseline J‑0b72c84873a0 (`eebab09d…` → `5b47e27b…`). Both ended `completed`,
  with `foreground_unchanged: true` and the launcher `verified` (`gain` normalisation).

## Cause of `dream-not-observed`

Both casts have `stay_on_while_plugged_in` = 3 (screen stays on while powered,
the coordinator's `stay-awake-while-powered` configuration). Android's
PowerManagerService treats a stay-on device as being kept awake
(`isBeingKeptAwakeLocked()` includes `mStayOn`). `isItBedTimeYetLocked()` is then
false, so the idle timeout never starts a Dream
([AOSP PowerManagerService](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android14-release/services/core/java/com/android/server/power/PowerManagerService.java)).
This comes from the source and fits the readings. It was **not** proved on the
device, because that would mean changing Will's persistent TV setting
(`CHANGE=allow-standby`), which this task does not own. On 2026‑10‑23 the casts
were dreaming; on 2026‑10‑11, `stay_on_while_plugged_in` on cast2 was 0.

No second attempt: with the setting unchanged, it would fail for the same cause.
The same-app case (fix `0c706d6`) was not rerun, for the same reason.

The `adb-failure-1.json` in the trigger job is the known cleanup step that cannot start the
launcher's `DispatchActivity` (`SecurityException … not exported`). The job was not
affected.

## Attempt 2 (cast1, `attempt2/`): preparation

- **Before state** (`screensaver-list` J‑aab3112143a1): Seahorse Grid Dream selected,
  `enabled` 1, `activate_on_sleep` 1, `idle_timeout_ms` 600000, `sleep_timeout_ms`
  7200000, `stay_on_while_plugged_in` 3, `running_state: not-running`.
- **`CHANGE=allow-standby` was not applied.** This session's permission classifier
  denied the configure call. Will is being asked directly.
- **What it changes** (coordinator `conditions.py`, `CONFIGURATIONS`): only global
  `stay_on_while_plugged_in`, 3 → 0. The inverse is `CHANGE=stay-awake-while-powered`.
  It does not touch `sleep_timeout`, and no reviewed coordinator configuration writes that
  setting. Cast1's existing `sleep_timeout` of 7200000 (2 h) will probably put the cast into
  standby after 2 h idle once stay-on is 0, where it may be unreachable for coordinator
  jobs. That is not proved on the device.
- **Seahorse Release built at HEAD `8f3ed151`** (`task build-seahorse-screensaver-apk`, level build in the
  Linux container, then Gradle): `bd599a28…`, frozen as
  `build-docker/seahorse-head/screensaver-seahorse-release-bd599a28.apk`. There were no
  uncommitted source changes under `android/screensaver`, `engine`, `wfsource` or the level
  script. The build regenerates the Seahorse level files, which already differed from the
  committed copies in the working tree.
- **Installed on cast1:** batch `B‑fc80f79c72a5`, J‑abc4badbe506, `25dfeda6…` (the
  2026‑11‑10 Release) → `bd599a28…`, hash verified, launcher `verified`, cleanup
  `restored`, health `ready`.
- **After** (`screensaver-list` J‑c008d1e5d421): the Seahorse Grid Dream is still
  selected; every other value is unchanged, including `stay_on_while_plugged_in` 3.

## allow-standby applied (`attempt2/configure-allow-standby-J-8a911f1f5d03/`)

The coordinator session ran `CHANGE=allow-standby` on cast1 on Will's direct instruction (J‑8a911f1f5d03):
`stay_on_while_plugged_in` original 3, read-back 0, health `ready`. Will's permanent setup for cast1
is now stay-on 0 with the Seahorse Grid Dream selected.

## Attempt 2, trigger (`attempt2/trigger-J-dcc185494948/`, `attempt2/install-B-4fc04e221c31/`)

- `screensaver-trigger` J‑dcc185494948 **observed the Dream**: `running_state: running`, active component
  Seahorse Grid, `stay_on_while_plugged_in` 0, at 01:23:35 UTC (`screensaver.png` shows the seahorse grid).
- The trigger job's own cleanup then restored the earlier foreground (the launcher). It woke the cast
  (`woke_before_retry: true`) after an `am start -W` HOME timed out (`foreground-restore-failure.json`).
- The two-APK install queued behind it (B‑4fc04e221c31: J‑e69e1279c050, J‑b16927dbfc85) therefore found
  the launcher in front, not the Dream. Both installed and verified, but this run is **not** the
  dreaming case. A queued job behind `screensaver-trigger` can never meet the Dream for this reason.

## Attempt 3: two-APK install against the idle Dream — PASS (`attempt3/`)

1. With no job after 08:26:55 local, cast1 went into the Seahorse Dream on its own 10-minute idle timer.
   `capture` J‑6a7e59b90a7a (08:40) shows the seahorse grid.
2. Batch `B‑846ea8805011` (Aquarium show `e2ac53f5…`, Baseline `5b47e27b…`):
   - **J‑eaa0ce92d5de (Aquarium):** `background-install.json` records `before` = the Seahorse
     `DreamActivity`, `foreground_unchanged: true`. The install ran under the Dream without
     disturbing it. Launcher verification then woke the cast (`input keyevent KEYCODE_WAKEUP`
     08:41:17, then `am start -n …HomeActivity` without `-W`, 08:41:18: fix `4b23847` on hardware)
     and verified the tile (`gain`). Cleanup recorded the Dream as `transient_dream` and left the
     launcher in front; `restored`, health `ready`.
   - **J‑20f3828bfd8b (Baseline):** ran next on the awake launcher; installed (`6c245338…` →
     `5b47e27b…`), launcher `verified`, foreground unchanged, `restored`.
   - Afterwards: the Dream is not running and the launcher is in front. The Dream starts again on
     the next idle timeout (see attempt 4).
3. **Baseline displacement and repair.** Between attempt 2 and attempt 3, another session installed its
   Baseline diagnostic build `6c245338…` on cast1 (`runtime-editing-followups-2026-11-13`, J‑8c0da2aee2ea,
   built 2026‑11‑13 08:17). It is newer than `5b47e27b…`. Attempt 3 overwrote it, so batch
   `B‑0b2d8212f2b6` (J‑3f3b009644bc) reinstalled `6c245338…` (`5b47e27b…` → `6c245338…`, verified,
   launcher verified).
4. Another owner's `preview-video` (J‑fbc417b66adc) ran on cast1 just before the capture. Its evidence
   was not kept here.

## Attempt 4: same-app Dream (fix `0c706d6`) — PASS (`attempt4-same-app/`)

- After another idle period, `capture` J‑eaae62db8517 (08:58) shows the Seahorse Dream.
- Batch `B‑e3727f47ffe9`, J‑1b9482638d60: install the Seahorse screensaver `bd599a28…` (the package
  whose Dream was running).
  - `foreground-before-install.txt`: Seahorse `DreamActivity` on top.
  - The job **woke first** (08:59:11 `KEYCODE_WAKEUP`, `am start` HOME): `foreground-after-wake.txt` shows
    the launcher.
  - It then installed in the background (`foreground_unchanged: true`), `bd599a28…` → `bd599a28…`
    verified, launcher `verified`, `succeeded`/`completed`, `restored`, health `ready`.
  - The 2026‑10‑25 `plugin-error` (J‑d2b5478d6fa1, J‑4ed799902b09) did not recur. With the Dream
    woken there is no foreground conflict, so the job installs rather than failing.

## Final state of cast1 (`final-state/`, `screensaver-list` J‑0ec0aae5157b)

| Setting / package | Value |
|---|---|
| Selected Dream | `org.worldfoundry.seahorsegrid/org.worldfoundry.screensaver.SeahorseGridDreamService` (`bd599a28…`, Release built at HEAD `8f3ed151`) |
| `stay_on_while_plugged_in` | 0 (standby allowed, Will's setup) |
| `enabled` / `activate_on_sleep` | 1 / 1 |
| `idle_timeout_ms` / `sleep_timeout_ms` | 600000 / 7200000 (the 2 h sleep timer is unchanged) |
| Aquarium | `e2ac53f5…` (show build) |
| Baseline | `6c245338…` (the other session's newest diagnostic build, restored) |
| Queue | idle, nothing queued, health `ready` |

## Follow-up: Dream when idle, never full sleep (`followup-dream-without-sleep/`)

The coordinator's new reviewed `CHANGE=dream-without-sleep` (`a80d9a5`, release 0.1.141; [plan](https://github.com/wbniv/chromecast-coordinator/blob/main/docs/plans/2026-11-13-dream-without-sleep.md)) was applied on cast1 by the coordinator session (J‑27f60408d469): `sleep_timeout` 7200000 → -1, stay-on already 0. An earlier attempt, J‑73786707fc33, had found cast1 in full standby under the old 2 h timer (`device-not-found-on-network`). The read-back is J‑bc627eb4dee5: stay-on 0, `sleep_timeout_ms` -1, Seahorse Dream selected and running. Capture J‑a116601ea2c5 at 13:25 shows the Dream. A read-only probe at 15:25 +0700 (J‑2bda356261bd), 2 h 20 min after Will's remote wake, found cast1 `ready` and still dreaming. `attentive_timeout` is not read by the coordinator.
