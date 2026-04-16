# WorldFoundry → Steam-Ready Game Engine

**Date:** 2026-04-12  
**Goal:** Modernize the WorldFoundry runtime so a new game built on it can be packaged and published on Steam.

---

## Context

WorldFoundry is a complete 3D game engine (GPL v2, 1994–2003) with a proven game loop, content pipeline, and existing demo levels. Steam's minimum requirement is an executable that launches — no Steamworks SDK integration beyond that.

The toolchain modernization is already underway on the `2026-iffcomp` branch: `iffcomp` builds on GCC 15 / Clang, PSX targets have been dropped, and there is a documented plan to rewrite `wftools` in Go/Rust (`2026-04-11-wftools-rewrite-analysis.md`). This plan covers the **runtime engine** (`wfsource/`) side of that work.

### What blocks shipping today

| Blocker | Detail |
|---------|--------|
| Build system | GNU Make + 1990s OpusMake; combinatorial explosion of modes |
| C++ dialect | Assumes GCC 2.95 / MSVC 6.0; LP64 issues, removed stdlib headers |
| Platform HAL | Linux/Win/PSX forks; Win path is untested against modern MSVC |
| Renderer | Shaped by PS1 constraints (order tables, 1024×512 VRAM model) |
| Audio | Stub only |
| Window management | No fullscreen toggle, hardcoded 320×240 / 640×480 |

### What carries over intact

- **Content pipeline** — `iffcomp`, `textile`, `levelcon`, `iff2lvl` already modernized or in progress
- **Existing texture maps** — `.tga`/`.bmp` assets load directly as GL textures once the PS1 VRAM atlas packing constraint is removed; no texture file changes needed
- **Game logic** — OAS/OAD data-driven object system, mailbox communication, movement state machines, room streaming all work as-is
- **Asset format** — IFF/`.lev`/`cd.iff` pipeline is byte-exact after modernization

---

## Phase 1: Runtime C++ Modernization

**Goal:** `wfsource` compiles clean on GCC 15 / Clang 18 targeting Linux x86-64.

Apply the same systematic fixes documented in `2026-04-11-iffcomp-modernization.md` to the full runtime:

- Fix LP64 `int32`/`long` mismatches (same class already patched in pigsys/math for iffcomp)
- Replace removed stdlib headers (`<strstream>` → `<sstream>`, etc.)
- Fix implicit `int` return types, `register` keyword, C-style casts
- Remove or guard all `#ifdef __PSX__` blocks (PSX is dropped)
- Remove dead `DO_MULTITASKING` / `DO_SLOW_STEREOGRAM` paths

**Critical files:**
- `wfsource/source/pigsys/` — OS abstraction, LP64 issues concentrated here
- `wfsource/source/hal/linux/` — HAL entry points
- `wfsource/source/math/scalar.hp` — already known-good from iffcomp work
- `wfsource/source/gfx/gl/` — OpenGL renderer pipeline

**Verification:** `make BUILDMODE=debug RENDERER=gl` produces a binary that loads a level without crashing.

---

## Phase 2: Replace Build System with CMake

**Goal:** Single CMake build that works on Linux and cross-compiles for Windows.

The current GNUmakefile has 7 build modes × 3 streaming modes × 3 platforms. For shipping: `debug` + `release` × Linux + Windows is sufficient.

Steps:
- Write `wfsource/CMakeLists.txt` with one static library target per subsystem (math, physics, gfx, hal, pigsys, asset, etc.)
- Top-level `CMakeLists.txt` composes them into the game executable
- Keep `prep` in the CMake build via `add_custom_command` (do not rewrite `prep` yet — that is Phase 6 of the tools rewrite plan)
- Wire `wftools` pipeline as CMake `ExternalProject` or pre-built binaries

**Reference files for library dependency graph:**
- `wfsource/GNUmakefile`, `GNUMakefile.env`, `GNUMakefile.bld`, `GNUMakefile.rul`
- `wfsource/source/*/GNUmakefile` — per-directory source lists

**Verification:** `cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build` produces a working executable.

---

## Phase 3: Replace HAL with SDL2

**Goal:** Window creation, input, and audio handled by SDL2, eliminating the platform-forked HAL.

SDL2 maps cleanly onto WorldFoundry's existing abstraction boundaries:

| WorldFoundry concept | SDL2 replacement |
|----------------------|-----------------|
| `PIGSMain()` bootstrap | `SDL_Init` + `SDL_CreateWindow` |
| Joystick/keyboard HAL | `SDL_GameController` + `SDL_Event` loop |
| Audio device stub | `SDL_mixer` (WAV + streaming music) |
| GL context (X11/WGL) | `SDL_GL_CreateContext` |

