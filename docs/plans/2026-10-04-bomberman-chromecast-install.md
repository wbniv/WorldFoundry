# Install the existing Bomberman prototype on both Chromecasts

Status: installed and checksum-verified on both Chromecasts on 2026-10-04 through background-only coordinator jobs. Foreground activities and the then-active personal reservation were preserved. Cat-Boom! directional movement on cast2 was fixed and recorded on 2026-10-05; cast1 hardware gameplay verification remains pending. Will requested installation on all Chromecasts.

Package the existing wf-games solo browser prototype as an offline Android TV WebView app, `org.worldfoundry.wf_game.bomberman`. Preserve its current rules and cat roster. Remote arrows select a cat before play and move during play; OK starts/restarts or drops one bomb, and Back pauses/resumes. Handle held movement and cancellation on backgrounding. Keep the browser prototype assets frozen in this repository with their source checksums. The broader movement and multiplayer plans remain separate.

Use the installed Android SDK and the same pinned Eclipse compiler as the Quilt Night wrapper. Include launcher icon/banner generated from the existing cat atlas. No server or Internet permission is needed. Gameplay mockup reference: [accepted solo screen](/home/will/wf-games/bomberman/solo-phone-play.png); verify final TV layout with actual captures.

Register Bomberman in the protected coordinator as a Java-only app with `.TvActivity`, preserving its package and immutable APK validation. Deploy only the reviewed adapter change when the coordinator has no active or queued sessions. Will clarified that installation should preserve video playback: submit one install-only job per registered device, retaining reservations and never launching or sending input. Reject an update if the target app is currently foreground. Interactive testing remains blocked during reservations.

Verification:

1. Build, verify signing and record the APK SHA256 plus bundled source hashes.
2. Browser-test cat selection, start, held/released movement, bomb press, pause, restart and TV layout; verify no network assets are needed.
3. Run coordinator regression tests for request validation and Java-only APK admission.
4. Submit both device jobs, verify installed checksum, launched foreground package, successful WebView load and remote controls; collect screenshots and logs through coordinator evidence.
5. Record completed devices and queued/reserved devices separately. Do not report a queued installation as installed.

Evidence will be recorded under `docs/diagnostics/bomberman-chromecast/`.

## Local validation and remaining blocker

Signed APK and source checksums: [build receipt](../diagnostics/bomberman-chromecast/build-receipt.json). Chromium and WebKit passed chooser, start, held/released movement, bomb, pause/resume and layout at 960×540 and 1920×1080; [raw output](../diagnostics/bomberman-chromecast/browser-verification.txt). Coordinator regression run passed 43 tests; the final four focused background-install checks also pass, including preservation of reservations and exclusive ownership.

The initial protected adapter deployment failed before mutation because `sudo -n` required interactive authentication. [Historical blocker record](../diagnostics/bomberman-chromecast/deployment-blocker.txt). Will completed the administrator deployment; the shared coordinator now supports Bomberman and multi-device installation with launcher verification. Use `task chromecast:submit APP=bomberman WORKFLOW=install DEVICE=all` to install the latest frozen build.

## Cast2 directional input repair, 2026-10-05

Cast2's log identifies WebView **91.0.4472.114**. The TV movement adapter used
`Array.at(-1)`, introduced in Chromium 92, so directional movement failed while
OK/bomb input worked. Replace it with `keys[keys.length - 1]` and retain the
frozen browser game's movement rules.

**PASS:** the browser regression reproduces a stationary player when `.at()` is
removed before the fix. After the fix, Chromium and WebKit pass at 960×540 and
1920×1080, plus 960×540 with `.at()` removed: all four directions, hold/release,
bombs, pause/resume and layout. [Browser results](../diagnostics/bomberman-cast2-input/browser-verification.txt).

**PASS:** coordinator recording `J-342b1f1daa37` on cast2 captures actual Android
directional input moving the cat from column 1 to column 4. No JavaScript errors
appear in the [device log](../diagnostics/bomberman-cast2-input/after/logcat.txt).
Compare [before right input](../diagnostics/bomberman-cast2-input/before-right.png)
and [after right input](../diagnostics/bomberman-cast2-input/after-right.png).
The recorder's existing `school` trace labels are aquarium-specific; for this
test its OK press starts the game and its final RIGHT segment measures movement.
The first recording attempt lost the target foreground and is excluded from
verification. The final frozen APK includes only a comment clarification beyond
the successfully recorded movement implementation.

**PASS:** final APK `e420c5da610d5386` installed and its actual launcher artwork
verified on cast2 in `J-65b75ee182b5`; cleanup completed and device health is ready.
[Final receipt](../diagnostics/bomberman-cast2-input/install-verified/receipt.json).
An earlier install completed its APK stage but failed foreground restoration;
coordinator reconnect recovered the device before this successful retry.

The ongoing [WebView compatibility standard](../reference/chromecast-webview-compatibility.md)
is linked from the root AGENTS.md so future TV code supports the measured floor.
