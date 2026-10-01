# Aquarium on every platform: macOS and iOS (Metal), Android, Chromecast

Status: **in progress (2026‑10‑01).** The aquarium runs on macOS (Metal, CI), in the iPhone and iPad simulators, and on a **real Chromecast HD**; the separate macOS and iOS aquarium apps, touch on iOS and a real phone remain. Written 2026‑09‑30. Sub-plan for Android and Chromecast:
[2026‑09‑30‑aquarium‑chromecast](2026-09-30-aquarium-chromecast.md) (being written by its own agent).

- [x] Phase A: baseline. macOS is green in CI; iOS builds, links and draws in the simulators; Android builds in CI, runs in an emulator and on a real Chromecast HD. Real iPhone/iPad/phone devices are not tested
- [x] Phase B: one aquarium-only `cd.iff` (`wflevels/aquarium-cd.iff`), used by the Android app and the iOS screenshot variant
- [ ] Phase C: **macOS** `Aquarium.app` on Metal
- [ ] Phase D: **iOS** aquarium app on Metal: the aquarium renders in the iPhone and iPad simulators (screenshot-only variant; the iPhone shot is rotated); the separate app and touch verification remain
- [x] Phase E: **Chromecast** with Google TV: runs on a real Chromecast HD (32-bit `armeabi-v7a`) and the D-pad moves the fish; release frame rate and a gamepad remain

## Context

The aquarium level is finished on Linux ([plan](2026-09-30-aquarium-level.md), Phases 0–4, 38 tests, demo video in
`tests/recordings/`). On 2026‑09‑30 the user asked for two things, in this order:

1. Make sure World Foundry **still** builds and runs on macOS, iOS (iPhone and iPad), Android and Chromecast.
2. Then run the aquarium on a Chromecast, and have **Metal versions running the aquarium on macOS and iOS**.

The user also decided that snowgoons and the aquarium are **separate apps** (own app id, name, icon, level), not one
app with a level selector, and that the snowgoons default need not be protected. `WORLD_SCALE = 10` stays (decision the
same day; the three ×1 limits are listed in the [aquarium plan](2026-09-30-aquarium-level.md) § Scale decision).

State today, with evidence (Codemagic app `6aafa6886ab3f21cf431a6cb`, branch `2026-new-level`):

| Platform | What CI shows on 2026‑09‑30 | Consequence |
|---|---|---|
| macOS desktop | Build `6abd0d96` (commit `2f0f0efb`) **builds, links and runs**, but the snowgoons frame gate failed: 35 px beyond tolerance. The Linux reference was **stale** since `4c02b471` (`WF_CULL` on by default): the current Linux engine differs from it in the same 35 px, with `WF_CULL=0` it matches exactly, and the macOS frame matches a fresh Linux frame with 0 px beyond tolerance (497 px off by 1). Reference regenerated, guard test added. | Metal is fine; re-run to confirm (build `6abd118f`). |
| iOS simulator | Build `6abd0e31` **fails** at "Configure CMake for iOS Simulator" (1 min). The log was not teed, so the error text is unknown. Leading hypothesis: the default physics engine is now Jolt (`CMakeLists.txt:30`), whose archive is extracted only by the macOS workflow, not the iOS one. The workflow also still carries Phase 0 comments ("no if(IOS) branch yet") and boots only an iPhone simulator. | iOS has had no working CI since April. |
| Android / Chromecast | Build `6abd0e34` queued behind the others. One APK serves phone and Google TV. Phases 2 and 3 of the [Chromecast plan](2026-04-23-chromecast-googletv-port.md) (phone and TV device verification) were never run. | "Runs" needs a device. |

How a level reaches an app: as `cd.iff` in the app's assets (`AAssetManager` on Android; the bundle on iOS and macOS),
assembled by `task build-cd-iff` (`wftools/cdpack-rs`) from `shell.fth` plus standalone level IFFs. The `-L<level>`
flag is only a dev and CI bypass. The macOS smoke uses `-L` deliberately, so **the macOS `cd.iff`-from-bundle path has
never been exercised**.