This removes the X11 dependency on Linux and gives the Windows build path for free.

Steps:
1. Write `wfsource/source/hal/sdl2/` — new HAL implementation
2. Replace `source/gfx/gl/` context setup with SDL2 GL context
3. Replace `source/input/` platform code with SDL2 gamepad events (keep `inputdig.hp` interface)
4. Replace `source/audio/` stub with `SDL_mixer`
5. Retire `hal/linux/` and `hal/win/` once SDL2 path is verified

**Critical files:**
- `wfsource/source/hal/linux/hal.cc` — current Linux entry point (reference)
- `wfsource/source/gfx/gl/` — GL context init to replace
- `wfsource/source/input/inputdig.hp` — interface stays, only impl changes
- `wfsource/source/audio/` — stub being replaced

**Verification:** Game window opens, controller and keyboard input works, WAV effects play.

---

## Phase 4: OpenGL Renderer Modernization

**Goal:** Renderer runs on OpenGL 3.3 core profile at arbitrary resolution.

The existing GL pipeline emulates PS1 order-table behavior. Unwind that for the PC path:

- Remove order-table linked-list submission; use Z-buffer directly
- Remove 1024×512 VRAM model; textures are plain GL textures (no manual atlas packing — existing `.tga`/`.bmp` texture maps load directly)
- Support arbitrary window resolution
- Add fullscreen toggle via `SDL_SetWindowFullscreen`
- `RENDERER_PIPELINE=gl` is the only remaining target

**Critical files:**
- `wfsource/source/gfx/display.hp` — order table / double-buffer / VRAM interface
- `wfsource/source/gfx/glpipeline/` — GL pipeline implementation
- `wfsource/source/gfx/texture.hp` — texture/VRAM management

**Verification:** Demo levels render at 1920×1080 without visual corruption at ≥30fps.

---

## Phase 5: Windows Build

**Goal:** Game builds and runs on Windows (MSVC 2022 or MinGW-w64).

Because SDL2 owns all platform code after Phase 3, this is mostly ensuring CMake finds SDL2 on Windows and the C++ fixes hold under MSVC.

Steps:
- Test CMake build with `cl.exe` (MSVC 2022) targeting `x64`
- Fix MSVC-specific issues (typically: `__declspec` inconsistencies, `for`-loop scoping)
- Bundle SDL2 DLLs alongside the executable
- Produce a `.exe` that launches from Explorer and from the Steam client

**Verification:** `cmake --preset windows-release` produces `WorldFoundry.exe` that runs on a clean Windows 10/11 machine.

---

## Phase 6: Steam Packaging

**Goal:** Submit a launchable game to Steam. No Steamworks SDK needed.

Steps:
1. Register app on Steamworks (App ID)
2. Create `steam/app_build.vdf` and `steam/depot_build.vdf` for `steamcmd`
3. Place `steam_appid.txt` alongside the executable (enables Steam overlay auto-detection)
4. Upload: `steamcmd +login ... +run_app_build steam/app_build.vdf`
5. Set Steam launch option, configure store page (capsule art, screenshots, description)

**Verification:** Game appears in Steam library, launches via "Play", Steam overlay (Shift+Tab) activates.

---

## Files to Create / Modify

| File | Action |
|------|--------|
| `wfsource/CMakeLists.txt` | Create |
| `wfsource/source/hal/sdl2/hal.cc` | Create |
| `wfsource/source/gfx/gl/context_sdl2.cc` | Create |
| `wfsource/source/audio/sdl_mixer.cc` | Create |
| `wfsource/source/gfx/glpipeline/*.cc` | Modify — remove order-table emulation |
| `wfsource/source/gfx/display.hp` | Modify — remove VRAM model |
| `wfsource/source/pigsys/*.cc` | Modify — LP64 + dialect fixes |
| `steam/app_build.vdf` | Create |

---

## End-to-End Verification Checklist

- [ ] `cmake --preset linux-release && cmake --build build/linux` — clean, no errors
- [ ] `./WorldFoundry wflevels/snowgoons/cd.iff` — level loads, player moves, ≥30fps
- [ ] All existing texture maps display correctly (no VRAM atlas required)
- [ ] Fullscreen toggle works
- [ ] Controller input works
- [ ] Audio plays
- [ ] Windows `.exe` builds and runs on clean Windows 10/11
- [ ] `steamcmd` upload completes; game launches from Steam client
