# Verify Android 4K paths and fallback

Status: in progress. Scope requested by Will: screensaver and preview, display-mode changes and recovery, phone behavior, physical 4K detail, and fallback when 4K is unavailable. Performance profiling and optimization are outside this task.

## Existing evidence

The [4K rendering plan](2026-11-25-android-4k-rendering.md) records the shared Android host change and the initial cast2 3840×2160 Activity viewport, bamboo scene, and cast1 1920×1080 control. The Homeboard [Android 4K HOWTO](../../../homeboard-tv/docs/how-to/android-4k.md) and its tester establish the distinction between output mode, app surface and physical pixel detail. Reuse the tester; an upscaled screenshot cannot establish panel detail. The implementation is not yet accepted for all lifecycle and device paths.

## Work

1. Audit the shared SurfaceView's active-mode selection, lifecycle, listener cleanup, and resizing, including mode transitions that do not cause layout. Implement host-side fixes needed to re-evaluate on display changes and fall back to the layout size when output is not 4K or unavailable. Preserve fullscreen TV and aspect constraints; do not change system display settings in the application. Add focused policy tests for 4K, 1080p, missing display, windowed/portrait and mismatched aspect cases, and mode transitions. Engine code requires Will's explicit permission before modification.
2. Build and freeze a Clocks APK with its hash. On cast2, test Activity, preview and actual Android Dream, recording the requested and actual surface dimensions, viewport, output mode, screenshots, and cleanup. Exercise pause/resume and surface recreation. On cast1 verify 1080p fallback; on Pixel verify the phone-sized window, rotation and touch alignment. Record coordinator job IDs, receipts, and per-test outcome.
3. On cast2 record the original display mode, switch through a supported 1080p mode and back to the original 4K mode only within a coordinator-owned session with restoration. Confirm the renderer changes to the correct surface without stale size or crash and recovers through resume. If the coordinator cannot safely keep ownership through the sequence or restore the original mode, document the limitation rather than issue uncoordinated commands.
4. Use the existing Homeboard tester on a 4K output to check horizontal and vertical one-, two- and four-pixel patterns. Record the TV, active mode, output and surface, and direct panel observation or suitable close photography. Do not infer physical detail from a screenshot. If observation is unavailable, leave this acceptance explicitly open.
5. Retain useful evidence and distinguish a completed coordinator job from a passed visual assertion. Summarize exact successes, failures, unavailable devices and outstanding tests in this plan. Never claim full acceptance from the previously successful 4K chooser alone.

## Current availability

At start, cast1, cast2 and Pixel all reported coordinator control unavailable because wireless debugging was not advertising. The tablet is also unreachable. Continue policy and build work while devices reconnect; no direct-device fallback is permitted.

## Implementation and local checks

The Android host now listens for display changes while the view is attached, re-evaluates the requested buffer on the UI thread, and unregisters the listener on detach. The extracted policy keeps layout-size fallback for 1080p, phone, missing sizes, partial windows, incompatible aspect ratios and portrait targets. The plain-Java policy test passed eight checks in `wf-linux-test:local`; `:screensaver:assembleClocksRelease --offline` succeeded. The frozen test APK is `build/clocks-deploy-2026-11-25/clocks-4k-recovery-test.apk`, SHA-256 `58b8da6ed11ffda99a376aa8a296749f4d0c53b0b1b5af93e1968feed839a4fa`.

These local checks do not verify actual surface changes, Android Dream/preview, phone behavior or physical pixels. Cast2 coordinator reconnect job J‑477c64f74ce5 failed `device-not-found-on-network` after the network change. Device verification remains pending until the devices are reachable on the current network.

## Reconnected-device checks

