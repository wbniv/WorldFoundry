# Investigation: Mobile port — Android and iOS

**Date:** 2026-04-14
**Status:** Deferred — plan captured for future work, not scheduled.
**Scope:** Android (arm64, arm32 secondary) and iOS (arm64 only). No other mobile OS considered — iPad is a size profile of iOS; everything else is rounding error.

## Context

WF today is a Linux-only desktop build: `wftools/wf_engine/build_game.sh` compiles with `-DWF_TARGET_LINUX -D__LINUX__ -DRENDERER_GL` and links against system `GL`, `GLU`, `X11`, and `lua5.4`. The codebase carries `__LINUX__` / `__WIN__` / `__PSX__` platform defines and a `wfsource/source/hal/` abstraction with a `hal/linux/` subdir, but no current code paths target mobile. Vendored libraries (wasm3, quickjs, jerryscript) are already portable to mobile; Lua is system-linked today and would need vendoring.

The exploration's key finding: **the engine's portability story is uneven**. Input, HAL, and the build system are cleanly isolated and cheap to port. Graphics is the heavy item — `wfsource/source/gfx/glpipeline/*.cc` calls `glBegin`/`glEnd` immediate-mode directly, with no backend abstraction, and immediate mode does not exist on any mobile API (GLES 2+, Metal, or Vulkan). The main loop and windowing are X11-specific and synchronous; mobile requires OS-driven event callbacks and lifecycle hooks that the current loop does not have.

