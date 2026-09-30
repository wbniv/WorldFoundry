# Porting status: World Foundry on every platform

As of 2026‑10‑01 00:45 (+07) = 2026‑09‑30 17:45 UTC. Everything below was observed in a Codemagic build or a local
run on that day, and each claim links to its evidence. **—** means not assessed today, not "works". Legend: ✅ verified,
🟡 partial, ❌ not working, ⬜ not tested. Plan: [the aquarium on every platform](plans/2026-09-30-aquarium-platforms.md).

## Summary

| Platform | Builds | Runs | Draws the game | Input | On a real device |
|---|---|---|---|---|---|
| **Linux desktop** (OpenGL) | ✅ | ✅ | ✅ (the reference renderer) | ✅ keyboard, gamepad | ✅ (this machine) |
| **macOS desktop** (Metal) | ✅ [build 6abd3923](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd3923a7c72c2289f7506c) | ✅ window, close paths, fullscreen | ✅ pixel-matches Linux | 🟡 keyboard ✅, ⌘Q ✅, red button ✅, Esc not provable in CI | ⬜ no Mac owned; Retina untested |
| **iOS, iPhone and iPad** (Metal) | ✅ builds and links ([build 6abd3f6b](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd3f6b471c8a90c6e1da1a)) | 🟡 installs and launches in simulators, then aborts after about 10 s | ❌ only the clear colour | ⬜ touch not implemented yet | ⬜ needs the $99 Apple account |
| **Android phone and tablet** (GLES 3) | ✅ [build 6abd1529](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd1529669c35dd0f161d7a) (was broken 09‑21 to 09‑30, fixed) | ⬜ not run since the fix | ⬜ | ⬜ | ⬜ |
| **Chromecast with Google TV** (same APK) | ✅ aquarium app [build 6abd1c20](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd1c20874cdae673caf7ae) | ⬜ | ⬜ | ⬜ gamepad profile ready | ⬜ needs the device's IP address |

## The aquarium on each platform

Scripted, deterministic frames (`--frame-step-smoke`, `-rate20`, frame 20 of a fixed run; no player input), not
real-time play. The same level file and the same flags on every platform.

| Linux, OpenGL (reference) | macOS, Metal (Codemagic) |
|---|---|
| <img src="porting-status/aquarium-linux-gl.png" width="420"> | <img src="porting-status/aquarium-macos-metal.png" width="420"> |
| The committed reference frame, byte-identical across three runs. | Rendered by Metal on a Codemagic Mac. **306 865 of 307 200 pixels are exact; the other 335 differ by one level, none beyond the tolerance of 3** ([macOS build](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd3923a7c72c2289f7506c)). |

| macOS Metal, frame 100 | macOS Metal, frame 200 | macOS Metal, real window |
|---|---|---|
| <img src="porting-status/aquarium-macos-metal-frame100.png" width="133"> | <img src="porting-status/aquarium-macos-metal-frame200.png" width="133"> | <img src="porting-status/aquarium-macos-metal-windowed.png" width="133"> |
| Later in the same run: the anemone sways and the fish's pose changes. | Frame 200 of the same deterministic run. | Presented to a real `CAMetalLayer` window (`--windowed`) on the runner. |


| iOS simulator, iPhone 17 Pro | iOS simulator, iPad Pro 13‑inch |
|---|---|
| <img src="porting-status/ios-iphone-simulator.png" width="200"> | <img src="porting-status/ios-ipad-simulator.png" width="320"> |
| **The app runs, but no scene is drawn:** the screenshot is the solid clear colour. The engine's frames do not reach the Metal view yet. | Same. The CI check called the iPad "OK" because the black letterbox bars add colours: a **false positive**, being fixed. |

| Android and Chromecast: the app tile | What the TV will show (16:9) |
|---|---|
| <img src="porting-status/android-tv-banner.png" width="320"> | <img src="porting-status/aquarium-16x9-linux.png" width="420"> |
| The aquarium's Google TV launcher banner. The APK builds; no device has run it yet. | A Linux render at 1920×1080 (the TV's shape); the level was tuned for 4:3, and the whole tank still fits. **Not a Chromecast screenshot.** |

## Details

### macOS (Metal): working
- CI `macos-desktop-debug` builds and links (Ninja, arm64, Jolt physics, Forth scripting), runs the headless frame-step smoke, and compares frames with Linux: snowgoons 306 702 of 307 200 exact, the aquarium 306 865 of 307 200, neither with any pixel beyond tolerance 3.
- A real window with a `CAMetalLayer` presents drawables on the runner; keyboard input works ([2026‑09‑21 VNC session](plans/2026-09-21-macos-human-verification.md)).
- **⌘Q and the red close button** quit cleanly (status 0) with real System Events input, and **`-fullscreen`** covers the display without changing its resolution ([close-paths step](plans/2026-09-21-macos-close-paths.md)).
- **Open:** Retina (the runner is scale 1.0), Esc delivery in CI (the VNC pass stands), double-click launch of the `.app`, the `cd.iff`-from-bundle path (CI uses `-L`), a real Mac.

### iOS (Metal): builds, does not draw yet
- Got from "configure fails" to "builds, links, installs, launches" today: Jolt extraction, the `MTLStorageModeManaged` iOS guard, and three missing link symbols.
- **Open:** engine frames to the screen (iOS Phase 2C‑B), a CoreAudio deadlock that aborts the app on the simulator, touch input and lifecycle (Phase 3), real devices (signing). A branch is working on the first two.

### Android and Chromecast (GLES 3): builds, unrun
- The Android build had been **broken since 09‑21** (`GL_RGB5` is not in GLES 3.0; `backtrace()` needs API 33) and is fixed. Both apps (snowgoons and the aquarium, separate app ids) build in CI.
- **Open:** running either on a phone or a Chromecast, frame cost on Chromecast hardware, audio (silent stub). The device run needs the Chromecast's IP address with Network debugging enabled, and ideally a paired gamepad.

### Linux: the reference
- Builds, runs and renders everything; the aquarium has 38 passing tests and a demo video (`tests/recordings/aquarium_phase4_motion_demo.mp4`). Its committed frames are the references the other platforms are compared against, and a test re-renders them so they cannot go stale.

## Reproduce

- Drive Codemagic without an AI in the loop: `scripts/codemagic-queue.py --run macos-desktop-debug:2026-new-level`.
- Budget: 500 free Mac-minutes a month on M2 machines, one build at a time.