With frozen APK `58b8da6ed11ffda99a376aa8a296749f4d0c53b0b1b5af93e1968feed839a4fa`, cast2 check J‑98060d182605 completed and logged a requested and actual 3840×2160 surface and viewport; cast1 check J‑ede33b0a03dd completed and logged an actual 1920×1080 surface and viewport. These are startup checks, not display-change tests. Evidence is under `docs/diagnostics/android-4k-baseline-2026-11-25/recovery-cast2/` and `recovery-cast1/`. Actual Dream check J‑87a67b532197 failed `dream-not-observed` after the idle wait; coordinator cleanup completed with no unresolved effects. This does not establish whether the Dream itself works. At that point preview, mode-change/recovery, phone and physical-detail tests remained open.

## Screensaver idle retry

On 26 November cast2 was temporarily changed from `stay_on_while_plugged_in=3` to `0` using coordinator configure J‑91e4788a9eea. Dream check J‑2bb61f9dc696 observed the Clocks Dream and captured [the rendered clock](../diagnostics/android-4k-baseline-2026-11-25/dream-success/dream.png). Configure J‑9c60eb1d70a2 restored the original setting from `0` to `3`. The Dream check proves idle launch and visible rendering; the original check did not capture EGL dimensions, which were subsequently recovered as described below. Preview, live mode-change recovery, rotation and touch, and physical pixel detail also remain open.

Follow-up check J‑7d8a1e162929 recovered the append-only engine log from the successful idle run. The Dream's level 4 startup immediately before the subsequent menu startup reports `surface=3840x2160 viewport=0,0,3840,2160`; its level and timing match the Dream capture. The actual Dream rendering surface and viewport are therefore verified at 4K on cast2. [Recovered log](../diagnostics/android-4k-baseline-2026-11-25/dream-log-recovery/wf.log). Physical panel detail remains unverified.

## Preview and live output transition

On cast2, Clocks preview job J‑63134bc95c5b displayed Tide Harbour ([capture](../diagnostics/chromecast-capture-J-b688aa51c6e8/screenshot.png)); the subsequent [recovered log](../diagnostics/android-4k-baseline-2026-11-25/cast2-preview-log/wf.log) records a 3840×2160 surface and viewport for level 1. The original Seahorse Grid screensaver selection was restored by J‑0d2d7cd1f7a6. With a Clocks scene in the foreground, temporary [mode job J‑eaab822c0e0b](../diagnostics/android-4k-baseline-2026-11-25/cast2-mode-recovery/display-mode.json) changed HDMI output from 3840×2160@60 to 1920×1080@60 and restored the original preference and 4K output. The [post-switch log](../diagnostics/android-4k-baseline-2026-11-25/cast2-mode-recovery/wf.log) records the same running level's viewport moving 3840×2160 → 1920×1080 → 3840×2160. This verifies the live transition for this device and scene, not unplug/reconnect or allocation failure.

Pixel Clocks launch J‑7c18271672cf completed with a phone-sized surface. Automated touch jobs J‑75394a9d1d5d, J‑5a95436be739 and J‑82649f5a1282 failed the coordinator's content-rectangle preflight; no touch was injected, so touch remains unverified. Rotation and physical 4K pixel detail remain unverified.

## Physical-detail observation

On 26 November, Homeboard 4K Tester job J‑2ba2fe642904 ran on cast2. Its [capture](../diagnostics/android-4k-baseline-2026-11-25/cast2-physical-final/screenshot.png) reports a 3840×2160 surface and 3840×2160@60 output. Will observed that the finest lines looked gray. This is not proof that individual one-pixel black and white lines reached the panel distinctly; it also does not identify whether the cause is rendering, capture, TV processing, or visual resolution. Record as inconclusive rather than a native-pixel pass.

## Pixel touch verification

After pairing and unlocking the Pixel, touch job J‑94b372597b17 completed using the observed landscape window bounds (113, 0, 2244, 1008). The [after capture](../diagnostics/android-4k-baseline-2026-11-25/pixel-touch-pass/touch-frame-002.png) shows Minute Machine after tapping its chooser row; the coordinator recorded both touch edges. This verifies that selection in this landscape configuration; rotation and settings-touch coverage remain open.
