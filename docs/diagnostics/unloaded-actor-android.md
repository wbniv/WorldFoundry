# Chromecast unloaded-source actor verification — 2026-10-09

**Passed on both dedicated Chromecasts.** This run verifies the previously
pending inactive-source actor path, including permanent asset binding for an
actor whose source room has never loaded.

| Device | Job | Verified intervals | Complete 12-phase cycles | Active / inactive target intervals |
|---|---|---:|---:|---:|
| Chromecast HD / Android 14 | `J-dc0208160ed7` | 117 | 9 | 59 / 58 |
| Project Room / Android 12 | `J-459777d97f8a` | 114 | 9 | 57 / 57 |

Batch: `B-da4fa007e9ab`. Both jobs completed, both receipts have
`cleanup_verified: true`, and the final queue shows ready, unowned devices and
no waiting jobs. All installation, launch, recording and restoration ran through
the coordinator. No direct device access was used.

## What was checked

The anchored Player runs a Forth test every 0.6 game seconds. It starts in A
while the target MBR actor is in disconnected, unloaded D. The first command
moves the target to A. Later phases move it back into inactive D, return it to
A, write D then A positions in one script, visit D to warm/bind the target,
leave D, and repeat the inactive-source moves.

At each interval the script prints actual Player, camera and target X positions,
the target heartbeat delta and Player update count. The offline validator checks
the complete command sequence, contiguous observations, destination poses,
camera arrival, target updates at the normal frame rate when active, and at most
one final update when the command leaves the target in an inactive room.
It requires the first never-loaded observation; that observation was retained
and passed on both devices.

- [x] Never-loaded target enters A and starts updating without visiting D.
- [x] Previously bound target moves from inactive D into A and resumes updates.
- [x] Target stops updating after entry into inactive D.
- [x] Repeated returns and multiple writes in one script pass.
- [x] Camera continues to follow cross-room Player changes.
- [x] No assertion, script, nil-pointer, sanitizer or fatal crash diagnostics.
- [x] Both recordings decoded and sampled frames visually inspected: the target
  appears in A during active phases and disappears during inactive phases.
- [x] Coordinator cleanup verified for both sessions.

The counts cover the full retained engine logs, including the launch period
before recording. Requested recording duration was 45 seconds; videos are
42.560 and 44.720 seconds. Sampled contact sheets are evidence of rendering,
not a frame-by-frame review or a performance guarantee.

## Build and portability correction

The Android compiler initially rejected the membership pass because
`LevelRooms::GetRoom` returns a const reference. Desktop GCC's `-fpermissive`
accepted that mistake. The corrected implementation puts the mutable pass
inside `LevelRooms::UpdateMovingObjects`, using its owned `_rooms` array.
The loop's scheduling and MBR filter are unchanged.

After this correction, the native assertions build passed all three teleport
regressions (watched script, transform API and unloaded actor), and the new
autonomous fixture passed 18 intervals on desktop before upload. The earlier
24/24 full-suite result remains recorded for the pre-portability implementation.

Device engine: armeabi-v7a, Android API 21, NDK 26.2.11394342, Release, Jolt,
zForth, assertions off, UBSan off. Debug sections were stripped before packaging;
code and dynamic symbols retained. The APK preserves the existing reviewed
Android manifest and Java launcher glue, replacing the native library and level.
Frame profiling is omitted to keep the initial test observations in the log.

Frozen APK SHA-256:
`aab35eb38ad006b2a187f39fb96af6b77bf805484d88f81efb17364963c1d694`.
Device native library SHA-256:
`1dd419570fad226d6c80f1ff66cc7271ac653a9da1bf7deb0c3687331474a566`.
Packaged `cd.iff` SHA-256:
`f3962f83c188a65a5f27809c179ac63db06418c7f792b1ecb2d6bc4706949a5d`.

Sources are engine commit `280a1fb2` plus the retained
[const-correctness patch](unloaded-actor/android/t4-unloaded-android-engine.patch).
The generator adds `--unloaded-autonomous` (with `--unloaded-actor`) for this
device fixture; it leaves the default and command-driven fixtures unchanged.

## Evidence

- [Batch and job states](unloaded-actor/android/devices/batch.json)
- [Offline validation](unloaded-actor/android/devices/validation.json)
- [Validator source](unloaded-actor/android/validate_unloaded_device.py)
- [APK provenance](unloaded-actor/android/inputs/unloaded-actor-receipt.json)
- [Fixture inputs and compiler receipt](unloaded-actor/android/inputs/receipt.json)
- [Chromecast HD sampled recording](unloaded-actor/android/cast01-sheet.png)
- [Project Room sampled recording](unloaded-actor/android/cast02-sheet.png)
- [Raw logs, videos and receipts](unloaded-actor/android/devices/)

The frozen APK is retained locally in ignored `build-teleport/android-unloaded/`.
No arm64 phone test, non-MBR relocation or dynamic collision/contact test is
claimed by this anchored regression.
