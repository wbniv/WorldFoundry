# Plan: Chromecast / Google TV port

**Date:** 2026-04-23
**Status:** Phase 0 ✅ Phase 1 ✅ done. Phase 2 needs Android phone hardware.
**Branch:** `party-games-platform`, worktree `/home/will/WorldFoundry.party-games-platform`.
**Goal:** Run World Foundry (snowgoons) on a Chromecast with Google TV device — launch
from the TV leanback launcher, take gamepad input, render correctly at TV resolution.

## Context

The Android port (closed 2026-04-18) already baked in Google TV support:
- `LEANBACK_LAUNCHER` intent filter in manifest ✅
- `android.software.leanback` feature declaration (`required=false`) ✅
- TV-mode detection via `AConfiguration_getUiModeType()` — suppresses touch HUD on TV ✅
- Gamepad input wired (`AKEYCODE_DPAD_*` + analog sticks + A/B/X/Y/L1/R1) ✅

What the Android plan never did: **device verification** (Phase 3 Step 7 is ⬜ in
[android-port](2026-04-16-android-port.md)). Neither a phone nor a TV has ever run the
APK. Additionally:
- No TV **banner image** existed — Google TV launcher shows a blank tile without
  `android:banner` on `<application>`.
- **Audio is silent stubs** — acceptable for v1; **[Stale: Android has run the real miniaudio backend since April; the Chromecast HD's log reads `audio: miniaudio v0.11.25 ready`. What is true: the apps bundle no sounds or music and nobody has listened on a TV, see [Phase D of the aquarium plan](2026-09-30-aquarium-chromecast.md#phase-d-audio).]**
  [audio-assets-from-iff](2026-04-18-audio-assets-from-iff.md) is the follow-up.
- **No CI for Android** — only iOS has a Codemagic workflow; Android builds are local-only.

This plan is primarily **verification + the two small missing pieces** (banner image,
Android CI), not new HAL code.

## Settled decisions

| Decision | Choice |
|----------|--------|
| Build target | Same APK as phone/tablet (arm64-v8a, minSdk 21) |
| Graphics | GLES 3.0 via EGL — unchanged from the Android port |
| Input | Gamepad-only on TV; touch path unchanged for phone |
| Audio | Silent stub for v1; (stale, see above; no sounds are bundled) `audio-assets-from-iff` is the Phase 4 unblock |
| Distribution | ADB sideload for v1; Play Store submission is out of scope |

## Prerequisites

- Hardware: an Android phone for Phase 2; a Chromecast with Google TV for Phase 3
  (Chromecast 4K: arm64-v8a. **Chromecast HD: 32-bit only, armeabi-v7a** (verified on a real device 2026‑10‑01), so the APK needs both ABIs)
- No code prerequisites; the Android port is the foundation

## Steps

### Phase 0 — TV banner image ✅

**Commit:** `7219b5f` — `android: TV banner template from wflogo.png + wire android:banner`

`android/app/src/main/res/drawable/tv_banner.png` — 320×180 px, logo fills left half,
174px blank right side reserved for per-game/per-level title text. Wire
`android:banner="@drawable/tv_banner"` on `<application>` in AndroidManifest.xml.
`wflogo.png` added to repo root as the source image.

### Phase 1 — Codemagic Android workflow ✅

`android-apk-debug` workflow added to `codemagic.yaml`. Linux instance (`linux_x2`),
NDK r26c pinned, `./gradlew :app:assembleDebug`, artifact `apk/debug/*.apk`. Manual
trigger only (no webhook yet). Trigger from Codemagic dashboard to verify APK artifact.

### Phase 2 — Phone verification


**Estimate: 1 day. Requires an Android phone (arm64, API 21+).**

This is the unfinished Phase 3 Step 7 from the Android port plan. Verify on phone
before TV to isolate any issues from TV-specific behaviour.

1. `adb install android/app/build/outputs/apk/<app>/debug/worldfoundry-<app>-debug.apk` (`<app>` = `snowgoons` or `aquarium` since 2026‑09‑30; `task chromecast-aquarium -- <ip>` automates this, see [aquarium-chromecast](2026-09-30-aquarium-chromecast.md))
2. Verify:
   - App launches to game (snowgoons level loads)
   - Touch d-pad (bottom-left) and A/B (bottom-right) move player
   - Home → back cycle survives 3× without crash (EGL context preservation)
   - No audio (expected)
3. Document any regressions; file follow-up plans as needed.

### Phase 3 — Google TV device verification


**Estimate: 2–3 days. Requires Chromecast with Google TV.**

Chromecast has no USB host port — ADB is over the network:
1. Enable Developer Options: TV Settings → Device Preferences → About → Build → click 7×
2. Enable Network debugging: Developer Options → Network debugging → ON
3. `adb connect <chromecast-ip>:5555` (IP at Settings → Network → About)
4. `adb install android/app/build/outputs/apk/<app>/debug/worldfoundry-<app>-debug.apk` (`<app>` = `snowgoons` or `aquarium` since 2026‑09‑30; `task chromecast-aquarium -- <ip>` automates this, see [aquarium-chromecast](2026-09-30-aquarium-chromecast.md))

Verify:
- TV launcher grid shows WF tile with the banner image from Phase 0
- App launches (gamepad or TV remote)
- **No on-screen touch d-pad** rendered (TV-mode detection fires)
- Gamepad DPAD + A/B + analog sticks drive the player
- Home → back survives without crash
- No audio (expected for v1)

### Phase 4 — Audio unblock


**Depends on:** [audio-assets-from-iff](2026-04-18-audio-assets-from-iff.md) landing.

Miniaudio on Android auto-selects AAudio (API 26+) or OpenSL ES (API 21+) — no
Android-specific audio code needed. The only required change is `audio-assets-from-iff`
landing, removing the loose `.mid`/`.sf2` file dependency that currently causes audio
init to silently skip on devices without those files.

Verify (after that plan lands): music plays during snowgoons on both phone and TV.

## Critical files

| File | Change |
|------|--------|
| `android/app/src/main/AndroidManifest.xml` | `android:banner="@drawable/tv_banner"` on `<application>` ✅ |
| `android/app/src/main/res/drawable/tv_banner.png` | 320×180 TV banner (logo left, right reserved for title) ✅ |
| `wflogo.png` | Source logo added to repo root ✅ |
| `codemagic.yaml` | New `android-apk-debug` workflow after existing iOS workflow ✅ |

No HAL or CMake changes needed — the Google TV code path is already in place.

## Verification summary

1. **Build:** Codemagic `android-apk-debug` produces a downloadable APK artifact
2. **Phone:** launch, touch nav, pause/resume ×3 — no crash
3. **TV:** leanback launcher tile shows banner, gamepad works, touch HUD absent

## Out of scope

- Play Store / Google TV channel submission and rating
- Leanback UI library (native NativeActivity game; no Android Views)
- Vulkan backend (GLES 3.0 is the v1 graphics path)
- 4K framebuffer optimisation (`EGL` surface from `ANativeWindow` already adapts to
  the display size — no extra code)
- Adaptive phone icon (tracked in [android-launcher-polish](2026-04-18-android-launcher-polish.md))
- Additional scripting engines beyond zForth on Android
