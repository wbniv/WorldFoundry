# Plan: WF streams → platform filesystem sinks (iOS/Android)

**Date:** 2026-04-22
**Status:** Deferred

## Context

WF has a small but real streams subsystem in `wfsource/source/streams/`:
`binstrm.cc` creates `ostream_withassign` instances (`cbinstrm`, `cstreaming`,
`ctest`) and assigns them either to `NULL_STREAM` (a no-op sink, when
`SW_DBSTREAM` gates them off) or to a real `std::ostream` — typically
`std::cerr` / `std::cout` / a file stream — at startup. Modules throughout the
engine emit diagnostic traffic via `DBSTREAM1(cbinstrm << ...)` etc. The
`SW_DBSTREAM` level knob (0–5, see [dbstrm.hp](../../wfsource/source/streams/dbstrm.hp))
controls how much of it is live.

On Linux this works out of the box because `std::cout` / `std::cerr` land on
the terminal the user launched `wf_game` from. On mobile there's no terminal
and stdio goes to `/dev/null` by default, so every DBSTREAM line disappears.

**Today's iOS shim** (2026-04-22, shipped in Phase 2C-A): `WFOpenDiagnosticLog`
in [hal/ios/native_app_entry.mm](../../wfsource/source/hal/ios/native_app_entry.mm)
dups the two stdio fds to `NSTemporaryDirectory()/wf.log` before HALStart
runs. Codemagic pulls that file out of the simulator container. Android does
the equivalent dance in
[hal/android/native_app_entry.cc](../../wfsource/source/hal/android/native_app_entry.cc)
(`OpenDiagnosticLog` around line 100). Both work, but both are raw-fd hacks
that route around WF's own streams layer rather than through it.

## The deferred work

Teach WF's streams subsystem about platform-filesystem sinks so iOS/Android
treat `cbinstrm` / `cstreaming` / `ctest` the same way Linux currently does —
real `std::ostream`s backed by a real file, with the file path resolved by
the HAL.

Rough shape:

1. **HAL function `HALOpenDiagnosticStream()`** returning a
   `std::unique_ptr<std::ostream>` (or similar) to whatever sink the platform
   prefers. Linux returns a ref to `std::cerr`; iOS returns an `std::ofstream`
   opened at `NSTemporaryDirectory()/wf.log`; Android returns an `std::ofstream`
   at `externalDataPath/wf.log`.
2. **`streams/binstrm.cc`** swaps its startup `CREATEANDASSIGNOSTREAM(..., NULL_STREAM)`
   assignments for assignments to the HAL-provided stream when `SW_DBSTREAM > 0`.
   No changes to callers.
3. **Retire the raw-fd dup2** from `native_app_entry.mm` and `native_app_entry.cc`.
   Crash signal handlers stay (they need raw-fd writes because stdio may be
   corrupt by then).
4. **Log rotation** — optional later refinement. Android's `O_APPEND` grows
   forever; a `wf.log.prev` cutover on launch would bound disk use.

## Why deferred, not now

Phase 2C of the iOS port is "boot the engine and watch where it crashes" —
unblock first, design later. The dup2 shim gets us log visibility for the
Codemagic run loop today; the clean redesign isn't load-bearing for getting
snowgoons on-screen. Revisit once:

- Android and iOS are both rendering real frames, so the streams redesign
  isn't racing bigger fires.
- The engine-thread vs. main-thread split on iOS (Phase 2C-B) is settled,
  which affects who opens the stream and when.

## Critical files (when this lands)

| File | Change |
|------|--------|
| `wfsource/source/hal/hal.h` | Add `HALOpenDiagnosticStream` declaration. |
| `wfsource/source/hal/linux/platform.cc` | Implement returning `std::cerr`. |
| `wfsource/source/hal/android/platform.cc` | Implement returning `std::ofstream` at `externalDataPath/wf.log`. |
| `wfsource/source/hal/ios/platform.mm` | Implement returning `std::ofstream` at `NSTemporaryDirectory()/wf.log`. |
| `wfsource/source/streams/binstrm.cc` | Wire `cbinstrm`/`cstreaming`/`ctest` to the HAL-provided stream. |
| `wfsource/source/hal/ios/native_app_entry.mm` | Delete `WFOpenDiagnosticLog` dup2 path; keep `WFInstallCrashHandlers`. |
| `wfsource/source/hal/android/native_app_entry.cc` | Same — delete `OpenDiagnosticLog`; keep signal handlers. |

## Out of scope

- Redirecting `printf` / `std::cout` / `std::cerr` *outside* the WF streams —
  third-party libraries (miniaudio, zForth) still use raw stdio. They stay
  on the dup2 shim or get their own routing.
- Structured logging (levels, tags, async flush). `SW_DBSTREAM` is fine as-is.
- A log viewer UI on-device — Codemagic artifact inspection is enough for v1;
  a read-only `UITextView` viewer is mentioned in the parent iOS port plan
  ([2026-04-21-ios-port-codemagic.md](../2026-04-21-ios-port-codemagic.md))
  under Phase 5, not here.
