# Sea Stars: cast1 acceptance, 2026‑11‑20

Plan: [Sea Stars](../../plans/2026-11-10-starfish-tank.md), verification steps 10–12. Device: cast1 (`chromecast-test-01`, Chromecast HD, Android 14, armeabi‑v7a). Every device action went through the coordinator. Build: `f8d95b37` plus the Dream fix below; game APK sha256 `03cc5d62…`, Dream APK `11fae056…`.

| Step | What | Result |
|---|---|---|
| 10 | Early gate: static tank with no actors ≤ 38 ms | **NOT RUN.** No static-tank variant exists |
| 11 | Selector reaches Sea Stars (row 11 of 11) and Back returns | **PASS** (J‑cb08302accc8): started at 21.2 FPS on the on-screen counter; Back showed the menu at "11 / 11" |
| 11 | D7 gate: wide idle ≥ 20 FPS, default population, median of 3 × 120 s | **PASS: 23.99 FPS** (24.09, 23.91, 23.99; jobs J‑a40ff60e3f1a, J‑1486f4d2d2e1, J‑266da3e4edd7). p50 frame 50.05 ms, three display refreshes |
| 12 | Dream with Sea Stars, autopilot climbs the front glass | **PASS after a fix**, but the run was **383 s, not 10 minutes**: the check's own shortest window is 380 s. The screenshot shows the autopilot's star on the front glass with its oral side to the camera (J‑9246d246c7e1) |
| 12 | Settings restored | **PASS**: Seahorse Dream selected, enabled, activate_on_sleep 1, idle 600000 ms, stay-on 0, `tank = random` (`cast1-settings-after-restore.json`) |

## The Dream bug the first run found

The first Dream check (J‑d9db9b52ef42) ran, but showed the **Clownfish** tank. `dream_host.cc` built the positional level argument as `'0' + level`, so tank 10 became `:`, which the engine's `atoi()` reads as 0. Fixed in `f941db11` (decimal via `snprintf`); `tests/test_dream_host_vram.py` now fails if the one-digit form returns and checks the guard against the tank list. The game app was never affected.

## Settings phases, 2026‑11‑20 (afternoon)

| Step | What | Result |
|---|---|---|
| 10 | Early gate: empty tank (`--empty` variant) ≤ 38 ms | **PASS**: p50 33.37 ms in all three 120 s runs (J‑6813c0e83b5a run 1; runs 2 and 3 the same). 32.5–32.7 FPS, so the cost is the display's 30 fps pacing, not the level |
| Phase 5 | The Dream's phone form on cast1 | **PASS**: the Aquarium Dream serves nine `sea-stars.*` settings (`phase5-settings.json`). Setting Red Fromia 5 and Chocolate-chip stars 4 through the coordinator showed 5 Fromia and 4 chips on screen (J‑4eee56be1c79) |
| 12 | 10 minute Dream, recorded, with a glass climb | **FOUND A BUG, not closed.** The recording (J‑7c2edc48df59, 597 s, four MP4 segments) shows the star climbing once, then standing still from 42 s to 585 s. Cause below; the earlier 383 s "PASS" missed it because the climb comes in the first 14 s |

**The autopilot stall.** Landing from the back wall latches the held DOWN (`st-change`, added for the stick-hold bounce); a latch clears only when the buttons change. Autopilot step 4 kept holding DOWN, so the star never left the back-right corner. It moved again only when a frame hitch over 200 ms forced a neutral stick (the recording has hitches of 250–420 ms). Reproduced in the zForth VM; fixed in `6c83fbb1` (step 4 presses nothing until the latch clears), guarded by `test_dream_autopilot_keeps_lapping` (600 s at 30 fps, at least 5 front-glass climbs, no standstill over 25 s; the old script gives 1 climb).

**Re-recorded with the fix (game `8aca0680…`, Dream `59d886aa…`, J‑48fd1fcc99fb, 596 s): PASS.** The star laps continuously: eight large-star glass episodes (starting at 0, 49, 129, 211, 290, 373, 458 and 543 s, about 80 s apart, 8 climbs in 10 minutes), longest standstill 28 s (the scripted 20 s rest, stretched by the Dream's wall-clock pacing), against 9 minutes parked before the fix. [`dream10-fixed-front-glass.png`](dream10-fixed-front-glass.png) shows the climb at 83–87 s: the star at the front-right edge of the sand, then up the front glass with its oral side to the camera; per-second tracking is in [`dream10-fixed-star-track.json`](dream10-fixed-star-track.json) (second, blue pixels, x, y, height).

**Baseline restored: PASS** (J‑bc48d1edffa3, J‑8b47d5173062, J‑a2f2bff9c0f3): Seahorse Dream selected and enabled, `activate_on_sleep` 1, idle 600000 ms, sleep timeout −1, stay-on 0, nothing running; every field equals [`cast1-settings-after-restore.json`](cast1-settings-after-restore.json) ([`cast1-settings-after-second-restore.json`](cast1-settings-after-second-restore.json)).

**Mac and iOS, on Codemagic (branch `2026-new-level`):** macOS Desktop (Debug, headless) [build 6b002cad…](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6b002cada30564f93e0e18a7) and iOS Simulator (Debug) [build 6b002e8f…](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6b002e8f834ddd44ee9207c2), including the iPhone and iPad simulator run, both finished green. About 20 Mac minutes; 257 of 500 used this month.

**The coordinator fence.** After the first re-record attempt cast1 was fenced `cleanup-unverified` (an automatic readd failed its foreground restore: another principal's job began with the Aquarium Dream in the foreground, and my earlier restore had already selected the Seahorse Dream). It cleared by itself within about an hour and the queued jobs then ran. Lesson: end a Dream recording by restoring settings only when no other job can start in between, or leave the original Dream selected until the last job.

**Still open on cast1:** the Phase 6 gate, at least 20 FPS (median of 3 × 120 s) at the default and at the maximum population.

## Not covered

- Step 10's no-actor gate (above).
- The app APKs on cast1 are now the Sea Stars builds. Their previous builds were not recorded, so they were not restored.
- cast2 smoke only (28.75 FPS, J‑3f080736b0cf); it is a faster device and not a gate.