Intended outcome: `WF_TARGET=android` and `WF_TARGET=ios` build flavours that produce, respectively, an AAB/APK and an IPA that runs snowgoons on-device, with touch input mapped to the existing joystick bitmask, assets loaded from the platform's bundle, and correct suspend/resume behaviour. Not a shipping product — a proof-of-viability that makes every subsequent mobile decision concrete.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Target set | **Android arm64 + iOS arm64** (v1). arm32 Android as a stretch. | arm64 is ≥99% of active devices on both platforms. arm32 Android costs extra toolchain setup for a shrinking minority. |
| Build system | **Migrate `build_game.sh` → CMake** | Android NDK uses CMake natively; Xcode can consume CMake via project generation or directly via CMake's Xcode generator. Keeps one source of truth. Preserves the existing env-var feature-flag surface (`WF_ENABLE_FENNEL`, `WF_JS_ENGINE`, `WF_WASM_ENGINE`, `WF_PHYSICS_ENGINE`). |
| Graphics backend (Android) | **OpenGL ES 3.0** (primary), Vulkan as a follow-up | GLES 3.0 is universally supported, closest translation from current fixed-function GL, lowest effort. Vulkan doubles the porting cost for a v1 with no benchmark to justify it. |
| Graphics backend (iOS) | **Metal via MoltenVK shim**, or **native Metal** if shader-translation pain forces it | iOS removed OpenGL ES from v12+. MoltenVK lets one Vulkan path target both iOS (via Metal) and Android later. Alternative: write a thin Metal backend; revisit once the GLES path exists and we can measure. |
| Immediate-mode → VBO rewrite | **Mandatory for v1** | `glBegin`/`glEnd` is gone in all mobile APIs. Not a "nice cleanup" — a hard blocker. Ship this work as a retrofit on the Linux build first (GLES 3.0 core-profile also runs on Linux), *then* port. |
| Input | **Touch → virtual joystick bitmask** | Existing input layer (`hal/linux/input.cc`) maps X11 keys to `EJ_BUTTONF_*` bits. Mobile layer replaces the X11 front-end with touch hit-testing of an on-screen dpad + buttons, emitting the same bitmask. Zero changes below the HAL seam. |
| Windowing + lifecycle | **Android: `NativeActivity` via `android_native_app_glue`. iOS: `UIViewController` + `CAMetalLayer` (or `CAEAGLLayer` if GLES)** | Standard patterns; well-documented. Game main loop becomes a callback the OS drives (`onFrame` / `CADisplayLink`), replacing X11's `for(;;)` pump. |
| Audio | **Skip in v1** | WF has no working audio today (`audio/audio.cc` is empty). Porting "no audio" to mobile is free. Pick a backend when audio becomes a thing (`OpenAL Soft` is portable; native `AudioTrack` / `AVAudioEngine` is lower-level but first-party). |
| Asset delivery | **APK/IPA bundle + lazy copy to app-private dir on first launch** (if mutating I/O is needed) | Android `AAssetManager` and iOS `NSBundle` both expose read-only asset access; redirect `hal/dfhd.cc` through an asset shim. If WF ever writes back to asset paths (savegames, patched levels), those writes go to `Context.getFilesDir()` / `NSDocumentDirectory`. |
| Lua | **Vendor Lua 5.4 source** into `wftools/vendor/lua-5.4.x/` | Linux relies on `-llua5.4` system package; mobile has no such thing. Static-link the vendored copy. Lua is small (~200 KB stripped) and already builds portably. Linux build switches to the vendored copy for parity — remove a system dependency across the board, not just on mobile. |
| Scripting engines | **All current engines (Lua, Fennel, QuickJS, JerryScript, wasm3) included unchanged** | All five are pure-C or portable-C++ and build on iOS/Android without modification. Verified via vendor tree inspection (`platforms/android/` in wasm3, `__ANDROID__` handling in quickjs's cutils.h, etc.). No mobile-specific engine work. |
| Physics (Jolt) | **Works as-is** when the Jolt integration plan has landed | Jolt supports arm64 natively with NEON SIMD. No mobile-specific work beyond the CMake target. |
| Code signing / distribution | **Dev-build via sideload only in v1** | Android: debug APK, sideload. iOS: developer-profile signing, install via Xcode on a tethered device. App Store / Play Store distribution is a separate concern once there's a product to ship. |
| Screen size / orientation | **Landscape only. Single reference resolution at launch (e.g., 1920×1080), letterbox everything else** | Don't do responsive UI in a proof-of-viability. Landscape matches the joystick-driven control scheme. |

## Cost-to-port: honest per-area assessment

Short summaries from exploration; port cost is roughly proportional to area size and unfamiliarity.

| Area | Current state | Port cost |
|------|---------------|-----------|
| **Graphics pipeline** (`gfx/glpipeline/*.cc`) | Direct `glBegin`/`glEnd` immediate mode, ~800 LOC across 8 renderer files | **Heavy.** Rewrite to VBO + shader-based batches. Ship first on Linux GLES 3.0 core-profile to keep one code path. |
| **Window + main loop** (`gfx/gl/mesa.cc`, `gfx/gl/display.cc`) | X11 + GLX, synchronous `for(;;)` in `RunGameScript` | **Moderate.** Replace with platform-specific shim; invert control so OS drives frames. Add lifecycle hooks (suspend/resume, context loss) the main loop does not have today. |
| **Input** (`hal/linux/input.cc`, `gfx/gl/mesa.cc` event pump) | X11 `XNextEvent` → `EJ_BUTTONF_*` bitmask | **Light.** HAL seam is clean. Write touch-to-bitmask shim per platform; everything below it unchanged. |
| **HAL** (`wfsource/source/hal/`) | Thin — input, timer, platform init, process stub | **Light.** Add `hal/android/`, `hal/ios/` mirroring `hal/linux/`. |
| **Filesystem** (`hal/dfhd.cc`) | POSIX `open()` on loose level files or `cd.iff` | **Moderate.** Redirect through `AAssetManager` / `NSBundle`. Writes land in platform app-private dir. |
| **Audio** (`audio/audio.cc`, `audio/linux/device.cc`) | Empty stubs | **Free for v1** — no code to port. |
| **Build** (`build_game.sh`) | Bash loop calling `g++` per-TU | **Light-moderate.** CMakeLists that preserves the TU list + feature-flag structure. Android uses NDK CMake toolchain; iOS uses CMake's Xcode generator or ExternalProject + xcodebuild. |
| **Vendored libs** (`wftools/vendor/`) | wasm3, quickjs, jerryscript already portable; Lua system-linked | **Light.** Vendor Lua 5.4. Everything else compiles unchanged. |
| **Lifecycle** (no current hooks) | `for(;;)` in `game.cc` ignores OS signals | **Moderate.** Add pause/resume hooks; on GL context loss reload textures/VBOs; save volatile state on suspend. This is new code, not a port. |

Rough total: **a focused engineer-quarter for Android v1, plus ~2 weeks incremental for iOS v1** once Android is working (most work is shared; iOS adds Metal/MoltenVK and Xcode plumbing). Numbers are fuzzy until the graphics rewrite is scoped more precisely.

## Implementation

### Phase 0 — Retire immediate-mode GL on Linux

Goal: Linux build uses GLES 3.0 core-profile (or equivalent desktop GL 3.3 core) via VBOs + shaders. **No mobile work yet.** This is the single biggest piece of mobile-enabling work, and it has value independently — the existing immediate-mode path blocks every modern graphics target, not just mobile.

1. Introduce a thin renderer-backend interface behind `wfsource/source/gfx/renderer.hp`. Don't over-abstract: start with `SubmitBatch(VBO, index, shader, uniforms)`. Two backends over time — `glpipeline_legacy` (current immediate-mode, kept working during transition) and `glpipeline_modern` (VBO-based).
2. Port one renderer TU at a time (`rendgtp.cc` first — the representative shader combo). Validate snowgoons renders identically under the new path via golden-image diff.
3. Once all 8 renderer TUs are ported, retire `glpipeline_legacy` behind a `WF_RENDERER=legacy|modern` switch. Default to modern; keep legacy as a parachute.
4. **Verify:** snowgoons renders identically on Linux under `WF_RENDERER=modern`; frame time parity (or better, given batched draws).

### Phase 1 — CMake build, vendor Lua, keep Linux default

Goal: `cmake -B build && cmake --build build` produces the same `wf_game` as `build_game.sh` does today. No mobile code yet; this removes the bash-script dependency and puts the build on a foundation that NDK / Xcode can consume.

1. Write `CMakeLists.txt` at the repo root and in `wftools/wf_engine/` mirroring `build_game.sh`'s TU list and feature flags.
2. Vendor Lua 5.4 source into `wftools/vendor/lua-5.4.x/`; link statically. Drop the `-llua5.4` system dep from the Linux build.
3. Keep `build_game.sh` working during the transition; retire it once CMake parity is verified.
4. **Verify:** binary-identical (modulo timestamps) output between `build_game.sh` and CMake build. All existing feature flags (`WF_ENABLE_FENNEL`, `WF_JS_ENGINE`, `WF_WASM_ENGINE`, future `WF_PHYSICS_ENGINE`) work identically.

### Phase 2 — HAL, filesystem, and lifecycle scaffolding

Goal: Introduce the hooks mobile platforms need, without adding platform-specific code yet. Linux build continues to work.

1. Add suspend/resume hooks to the game loop (`wfsource/source/game/game.cc` around the `for(;;)` in `RunGameScript`). Linux no-ops them; mobile will call into them from the OS callback.
2. Factor `hal/dfhd.cc` through an asset-accessor interface. Linux impl: open files from working dir (today's behaviour). Mobile impls: bundle-backed.
3. Add GL context loss / restore hooks: texture/VBO re-upload after a backgrounding-induced context teardown. Android GLES can drop contexts; iOS Metal doesn't, but the hook is uniform.
4. **Verify:** Linux build unchanged; suspend/resume callbacks exist but do nothing meaningful on Linux.

### Phase 3 — Android port

Goal: An APK that launches, runs snowgoons, takes touch input, handles background/foreground transitions without crashing.

1. Add `hal/android/` with platform init, input, filesystem (`AAssetManager`), and timer implementations.
2. Write the `NativeActivity` entry point (`android_native_app_glue`-style); map the OS's `onStart`/`onPause`/`onResume`/`onStop` to Phase 2's hooks.
3. CMake NDK toolchain build (arm64-v8a): compile engine + vendored libs + Jolt + scripting engines into `libwf_game.so`; Gradle packages into AAB/APK.
4. Touch shim: on-screen dpad and 4–6 buttons; hit-test each `MotionEvent`; emit `EJ_BUTTONF_*` bitmask to the existing input path.
5. Asset pipeline: bake `cd.iff` (or loose levels) into `assets/` in the APK; redirect Phase 2's asset accessor to `AAssetManager_open`.
6. GL renderer: hook Phase 0's `glpipeline_modern` to GLES 3.0 context from `EGLContext`.
7. **Verify:** sideload APK to a device, launch, play snowgoons. Pause by pressing Home; resume; game continues. No crash on orientation change (lock to landscape as first defence).

### Phase 4 — iOS port

Goal: An IPA that runs snowgoons on a tethered iPhone. Can be sideloaded via Xcode with a developer profile.

1. Add `hal/ios/` mirroring `hal/android/` — platform init, input, filesystem (`NSBundle`), timer.
2. Xcode project wrapping the CMake build (use CMake's Xcode generator; the `.app` bundle is a thin Swift/Obj-C shell over `libwf_game.a`).
3. `UIViewController` with `CAMetalLayer` (if going native Metal) or `CAEAGLLayer` (if GLES-via-MoltenVK). Pick one in Phase 4a; defer the cross-platform Vulkan decision.
4. Touch shim same as Android; OS event → bitmask.
5. Asset pipeline: `NSBundle mainBundle` + app-private `Documents/` for writes.
6. Graphics: the unknown. If GLES-via-MoltenVK works out-of-the-box, ship it. If shader translation fails, write the Metal backend (likely smaller-scope than feared — WF's shader needs are modest).
7. **Verify:** install via Xcode, play snowgoons on a physical iPhone. Suspend/resume behaviour parity with Android.

### Phase 5 — Second-level test + performance pass

1. Both platforms run a non-snowgoons level (validates that level-load path and asset redirection aren't snowgoons-hard-coded anywhere).
2. Profile: frame time, GPU time, memory use. Mobile CPUs are ~10× slower than a dev laptop; GPUs vary wildly. Identify top hotspots with `simpleperf` (Android) and Xcode Instruments (iOS).
3. Publish size matrix: APK size, IPA size, RSS during play. Compare against the Linux build's equivalents.

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/gfx/glpipeline/*.cc` (8 files) | Phase 0 — rewrite each to the VBO/shader backend |
| `wfsource/source/gfx/renderer.hp` | Phase 0 — introduce thin backend interface |
| `wfsource/source/gfx/gl/mesa.cc` | Phase 3/4 — X11/GLX split out to `hal/linux/`, mobile equivalents added |
| `wfsource/source/gfx/gl/display.cc` | Phase 3/4 — `glXSwapBuffers` → platform swap |
| `wfsource/source/hal/dfhd.cc` | Phase 2 — redirect through asset accessor interface |
| `wfsource/source/hal/android/`, `wfsource/source/hal/ios/` | Phase 3/4 — new platform HAL impls |
| `wfsource/source/game/game.cc` (`RunGameScript`, `RunLevel`) | Phase 2 — add suspend/resume hooks |
| `wftools/wf_engine/build_game.sh` | Phase 1 — deprecate in favour of CMake |
| `CMakeLists.txt` (root + subdirs) | Phase 1 — new |
| `wftools/vendor/lua-5.4.x/` | Phase 1 — new (vendored Lua) |
| Android Gradle / `AndroidManifest.xml` | Phase 3 — new |
| Xcode project wrapper | Phase 4 — new |

## Reuses

- HAL pattern (`hal/linux/` → `hal/android/`, `hal/ios/`) — no new abstraction, just new subdirs.
- Input bitmask (`EJ_BUTTONF_*`) — all platforms emit into it; scripts and game logic unchanged.
- Existing feature-flag env vars (`WF_ENABLE_FENNEL`, `WF_JS_ENGINE`, `WF_WASM_ENGINE`, `WF_PHYSICS_ENGINE`) survive the CMake migration unchanged.
- Vendored scripting engines — no mobile-specific changes.
- Jolt Physics — arm64 + NEON already supported upstream.

## Verification

1. **Linux parity at each phase.** Phase 0 — snowgoons golden-image match under `WF_RENDERER=modern`. Phase 1 — CMake build byte-equivalent to `build_game.sh`. Phase 2 — Linux build unaffected by new hooks.
2. **Android launch + play.** Phase 3 — APK installs on an arm64 device, snowgoons runs, suspend/resume works.
3. **iOS launch + play.** Phase 4 — IPA installs via Xcode on an iPhone, snowgoons runs, suspend/resume works.
4. **Second-level smoke test.** Phase 5 — non-snowgoons level loads and plays on both.
5. **Size matrix.** APK (arm64), IPA (arm64), plus Linux stripped binary side-by-side. Highlights platform overhead (NDK runtime, Objective-C runtime, etc.).
6. **Lifecycle torture.** Force-background the app 10× in a row; confirm no GL-context leaks, no save-state corruption, no crash.

## Follow-ups (out of scope)

1. **App Store / Play Store distribution.** Signing, metadata, review process. Separate plan when there's a product to ship.
2. **arm32 Android.** Build config addition; ~2 days of work; defer until data shows a user base that needs it.
3. **Vulkan backend.** After GLES 3.0 path proves out, a Vulkan backend unifies Android + iOS (via MoltenVK) at the cost of a bigger port.
4. **Audio.** OpenAL Soft is the cheap portable choice; platform-native is lower-latency. Own plan when audio is added.
5. **Haptics / gyro / camera / mic.** All possible on both platforms; none are in scope for a proof-of-viability.
6. **Orientation / responsive layout.** v1 is landscape-locked letterboxed; real device-size handling is a UI redesign.
7. **Backgrounded gameplay (push notifications, headless sim).** Most mobile games don't do this; note the absence.
8. **Minimum OS version.** Android API level and iOS version to pin; affects GLES/Metal availability and the NDK/Xcode version. Decide when a dev device is in hand.

## Open questions

- **iOS graphics backend: MoltenVK or native Metal?** MoltenVK is one code path for Android+iOS; native Metal is fewer moving parts per platform but doubles backend work. Defer until Phase 0's Linux VBO rewrite exposes how much of WF's rendering is shader-complexity-bound vs geometry-bound. Geometry-bound ⇒ MoltenVK is fine; shader-bound ⇒ native Metal may be simpler than making SPIR-V cross-compile happy.
- **Input: on-screen controls only, or also MFi / Android gamepad?** The existing `EJ_BUTTONF_*` bitmask naturally maps to physical gamepads, and plenty of mobile users pair controllers. Plumbing it is one-day-of-work per platform and avoids the "mobile games feel bad on touch" trap for any user who brings a controller. Lean toward "yes, support both" but costs a small amount of extra scope in Phase 3/4.
- **Asset bundling: loose files or `cd.iff`?** Both work on mobile. Loose files make hot-reload and per-level patching easy; `cd.iff` is one asset. Decide based on whether the dev workflow wants iterate-without-rebuild on-device.
- **Lua vendoring affects Linux too.** Vendoring Lua for mobile is a hard requirement; doing it only for mobile creates two Lua versions. Decision: vendor for all platforms, drop the Linux `-llua5.4` system dep. Mentioned in Phase 1; calling out here that this is a Linux-visible change, not mobile-only.
- **Frame-rate target.** Desktop WF doesn't pin a frame rate (see the load-bearing variable-tick-rate constraint). Mobile OSes strongly prefer 60 Hz (or 120 Hz on newer iPhones). The existing variable-`dt` handling should ride through, but validate on-device — power draw may force a 30 Hz cap on lower-end Android that the tick-rate code has never seen.