Mac-minutes: 500 free per month on M2 machines, "reset on the 1st of each month" ([Codemagic pricing](https://docs.codemagic.io/billing/pricing/);
the time zone is not stated). 81 min were used by 13:22 UTC on 2026‑09‑30. Automated macOS builds cost 2–3 min each;
this month's usage was mostly one 32 min interactive session.

## Approach

**One shared piece, four apps.** Every app gets its own `cd.iff` containing only its level and a `shell.fth` that starts it
without a menu. Build it once, generically (`build-cd-iff-aquarium`, output path a parameter), and reuse it. The
Android agent builds it first ([Chromecast plan](2026-09-30-aquarium-chromecast.md)). Rejected: a single multi-level app
with a level selector (the user's decision), and `-L` on device (not how apps find their level).

**Phase A: baseline first.**
- macOS: confirm the fixed commit is green, including the aquarium parity step (informational: it reports MATCH or
  DIFFERS with counts).
- iOS: revive `ios-simulator-debug`. Extract Jolt (or force legacy physics, whichever CMake supports for `-G Xcode`),
  tee every step's output into a log artifact so failures are readable without the web UI, remove the Phase 0 comments,
  and boot **an iPad simulator as well as an iPhone**. Budgeted iterative CI runs; stop after four failed attempts
  with the evidence.
- Android: the APK builds (`android-apk-debug`, effective instance `mac_mini_m2`).

**Phase C: macOS `Aquarium.app`.** Its own bundle id, name and icon; the aquarium-only `cd.iff` inside the bundle;
keyboard and gamepad profile (arrows, B/C, A dart). First prove the bundle path on Linux (`wf_game` in a directory with
only that `cd.iff`, no `-L`), then add a CI step that launches the `.app` **without `-L`** and checks the frame against
the Linux reference, then one interactive session over Codemagic's SSH/VNC (the user ticks "Enable SSH/VNC access" on
the build page; keystrokes work through `vncdotool`, pointer and ⌘ do not, see `docs/howto/macos-vnc-session.md`).

**Phase D: iOS aquarium app.** Its own bundle id and name; the aquarium-only `cd.iff`; the **touch profile**
(`task aquarium-touch-level`: a D-pad plus A and B). CI boots iPhone and iPad simulators, installs, launches, and
captures screenshots. The touch profile has never run on real touch input, so simulator taps are the only evidence
available here. The iOS touch layer (iOS plan § Phase 3) is written and unit-tested on Linux but has not been run in a
simulator. Its scripted taps (`SIMCTL_CHILD_WF_TOUCH_SCRIPT`) are the planned evidence.

**Phase E: Chromecast.** The Android app for the aquarium, gamepad profile, sideloaded with `adb` over the network; the
only manual step is enabling Network debugging on the device and giving its IP. Details in the sub-plan.

**Visible surface:** none new beyond each app's icon or TV banner. The apps show the level frame already mocked up in the
[aquarium plan](2026-09-30-aquarium-level.md); icons and banners are generated from real captures inside the sub-plans,
so there is no mockup bundle here.

**Cost:** no money inside the free tier. Estimate of Mac-minutes: macOS builds about 3 min each, iOS about 10–25 min per
full run and about 2 min per configure failure, Android about 10–30 min, one interactive macOS session about 35–60 min:
roughly 150–250 min in total against the 500 min pool. Stop and ask before crossing 400 (the standing budget rule).
Overage, if billing were enabled, is $0.095/min on M2 machines (unverified whether billing is enabled).
Free minutes apply to **M2 machines only** (M4 is charged), so every workflow stays on `mac_mini_m2`.

**Time zone:** Codemagic does not say which zone the 1st rolls over in. Plan Mac-minute work to finish before
04:00 on 2026‑10‑01 in UTC+7 (the earliest plausible rollover, a Helsinki midnight); later work simply draws on the October pool.

## Out of scope

- **Real iPhone or iPad hardware:** needs Apple signing and provisioning; TestFlight and the App Store as well. Only
  simulators here.
- **Play Store submission** and any distribution beyond `adb` sideload.
- **Sound** on any platform (the audio device is real, `audio: miniaudio v0.11.25 ready` on the Chromecast HD, but the apps bundle no sounds or music and nobody has listened on a TV; see the "Audio assets from IFF" and "Sound effects without Lua" items in `TODO.md`).
- **Steering the fish with only a TV remote** (a D-pad and OK, no B, C or A). The gamepad profile is the target.
- **Changing `WORLD_SCALE`** or the engine's fixed limits (decided 2026‑09‑30).
- **macOS close paths** (⌘Q, red button, Retina, `-fullscreen`): stay under the macOS Metal renderer item in `TODO.md`.
- **Restoring texture alpha** (translucent front pane): its own `TODO.md` item.

## Verification

Numbered, runnable steps. Each stays **PENDING** until run; results are pasted under the step with PASS or FAIL.

1. **macOS baseline.** Run `macos-desktop-debug` on the fixed commit. Expected: exit 0; "Compare deterministic capture with Linux reference" PASS (0 px beyond tolerance 3); the aquarium step prints `AQUARIUM PARITY: MATCH` or `DIFFERS` with its counts. **PASS** on build `6abd118f026528c4b225b7bd` (commit `82eb561d`, 3.2 min): snowgoons `exact=306702/307200`, 0 px beyond tolerance 3, `PASS`; **aquarium** `exact=306865/307200`, histogram `{0: 306865, 1: 335}`, 0 px beyond tolerance 3, `PASS`, and the frame is the aquarium. Metal already renders the aquarium as Linux GL does.
2. **Reference freshness guard.** `python3 -m pytest tests/test_renderer_references_fresh.py tests/test_codemagic_aquarium_parity.py -q`. Expected: all pass on Linux; the guard fails when the old snowgoons reference is put back. Done on 2026‑09‑30: 13 passed, and the guard failed on the old reference.
3. **iOS baseline.** `ios-simulator-debug` on iPhone **and** iPad simulators. Expected: configure, build, install and launch succeed; each screenshot is non-blank; the log artifact is present. **PASS** on build `6abd4a709ee70f86b0ffeff6` (branch `ios-render`, commit `0ebfd2ae`, 8.7 min), with a stricter check than the one written here. Each device must be alive at 20 s, and the centre crop must have more than 50 colours. Results: `IOS IPHONE: OK` (`centre_colours=306`) and `IOS IPAD: OK` (`273`). Both screenshots show the bundled level drawn by Metal: platforms, player and crates. The earlier `IOS IPAD: OK` on `6abd3f6b` was a false positive (a solid clear colour between letterbox bars). Build `6abd4f31103ed7df74f88df3` repeated both OK lines. Its informational aquarium pass added `IOS AQUARIUM IPHONE: OK` (`1038`) and `IOS AQUARIUM IPAD: OK` (`891`). `ios-aquarium-iphone.png` and `ios-aquarium-ipad.png` show the tank, fish, anemone and sand. The simulator runs silent: audio init is skipped there, see [iOS port plan](2026-04-21-ios-port-codemagic.md).
4. **Android baseline.** `android-apk-debug`. Expected: build succeeds and the APK artifact is published. **PASS** ([build 6abd1529](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd1529669c35dd0f161d7a), 18.2 min on the fixed branch; aquarium app [6abd1c20](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd1c20874cdae673caf7ae), 3.4 min; multi-ABI build [29889afc](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd5d72ecb4a764dec72514), 3.5 min; all green).
5. **Aquarium `cd.iff` on Linux.** In a directory holding only the aquarium `cd.iff`, run `engine/wf_game --frame-step-smoke=30 --cycles=1 -rate20 --capture-frame=20=<png>` with no `-L`. Expected: the PNG shows the aquarium. **PENDING**.
6. **macOS `Aquarium.app`.** The bundle contains the aquarium `cd.iff` and nothing else level-specific; CI launches it without `-L`; the frame is compared with the Linux reference; one interactive session moves the fish with the arrow keys. **PENDING**.
7. **iOS aquarium app.** iPhone and iPad simulator screenshots show the aquarium; injected touch on the D-pad moves the fish. **PARTIAL:** the aquarium renders in the iPhone and iPad simulators through the screenshot-only variant ([CI run](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6abd5ab2f1419867777e7c1b); the iPhone shot is rotated, the app is landscape-only). Touch code merged and the build stays green (`1ad80acc`); injected taps not yet run. A separate iOS aquarium app is not built.
8. **Chromecast.** Install and launch on the device with the sub-plan's script; screenshot shows the aquarium; a gamepad moves the fish; frame time recorded. **PASS on a real Chromecast HD** (2026‑10‑01 02:15 Bangkok = 2026‑09‑30 19:15 UTC): installed, launched in 1.1 s, alive after 30 s, no crash lines, EGL up; the screenshot shows the aquarium; the D-pad held RIGHT then UP moved the fish ((−1.600, 2.400) → (−0.725, 2.526)); the debug APK draws at about 0.4 s per frame. Gamepad and a release-build frame rate remain. Evidence: `~/tmp/android-device-run/aquarium-20260930T191435Z/`.
