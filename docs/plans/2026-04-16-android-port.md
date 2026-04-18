# Plan: Android port

**Date:** 2026-04-16
**Status:** Closed 2026-04-18 — Phases 0+1+2 + Phase 3 steps 1–7 all landed, plus post-boot polish (viewport/projection aspect, pause/resume EGL preservation, zForth `here` director fix, on-screen touch HUD). Remaining polish tracked as separate plans: [android-launcher-polish](2026-04-18-android-launcher-polish.md) and [audio-assets-from-iff](2026-04-18-audio-assets-from-iff.md). Tag `pre-legacy-gl-retire` (`807d1ea`) marks the last commit with `backend_legacy.cc` present.
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
5. 🟡 **Step 4c.** Retire remaining fixed-function call sites. **Proper shader ports, not `#ifndef __ANDROID__` stubs** — otherwise Android snowgoons loses visible features (lit surfaces, fog, matte background).

   a. ✅ **Per-vertex normal through the seam.** `DrawTriangle` carries the face normal; modern backend's `Vert` struct has `nx/ny/nz`, VBO attrib location 3 bound to `a_normal`, replicated across all three verts at pack time (`backend_modern.cc:367-374`). Visually verified 2026-04-17 (snowgoons with `WF_RENDERER=modern` looks identical to legacy).

   b. ✅ **Directional lighting in the shader.** Backend has `SetAmbient`/`SetDirLight`/`SetLightingEnabled`. Modern backend transforms light direction into eye space via the current modelview (`backend_modern.cc:263-288`); vertex shader does `lit = u_ambient + Σ u_light_color[i] · max(0, N·L_i)` (`backend_modern.cc:71-80`); fragment multiplies color by `v_lit`. `camera.cc:219-235` calls `SetModelView` then `SetAmbient` then `SetDirLight` ×3 with world-space directions negated; `display.cc:220` enables lighting at init. Legacy backend routes the same methods back to `glLightModelfv`/`glLightfv`. Visually verified 2026-04-17.

   c. ✅ **Linear fog in the shader.** `SetFog(rgb, start, end)` + `SetFogEnabled(bool)` on backend. Vertex shader computes eye-space Z from `u_mv * position` and derives `fog_factor = clamp((u_end − eye_z)/(u_end − u_start), 0, 1)`; fragment does `mix(fog_color, color, fog_factor)` when fog is enabled. `camera.cc:237-241` calls both. Visually verified along with (a+b) 2026-04-17.

   d. ✅ **`rendmatt.cc` quads through the seam** (`e8acdf8`). Each tile emits two `DrawTriangle` calls on the same texture; matte bracket calls `ResetModelView` + `SetLightingEnabled(false)` + `SetFogEnabled(false)` before draw and re-enables after. Visually verified as part of the 2026-04-17 snowgoons run.

   e. ✅ **Strip vestigial fixed-function calls in `display.cc` and `camera.cc`.** Every remaining `glLight*`/`glMaterial*`/`glShadeModel`/`glEnable(GL_LIGHT*|GL_FOG)` outside `backend_legacy.cc` turned out to be inside `#if 0` blocks (display.cc:223-265 debug init) or `#if defined(USE_ORDER_TABLES)` (PSX-only). No live code needed stripping. USE_ORDER_TABLES removal is a separate cleanup pass.

   f. ✅ **Retire `backend_legacy.cc`** (`62ef11f` deleted the TU, `ff589c8` cleaned up the leftover plumbing). `backend_factory.cc` now unconditionally returns `ModernBackendInstance()` — 20 lines, no env var, no `#ifdef __ANDROID__` split. `display.cc`/`display.hp` `LoadGLMatrixFromMatrix34` deleted. Tag `pre-legacy-gl-retire` (`807d1ea`) marks the last commit with the legacy backend present. LOC impact documented in `docs/investigations/2026-04-15-loc-tracking.md` (−541 net for the OpenGL rewrite in isolation).

6. ✅ **Verify:** snowgoons renders identically on Linux under the (now-sole) modern backend (visually confirmed 2026-04-17, modern vs legacy side-by-side before legacy was retired). Frame-time parity not quantified; subjective playthrough was indistinguishable.

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
4. ✅ **Step 4 (2026-04-17).** Step 4a (`148b319`): gamepad path — AKEYCODE_DPAD_* + AKEYCODE_BUTTON_A/B/X/Y/L1/R1/START/SELECT + joystick AXIS_X/Y/HAT_X/HAT_Y past threshold → EJ_BUTTONF_*. Step 4b (`58fd790`): touch path — fixed-pixel bottom-left d-pad cross + bottom-right A/B rectangles, multi-touch merged per-frame. TV-mode detection via AConfiguration_getUiModeType; touch events dropped on TV. Gamepad and touch states tracked separately (gGamepadButtons + gTouchButtons) and ORed on flush.
5. ✅ **Step 5 (2026-04-17).** `hal/android/asset_accessor_aasset.cc` wraps AAssetManager_open / AAsset_read / AAsset_seek64 / AAsset_close / AAsset_getLength64 — same shape as the Phase-2 AssetAccessor interface. native_app_entry.cc stashes `app->activity->assetManager` at android_main entry so the accessor can grab it during _PlatformSpecificInit. `cd.iff` is bundled into the APK via a symlink at `android/app/src/main/assets/cd.iff` pointing at the canonical `wfsource/source/game/cd.iff` — no copy, no staleness. Android copy of `asset_accessor_posix.cc` retired (the POSIX fallback that served us pre-AAssetManager).
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
