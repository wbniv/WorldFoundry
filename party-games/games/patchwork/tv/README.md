# Android TV display launcher

A thin Android WebView activity for first hardware tests on the dedicated
Chromecast with Google TV. The game rules, shared state, phone interfaces,
visuals and scoring remain in the JavaScript platform. This is an installed
Android TV app, not a verified Google Cast custom receiver or sender-button
launch. The latter still needs an updated receiver registration and hosting.

## Build and freeze

```sh
python3 party-games/games/patchwork/tv/build.py --origin http://192.168.4.21:8096
python3 party-games/games/patchwork/tv/build.py --origin http://192.168.4.21:8096 --automated-check
```

Use the current LAN origin, not localhost. The origin is fixed inside the APK.
The build uses Android SDK 34, pinned Eclipse ECJ 3.39.0, D8, aapt, zipalign and
apksigner. Compiler SHA-256 is checked before use. Development signing keys and
build outputs are ignored by git. The debug key is not for app-store releases.
Each signed APK is copied to a filename containing its hash; its full hash and
build settings are saved in a build receipt. No native engine libraries or
community implementation code are included.

Version 0.2 uses a distinct `QuiltNightLauncher` activity alias and explicit
square/round `launcher_icon_v2` artwork. Google TV was captured still showing
the rejected diagonal icon after installing an APK whose icon pixels matched
the square-grid source. The refreshed version/launcher entry is installed;
Will verified its displayed TV home-screen icon. Coordinator app
checks continue to launch `TvActivity` directly.

## Owned hardware test

The coordinator adapter registers APP=patchwork with a fixed TvActivity.
Only this Java-only app can omit native ABI libraries. Native apps retain their
existing compatibility check. Tests verify these cases and activity mapping.
The installed protected service must include this adapter before submission.

The automated-check build launches two simulated controllers **inside the TV
app session**, plays all 18 turns and runs the shared score ceremony. It does
not control any external physical phone. The coordinator checks JavaScript
mount and completion logs, captures evidence and performs normal cleanup.

```sh
task chromecast:queue
task chromecast:check APP=patchwork POOL=chromecast-test APK=<frozen-automated-apk> DURATION=60 ASYNC=1
task chromecast:watch JOB=<returned-job-id>
task chromecast:evidence JOB=<returned-job-id> OUT=docs/diagnostics/patchwork-cast1
```

Use normal pool allocation; the coordinator respects interactive reservations.
Use the interactive APK for ordinary joining and manual play after validation;
automated APKs visibly use Device check A/B and are testing-only.

The check task restores the previous app/home after its session. Installation
persists; the user can later open Quilt Night through the TV launcher to play.
Agent-driven launch/input/capture must always remain inside owned sessions.

## Current evidence

Both APK variants build and pass signature verification. The installed service
recognizes APP=patchwork. Physical job **J-f62e22b4423d** completed on Chromecast
HD / Android 14 through normal pool allocation, using the frozen HTTPS build
`75bd2d3026fab66e83e523f7421aef766be2876824eefb703eb90772fda99b70`.
Two simulated controllers inside the TV session played all 18 turns, all three
scoring rounds and the complete final ceremony. The receipt confirms completion
and cleanup; the screenshot shows both final scores. Physical phones and Google
Cast sender-button launch remain unverified.

The local LAN builds timed out connecting to the laptop. The protected network
rules reject user-owned traffic to the TVs, including server replies. Testing
uses a temporary HTTPS origin without changing these rules. The receiver now
loads CAF only for actual Cast contexts, so Android TV does not wait on an
unnecessary external SDK. The browser regression test asserts no CAF request.
All 36 platform tests and 48 selected coordinator tests pass.

- [Physical full-game receipt](../../../../docs/diagnostics/patchwork-tv-J-f62e22b4423d/receipt.json)
- [Physical final standings](../../../../docs/diagnostics/patchwork-tv-J-f62e22b4423d/screenshot.png)
- [Ordinary launch/resume receipt](../../../../docs/diagnostics/patchwork-tv-J-bbb786952d30/receipt.json)
- [Ordinary lobby after resume](../../../../docs/diagnostics/patchwork-tv-J-bbb786952d30/resumed-screenshot.png)
- [Physical WebView log](../../../../docs/diagnostics/patchwork-tv-J-f62e22b4423d/logcat.txt)
- [Frozen HTTPS automated build](../../../../docs/diagnostics/patchwork-tv-https-build.txt)
- [Frozen HTTPS interactive build](../../../../docs/diagnostics/patchwork-tv-https-interactive-build.txt)
- [Coordinator tests](../../../../docs/diagnostics/patchwork-coordinator-tests.txt)

Temporary test origin: `https://collections-timing-riding-computing.trycloudflare.com`.
It is valid only while the development server and tunnel are running; it is not
production hosting. The interactive APK targets this URL. The initial interactive check lost foreground before its launch validation.
Retry **J-bbb786952d30** passed ordinary launch, remote keys and Home/resume
with the same process; cleanup is verified. The interactive build remains
installed and can be opened as Quilt Night from the TV launcher.

Implementation detail: WebView DOM storage is enabled for theme preferences;
file/content access is disabled. The activity allows same-origin navigation
and keeps the screen awake during play. The development APK uses LAN HTTP;
production packaging, HTTPS configuration and artwork remain separate work.

## State-by-state layout review

[Open the screenshot gallery](../../../../docs/diagnostics/patchwork-tv-review/index.html).
Job J-2104f8e72e64 recorded a complete six-player game with long names. Its
106 extracted physical frames cover all gameplay phases, every turn, readiness
changes, both intermediate round-result screens, all 36 player scoring steps
and final standings. The 150-second owned recording completed, including
cleanup; J-59b39dae068a restored and checked the ordinary interactive APK.

The browser capture retains actual public state snapshots. Replaying 106 states
in linen/night/paper gives 318 layouts with zero fit failures at 960×540.
Viewport bounds and footer overlap are checked strictly; text Range geometry
allows six pixels of font ascent beyond a line box. Representative physical
frames were inspected separately. These checks cover the normal full game;
error screens and every possible disconnect/name/score combination are not
claimed as exhaustively captured.

```sh
python3 party-games/games/patchwork/tv/build.py --origin <https-origin> --visual-check
python3 party-games/games/patchwork/test/tv-state-check.py
python3 party-games/games/patchwork/test/tv-state-replay.py
# After an owned record workflow and evidence download:
python3 party-games/games/patchwork/test/extract-tv-states.py <evidence-directory>
python3 party-games/games/patchwork/scripts/render-tv-review.py
```

Frame extraction selects the last video sample already displayed at each state
midpoint. Android screenrecord emits frames on changes; seeking blindly to a
midpoint instead selects the next state and mislabels images. The manifest
records state timestamps, requested times and chosen sample times.
