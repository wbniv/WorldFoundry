# Closing the Android Port — Remaining Work

**Date:** 2026-04-18
**Branch:** 2026-android
**Status:** Playable APK shipped; this doc lists what's left to call it "done."

## Context

Branch `2026-android` has reached playable state: APK boots, Snowgoons runs, touch + gamepad work, on-screen HUD renders, pause/resume preserves EGL context. Recent commits (aebbb15 → 5ced46c) wrapped the hardest engineering.

Question: what's left before the port can be considered **closed** — explicitly excluding Play Store / distribution work? Goal: a polished, sideloadable APK that looks and feels finished.

## What's actually missing

### 1. App icon (the real gap)

Verified state:
- `android/app/src/main/res/` contains only `layout/` and `values/` — **no `mipmap-*` dirs.**
- `AndroidManifest.xml` has no `android:icon` attribute on `<application>` or either `<activity>`.
- Result: launcher shows the generic Android gear icon for both "World Foundry" and the LogViewer second launcher.

**Action:**
- Generate `ic_launcher` at mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi (48/72/96/144/192 px) under `res/mipmap-*/`.
- Add adaptive icon XML (`res/mipmap-anydpi-v26/ic_launcher.xml`) with foreground + background drawables for Android 8+.
- Add `android:icon="@mipmap/ic_launcher"` and `android:roundIcon="@mipmap/ic_launcher_round"` to `<application>` in AndroidManifest.xml.
- Optional: give LogViewerActivity a distinct icon (e.g. a document glyph) so the two launcher entries are visually distinguishable.

Source art: reuse whatever WF logo/mark exists in-repo; if none at the right resolution, generate from a high-res master.

### 2. Stale build.gradle.kts comment

`android/app/build.gradle.kts:60-62` says "the packaged APK ships no assets — sideload cd.iff to /data/local/tmp/wf/cd.iff". This is **out of date** — `android/app/src/main/assets/cd.iff` exists (symlink) and Gradle bundles it.

**Action:** Delete the stale comment. Confirm on a fresh install (uninstall, reinstall, wipe `/data/local/tmp/wf/`) that Snowgoons still boots purely from bundled assets.

### 3. README status table out of sync

`android/README.md` status table still lists Phase 3 steps 4/5 as pending, but 2026-04-18 wf-status entry marks Phase 3 step 7 (device smoke test) complete.

**Action:** Update the status table to reflect current reality (Phases 1–3 done; port complete pending icons + polish).

### 4. wf-status.md rolling summary

When the port is closed, prepend a new topical paragraph to the top of `docs/wf-status.md`'s Summary section noting Android port closure (per the reverse-chronological convention).

## Intentionally out of scope

- Play Store submission, release keystore, minification (debuggable is fine for sideload).
- ProGuard/R8 rules (Java surface is tiny: `LogViewerActivity` only).
- Splash screen (NativeActivity → game is acceptable).
- Adaptive HUD layout for unusual aspect ratios (fixed-pixel regions are fine for v1).
- Localization, analytics, crash reporting.

## Critical files

- `android/app/src/main/AndroidManifest.xml` — add `android:icon` / `android:roundIcon`.
- `android/app/src/main/res/mipmap-*/` — new PNG directories.
- `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` — new adaptive icon.
- `android/app/src/main/res/drawable/` — foreground/background vector drawables for adaptive icon.
- `android/app/build.gradle.kts` — delete stale comment (lines 60–62).
- `android/README.md` — refresh status table.
- `docs/wf-status.md` — prepend port-closure paragraph to Summary section.

## Verification

1. `./gradlew :app:assembleDebug` — build succeeds.
2. `adb install -r android/app/build/outputs/apk/debug/app-debug.apk` on a clean device (after `adb uninstall org.worldfoundry.wf_game` and `rm -rf /data/local/tmp/wf`).
3. Home screen / app drawer shows the WF icon (not the gear) for both "World Foundry" and "WF Log Viewer" launchers.
4. Tapping the icon boots Snowgoons from bundled `cd.iff` with no sideloaded files present.
5. Briefly verify pause/resume still works (home button → reopen) and that HUD + gamepad still behave.
