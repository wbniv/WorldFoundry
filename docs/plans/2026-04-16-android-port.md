# Plan: Android port

**Date:** 2026-04-16
**Status:** In progress — Phases 0 (steps 1–4c/a–e done; 4c/f gated on visual parity + legacy retire), 1, 2 complete; Phase 3 steps 1–3 + 6 done (libwf_game.so links, NativeActivity entry + EGL live, Gradle project scaffolded); step 4 (real input), step 5 (AAssetManager), step 7 (device smoke test) remaining
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

zForth: ~4 KB compiled core + WF bridge; pure portable C, no OS-specific code. All other engines are portable to arm64 and can be re-enabled later.

**Note on WAMR if re-enabled later:** change `WAMR_BUILD_TARGET` from `X86_64` to `AARCH64`.

## Prerequisites (must land first)

Each has standalone value on Linux; Android blocks on all four.

1. **[lua-not-special](2026-04-16-lua-not-special.md)** ✅ Done 2026-04-16 — `WF_LUA_ENGINE=none` available; Android build will be Forth-only.

2. **Phase 0 — Retire immediate-mode GL (Linux VBO rewrite)** 🟡 In progress 2026-04-17
   `glBegin`/`glEnd` does not exist in GLES 3.0. Rewrite `gfx/glpipeline/*.cc` to VBO + shader batches on Linux first. Steps 1, 2, 4a, 4b landed (`b868a26`, `c3c62c7`, `bba0a65`, `cfb309d`): renderer backend seam (`gfx/renderer_backend.hp`), all 8 render TUs ported (−928 LOC), matrix state routed through backend, modern VBO + shader backend (`gfx/glpipeline/backend_modern.cc`, GLSL 330 core / GLES 300 es) selectable via `WF_RENDERER=modern`. Default: modern on Android, legacy on desktop. Step 4c remaining: retire `glMaterialfv`/`glEnable(GL_LIGHTING)`/`glShadeModel` in `display.cc`, `glLightfv`/`glLightModelfv` in `camera.cc`, `glBegin(GL_QUADS)` in `rendmatt.cc`.

3. **Phase 1 — CMake build** ✅ Done 2026-04-17
   `CMakeLists.txt` at repo root; NDK r26c at `/usr/lib/android-sdk/ndk/26.2.11394342`; `task build-cmake` (Linux) and `task build-cmake-android` (arm64-v8a, API 21) in Taskfile. Linux CMake build produces a runnable `engine/wf_game` (launches snowgoons); Forth-only flag combination compiles; Android build reaches the expected Phase 0 boundary (`GL/gl.h` not found). 64-bit collision-message bug discovered + fixed along the way.

4. **Phase 2 — HAL lifecycle + filesystem abstraction**
   Add suspend/resume hooks to the game loop; factor `hal/dfhd.cc` through an asset-accessor interface. Linux no-ops the hooks.

## Steps

### Phase 0 — Retire immediate-mode GL on Linux
**Estimate: 2–3 weeks.** Largest phase; carries the most risk. Depth of `glBegin`/`glEnd` entanglement in the 8 renderer TUs was unknown until the first TU was opened.

