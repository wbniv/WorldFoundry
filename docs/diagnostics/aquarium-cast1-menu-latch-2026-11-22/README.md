# Aquarium on cast1: the menu, the key latch, `screensaver-show` and the Dream (2026‑11‑22)

The unified-launcher Aquarium APK with the menu key latch, `screensaver-aquarium-release.apk` built from `bef848b8` (18 467 357 bytes, sha256 `a0a44ba7eca9bfee510513db9aedf436168d062c14ed9c7ebf731a463b3195ee`), on the Chromecast HD `chromecast-test-01`. Results and the numbered steps are in the [One Aquarium app plan](../../plans/2026-11-21-one-aquarium-app.md) (Verification 4 to 7) and the [menu key latch plan](../../plans/2026-11-21-menu-key-latch.md) (step 5).

| File | Job | What it shows |
|---|---|---|
| `menu-1-normal-launch.png` | `J‑3efc2e7072c3` (`check`) | normal launch: the menu at 1 / 11 |
| `menu-2-after-20ms-tap.png` | same | after a 23 ms DPAD_DOWN tap (device clock): 2 / 11 |
| `menu-3-after-50ms-hold.png` | same | after a 46 ms tap: 3 / 11 |
| `tank-4-calm-betta-after-ok.png` | same | after OK: the Calm Betta tank |
| `menu-5-after-back-in-tank.png` | same | after Back in the tank: the menu, still on 3 / 11 |
| `input-timeline.json` | same | every key edge with its device uptime |
| `show-no-level-J-cf050836b9c6.png` | `screensaver-show` | the preview activity, a tank, no menu |
| `show-level-aquarium_plants-J-a59814391138.png` | `screensaver-show`, `WF_CC_LEVEL=aquarium_plants` | the planted tank, no menu |
| `dream-check-J-95eed06d2d53.json`, `dumpsys-dreams-J-95eed06d2d53.txt` | `dream-check` | the real Dream, `AquariumDreamService`, not a preview |
| `aquarium-engine-log-tail-J-8fa27c7326e3.txt` | `screensaver-list` | the app's engine log: `start level 10 of 11` (the `LEVEL` run) and `start level 3 of 11` (the Dream) |
| `steer-1-clownfish-loaded.png` … `steer-5-after-hold-up-2s.png` | `J‑08baa5d0ca23` (`check`) | steering: in the clownfish tank started from the menu, no input for 2 s leaves the fish at x≈680; hold Right 3 s takes it to x≈1185, hold Left 3 s to x≈600, hold Up 2 s to the top-left corner. The player steers; it is not autopilot |

Back on the menu left the app (the last capture of `J‑3efc2e7072c3` is the Google TV home screen, 2.7 MB, not kept). The Dream's own screenshot is solid black and is not kept.

An earlier run of the steering script, `J‑52a12bbaba60`, ended `failed` with `target-left-foreground` about 5 s after the launch, before any key was sent: the TV launcher's `HomeActivity` was on top and the Aquarium task was not visible (the activity was not finished). Nothing else was using cast1 and no logcat was kept, so the cause is **unexplained**; the identical rerun completed. One such exit in four launches of this APK on cast1.
