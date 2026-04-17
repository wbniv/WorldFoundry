# Plan: Android port

**Date:** 2026-04-16
**Status:** Not started
**Goal:** An APK that launches, runs snowgoons on an arm64 Android device, takes touch input, and handles background/foreground transitions without crashing. Proof-of-viability, not a shipping product.

## Scripting engines on Android

**Forth (zForth) only — initially.** All other engines are disabled for the Android build:

```
WF_LUA_ENGINE=none       # requires lua-not-special plan to land first
WF_ENABLE_FENNEL=0       # auto-disabled when Lua is absent
WF_JS_ENGINE=none
WF_WASM_ENGINE=none
WF_ENABLE_WREN=0
WF_REST_API=0
WF_FORTH_ENGINE=zforth   # default, explicit for clarity
```

**Prerequisite:** The [lua-not-special plan](2026-04-16-lua-not-special.md) must land before `WF_LUA_ENGINE=none` is available. Until then, Lua is compiled in unconditionally and the Android build ships Forth + Lua.

This drops ~600 KB from the binary (QuickJS, JerryScript, wasm3/WAMR, Wren, Fennel minifier, cpp-httplib, Lua). zForth is ~4 KB compiled core + the WF bridge; pure portable C, no OS-specific code. If other engines are needed later, they are all portable to arm64 and can be re-enabled — but v1 ships Forth only.

**Note on WAMR if re-enabled later:** `build_game.sh` defaults WAMR to `X86_64`; an Android build would need `WAMR_BUILD_TARGET=AARCH64`.

## Prerequisites (must land first)

These are large enabling workstreams. Each has standalone value on Linux; Android blocks on all three being complete.

1. **Phase 0 — Retire immediate-mode GL (Linux VBO rewrite)**
   `glBegin`/`glEnd` is a hard blocker — it does not exist in GLES 3.0. Rewrite `gfx/glpipeline/*.cc` to VBO + shader batches on Linux first. See details below.

2. **Phase 1 — CMake build + vendor Lua**
   Android NDK consumes CMake natively. Replace `build_game.sh` with `CMakeLists.txt` that reproduces the same build; vendor Lua 5.4 into `engine/vendor/lua-5.4.x/` (no system deps).

3. **Phase 2 — HAL lifecycle + filesystem abstraction**
   Add suspend/resume hooks to the game loop and factor `hal/dfhd.cc` through an asset-accessor interface. Linux no-ops the hooks; Android will call into them.

## Steps

### Phase 0 — Retire immediate-mode GL on Linux

1. Introduce thin renderer-backend interface at `wfsource/source/gfx/renderer.hp`. Start minimal: `SubmitBatch(VBO, index, shader, uniforms)`. Keep `glpipeline_legacy` (current) working during transition.
2. Port one renderer TU at a time — `rendgtp.cc` first (representative shader combo). Validate via golden-image diff against snowgoons.
3. Port remaining 7 renderer TUs. Retire `glpipeline_legacy` behind `WF_RENDERER=legacy|modern`; default modern.
4. **Verify:** snowgoons renders identically on Linux under `WF_RENDERER=modern`; frame time equal or better.

### Phase 1 — CMake build, vendor Lua

1. Write `CMakeLists.txt` at repo root and in `engine/` mirroring `build_game.sh`'s TU list and all feature flags (`WF_ENABLE_FENNEL`, `WF_JS_ENGINE`, `WF_WASM_ENGINE`, `WF_PHYSICS_ENGINE`).
2. Vendor Lua 5.4 source into `engine/vendor/lua-5.4.x/`; link statically. Drop `-llua5.4` system dep on Linux too.
3. Keep `build_game.sh` working until CMake parity is verified; then retire it.
4. **Verify:** CMake output is byte-equivalent to `build_game.sh` output. All feature flags work.

### Phase 2 — HAL lifecycle + filesystem abstraction

