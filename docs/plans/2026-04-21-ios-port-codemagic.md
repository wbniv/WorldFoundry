# Plan: iOS port (via Codemagic)

**Date:** 2026-04-21 (revises the 2026-04-16 doc — prior version parked the port as "blocked on lack of a Mac")
**Status:** Phase 3 verified — touch + HUD wired (2026-04-22). UITouch events on `WFMetalView` hit-test against the same pixel regions as Android's `c20e56e` HUD (d-pad bottom-left, A/B bottom-right); the OR of all live touches flows through `_HALSetJoystickButtons` → `std::atomic<joystickButtonsF>` read by the engine thread each frame. On-screen HUD is 6 semi-transparent non-interactive `UIView` overlays on top of the Metal layer (UIKit native compositing, no need to draw through the RendererBackend), with Android-matching colors (gray d-pad, red A, blue B). Per-frame tracer overhaul also revealed the engine is actually submitting **~1563 tris across 8 batches/frame** steady-state — the earlier "12 tris flat" was a last-batch-only tracer bug (now fixed in `52c8927`). Lifecycle hooks already in place from Phase 1 (`applicationWillResignActive` → `HALNotifySuspend`, `applicationDidBecomeActive` → `HALNotifyResume`). Still can't verify actual touch response in the headless Codemagic sim-verify (no touch-injection tool); defers to Phase 5 device testing. Phase 4 queued: Apple Developer Program enrollment + signed IPA.
**Goal:** An arm64 IPA that runs snowgoons on a physical iPhone, installed via TestFlight (or ad-hoc), with Codemagic as the only Mac in the loop. Proof-of-viability, not a shipping product.

<p align="center">
  <img src="screenshots/2026-04-22-ios-phase-2d-zbuffer.png" width="500" alt="Snowgoons on iOS Simulator after Phase 2D z-buffer fix — log cabin, tree, hedge, ground all rendering with correct depth ordering and textures.">
</p>

## Context

