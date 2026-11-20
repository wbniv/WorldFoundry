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

## Not covered

- Step 10's no-actor gate (above).
- The Dream ran 383 s, not 10 minutes, and the "glass climb at least once" is shown by one screenshot, not a recorded MP4.
- The app APKs on cast1 are now the Sea Stars builds. Their previous builds were not recorded, so they were not restored.
- cast2 smoke only (28.75 FPS, J‑3f080736b0cf); it is a faster device and not a gate.