1. ✅ **Step 1 (2026-04-17, `b868a26`).** Thin renderer-backend interface at `gfx/renderer_backend.hp` with per-triangle `DrawTriangle` seam. Legacy backend (`gfx/glpipeline/backend_legacy.cc`) maps calls back to fixed-function GL — behavior byte-identical. `rendgtp.cc` (GouraudTexturePreLit) ported first as proof.
2. ✅ **Step 2 (2026-04-17, `c3c62c7`).** Remaining 7 render TUs (fcp/fcl/ftp/ftl/gcp/gcl/gtl) all feed `RendererBackendGet().DrawTriangle`. Per-variant `FLAG_TEXTURE × FLAG_GOURAUD × FLAG_LIGHTING` branching collapsed to a single shape — net −928 LOC. Snowgoons runs cleanly.
3. ✅ **Step 4a (2026-04-17, `bba0a65`).** Matrix state routed through backend: `SetProjection` / `SetModelView` / `ResetModelView`. Call sites updated in `display.cc`, `camera.cc`, `rendobj3.cc`. Legacy impl maps to `glMatrixMode` + `gluPerspective` / `glLoadMatrixf` / `glLoadIdentity`.
4. ✅ **Step 4b (2026-04-17, `cfb309d`).** `ModernRendererBackend` in `gfx/glpipeline/backend_modern.cc`: interleaved VBO (pos/color/uv), CPU accumulation per batch, GLSL 330 core / GLES 300 es shader pair (MVP uniform, texture-or-vertex-color fragment). CPU-computed MVP from separate projection + modelview. Flush on texture / modelview change or `EndFrame`. `gfx/glpipeline/backend_factory.cc` picks modern on Android, legacy on desktop by default; `WF_RENDERER=modern` flips desktop for regression. Snowgoons runs clean on both backends for 10 s with no GL errors.
5. ⬜ **Step 4c.** Retire remaining fixed-function call sites. **Proper shader ports, not `#ifndef __ANDROID__` stubs** — otherwise Android snowgoons loses visible features (lit surfaces, fog, matte background).

   a. **Per-vertex normal through the seam.** `DrawTriangle(v0, v1, v2, nx, ny, nz, texture)` currently passes a per-triangle normal that the modern backend ignores. Promote to `a_normal` vertex attribute in the interleaved VBO (replicate the face normal into all three verts at pack time). Needed as the input to (b).

   b. **Directional lighting in the shader.** Add backend methods `SetAmbient(rgb)`, `SetDirLight(index, dirXYZ, colorRGB)`, `SetLightingEnabled(bool)`. `camera.cc` `SetLightsAndViewMatrix` calls these instead of `glLightModelfv`/`glLightfv`. Vertex shader transforms the normal by the modelview's 3×3 upper-left and computes `lit = u_ambient + Σ u_light_color[i] · max(0, N·(−L_i))`; fragment multiplies color by `lit`. Matches the GL fixed-function equation for directional lights with all-white materials and the current three-light setup. Modern backend stores the light state; legacy maps the new methods back to `glLightModelfv`/`glLightfv` so behavior stays unchanged on Linux until legacy is retired.

   c. **Linear fog in the shader.** Add `SetFog(enabled, colorRGB, start, end)`. `camera.cc` calls it when it currently sets `glFogfv`/`glFogf`. Vertex shader computes eye-space Z from `u_mv * position` and derives `fog_factor = clamp((u_end − eye_z)/(u_end − u_start), 0, 1)`; fragment does `mix(fog_color, color, fog_factor)` when fog is enabled.

   d. **`rendmatt.cc` quads through the seam.** Each `glBegin(GL_QUADS)` block becomes two `DrawTriangle` calls on the same texture; the per-matte `glDisable(LIGHTING)`/`glDisable(FOG)` become `SetLightingEnabled(false)` / `SetFog(false, …)` for the duration of the draw (re-enabled after). Matte stays unlit/unfogged by design.

   e. **Strip vestigial fixed-function calls in `display.cc` and `camera.cc`.** After (a–d) the remaining `glEnable(GL_LIGHTING/LIGHT0-2/NORMALIZE/FOG/TEXTURE_2D)`, `glShadeModel`, `glMaterialfv(lightWhite/lightBlack)` calls are all redundant — the shader controls each via uniforms, and the material is implicit in the per-vertex color. Delete them outright on both backends.

   f. **Retire `backend_legacy.cc`.** After visual parity on Linux with `WF_RENDERER=modern`, delete the legacy backend and the `WF_RENDERER` env var; modern becomes the only backend. Also delete `display.cc`'s `LoadGLMatrixFromMatrix34` helper (only the legacy backend used it).

6. ⬜ **Verify:** snowgoons renders identically on Linux under the (now-sole) modern backend; frame time equal or better. Lit surfaces shade correctly, fog fades distant geometry, matte background scrolls.

### Phase 1 — CMake build
**Estimate: 2–3 days.** Mechanical translation of `build_game.sh`; no new logic.

1. Write `CMakeLists.txt` at repo root and in `engine/` mirroring `build_game.sh`'s TU list and all feature flags (`WF_LUA_ENGINE`, `WF_ENABLE_FENNEL`, `WF_JS_ENGINE`, `WF_WASM_ENGINE`, `WF_PHYSICS_ENGINE`).
2. Keep `build_game.sh` working until CMake parity is verified; then retire it.
3. **Verify:** CMake output byte-equivalent to `build_game.sh`. All feature flags work.

