# Aquarium screensaver for Chromecast with Google TV

Status: video prototype built, installed, and selected on both test Chromecasts
on 2026-10-17. A live World Foundry level and public distribution remain future
work. This is a separate Android TV app; it does not add screensaver code to
the game APK or other platforms.

## Completed prototype

- [x] Build `android/screensaver` as its own Gradle module and application ID,
  `org.worldfoundry.screensaver`. Its APK has a TV launcher and an Android
  `DreamService`, with no native engine library.
- [x] Use a silent aquarium recording with the gameplay label strip removed.
  `TextureView` displays it in both the launcher and Dream; the first
  `SurfaceView` attempt yielded dark device captures.
- [x] Keep the screensaver passive: no phone-controller prompt, QR code,
  gameplay labels, phone server, or `INTERNET` permission. The current bundled
  33.87-second recording was sampled across its full loop and contains only
  aquarium imagery; the installed final APK matches the inspected build hash.
- [x] Add the app and `dream-check` workflow to the shared Chromecast
  coordinator. The workflow waits for natural idle activation, captures the
  Dream, and restores temporary settings and foreground.
- [x] Verify visible Dream captures on [cast1](../diagnostics/screensaver-texture-dream-cast1/dream.png)
  and [cast2](../diagnostics/screensaver-texture-dream-cast2/dream.png). These
  captures used the earlier recording with gameplay text. The final clean
  recording was verified in the Dream on
  [cast1](../diagnostics/screensaver-final-dream-cast1/dream.png) and
  [cast2](../diagnostics/screensaver-final-dream-cast2-verified/dream.png), and
  through fullscreen launcher captures on
  [cast1](../diagnostics/screensaver-final-check-cast1/screenshot.png) and
  [cast2](../diagnostics/screensaver-final-check-cast2/screenshot.png).
- [x] Install the final APK on both devices and persistently select its Dream.
  The frozen artifact is `/tmp/worldfoundry-screensaver-20261017-v4-debug.apk`,
  SHA-256 `b314400f2d1e43509fd80baee1268e070960fad0d599a1eb5a9b03c72ffcbfc0`.
  [Cast1 selection](../diagnostics/screensaver-selected-cast1/configure.json)
  and [cast2 selection](../diagnostics/screensaver-selected-cast2/configure.json)
  recorded the previous Google Backdrop component. Cast1's powered-awake
  setting was changed to permit idle Dreams, with an
  [inverse recorded](../diagnostics/screensaver-allow-standby-cast1/configure.json).
- [x] Harden the shared coordinator after a cast2 check started while Android's
  private Dream activity was already foreground. Cleanup now verifies the
  original Dream remains selected and returns to verified Home, which allows
  later idle activation. The checker waits for an active, foreground Dream and
  rejects a record marked `isWaking=true`. A reviewed release with only these
  two runtime changes was deployed with recovery records preserved; cast2's
  fence was cleared by `readd`. Both final checks then completed and restored
  their settings. The focused coordinator suite passed (53 tests); a separate
  service continuation test failed in the broader run and was not used as
  evidence for this fix.

## Test cast1

Press Home on the cast1 remote and leave the TV idle for up to about 10 minutes.
The selected aquarium Dream should appear. A remote key should wake the TV.
For a coordinator-owned capture and receipt, use the exact cast1 command in
[the device coordinator guide](../device-coordinator.md#aquarium-screensaver).
Opening the app from the Apps row checks fullscreen playback only.

## Remaining work

1. Check wake, restart, and longer running behavior before treating the
   prototype as a release candidate. Recheck every future recording for
   controller prompts throughout its full loop, including after transitions.
2. Decide whether a recorded aquarium is sufficient for a public app. A public
   release needs a signed app bundle, TV listing/review, and clear instructions:
   Google TV users can install the app normally, but enabling its automatic
   idle Dream requires debugging and manual component selection.
3. If a live level is wanted, design a screensaver-only native host and propose
   any required engine surface, lifecycle, or frame-cap changes. Obtain Will's
   explicit permission before editing World Foundry engine code.

See [the investigation](../investigations/2026-10-17-chromecast-screensaver-from-a-level.md)
for implementation findings, distribution constraints, evidence, and rollback.
