# Prime Numbers: Chromecast study app

Status: implemented, installed, and hardware-verified on Chromecast 1, including the latest reference-only Study revision, 2026-10-06. Chromecast 2 / WebView 91 verification and the ten-minute study soak remain pending.

## Current delivery

Implementation and saved verification evidence are committed in `525b1d29` and pushed to `origin/2026-new-level`. The installed artifact is `primes-32c0237d6bbad591.apk`, SHA256 `32c0237d6bbad591edce019fb4cfe0d22f0e67bf5da8e22e9412c8d8c1483d26`; [build receipt](../diagnostics/prime-numbers-chromecast/reference-only/build-receipt.json). Earlier build results below are historical and do not describe additional modes in the current app.

| Item | Current result | Evidence / remaining work |
| --- | --- | --- |
| Study | Complete | 1–100 chart; highlighted primes without stars; 25-prime list fills the right column; OK keeps the chart visible. |
| Recall | Complete | OK marks/unmarks directly; Check reviews all marks; answers stay hidden until Check. |
| Icon and banner | Packaged; circular launcher icon verified | Actual banner presentation on a banner-style TV launcher remains unverified. |
| Browser verification | PASS | Both target sizes and selected newer APIs removed; [results](../diagnostics/prime-numbers-chromecast/reference-only/browser/results.json). |
| Installer and coordinator tests | PASS | 12 recovery/retry cases plus 4 admission cases; [output](../diagnostics/prime-numbers-chromecast/reference-only/tooling-tests.txt). |
| Chromecast 1 installation and input | PASS | Job `J-9638f51a96ce`; [assertions](../diagnostics/prime-numbers-chromecast/J-9638f51a96ce/prime-assertions.json). Tested WebView 153.0.8010.36. |
| Chromecast 2 / WebView 91 | Pending | Device needs local setup; verify actual startup, directions including hold/release, Recall, Back, and Home/resume. |
| Ten-minute Study soak | Pending | Check prolonged readability and responsive input afterward on hardware. |

Keep the TV remote untouched during automated checks. Will confirmed physical input during two earlier failed navigation checks; the later uninterrupted check passed. Installer recovery and explicit check retry are implemented in the program, with saved jobs/evidence; no ad hoc device-control fallback is required.

## Goal

Build an offline Chromecast / Android TV app that displays every integer from 1 through 100 and clearly highlights the primes. It should work as a quiet reference chart for memorization, with optional active recall using only the TV remote. Launch directly into the chart, without sign-in, a phone, or a network connection.

## Study screen

- Display a fixed 10×10 grid in increasing row order: 1–10, 11–20, through 91–100. Keep all 100 numbers visible together, with no scrolling.
- Use a dark, calm background, large tabular numerals, and generous spacing. Prime cells have a bright accent fill; other cells have a neutral fill. A legend explains both styles. Remove the redundant stars from number boxes; accessible labels retain each number's classification.
- Give the selected cell a separate high-contrast outline so focus cannot be confused with prime highlighting.
- Remove the default “The Idea” explanation section. Fill the whole right column with “The 25 to remember,” displayed as an ordered 5×5 list of large prime numerals.
- Study stays a reference chart. OK on a number leaves the prime list visible; there is no explanation mode or factor list.
- Reserve roughly 5% margins around the TV viewport and verify layout at 960×540 and 1920×1080. Use a responsive right column, with grid numerals targeting at least 24 CSS pixels at the smaller viewport. Confirm couch-distance readability on actual hardware.
- Avoid background motion, flashing, timers, and sound. Keep the screen awake only while the app is foreground so it can serve as a study display.

## Remote controls

| Input | Behavior |
| --- | --- |
| D-pad | Move one cell in the corresponding direction; stop at edges rather than wrapping. |
| Held direction | Repeat after a short delay at a controlled rate; stop immediately on release. |
| OK on a number | Study: keep the reference chart visible. Recall: directly mark/unmark it. Ignore repeated OK keydown events. |
| Up from the top row | Move to the Study / Recall mode controls. |
| Left / Right on mode controls | Choose Study, Recall, or Check (Check is available in Recall). |
| OK on a mode control | Enter that mode and return focus to the grid. |
| OK on Check | Review all selected prime candidates together; no per-number questions. |
| Down from mode controls | Return to the last selected grid cell. |
| Back | Hide Recall results first; return from Recall to Study next; in Study, return from mode controls to the chart before normal Android exit. |

