# Plan: macOS port — renderer-agnostic runtime bring-up (headless)

**Date:** 2026-05-26
**Status:** Implemented (authored from Linux); awaiting first Codemagic macOS build.
**Companion:** [docs/investigations/2026-05-26-macos-port-estimate.md](../investigations/2026-05-26-macos-port-estimate.md)

## Context

Start the macOS desktop port **now**, doing only the renderer-agnostic work — the larger, lower-risk half of the runtime port that does not depend on the (deferred, Metal-direct) renderer or on iOS Metal completion. Goal: bring macOS to roughly where iOS is today (all engine sources compile + link under Apple Clang, the binary boots and opens `cd.iff`) but with **rendering as a TRUE no-op** — no window, no Metal, no GL context. Because headless is simpler than iOS's UIKit/Metal path, macOS actually runs the engine `Load → Step → Unload` loop (which iOS hasn't driven yet), drawing nothing.

Decision history (this session): an earlier idea to mirror iOS's structure (AppKit + `CAMetalLayer` cornflower-blue clear + engine thread) was judged **waste** — it pulls in Metal/Cocoa frameworks and a threaded architecture for a clear rectangle the no-op doesn't need, and the real Metal window arrives later anyway. So macOS boots **"Linux-minus-X11"**: a thin `main()` → `HALStart()` on the main thread.

## Key validated insight

The frame loop touches the GPU only through the `Display` object and `RendererBackendGet()` — never a window directly ([`game.cc`](../../wfsource/source/game/game.cc) `StepFrame`/`SmokeRunFrameStep`). `WFGame`'s ctor always builds a `Display`; on Linux that opens an X11/GLX window, but [`gfx/display.cc`](../../wfsource/source/gfx/display.cc) `#include`s a per-platform impl — iOS's [`display_ios.cc`](../../wfsource/source/hal/ios/display_ios.cc) is a windowless timer. So a macOS `display_macos.cc` (clone of the iOS one) + a no-op `RendererBackend` makes `Display` a pure timer: no window, no GL context, loop runs. Texture uploads in `LoadLevel` (`PixelMap` → `glGenTextures`/`glTexImage2D`) are absorbed by GL entry-point stubs, exactly as iOS does in [`gl_stubs.cc`](../../wfsource/source/hal/ios/gl_stubs.cc).

## What was implemented

**New files**
- [`wfsource/source/hal/macos/platform_main.cc`](../../wfsource/source/hal/macos/platform_main.cc) — thin `main()` shell (clone of the Linux one, minus the non-standard `strlwr` cosmetic call).
- [`wfsource/source/hal/macos/display_macos.cc`](../../wfsource/source/hal/macos/display_macos.cc) — headless `Display` (clone of `display_ios.cc`).
- [`wfsource/source/hal/macos/gl_stubs.cc`](../../wfsource/source/hal/macos/gl_stubs.cc) — no-op GL entry points (clone of `hal/ios/gl_stubs.cc`, `<OpenGL/gl.h>` for the type vocabulary; OpenGL.framework is **not** linked).
- [`wfsource/source/hal/macos/window_macos.cc`](../../wfsource/source/hal/macos/window_macos.cc) — `HALWindowCloseRequested`/`HALRequestClose`/`HALCloseWindow` (these live in `mesa.cc` on Linux, excluded on macOS).
- [`engine/stubs/renderer_stub.cc`](../../engine/stubs/renderer_stub.cc) — `HeadlessBackend` (no-op `RendererBackend`) + `HeadlessBackendInstance()`.

**Reused verbatim** (portable POSIX/miniaudio, listed explicitly in the macOS CMake arm): `hal/linux/{platform_init,audio,input,lifecycle,asset_accessor_posix}.cc`.

