# Plan: Android launcher polish — adaptive-icon XML

**Date:** 2026-04-18
**Status:** Implemented 2026-09-21, steps 1–2 unverified (no local Android SDK/device)
**Goal:** Layer an adaptive-icon XML (`res/mipmap-anydpi-v26/ic_launcher.xml`) on top of the legacy mipmap PNGs that just landed so Android 8+ renders the launcher icon via foreground + background drawables (rounded/themed/dynamic-shape form) instead of the legacy squared PNG. Carry-over from the Android port closure audit — small piece left after the port itself was declared closed.

## Context

The Android port plan ([docs/plans/2026-04-16-android-port.md](2026-04-16-android-port.md)) closed 2026-04-18. The closure audit ([docs/investigations/2026-04-18-android-port-closure.md](../investigations/2026-04-18-android-port-closure.md)) named launcher icons as the main remaining polish item. Legacy `res/mipmap-*/ic_launcher.png` PNGs landed as part of closure. Android 8+ prefers **adaptive icons** (XML pointing at separate foreground + background drawables) so the launcher can apply its own shape mask, monochrome theme, etc. Without the adaptive XML the phone falls back to the legacy PNG and can't do round/themed forms.

## Scope

1. Add `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` (and `ic_launcher_round.xml`) pointing at:
   - `@drawable/ic_launcher_foreground` — WF mark, transparent around it
   - `@drawable/ic_launcher_background` — solid fill or gradient
2. Add the two foreground/background vector drawables under `res/drawable/` (source art: reuse whatever WF mark exists in-repo; generate vector form).
3. Ensure `AndroidManifest.xml` `<application android:icon="@mipmap/ic_launcher" android:roundIcon="@mipmap/ic_launcher_round">` (add if not already).
4. Optional: distinct icon for `LogViewerActivity` so the two launcher entries ("World Foundry" and "WF Log Viewer") are visually distinguishable — a document glyph is fine.

## Verification

1. `./gradlew :app:assembleDebug` succeeds.

    ```
    NOT RUN — no Android SDK on this machine, and `task android-sdk-install`
    needs an interactive `sudo` password this session couldn't supply.
    ```

    **BLOCKED**, not failed — needs a machine with the SDK installed or a human to
    do the one-time interactive `sudo` for `android-sdk-install`.

2. `adb install -r …` on a clean device (Android 8+).

    ```
    NOT RUN — depends on step 1's APK, and no device attached.
    ```

    **BLOCKED**, same reason as step 1.

3. Launcher shows WF adaptive icon (rounded on Pixel, squircle on Samsung, themed on Android 13+).

    ```
    $ python3 -c "import xml.dom.minidom as m; m.parse(f)" for every mipmap-anydpi-v26/*.xml, colors.xml, AndroidManifest.xml
    OK: all 6 files well-formed

    $ grep -o '@mipmap/[a-z_]*\|@string/[a-z_]*' AndroidManifest.xml
    @mipmap/ic_launcher @mipmap/ic_launcher_log @mipmap/ic_launcher_log_round
    @mipmap/ic_launcher_round @string/app_name @string/log_viewer_label
    -> every reference resolves to a file that exists in res/

    $ for d in mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}; do ls $d; done
    -> each density has ic_launcher{,_foreground,_round}.png and
       ic_launcher_log{,_foreground,_round}.png

    foreground PNG sizes: mdpi 108x108, hdpi 162x162, xhdpi 216x216,
    xxhdpi 324x324, xxxhdpi 432x432 — matches the standard 108dp adaptive-icon
    scale exactly at each density bucket.

    Rendered ic_launcher_foreground.png (xxxhdpi): WF mark correctly scaled
    inside the safe zone, transparent surround. Visually confirmed.
    ```

    **PASS** on everything checkable without a device/emulator (XML correctness,
    resource wiring, generated-art correctness). Actual on-device
    rounded/squircle/themed rendering is unverified — that needs step 1+2.

4. `LogViewerActivity` entry visibly distinct from the main "World Foundry" entry (if the optional piece is done).

    ```
    ic_launcher_log_background (#1B2733) != ic_launcher_background (#000000)
    ic_launcher_log_foreground.png (xxxhdpi): distinct programmatic document
    glyph (red rule lines, grey folded corner), not a recolor of the WF mark.
    ```

    **PASS** (visual + resource inspection) — done, and distinct by construction.

### Deviation from scope

Step 2 said "vector drawables under `res/drawable/`" — implemented instead as
**raster PNGs under `res/mipmap-*/`** (one set per density) plus a flat
`@color` background, not a vector drawable. Reasoning (from
`scripts/gen-android-adaptive-icon.py`'s docstring): WF has no vector master
for its launcher mark, and the source `ic_launcher.png` already has solid
corners, so a flat-color background + rasterized foreground reproduces it
exactly with no lossy hand-traced vector approximation. Re-run the script
whenever the source `mipmap-xxxhdpi/ic_launcher.png` changes.

## Out of scope

- Play Store submission, release keystore, R8/ProGuard.
- Icon source art generation if no WF mark exists yet at usable resolution — treat that as a prerequisite, not part of this plan.