Include short visible control hints and accessible labels for the numbers, classification, and focus state. Hide actual classifications in Recall until Check.

## Recall mode

Keep the same number positions but hide actual prime classifications and the prime list. OK directly toggles a mark on the focused number, with no question or answer-choice panel. Highlight the learner's own marks and show the marked count; do not reveal whether a mark is correct yet.

The learner chooses Check from the top controls when ready. Review all marks together: number of correctly marked primes, incorrect marks in coral, and missed primes outlined on the chart and listed in the right panel. Back hides results while preserving marks; changing a mark also hides results. Returning to Study restores the reference chart. Re-entering Recall resets marks. No timer, score persistence, or streaks.

This adds a small memorization exercise while keeping the highlighted chart as the default experience.

## Number correctness

Compute classification locally with a small pure function: return false for numbers below 2; test integer divisors while `divisor * divisor <= number`. Generate cells from that classification instead of maintaining separate display and quiz answers.

Verify against this independent expected set of 25 primes:

```text
2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
73, 79, 83, 89, 97
```

Check every value in the range, particularly 1, 2, 49, 97, and 100. Classify 1 as neither prime nor composite.

## Implementation

The standalone app is under `android/prime-numbers/`, with package `org.worldfoundry.wf_game.primes`, launcher label **Prime Numbers**, and activity `.TvActivity`.

The existing [Bomberman wrapper](../../android/bomberman/README.md) and its `build.py` provided packaging references: a Java Activity displaying bundled HTML/CSS/JavaScript in a WebView, built with the installed Android SDK and pinned Java compiler. Prime-study logic stays independent of the wrapper. Implemented files:

- `assets/index.html`, `study.css`, and `study.js` for the chart, focus, and recall state.
- `src/org/worldfoundry/wf_game/primes/TvActivity.java` for fullscreen presentation, remote key forwarding, console logging, and lifecycle handling.
- `AndroidManifest.xml` with a Leanback launcher, landscape orientation, touchscreen optional, no Internet permission, and app-specific icon/banner resources.
- `build.py` producing a signed, hash-named frozen APK and a receipt with APK SHA256, package identity, and source hashes; retain a stable development signing key for upgrades.
- `verify.py` for number correctness and browser interaction checks using Python Playwright, plus a short build/run README.
- `install.py` for reviewed coordinator deployment, durable job following, bounded reconnect, foreground-app handling, evidence retrieval, and explicit failed-check retry.
- `scripts/wf_device/prime_checks.py` for the fixed, coordinator-owned hardware input check.

### Launcher icon and TV banner

Ship a distinct **Prime Numbers** identity in the TV app launcher. The icon is a 512×512 numbered 3×3 grid (1–9), with 2, 3, 5, and 7 in the same mint highlight as the study chart. The 320×180 banner combines that grid with a readable “Prime Numbers” title, “1–100,” and “Study & Recall.” Use the chart's dark background and light numerals for consistent recognition.

Generate both PNG resources with [`artwork.py`](../../android/prime-numbers/artwork.py), rendered at four times their output resolution and downsampled for clean edges. Declare both resources explicitly in `AndroidManifest.xml`. Verify the packaged APK resolves the expected label, icon, and banner, then inspect coordinator launcher screenshots from Chromecast 1. Including resources in the APK alone is not proof the TV displays them.

Support **Chromium/WebView 91**, following the [compatibility reference](../reference/chromecast-webview-compatibility.md). Use ordinary indexing and established CSS grid/flex layouts; avoid unguarded `.at()`, `Object.hasOwn`, `:has()`, and newer viewport units. Bundle all assets and fonts locally. Restrict navigation to the bundled app and avoid a JavaScript-to-native bridge unless a concrete requirement emerges.

Forward remote keydown and keyup consistently. Clear held-key state and repeat timers on blur, pause, or loss of window focus. Resume without a stuck direction or accidental answer. Handle Back in the wrapper so Android exit remains possible when no app panel or recall session consumes it. Save the current mode and selected cell across ordinary Activity recreation; a fresh launch defaults to Study.