1. Add suspend/resume hooks in `wfsource/source/game/game.cc` around the `for(;;)` in `RunGameScript`. Linux no-ops them.
2. Factor `hal/dfhd.cc` through an asset-accessor interface. Linux impl: open files from working dir (today's behaviour).
3. Add GL context loss / restore hooks: texture/VBO re-upload after backgrounding-induced context teardown.
4. **Verify:** Linux build unchanged; hooks exist but are no-ops.

### Phase 3 — Android port

1. Add `hal/android/` — platform init, input, filesystem (`AAssetManager`), timer.
2. Write `NativeActivity` entry point (`android_native_app_glue`-style). Map `onStart`/`onPause`/`onResume`/`onStop` to Phase 2 hooks.
3. CMake NDK toolchain build (arm64-v8a): compile engine + Lua + zForth + Jolt into `libwf_game.so` with the Forth-only flag set above. Add Gradle project + `AndroidManifest.xml`; package into APK.
4. Touch shim: on-screen dpad + 4–6 buttons; hit-test each `MotionEvent`; emit `EJ_BUTTONF_*` bitmask to the existing input path.
5. Asset pipeline: bake `cd.iff` (or loose levels) into `assets/` in APK; redirect Phase 2's asset accessor to `AAssetManager_open`.
6. GL renderer: hook Phase 0's `glpipeline_modern` to GLES 3.0 context from `EGLContext`.
7. **Verify:** sideload APK, launch, play snowgoons. Pause (Home), resume, game continues. No crash on orientation change (landscape-lock as first defence).

### Phase 4 — Second-level smoke test + performance pass

1. Run a non-snowgoons level to confirm level-load path is not snowgoons-hardcoded.
2. Profile with `simpleperf`: frame time, GPU time, RSS. Mobile CPU speed is a real concern — identify top hotspots and measure whether 30 fps is achievable on low-end hardware.
3. Publish size matrix: APK size (arm64) vs Linux stripped binary.
4. Lifecycle torture: force-background 10× in a row, confirm no GL-context leaks, no crash.

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/gfx/glpipeline/*.cc` (8 files) | Phase 0 — rewrite to VBO/shader backend |
| `wfsource/source/gfx/renderer.hp` | Phase 0 — new thin backend interface |
| `wfsource/source/gfx/gl/mesa.cc` | Phase 3 — X11/GLX split out to `hal/linux/`; Android equivalent added |
| `wfsource/source/gfx/gl/display.cc` | Phase 3 — `glXSwapBuffers` → EGL swap |
| `wfsource/source/hal/dfhd.cc` | Phase 2 — redirect through asset accessor |
| `wfsource/source/hal/android/` | Phase 3 — new: platform init, input, filesystem, timer |
| `wfsource/source/game/game.cc` | Phase 2 — add suspend/resume hooks |
| `engine/build_game.sh` | Phase 1 — deprecate in favour of CMake |
| `CMakeLists.txt` (root + subdirs) | Phase 1 — new |
| `engine/vendor/lua-5.4.x/` | Phase 1 — already vendored; confirm NDK build |
| `android/build.gradle`, `AndroidManifest.xml` | Phase 3 — new |

## Open questions

- **Android gamepad support?** `EJ_BUTTONF_*` maps naturally to physical gamepads via Android `InputDevice`. One day of work; out of scope for v1.
- **Asset bundling: `cd.iff`.** Ship the single archive; redirect the asset accessor to open it via `AAssetManager`. Loose-file iteration stays a Linux dev workflow.
- **Performance floor.** Mobile CPUs are slow. The variable-`dt` loop has run at 30 fps before so correctness is not the question; the question is whether the renderer + Jolt + game logic stay above a playable threshold on low-end ARM64. Measure in Phase 4.
- **Minimum Android API level: 21 (Android 5.0 Lollipop).** Settled — arm64-v8a cannot target below API 21 in any NDK version; NDK r26+ also enforces 21 as its floor. GLES 3.0 and NativeActivity are satisfied below that, so nothing is left on the table. Covers ~99.8% of active devices.
- **arm32 stretch goal.** Build config addition, ~2 days; defer until data shows a user base that needs it.

## Out of scope

- iOS (own plan, starts after this ships)
- App Store / Play Store distribution
- Audio (nothing to port — stubs are stubs)
- Haptics, gyro, camera, mic
- Orientation / responsive layout (landscape-locked letterbox only)
- Vulkan backend (GLES 3.0 is the v1 graphics path)
- Additional scripting engines beyond Forth + Lua on Android v1
