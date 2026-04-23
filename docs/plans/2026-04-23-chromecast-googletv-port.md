# Plan: Chromecast / Google TV port

**Date:** 2026-04-23
**Status:** Phase 0 + Phase 1 done — banner image + Codemagic Android workflow landed. Phases 2–3 need hardware.
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
- No TV **banner image** exists — Google TV launcher shows a blank tile without
  `android:banner` on `<application>`.
- **Audio is silent stubs** — acceptable for v1;
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
| Audio | Silent stub for v1; `audio-assets-from-iff` is the Phase 4 unblock |
| Distribution | ADB sideload for v1; Play Store submission is out of scope |

## Prerequisites

- Hardware: an Android phone for Phase 2; a Chromecast with Google TV for Phase 3
  (Chromecast 4K gen 2 / HD gen 2 both work — arm64-v8a, API 29+)
- No code prerequisites; the Android port is the foundation

## Steps

### Phase 0 — TV banner image
**Estimate: 1 day. No hardware required.**

Google TV launcher requires `android:banner` on `<application>`. Without it the app tile
in the leanback launcher grid is blank.

1. Create `android/app/src/main/res/drawable/tv_banner.png` — **640×360 px** (2×, 320×180 dp).
   Use any WF mark / placeholder art; polish later.
2. Add `android:banner="@drawable/tv_banner"` to `<application>` in
   `android/app/src/main/AndroidManifest.xml`.
3. `./gradlew :app:assembleDebug` — verify APK builds clean; `aapt dump badging` confirms
   banner attribute is present.

### Phase 1 — Codemagic Android workflow
**Estimate: 1 day. No hardware required.**

iOS has Codemagic CI; Android only has local `./gradlew`. Add an Android workflow so
every push produces a downloadable debug APK, enabling verification without a local
Android SDK.

1. Add `android-apk-debug` workflow to `codemagic.yaml` (after the two existing iOS
   workflows):
   - **Instance:** Codemagic Linux agents ship Android SDK + NDK pre-installed
   - **NDK version:** pin to r26c (matches local `26.2.11394342`)
   - **Build step:** `cd android && ./gradlew :app:assembleDebug`
   - **Artifact:** `android/app/build/outputs/apk/debug/*.apk`
2. Trigger manually in Codemagic dashboard; verify downloadable APK artifact.

### Phase 2 — Phone verification
**Estimate: 1 day. Requires an Android phone (arm64, API 21+).**

This is the unfinished Phase 3 Step 7 from the Android port plan. Verify on phone
before TV to isolate any issues from TV-specific behaviour.

1. `adb install android/app/build/outputs/apk/debug/app-debug.apk`
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
4. `adb install android/app/build/outputs/apk/debug/app-debug.apk`

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
| `android/app/src/main/AndroidManifest.xml` | Add `android:banner="@drawable/tv_banner"` to `<application>` |
| `android/app/src/main/res/drawable/tv_banner.png` | New — 640×360 px TV banner image |
| `codemagic.yaml` | New `android-apk-debug` workflow after existing iOS workflows |

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