No World Foundry engine changes are required. If implementation reveals an engine dependency, prepare a concrete proposal and obtain Will's explicit permission before modifying engine code, as required by [AGENTS.md](../../AGENTS.md).

## Delivery sequence

1. Implement the chart, prime classification, and deterministic focus navigation. Verify the default study experience first.
2. Add Recall with hidden answers and feedback; verify it uses the same classification source.
3. Package the app with its own TV launcher artwork, build and verify signing, and freeze the APK before submitting any device session.
4. Add the app identity and a study-specific remote-input trace to the shared Chromecast coordinator's supported app/workflow configuration. Follow the existing Java-only APK admission pattern, with focused validation tests. Do not assume a new `APP=primes` identifier is accepted before this registration is deployed through the documented service upgrade process.
5. Use the shared coordinator to install and test on both devices, with cast2 mandatory for WebView 91 interaction verification. Inspect captured output and record results in this plan.

## Verification and completion criteria

- Verify the grid contains 1–100 exactly once, in order, with exactly the expected 25 primes marked. Verify 1 is not described as composite and Recall scores marks consistently.
- Browser-test the actual bundled assets at both target viewport sizes: no clipping or scrolling, visible focus, readable numbers, distinct focus/prime styles, and hidden Recall answers. Test all four directions, boundaries, held/released input, rapid OK presses, unchanged Study chart after OK, mode controls, and Back behavior.
- Test lifecycle input cleanup and Activity recreation. API-removal checks can catch specific modern JavaScript dependencies but do not replace actual cast2 testing.
- Check `task chromecast:devices` and `task chromecast:queue`. Once app registration is available, submit the frozen APK with `APP=primes`, an explicit `DEVICE`, and the appropriate `task chromecast:submit`, `:check`, or `:record` workflow. Watch each returned job and download evidence with `task chromecast:evidence JOB=... OUT=...`.
- Respect personal reservations. Background-only installation may use `WORKFLOW=install`; foreground launch and input tests must wait for coordinator ownership. Use no raw Chromecast ADB or direct-control fallback.
- On **chromecast-test-02**, prove startup, all four directions including hold/release, correct highlighting, reference-only Study, Recall feedback, Back, and background/resume. Capture Study, direct Recall marks, and Recall results. Check logs for JavaScript exceptions and crashes.
- Repeat launch, readability, remote navigation, and lifecycle checks on **chromecast-test-01**. Perform a ten-minute study-display soak and confirm responsive input afterward; idle display should not require a continuous JavaScript animation loop.
- Store receipts, screenshots, recordings, and logs under `docs/diagnostics/prime-numbers-chromecast/`, separated by device/job. Record queued or reserved devices separately from completed tests.

Complete when the frozen APK launches from each TV's app launcher, all 100 numbers fit and are readable, mathematical classification is correct, Study and Recall work with the remote, and both devices have reviewed coordinator evidence. Until then, describe builds, installations, and verified behavior separately.

## Initial implementation results, 2026-10-06 (superseded app revision)

