# Prime Numbers for Android TV

An offline 1–100 reference chart with 25 highlighted primes,
and a remote-controlled Recall mode. Package: `org.worldfoundry.wf_game.primes`.
Targets Chromium/WebView 91; actual WebView 91 hardware verification remains
pending on Chromecast 2. Installed and verified on Chromecast 1 with WebView
153.0.8010.36. No World Foundry engine code or network service.

Build with `python3 android/prime-numbers/build.py`. Requires the installed
Android SDK, Java, Pillow, and the pinned ECJ compiler described in
`party-games/games/patchwork/tv/build.py`. The script generates the numbered-grid
512×512 icon and 320×180 TV banner, verifies APK signing, and writes a hash-named
APK plus `build/build-receipt.json`. Preserve `build/development-signing.p12`
for subsequent updates; build artifacts and this local development key are ignored
by Git.

Run `python3 android/prime-numbers/verify.py` with Python Playwright and its
Chromium browser installed. It exercises the actual bundled assets and saves
screenshots/results to `build/verification/`.

## Using the TV remote

D-pad moves through the chart and Up from the first row
reaches Study/Recall controls. The 25 primes fill the right column in Study.
In Recall, OK directly marks or unmarks numbers without questions. Choose Check
in the top controls to review correct marks, incorrect marks, and missed primes.
Answers stay hidden until Check; changing a mark hides results again.
Study remains a reference chart, with no explanations or factor lists.
Back dismisses results, returns from Recall to Study, then exits. If focus is
on the mode controls in Study, Back first returns to the chart. Mode and selected
number survive Activity recreation; marks reset on recreation and when a new
Recall session starts.

## Installation and recovery

Device work uses the shared coordinator. After deploying the reviewed Primes
registration, use the frozen APK path from the receipt:

For a single terminal command that authenticates the reviewed upgrade, installs
on Chromecast 1, verifies remote controls, and saves all output/evidence:

```sh
python3 android/prime-numbers/install.py
```

The installer writes `docs/diagnostics/prime-numbers-chromecast/installation.log`
and persists job IDs before watching, so interruption can resume the same jobs.
It never asks for a password in chat; sudo authentication stays in the terminal.
If an install or check job ends with `needs-local-setup`, it automatically runs
one bounded coordinator reconnect sequence, waits for completion, saves its evidence,
and submits a replacement workflow job. An interrupted reconnect resumes its
saved job. Missing wireless advertisements get up to three `chromecast:readd`
attempts, with 10- and 20-second waits before the second and third attempts.
Exhausted reconnect attempts or a second connection failure after recovery stop with the
Wireless debugging instruction; runtime failures and cancelled jobs are not
silently retried. No manual journal edits or separate reconnect command are
needed for this recovery path.
If background installation refuses an update because this app is foreground,
the installer proceeds to its owned interactive check session, which installs
and verifies the same frozen APK. That session still waits behind personal
reservations; the background workflow's protection remains intact.
After investigating a failed hardware check, rerun it once with
`python3 android/prime-numbers/install.py --retry-check`. This preserves the
failed job's evidence and submits one replacement check without journal edits.

Individual coordinator commands:

```sh
task chromecast:submit DEVICE=chromecast-test-01 WORKFLOW=install APP=primes APK=/absolute/path/primes-HASH.apk
task chromecast:check DEVICE=chromecast-test-01 APP=primes APK=/absolute/path/primes-HASH.apk VALIDATOR=prime-study
task chromecast:watch JOB=J-example
task chromecast:evidence JOB=J-example OUT=/absolute/path/evidence
```

`install` preserves foreground playback and reservations. Interactive checks
wait for ownership; they exercise the reference chart, Recall, all held/released
directions, Home/resume, and Back exit. No direct device-control fallback.
Leave the physical TV remote untouched while a check is running: physical and
automated button presses both reach the app and can invalidate navigation
assertions. A failed check saves its evidence; investigate that output before
using `--retry-check`.

The registration upgrade uses the existing maintenance/drain/rollback helper:

```sh
sudo python3 android/bomberman/deploy-coordinator.py --review android/prime-numbers/deploy-review.json
```

The review pins previous and new adapter hashes. Regenerate and review it if
either installed code or local adapters change; a mismatch stops before mutation.
Deployment preserves reservations and queued jobs and waits for active sessions.

## Verified release, 2026-10-06

The installed APK is `primes-32c0237d6bbad591.apk`, SHA256
`32c0237d6bbad591edce019fb4cfe0d22f0e67bf5da8e22e9412c8d8c1483d26`.
Its [build receipt](../../docs/diagnostics/prime-numbers-chromecast/reference-only/build-receipt.json)
records the sources used for that frozen artifact. Source implementation and
evidence were committed as `525b1d29`.

- Browser checks passed at 960×540, 1920×1080, and with selected newer APIs
  removed, covering all 100 numbers, the 25 primes, layout, remote input,
  reference-only Study, Recall marks/results, and lifecycle state.
- The twelve installer recovery/retry tests and four coordinator admission
  tests passed; [test output](../../docs/diagnostics/prime-numbers-chromecast/reference-only/tooling-tests.txt).
- Chromecast 1 check `J-9638f51a96ce` installed the exact frozen APK and passed
  Study, all four held/released directions, Recall, Home/resume, and Back exit;
  [assertions](../../docs/diagnostics/prime-numbers-chromecast/J-9638f51a96ce/prime-assertions.json).
  Reviewed captures show the [Study chart after OK](../../docs/diagnostics/prime-numbers-chromecast/J-9638f51a96ce/study-reference-screenshot.png)
  and [direct Recall marks](../../docs/diagnostics/prime-numbers-chromecast/J-9638f51a96ce/recall-marked-screenshot.png).

Earlier icon verification confirmed the actual circular Google TV launcher
tile. The TV banner is packaged, but its display on a banner-style launcher
remains unverified. Chromecast 2 interaction testing and a ten-minute Study
soak also remain pending. Removing newer browser APIs in desktop tests does
not establish WebView 91 hardware compatibility.

See [the plan](../../docs/plans/2026-10-06-prime-numbers-chromecast.md) for scope
and current device evidence.
