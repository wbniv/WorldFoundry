# Plan: Android launcher polish — adaptive-icon XML

**Date:** 2026-04-18
**Status:** Not started
**Goal:** Layer an adaptive-icon XML (`res/mipmap-anydpi-v26/ic_launcher.xml`) on top of the legacy mipmap PNGs that just landed so Android 8+ renders the launcher icon via foreground + background drawables (rounded/themed/dynamic-shape form) instead of the legacy squared PNG. Carry-over from the Android port closure audit — small piece left after the port itself was declared closed.

## Context

The Android port plan (`docs/plans/2026-04-16-android-port.md`) closed 2026-04-18. The closure audit (`docs/investigations/2026-04-18-android-port-closure.md`) named launcher icons as the main remaining polish item. Legacy `res/mipmap-*/ic_launcher.png` PNGs landed as part of closure. Android 8+ prefers **adaptive icons** (XML pointing at separate foreground + background drawables) so the launcher can apply its own shape mask, monochrome theme, etc. Without the adaptive XML the phone falls back to the legacy PNG and can't do round/themed forms.

## Scope

1. Add `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` (and `ic_launcher_round.xml`) pointing at:
   - `@drawable/ic_launcher_foreground` — WF mark, transparent around it
   - `@drawable/ic_launcher_background` — solid fill or gradient
2. Add the two foreground/background vector drawables under `res/drawable/` (source art: reuse whatever WF mark exists in-repo; generate vector form).
3. Ensure `AndroidManifest.xml` `<application android:icon="@mipmap/ic_launcher" android:roundIcon="@mipmap/ic_launcher_round">` (add if not already).
4. Optional: distinct icon for `LogViewerActivity` so the two launcher entries ("World Foundry" and "WF Log Viewer") are visually distinguishable — a document glyph is fine.

## Verification

1. `./gradlew :app:assembleDebug` succeeds.
2. `adb install -r …` on a clean device (Android 8+).
3. Launcher shows WF adaptive icon (rounded on Pixel, squircle on Samsung, themed on Android 13+).
4. `LogViewerActivity` entry visibly distinct from the main "World Foundry" entry (if the optional piece is done).

## Out of scope

- Play Store submission, release keystore, R8/ProGuard.
- Icon source art generation if no WF mark exists yet at usable resolution — treat that as a prerequisite, not part of this plan.
