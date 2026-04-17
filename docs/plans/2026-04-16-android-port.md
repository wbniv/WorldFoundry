# Plan: Android port

**Date:** 2026-04-16
**Status:** Not started
**Goal:** An APK that launches, runs snowgoons on an arm64 Android device or Google TV (Chromecast with Google TV), takes touch or gamepad input, and handles background/foreground transitions without crashing. Proof-of-viability, not a shipping product.

## Settled decisions

| Decision | Choice |
|----------|--------|
| Scripting engines | Forth (zForth) only — see below |
| Asset bundling | `cd.iff` via `AAssetManager`; loose-file iteration stays Linux-only |
| Minimum API level | 21 (Android 5.0 Lollipop) — arm64 + NDK r26 floor; ~99.8% device coverage |
| Graphics API | GLES 3.0 via EGL |
| Architecture | arm64-v8a only |
| Gamepad support | Yes in v1 — `InputDevice` → `EJ_BUTTONF_*` bitmask alongside touch |
| Google TV / Chromecast | Same APK; leanback manifest flag + runtime TV-mode detection; no on-screen d-pad on TV |

## Scripting engines on Android

**Forth (zForth) only.** All other engines are disabled for the Android build:

```
WF_LUA_ENGINE=none       # requires lua-not-special plan to land first
WF_ENABLE_FENNEL=0       # auto-disabled when Lua is absent
WF_JS_ENGINE=none
WF_WASM_ENGINE=none
WF_ENABLE_WREN=0
WF_REST_API=0
WF_FORTH_ENGINE=zforth   # default, explicit for clarity
```

Until the lua-not-special plan lands, Lua compiles in unconditionally; the interim Android build ships Forth + Lua.

zForth: ~4 KB compiled core + WF bridge; pure portable C, no OS-specific code. All other engines are portable to arm64 and can be re-enabled later.

**Note on WAMR if re-enabled later:** change `WAMR_BUILD_TARGET` from `X86_64` to `AARCH64`.

## Prerequisites (must land first)

Each has standalone value on Linux; Android blocks on all four.

1. **[lua-not-special](2026-04-16-lua-not-special.md)** — makes `WF_LUA_ENGINE=none` available so the Android build can be truly Forth-only.

2. **Phase 0 — Retire immediate-mode GL (Linux VBO rewrite)**
   `glBegin`/`glEnd` does not exist in GLES 3.0. Rewrite `gfx/glpipeline/*.cc` to VBO + shader batches on Linux first.

3. **Phase 1 — CMake build**
   Android NDK consumes CMake natively. Replace `build_game.sh` with `CMakeLists.txt`.

4. **Phase 2 — HAL lifecycle + filesystem abstraction**
   Add suspend/resume hooks to the game loop; factor `hal/dfhd.cc` through an asset-accessor interface. Linux no-ops the hooks.

## Steps

### Phase 0 — Retire immediate-mode GL on Linux

1. Introduce thin renderer-backend interface at `wfsource/source/gfx/renderer.hp`. Start minimal: `SubmitBatch(VBO, index, shader, uniforms)`. Keep `glpipeline_legacy` working during transition.
2. Port one renderer TU at a time — `rendgtp.cc` first. Validate via golden-image diff against snowgoons.
3. Port remaining 7 renderer TUs. Retire `glpipeline_legacy` behind `WF_RENDERER=legacy|modern`; default modern.
4. **Verify:** snowgoons renders identically on Linux under `WF_RENDERER=modern`; frame time equal or better.

### Phase 1 — CMake build

1. Write `CMakeLists.txt` at repo root and in `engine/` mirroring `build_game.sh`'s TU list and all feature flags (`WF_LUA_ENGINE`, `WF_ENABLE_FENNEL`, `WF_JS_ENGINE`, `WF_WASM_ENGINE`, `WF_PHYSICS_ENGINE`).
2. Keep `build_game.sh` working until CMake parity is verified; then retire it.
3. **Verify:** CMake output byte-equivalent to `build_game.sh`. All feature flags work.

### Phase 2 — HAL lifecycle + filesystem abstraction

1. Add suspend/resume hooks in `wfsource/source/game/game.cc` around the `for(;;)` in `RunGameScript`. Linux no-ops them.
2. Factor `hal/dfhd.cc` through an asset-accessor interface. Linux impl: open files from working dir.
3. Add GL context loss / restore hooks: texture/VBO re-upload after context teardown.
4. **Verify:** Linux build unchanged; hooks exist but are no-ops.

### Phase 3 — Android port

1. Add `hal/android/` — platform init, input, filesystem (`AAssetManager`), timer.
2. Write `NativeActivity` entry point (`android_native_app_glue`-style). Map `onStart`/`onPause`/`onResume`/`onStop` to Phase 2 hooks.
3. CMake NDK toolchain build (arm64-v8a): compile engine + zForth + Jolt into `libwf_game.so` with the Forth-only flags above. Add Gradle project + `AndroidManifest.xml`; package into APK.
4. Input: detect TV mode at runtime via `UiModeManager.getCurrentModeType() == UI_MODE_TYPE_TELEVISION`. On TV: physical gamepad/D-pad remote only → `EJ_BUTTONF_*` bitmask directly; no on-screen d-pad rendered. On phone/tablet: on-screen d-pad + 4–6 buttons (hit-test each `MotionEvent`) AND physical gamepad — both paths emit the same `EJ_BUTTONF_*` bitmask.
5. Asset pipeline: bake `cd.iff` into `assets/` in APK; redirect Phase 2's asset accessor to `AAssetManager_open`.
6. GL renderer: hook Phase 0's `glpipeline_modern` to GLES 3.0 context from `EGLContext`.
7. **Verify (phone):** sideload APK, launch, play snowgoons. Pause (Home), resume, game continues. No crash on orientation change (landscape-lock as first defence).
   **Verify (Google TV):** sideload same APK to Chromecast with Google TV via ADB, launch via leanback launcher, play snowgoons with a gamepad. No on-screen d-pad rendered.

### Phase 4 — Second-level smoke test + performance pass

1. Run a non-snowgoons level to confirm level-load path is not snowgoons-hardcoded.
2. Profile with `simpleperf`: frame time, GPU time, RSS. Mobile CPU speed is a real concern — measure whether 30 fps is achievable on low-end ARM64.
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
| `android/build.gradle`, `AndroidManifest.xml` | Phase 3 — new; leanback feature + launcher intent for Google TV |

## Open questions

- **Performance floor.** Mobile CPUs are slow. The variable-`dt` loop has run at 30 fps before so correctness is not the question; the question is whether the renderer + Jolt + game logic stay above a playable threshold on low-end ARM64. Measure in Phase 4.

## Out of scope

- iOS (own plan, starts after this ships)
- App Store / Play Store distribution
- Audio (nothing to port — stubs are stubs)
- Haptics, gyro, camera, mic
- Orientation / responsive layout (landscape-locked letterbox only)
- Vulkan backend (GLES 3.0 is the v1 graphics path)
- Additional scripting engines beyond Forth on Android v1