- Implemented [`android/prime-numbers/`](../../android/prime-numbers/README.md): offline chart, explanations, Recall, all remote input, lifecycle input cleanup, and generated icon/banner. No engine code changed.
- Signed frozen APK: `primes-485c4b8d6f7fe248.apk`, SHA256 `485c4b8d6f7fe248317cefc99f9a634a7d43ddcc922f00a978e45a36a44e18d2`. [Build receipt](../diagnostics/prime-numbers-chromecast/build-receipt.json) and [build output](../diagnostics/prime-numbers-chromecast/build.log). Manifest inspection resolves the expected app label, 512×512 icon, 320×180 banner, and TV activity.
- **PASS:** bundled browser checks at 960×540, 1920×1080, and 960×540 with newer APIs removed: classification of all 100 numbers, factor explanations, layout, held/released directions, OK repeat suppression, hidden answers, correct/incorrect Recall feedback, boundaries, Back, suspend, and state restoration. [Results](../diagnostics/prime-numbers-chromecast/browser/results.json), [Study screenshot](../diagnostics/prime-numbers-chromecast/browser/960-study.png), and [Recall screenshot](../diagnostics/prime-numbers-chromecast/browser/960-recall-hidden.png). Browser checks do not establish WebView 91 hardware compatibility.
- **PASS:** all 93 coordinator regression tests, including new package/ABI admission and validator restrictions. [Test output](../diagnostics/prime-numbers-chromecast/coordinator-tests.txt). The reviewed registration preserves the deployed `parmenides` app entry, which was absent from the repository's earlier app list.
- The initial noninteractive service upgrade required terminal sudo authentication. Will ran the installer and completed the reviewed upgrade; [saved installation output](../diagnostics/prime-numbers-chromecast/installation.log). The first install `J-2b15bfea824d` stopped before APK transfer because the expected wireless debugging advertisement was missing. Coordinator reconnect `J-78e5aae6f319` completed successfully; [reconnect receipt](../diagnostics/prime-numbers-chromecast/J-78e5aae6f319/receipt.json).
- **PASS:** replacement install `J-f0080603a360` installed the exact frozen APK and verified its actual Google TV launcher icon. [Installation receipt](../diagnostics/prime-numbers-chromecast/J-f0080603a360/receipt.json), [launcher screenshot](../diagnostics/prime-numbers-chromecast/J-f0080603a360/launcher/attempt-2-view-1.png), and [verified icon tile](../diagnostics/prime-numbers-chromecast/J-f0080603a360/launcher/verified-tile.png). This launcher displays circular icons; the declared TV banner is verified in the package, not claimed as displayed here. Cleanup completed and device health returned to ready.
- **PASS:** hardware study check `J-ab52213d2357` reviewed all 100 visible numbers, explanations for 1, 2, and 4, Recall hiding/revealing answers, all four held/released directions, Home/resume, and Back exit. [Assertions](../diagnostics/prime-numbers-chromecast/J-ab52213d2357/prime-assertions.json), [Study capture](../diagnostics/prime-numbers-chromecast/J-ab52213d2357/study-screenshot.png), [Recall feedback](../diagnostics/prime-numbers-chromecast/J-ab52213d2357/recall-prime-screenshot.png), and [receipt](../diagnostics/prime-numbers-chromecast/J-ab52213d2357/receipt.json). Reviewed logs show no JavaScript exceptions. Cast1 loaded WebView **153.0.8010.36**; this is not WebView 91 verification.
- [`install.py`](../../android/prime-numbers/install.py) includes automatic reconnect and replacement submission when an install/check ends in `needs-local-setup`. It performs one bounded reconnect sequence per invocation, with up to three coordinator attempts and waits of 10 and 20 seconds before attempts two and three. It journals reconnect jobs before watching, resumes interruptions, and downloads evidence. If background installation specifically refuses an update because this app is foreground, installation proceeds through the owned interactive check session, respecting personal reservations. `--retry-check` explicitly replaces one failed check while retaining its evidence. Other runtime, cancelled, uncertain-install, and service failures do not trigger blind retries or direct device control. **PASS:** twelve installer recovery/retry cases and four coordinator admission cases; [latest test output](../diagnostics/prime-numbers-chromecast/reference-only/tooling-tests.txt).
- Chromecast 2 remains `needs-local-setup` and has not been used. WebView 91 hardware compatibility, on-device banner presentation on a banner-style launcher, and the ten-minute study soak remain unverified.

## Full-column prime list and direct Recall marking

Will requested removal of “The Idea,” expansion of “The 25 to remember” to the entire right column, and Recall that marks primes without prompting. Study displays the 25 primes in a large ordered 5×5 list. This intermediate revision retained on-demand number explanations; the final reference-only revision below removes them.

Recall now uses OK to toggle the learner's own marks directly. It does not ask whether each number is prime or show per-number answer choices. Check reviews the whole selection; marks and answers are distinct until that point. Returning from results or editing marks hides answers again.