### Phase 2 — HAL lifecycle + filesystem abstraction
**Estimate: 2–3 days.** Plumbing only; Linux no-ops keep the diff reviewable.

1. Add suspend/resume hooks in `wfsource/source/game/game.cc` around the `for(;;)` in `RunGameScript`. Linux no-ops them.
2. Factor `hal/dfhd.cc` through an asset-accessor interface. Linux impl: open files from working dir.
3. Add GL context loss / restore hooks: texture/VBO re-upload after context teardown.
4. **Verify:** Linux build unchanged; hooks exist but are no-ops.

### Phase 3 — Android port
**Estimate: 1 week.** New platform layer + Gradle wiring; most steps are one-to-one with existing Linux equivalents.

1. ✅ **Step 1 (2026-04-17).** `hal/android/` stubs (`platform.cc`, `input.cc`, `lifecycle.cc`, `asset_accessor_posix.cc`), `audio/android/audio_stub.cc` silent backend. `gfx/gl/android_window.cc` stub peer of `mesa.cc`. All the Windows / X11 / GLU / fixed-function calls that can't compile on GLES are `#if defined(__ANDROID__)` gated. `libwf_game.so` links clean — ~30 MB arm64-v8a.
2. ✅ **Step 2 (2026-04-17).** `hal/android/native_app_entry.cc`: `android_main` on the glue-provided game thread, lifecycle handlers (INIT_WINDOW / TERM_WINDOW / PAUSE / RESUME / DESTROY), input stub. `gfx/gl/android_window.cc` now does real EGL 3.0 init from the `ANativeWindow` — `eglGetDisplay` / `eglChooseConfig(RGB888,D16,GLES3_BIT)` / `eglCreateContext(client=3)` / `eglMakeCurrent`. `XEventLoop` drains the ALooper non-blocking each frame. `libwf_game.so` exports both `ANativeActivity_onCreate` (loader entry) and `android_main` (thread entry).
3. ✅ **Step 3 (2026-04-17).** Gradle project at repo-top `android/`: `settings.gradle.kts`, `build.gradle.kts`, `app/build.gradle.kts` (AGP 8.5.2, compileSdk 34, minSdk 21, arm64-v8a only, `externalNativeBuild` points at repo-root `CMakeLists.txt`), `app/src/main/AndroidManifest.xml` (NativeActivity with LAUNCHER + LEANBACK_LAUNCHER intent-filters, landscape-locked). Taskfile `build-apk` / `install-apk` targets. APK packaging itself still requires the user to install Android SDK `platforms;android-34` + `build-tools;34.0.0` + Gradle — see `android/README.md`.
4. ⬜ **Step 4.** Input: detect TV mode at runtime via `UiModeManager.getCurrentModeType() == UI_MODE_TYPE_TELEVISION`. On TV: physical gamepad/D-pad remote only → `EJ_BUTTONF_*` bitmask directly; no on-screen d-pad rendered. On phone/tablet: on-screen d-pad + 4–6 buttons (hit-test each `MotionEvent`) AND physical gamepad — both paths emit the same `EJ_BUTTONF_*` bitmask.
5. ⬜ **Step 5.** Asset pipeline: bake `cd.iff` into `assets/` in APK; `hal/android/asset_accessor_aasset.cc` peer implementation of the Phase-2 `AssetAccessor` that wraps `AAssetManager_open` / `AAsset_read` / `AAsset_seek` / `AAsset_close`.
6. ✅ **Step 6 (rolled into step 2).** GL renderer: modern VBO+shader backend is selected on Android (see Phase 0 step 4b's `backend_factory.cc`) and consumes the EGL context from step 2.
7. ⬜ **Verify (phone):** sideload APK, launch, play snowgoons. Pause (Home), resume, game continues. No crash on orientation change (landscape-lock as first defence).
   **Verify (Google TV):** sideload same APK to Chromecast with Google TV via ADB, launch via leanback launcher, play snowgoons with a gamepad. No on-screen d-pad rendered.

### Phase 4 — Second-level smoke test + performance pass
**Estimate: 2–3 days.**

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