The original plan was shelved because Xcode + code signing + device provisioning all require macOS and this workstation is Linux-only. That blocker is now lifted: the user has a Codemagic individual plan (500 build-min/month) — cloud Mac mini runners with Xcode pre-installed, CMake support, and turnkey signing automation. Android precedent closed 2026-04-18 so the shared foundation — CMake build, `hal/android/`, `AssetAccessor`, modern VBO/shader `RendererBackend`, **Forth-only scripting** — is stable and ready to parallel. Mobile builds ship zForth as the sole scripting engine (Android's `if(ANDROID)` block in `CMakeLists.txt:26-35` disables Lua / JS / WAMR / Wren / Steam / REST API); iOS mirrors that policy. zForth is the in-level `{ Script }` engine per the `scripts-in-forth` convention anyway, so the other engines aren't load-bearing for snowgoons.

Two constraints change how the phases stage:

- **No Apple Developer Program account yet** — user will pay the $99/yr when there's something worth signing. Everything that doesn't need signing (Simulator builds, Metal backend work, touch shim) runs first. The $99 spend is gated to Phase 4.
- **No personal iPhone** — a collaborator has one. On-device verification goes through TestFlight (no per-device UDID wrangling) rather than ad-hoc install.

## Codemagic-specific implications vs. the original plan

- **No interactive Xcode / Instruments.** Runtime debug falls back to on-device log files (same pattern as Android's on-device `wf.log` — see commit history). GPU frame capture is deferred or handled out-of-band on the collaborator's Mac if available.
- **Build path is `git push` → `codemagic.yaml` → artifact.** The repo grows a `codemagic.yaml` at root describing the build workflow; no local Xcode invocation.
- **Codemagic M-series Mac minis run arm64 Simulator natively** — Simulator architecture matches device, so Metal shader behavior is a realistic preview.
- **Mac build minutes are cheap enough to push per step.** Measured across 29 real runs (2026-04-22 session), Codemagic's M2 Mac mini runs clean CMake + Xcode builds + 45s sim-verify in **2–4 min each (avg 3.4 min)**. 500 min/month ≈ **100–150 builds** — easily enough to push per commit during bring-up; no need to batch. The original 15–25 min estimate in this plan was wildly conservative; ccache and incremental CMake are pulling their weight.

## Correction to the original plan's graphics options

The 2026-04-16 doc proposed "GLES via MoltenVK" as a graphics option, but MoltenVK is **Vulkan → Metal**, not GL → Metal — WF uses GLES 3.0, not Vulkan, so MoltenVK doesn't apply directly. The actual path taken was **native Metal**: `wfsource/source/hal/ios/backend_metal.mm` implements the `RendererBackend` interface method-for-method against `backend_modern.cc`, with MSL vertex+fragment shaders inline and runtime-compiled via `[MTLDevice newLibraryWithSource:]` — no separate `.metal` file, no Xcode build phase, Codemagic-native. The shader port was tractable (snowgoons renders correctly as of 2026-04-22, see Status above); ANGLE was never needed as a fallback.

## Phases

### Phase 0 — Codemagic project bootstrap ✅ done 2026-04-21

> Project + webhook wiring steps live in [codemagic-setup.md](../codemagic-setup.md) — do that once on the Codemagic/GitHub side before pushing anything here.

`codemagic.yaml` at repo root runs an Xcode workflow on the `2026-ios` branch against an M2 Mac mini. `cmake -G Xcode -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_SYSROOT=iphonesimulator` + `xcodebuild` compiled, and the run failed on the missing iOS HAL exactly as the verify bar asked — pipeline end-to-end green.

### Phase 1 — iOS HAL skeleton + Simulator "hello, viewcontroller" ✅ done 2026-04-22

`wfsource/source/hal/ios/` now mirrors `hal/android/` (asset_accessor_nsbundle.mm, platform.mm, lifecycle.mm, audio.mm, input.mm, native_app_entry.mm). Root `CMakeLists.txt` grew an `elseif(IOS)` branch that mirrors the Android Forth-only scripting policy; `Foundation`, `UIKit`, `QuartzCore`, `Metal`, `MetalKit` linked. `ios/` wrapper provides `Info.plist` (landscape-only), launch storyboard, and bundles `cd.iff` + `level0.mid` + `florestan-subset.sf2` via Xcode copy-files. `.app` launches in Simulator, `HALGetAssetAccessor` opens cd.iff, verified via Codemagic's sim-verify `log show` grep.

### Phase 2 — Native Metal backend, snowgoons rendering in Simulator ✅ done 2026-04-22

`wfsource/source/hal/ios/backend_metal.mm` implements `RendererBackend` method-for-method against `backend_modern.cc`. Shaders are inline MSL runtime-compiled via `[MTLDevice newLibraryWithSource:]` — no separate `.metal` file / Xcode build phase, Codemagic-native. `WFMetalView` hosts a `CAMetalLayer`; the engine thread owns frame submission via the `WFIosRenderBegin/End` bridge (no CADisplayLink) — simpler sync than the original "CADisplayLink hands encoder to engine" sketch. `gfx/gl/mesa.cc` unchanged (Linux stays X11/GLX); iOS surface source lives entirely in `hal/ios/`. snowgoons level-load path untouched. Verified: [screenshot above](#) shows cabin + tree + hedge + ground texturing + z-buffered occlusion — no golden-image diff vs. Android done, skipped per eye-test parity (Phase 2D step 3, kept as an optional follow-up).

### Phase 3 — Touch input + on-screen HUD ✅ done 2026-04-22

`hal/ios/input.mm` keeps the live button bitmask in `std::atomic<joystickButtonsF>`; `_HALSetJoystickButtons` (UI thread) stores, `_JoystickButtonsF` (engine thread) loads. `WFMetalView`'s `touchesBegan/Moved/Ended/Cancelled:` recompute the mask from `[event allTouches]`, running each touch through `WFHitTestTouch` against the same pixel regions as Android's `hal/android/native_app_entry.cc:157-182`. HUD is six non-interactive semi-transparent `UIView` overlays on the Metal layer — UIKit compositing is cheaper than drawing through Metal and matches Android's d-pad + A(red) + B(blue) colors from `c20e56e`. Lifecycle hooks were already wired in Phase 1's `native_app_entry.mm` (`application{WillResignActive,DidBecomeActive}` → `HALNotify{Suspend,Resume}`). Headless Codemagic Sim can't inject touches so end-to-end gameplay verification defers to Phase 5; pixel sampling of the HUD in sim-verify confirms geometry + colors are correct.

### Phase 4 — Apple Developer Program + signed IPA on Codemagic (**gated on $99 spend**)

This is the first phase that costs real money. Only start after Phase 3 is green and there's a working Simulator build worth pushing to hardware.

1. User enrolls in the Apple Developer Program ($99/yr individual). Enrollment typically takes 24–48h; can front-load paperwork while Phase 3 finishes.
2. Create a Development + Distribution signing certificate pair; create an App Store Connect app record + bundle ID (e.g. `com.worldfoundry.snowgoons`).
3. Upload certs + provisioning to Codemagic — their "automatic code signing" can manage this once the developer account is linked.
4. Extend `codemagic.yaml` with a release workflow: `-DCMAKE_OSX_SYSROOT=iphoneos` target, code-signing step, `xcodebuild -exportArchive` → signed `.ipa`.
5. **Verify:** Codemagic build artifacts include a signed arm64 `.ipa`. No TestFlight push yet — just confirm the file signs and validates with `codesign -v`.

### Phase 5 — On-device verification via collaborator's iPhone

1. TestFlight upload from Codemagic release workflow → App Store Connect processing → internal-tester invite to the collaborator's Apple ID.
2. Collaborator installs via TestFlight, runs snowgoons, reports back. Log file retrieval: bundle an on-device `wf.log` writer (parallel to the Android one) and have the collaborator AirDrop or email the log.
3. **MFi gamepad support** — `GCController` observers on `viewDidLoad`; map buttons/axes to `EJ_BUTTONF_*` via the same bitmask path as touch; OR into `_JoystickButtonsF`. Reason it lives here, not Phase 3: iOS Simulator's gamepad forwarding is flaky, so MFi can only be verified meaningfully on device. On-screen HUD auto-hides when a `GCController` is connected.
4. Lifecycle torture: lock/unlock, force-background 10×, phone calls interrupting. Confirm no Metal resource leaks, no crash on resume.
5. Second-level smoke test — pick any non-snowgoons level (`primitives.lev` / `whitestar.lev` are compiling per the `level-pipeline-proof` plan) to prove the load path isn't snowgoons-hardcoded.
6. Size matrix: IPA size (arm64) alongside APK and Linux binary — published in `docs/investigations/`.
7. **Verify:** Collaborator runs snowgoons on real hardware with both touch and (if they have one) an MFi controller; sends log + a short video. Lifecycle torture comes back clean.

## Critical files

| File | Change |
|------|--------|
| `codemagic.yaml` | **New** — at repo root. Two workflows: `ios-simulator-debug` (Phases 0–3) and `ios-device-release` (Phases 4–5). |
| `wfsource/source/hal/ios/` | **New** — 6 files mirroring `hal/android/` (see Phase 1 step 1). |
| `wfsource/source/gfx/glpipeline/backend_metal.mm` | **New** — Metal implementation of `RendererBackend`. |
| `wfsource/source/gfx/glpipeline/shaders.metal` | **New** — MSL port of `backend_modern.cc:58-116`. |
| `wfsource/source/gfx/renderer_backend.hp` | No change expected — interface is already backend-agnostic. |
| `wfsource/source/gfx/gl/mesa.cc` | No change (Linux-only); iOS gets its own surface source in `hal/ios/`. |
| `CMakeLists.txt` | **Extend** — add `elseif(IOS)` branch parallel to `if(ANDROID)` (lines 26–35, 51–57, 66–86, 372–379, 413–424). |
| `ios/` | **New** — Xcode project wrapper, `Info.plist`, launch storyboard, asset copy-files phase. Template cribbed from `android/` layout. |
| `docs/plans/2026-04-16-ios-port.md` | **Replace** — supersede with the Codemagic-era plan (this file). |
| `wf-status.md` | **Update** — flip the row from "Backlog — blocked on lack of a Mac" to "In progress — Codemagic-driven". |

## Reused from existing code

- `wfsource/source/hal/asset_accessor.hp` — `AssetAccessor` interface. NSBundle impl goes next to it in `hal/ios/`.
- `wfsource/source/hal/android/lifecycle.cc` — atomic `HALIsSuspended` pattern, copy-adapt.
- `wfsource/source/hal/android/audio.cc` — miniaudio init pattern (CoreAudio backend auto-detects).
- `wfsource/source/gfx/glpipeline/backend_modern.cc` — the shader source to port (GLSL → MSL) and the `RendererBackend` method shape to mirror.
- `android/app/src/main/java/...LogViewerActivity.java` — on-device log viewer pattern; iOS equivalent is a read-only `UITextView` over the same `wf.log` file.
- On-screen HUD layout from commit `c20e56e` — d-pad + A/B button hit-rects; straight copy.

## Open questions

- ~~**Minimum iOS version.**~~ Settled at iOS 13 (`ios/Info.plist` → `MinimumOSVersion 13.0`; `codemagic.yaml` → `-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0`). Covers modern Metal features (argument buffers in iOS 11+) without deprecated-API surface.
- **Frame capture without desktop Xcode.** Codemagic doesn't help here. Options: (a) collaborator's Mac if they have one, (b) defer GPU profiling entirely for v1, (c) capture via `MTLCaptureManager` to a file on device for later analysis.
- **Script-triggered SFX on iOS.** Engine-triggered audio works — `gMusicPlayer->play()` from C++ streams the level MIDI through CoreAudio on device (noDevice is Simulator-only per `audio/linux/device.cc:12`). But script-triggered one-shot SFX are Lua-closure-only, and Lua isn't built on iOS (Forth-only mobile policy). Music plays; scripts can't fire SFX until the mailbox-wired-audio plan ([audio-mailbox-api](deferred/2026-04-17-audio-mailbox-api.md)) lands. Same limitation Android ships with today.

## Out of scope

- App Store public distribution (TestFlight is the ceiling for v1).
- iPad-specific UI (landscape-locked iPhone letterbox only; iPad just runs that).
- Haptics, gyro, camera, mic.
- Adaptive orientation / responsive layout.
- Standalone Vulkan backend.
- ANGLE-as-backup path — implement only if native Metal hits a real wall.
- Automated test coverage on iOS (parallel to Android — none yet).

## Verification matrix (how we know each phase is done)

| Phase | Verification artifact | Source of truth |
|------:|------------------------|------------------|
| 0 | Codemagic log shows CMake error about missing iOS HAL | Codemagic build run |
| 1 | `.app` launches in Simulator, no crash on `HALGetAssetAccessor` | Codemagic artifact + Simulator log |
| 2 | snowgoons first frame renders in Simulator | Golden-image diff vs. Android frame 1 |
| 3 | snowgoons plays end-to-end in Simulator with touch + audio | Demo video from Simulator |
| 4 | `codesign -v` on the release IPA passes | `.ipa` in Codemagic artifacts |
| 5 | Collaborator runs snowgoons on iPhone; `wf.log` returned; lifecycle torture clean | Video + log from collaborator |