Updated frozen APK: `primes-74c457236f3cef62.apk`, SHA256 `74c457236f3cef623efba1dec794f119ac783a50ec53b394fff111c1cec528ad`. [Build receipt](../diagnostics/prime-numbers-chromecast/layout-update/build-receipt.json). **PASS:** browser checks at both target sizes and with newer APIs removed verify the full-column list, no prompts, marking/unmarking, answer hiding, incorrect selections, and a perfect set of 25 marks. [Results](../diagnostics/prime-numbers-chromecast/layout-update/browser/results.json), [Study layout](../diagnostics/prime-numbers-chromecast/layout-update/browser/960-study.png), and [direct marks](../diagnostics/prime-numbers-chromecast/layout-update/browser/960-recall-marked.png).

**PASS:** updated APK installation and launcher verification on Chromecast 1 in `J-a3508a41d545`; [receipt](../diagnostics/prime-numbers-chromecast/layout-update/J-a3508a41d545/receipt.json). Will deployed the updated Recall checker through the installer. A later redundant install/reconnect failed during wireless discovery; the program then reconnected successfully in `J-942b32fd9178`. Its replacement background install was correctly refused while Prime Numbers was foreground, so the installer continued through its owned interactive check workflow. **PASS:** full hardware check `J-7ac7b36a1b25` reviewed the expanded prime list, direct marking/unmarking, Check results, all four held/released directions, Home/resume, and Back exit. [Assertions](../diagnostics/prime-numbers-chromecast/J-7ac7b36a1b25/prime-assertions.json) and [receipt](../diagnostics/prime-numbers-chromecast/J-7ac7b36a1b25/receipt.json). Saved output and recovery history are in [installation.log](../diagnostics/prime-numbers-chromecast/installation.log) and [jobs.json](../diagnostics/prime-numbers-chromecast/jobs.json).

### Remove redundant stars

Will noted that the prime highlighting already identifies the numbers, so the number-box stars have been removed in both Study and Recall. The accessible labels still identify classifications after answers are revealed. The full-column prime list and direct marking behavior remain in place.

Frozen build `primes-bb98c637cfeef2c8.apk`: [receipt](../diagnostics/prime-numbers-chromecast/no-stars/build-receipt.json). **PASS:** both browser viewport sizes and API-removal checks, including absence of number-box stars; [results](../diagnostics/prime-numbers-chromecast/no-stars/browser/results.json). **PASS:** Chromecast 1 installation `J-0e41cb99ea40`. The Study capture from `J-032a6e4bf3aa` confirms that stars are absent. Its input check and retry `J-85e61d088d7b` failed navigation assertions while Will was also using the TV remote, which he confirmed. These interrupted checks do not establish an app input regression or a full verification pass.

### Reference-only Study

Will requested removal of explanation mode. Study now keeps the full-column prime list visible after OK on any number. No factor lists were added. Recall still uses direct marking and Check for reviewing the whole selection.

Frozen build `primes-32c0237d6bbad591.apk`: [receipt](../diagnostics/prime-numbers-chromecast/reference-only/build-receipt.json). **PASS:** browser checks at both viewport sizes and with newer APIs removed, including unchanged Study after OK on 1, 2, and 4; [results](../diagnostics/prime-numbers-chromecast/reference-only/browser/results.json). The protected hardware checker matches the reference-only Study behavior and retains navigation logs on assertion failures.

Will ran `python3 android/prime-numbers/install.py` to deploy the reviewed checker. Its background install `J-ad277fb46a9d` respected the foreground-app guard, and the program installed the frozen APK through the owned check session. **PASS:** hardware job `J-9638f51a96ce`, with the TV remote untouched, verified reference-only Study, all four held/released directions, direct Recall marking/unmarking, Check results, Home/resume, and Back exit. [Assertions](../diagnostics/prime-numbers-chromecast/J-9638f51a96ce/prime-assertions.json), [receipt](../diagnostics/prime-numbers-chromecast/J-9638f51a96ce/receipt.json), [Study after OK](../diagnostics/prime-numbers-chromecast/J-9638f51a96ce/study-reference-screenshot.png), and [direct Recall marks](../diagnostics/prime-numbers-chromecast/J-9638f51a96ce/recall-marked-screenshot.png) were reviewed. Coordinator evidence verified 68 artifacts and cleanup completed; Chromecast 1 is ready.
