# Seahorse Grid screensaver animation variety

Date: 2026-10-19. Status: implemented and built; TV deployment waiting for coordinator device recovery.

## Goal

Give the 24 seahorses more motion while keeping the quiet grid composition. Use the clips already exported in the planted-tank seahorse meshes. Keep the change in the screensaver level generator; no World Foundry engine change is needed.

## Motion design

Each female/male pair starts in `rest_coil` at a staggered phase and shares a slow activity schedule. Each pair cycles through:

1. `swim` for five seconds: a gentle tail-rudder and fin motion, interpreted here as hovering in place.
2. `probe` for 2.7 seconds: a short tail search, without attaching to anything.
3. `greet_f` and `greet_m` together for 6.3 seconds: matching clips on the adjacent female and male.

Between activities, return to `rest_coil` for at least 7.5 seconds. Fade between clips over 1.3 to 1.5 seconds. All activities outlast their fade, so the next transition begins from a fully established clip. Stagger rest and fin phases by pair so the grid does not move in lockstep. Pair timing changes on each Dream start with the engine's start time, while the pair members remain synchronized.

Do not use `hold_idle` or `release` because the grid has no hitching posts. Do not use `startle` because there is no visible trigger. No actor position, camera, mesh or engine behavior changes.

## Implementation and checks

- Add a small per-actor clip scheduler to `scripts/build-seahorse-grid-level.py`. Use each actor's existing 40-cell mailbox block and the DFRM A/B clip fade cells. Preserve the existing render and fin calls.
- Verify the 12 pairs begin in staggered `rest_coil` phases, pair members select the same activity at the same time, greeting selects the matching female/male clip, transitions respect their fade and rest times, and the Forth script works in floating and fixed interpreter modes.
- Rebuild the nine-level screensaver bundle and APK, then inspect a live preview and Dream on every available Chromecast through the shared coordinator. Freeze the APK before submission and retain coordinator receipts. Device recovery gates remain in force.

## Build and deployment state

The nine-level bundle and screensaver debug APK built successfully. The frozen APK is `/tmp/wf-screensaver-seahorse-variety-2026-10-19.apk`, SHA-256 `7c92abbff0c576b7160474b9e5b778dd751969a8e4b9c48fc3beaa0e20f0a185`. The focused screensaver test run passed 36 cases, including the full activity cycle in floating and fixed zForth modes. Desktop frame capture was unavailable because `Xvfb` is not installed in this environment.

Coordinator install batch `B‑88c34a2ff750` accepted the artifact but installed it on neither TV. Its two children were rejected because cast1 is `recovery-required` and cast2 is `needs-local-setup`. Separate single-device install jobs `J‑b1ae81e3e460` (cast1) and `J‑807c5c410f66` (cast2) are now durably **queued** with the same frozen APK; the coordinator will run them when each device becomes ready. Cast1 still needs administrator readd after recovery preparation failed. Cast2 still reports that wireless debugging is not advertising and is held by shared transport recovery. Review each queued job's install and launcher verification receipt after recovery, then run live Dream checks.
