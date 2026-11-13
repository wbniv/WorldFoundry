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

## Attempt 2 (cast1, `attempt2/`): prepared, waiting on Will

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
