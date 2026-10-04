# Install the existing Bomberman prototype on both Chromecasts

Status: installed and checksum-verified on both Chromecasts on 2026-10-04 through background-only coordinator jobs. Foreground activities were preserved and device 02's personal reservation remains intact. Hardware gameplay verification remains pending. Will requested installation on all Chromecasts.

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

The protected adapter deployment failed before mutation because `sudo -n` requires interactive authentication. [Blocker record](../diagnostics/bomberman-chromecast/deployment-blocker.txt). Run `python3 /home/will/WorldFoundry-wbniv/android/bomberman/install.py` from a terminal; it authenticates sudo locally if needed, submits both background-only jobs and downloads their receipts. No launch or input occurs.