**Edits (all `WF_TARGET_MACOS`-guarded → Linux/iOS/Android unaffected)**
- [`CMakeLists.txt`](../../CMakeLists.txt) — an `APPLE AND NOT IOS` arm across every platform block (defs, dirs, skip, stub sources, shell, target, link frameworks, `-Wno-register`, ObjC++ audio); macOS joins the minimal-config gate (Forth-only, no editor/bridge/REST/WAMR/Lua/JS/Wren); macOS excluded from the X11/GLX host-GL + ctest targets.
- [`gfx/glpipeline/backend_factory.cc`](../../wfsource/source/gfx/glpipeline/backend_factory.cc) — `#elif WF_TARGET_MACOS` → `HeadlessBackendInstance()`.
- [`gfx/display.cc`](../../wfsource/source/gfx/display.cc) — 3rd arm → `display_macos.cc`.
- [`gfx/renderer.hp`](../../wfsource/source/gfx/renderer.hp) — macOS GL-header arm → `<OpenGL/gl.h>`.
- [`gfx/gl/wfprim.h`](../../wfsource/source/gfx/gl/wfprim.h) — exclude macOS from `<GL/glu.h>`; use the numeric `AssertGLOK` branch.
- [`engine/stubs/renderpoly3d_stubs.cc`](../../engine/stubs/renderpoly3d_stubs.cc) — widen guard to `WF_TARGET_IOS || WF_TARGET_MACOS`.
- [`pigsys/pigsys.hp`](../../wfsource/source/pigsys/pigsys.hp) — macOS reuses `cf_linux.h` (declares `strlwr`; treats Darwin as POSIX).

**CI:** new `macos-desktop-debug` workflow in [`codemagic.yaml`](../../codemagic.yaml) — `mac_mini_m2`, **Ninja** generator (not `-G Xcode`, so Jolt stays modifiable), `cmake --build --target wf_game`, then a headless `--frame-step-smoke=30` run. First build forces `-DWF_PHYSICS_ENGINE=legacy -DWF_ASAN=OFF` to spend the scarce Mac-min on the novel macOS code rather than re-compiling Jolt.

## Verification

- **Local (free, done):** Linux build green (`build_game.sh`, exit 0 — source edits don't regress Linux); `cmake` configure exit 0 (CMakeLists branches parse); `codemagic.yaml` valid YAML. macOS-only new files can't be compiled off-Mac — that's the Codemagic build's job.
- **Codemagic (`macos-desktop-debug`, manual trigger):** (1) Ninja configure + `cmake --build` under Apple Clang; (2) `wf_game` links with no unresolved symbols; (3) `--frame-step-smoke=30 --cycles=1 -L snowgoons-standalone.iff` from `wfsource/source/game` exits 0 (Load → 30 Steps → Unload), opening `cd.iff`. Expect Apple-Clang/framework iteration on the first runs (see investigation §Expected iteration points): `-fpermissive`, missing `<limits.h>`/`PATH_MAX`, framework link order, miniaudio ObjC++.

## Phase 2: `.app` bundle + NSBundle accessor (implemented, awaiting Codemagic)

Implemented in the same session, before the first Codemagic run:

- `macos/Info.plist` — macOS desktop bundle plist (`LSMinimumSystemVersion=12.0`, `NSHighResolutionCapable`, no iOS keys).
- `hal/macos/asset_accessor_nsbundle.mm` — NSBundle asset accessor (clone of `hal/ios/asset_accessor_nsbundle.mm`; Foundation/NSBundle API is identical on macOS).
- `hal/linux/platform_init.cc` — `#if WF_TARGET_MACOS` guard selects `HALCreateNSBundleAccessor()` (no-op on Linux which keeps `HALCreatePosixAssetAccessor()`); `asset_accessor_posix.cc` removed from macOS sources.
- `CMakeLists.txt` — macOS `add_executable` switched to `MACOSX_BUNDLE`; macOS bundle properties block (`set_target_properties`); resource bundling loop for `cd.iff`/`level0.mid`/soundfont; `asset_accessor_nsbundle.mm` added to macOS stub sources.
- `codemagic.yaml` — smoke-test binary path updated to `wf_game.app/Contents/MacOS/wf_game`; comment notes `-L` bypasses the NSBundle cd.iff lookup.

The smoke test still works: `-L` calls `ConstructDiskFile(gLevelOverridePath)` directly, bypassing the AssetAccessor entirely.

## Deferred (TODO)

The real Metal renderer + window (the gfx half, Metal-direct, shared with iOS); re-enabling Jolt + the full scripting roster on macOS once the headless bring-up is green.
