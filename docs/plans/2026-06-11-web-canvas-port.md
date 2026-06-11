# Web/canvas port of wf_game (Emscripten)

**Date:** 2026-06-11
**Feasibility:** [investigation](../investigations/2026-06-11-web-canvas-embedding.md) (architecture, difficulty ranking, ASYNCIFY-tax profiling table)
**Scope:** v1 = playable build in a browser `<canvas>` via Emscripten + WebGL 2 (ASYNCIFY main loop); v2 = committed follow-up that inverts the main loop into a state machine and drops ASYNCIFY.

---

## Decisions (resolved during planning)

### D1: Platform defines — reuse `cf_linux.h`, à la macOS

`pigsys/pigsys.hp:84-92` requires `__LINUX__`, `__ANDROID__`, or `WF_TARGET_*`; macOS/iOS reuse `cf_linux.h`, which `#define`s `__LINUX__`. The web build follows that precedent:

- CMake defines `WF_TARGET_WEB`; `pigsys.hp:84` gains `|| defined(WF_TARGET_WEB)` so `cf_linux.h` is selected. `__LINUX__` is therefore defined in the web build.
- `__EMSCRIPTEN__` (compiler-provided) is the *exclusion* knob: every site where `__LINUX__` means "X11" rather than "POSIX" gets an `__EMSCRIPTEN__`-first branch or a `!defined(__EMSCRIPTEN__)` guard (enumerated in P1.3 below — the audit found exactly 3 such sites; the other ~30 `__LINUX__` guards are POSIX-portable and Emscripten's musl libc satisfies them: `clock_gettime(CLOCK_MONOTONIC)`, `gettimeofday`, `<sys/time.h>`, `<unistd.h>` all exist).
- No new `cf_emscripten.h`. The alternative (clean header, no `__LINUX__`) would force edits at ~30 portable guard sites for zero behavioural gain. The existing `WF_POSIX` tech-debt TODO remains the proper long-term fix and is unchanged by this plan.

### D2: Source selection — mirror Linux, not macOS

Unlike macOS (which excludes `gfx/gl` + `gfx/glpipeline` and renders headless), the web build **keeps the full GL stack** and takes the GLES branch at each `#ifdef`, exactly like Android. `WF_DIRS` = Linux's list with `hal/linux` → `hal/emscripten`, plus explicit reuse of the portable `hal/linux/` files (the mechanism macOS already uses at `CMakeLists.txt:296-299`).

### D3: Window layer — new `gfx/gl/emscripten_window.cc`, included like `mesa.cc`

The window code is not a normal TU: `gfx/display.cc:45` → `#include <gfx/gl/display.cc>` → (at `:592`) `#include "android_window.cc"` (Android) or `#include "mesa.cc"` (`__LINUX__`). Because D1 defines `__LINUX__`, the new `__EMSCRIPTEN__` branch **must come before** the `__LINUX__` branch or the web build silently swallows X11 code.

### D4: Main loop — ASYNCIFY v1, state-machine inversion v2 (committed)

Per the investigation: v1 inserts one yield in `StepFrame()` and links `-sASYNCIFY` (later narrowed with `-sASYNCIFY_ONLY`); v2 hoists the two blocking loops (`game.cc:233` meta loop, `game.cc:665` level loop — the third loop at `game.cc:476` is `WF_ENABLE_EDITOR`-only and never builds for web) into a state machine driven by `emscripten_set_main_loop()`. The ASYNCIFY tax is measured at each step into the investigation's profiling table.

### D5: Scripting — zForth only

`WF_LUA_ENGINE=none`, `WF_JS_ENGINE=none`, `WF_WASM_ENGINE=none` (sidesteps WAMR's x86-64 inline asm entirely), `WF_ENABLE_EDITOR=OFF`, `WF_DEBUG_BRIDGE=OFF`, `WF_REST_API=OFF`, `WF_ENABLE_STEAM=OFF`.

---

## Phase 1 — Build skeleton (compiles + links)

**P1.1 — emsdk.** Install via [emsdk](https://emscripten.org/docs/getting_started/downloads.html) (pin the version in the Taskfile so the build is reproducible). New Taskfile entries:

```yaml
build-web:        # emcmake cmake -B build-web -DCMAKE_BUILD_TYPE=Release && cmake --build build-web
serve-web:        # python3 -m http.server -d build-web 8080
```

**P1.2 — CMake `elseif(EMSCRIPTEN)` branch** (insert before the final `else()` in the platform ladder at `CMakeLists.txt:152-203`; the Emscripten toolchain file sets `EMSCRIPTEN`, and `APPLE`/`ANDROID` are false):

```cmake
elseif(EMSCRIPTEN)
    # Web: full GL stack like Linux, GLES branches like Android (see plan D2).
    # savegame/ dirs are vestigial (no such directory; GLOB is empty) — kept
    # for symmetry with the other platforms.
    set(WF_DIRS
        pigsys streams cpplib math memory iff mailbox
        hal hal/emscripten
        gfx gfx/gl gfx/glpipeline
        input asset baseobject movement room physics
        anim timer scripting game ini loadfile
        profile renderassets savegame savegame/linux
        menu particle audio/linux
    )
```

plus, after the `WF_SKIP` list:

```cmake
if(EMSCRIPTEN)
    list(APPEND WF_SKIP
        gfx/gl/host_gl_context.cc      # X11/GLX editor-host injection registry
        gfx/gl/emscripten_window.cc    # #included by gfx/gl/display.cc, not a TU
    )
endif()
```

explicit reuse of portable Linux HAL files (mirror of the macOS block at `CMakeLists.txt:296-299`):

```cmake
    list(APPEND WF_SOURCES
        ${SRC}/hal/linux/asset_accessor_posix.cc   # POSIX reads work against MEMFS
        ${SRC}/hal/linux/audio.cc                  # _InitAudio/_TermAudio; miniaudio is portable
    )
```

defines and link options on the `wf_game` executable target (the existing `else() add_executable` branch at `CMakeLists.txt:755` already fires for Emscripten — verify it doesn't link X11/GL libs in that path; if it does, gate those behind `if(NOT EMSCRIPTEN)`):

```cmake
    list(APPEND WF_DEFS WF_TARGET_WEB RENDERER_GLES RENDERER_PIPELINE_GLES)
    target_link_options(wf_game PRIVATE
        -sMIN_WEBGL_VERSION=2 -sMAX_WEBGL_VERSION=2
        -sALLOW_MEMORY_GROWTH=1
        -sASYNCIFY                                  # v1 only; removed in Phase 7
        --preload-file ${CMAKE_SOURCE_DIR}/wflevels/moon_site01.iff@/moon_site01.iff
    )
    set_target_properties(wf_game PROPERTIES SUFFIX ".html")   # dev shell; custom shell in P6
```

**P1.3 — The three X11-leak sites** (the `__LINUX__`-means-X11 audit findings; everything else under `__LINUX__` is POSIX-portable):

1. `gfx/gl/display.cc:592-596` — window include chain. Becomes:

    ```cpp
    #if defined(__ANDROID__)
    #  include "android_window.cc"
    #elif defined(__EMSCRIPTEN__)
    #  include "emscripten_window.cc"
    #elif defined(__LINUX__)
    #  include "mesa.cc"
    #endif
    ```

2. `gfx/gl/host_gl_context.cc` — guard is `#if defined(__LINUX__) && !defined(__ANDROID__)`; excluded via `WF_SKIP` (P1.2) rather than a guard edit, since the web build never hosts an editor GL context.
3. `gfx/gl/mesa.cc:531` X11 cleanup — unreachable once (1) is in place; no edit.

`DESIGNER_CHEATS` stays undefined for web (its `glBegin` HUD and FBO video capture at `gfx/gl/display.cc:45,601,660,787,858` never compile).

**P1.4 — GLES branch widening.** Add `|| defined(__EMSCRIPTEN__)` to the `__ANDROID__` side at exactly these sites (complete list from the audit):

| Site | What it selects |
|------|-----------------|
| `gfx/renderer.hp:28` | `<GLES3/gl3.h>` vs desktop `<GL/gl.h>` |
| `gfx/gl/display.cc:32` | same |
| `gfx/glpipeline/backend_modern.cc:19-27` | GLES3 header vs `GL_GLEXT_PROTOTYPES` + desktop headers |
| `gfx/glpipeline/backend_modern.cc:44-56` | `#version 300 es` + precision qualifiers vs `#version 330 core` |
| `gfx/gl/wfprim.h:15-20` | numeric GL-error path vs `gluErrorString()` (no GLU on web) |
| `gfx/glpipeline/backend_modern.cc:593` | inspect during implementation; classify and widen if it's a GLES-path site |

`gfx/glpipeline/backend_factory.cc` needs **no edit** — only iOS/macOS are special-cased; the `#else` already yields `ModernBackendInstance()`.

**P1.5 — `hal/emscripten/` (new directory).** Mirror of `hal/linux/` minus the reused files:

| File | Contents |
|------|----------|
| `platform.h` | minimal, like `hal/linux/platform.h` |
| `platform_main.cc` | `main(argc, argv)` → `HALStart(...)`; argv arrives from `Module.arguments` |
| `platform_init.cc` | `_PlatformSpecificInit/UnInit`, `FatalError` (→ `emscripten_console_error` + JS alert), `ParseWindowSwitches`, window-geometry globals; start from a copy of `hal/linux/platform_init.cc` with the FPE handler and X11 bits dropped |
| `input.cc` | `emscripten_set_keydown_callback`/`keyup` + Gamepad API polling → build the joystick-button word and hand it to the same `_HALSetJoystickButtons()` the X11 path uses (`hal/linux/input.cc` holds the state; reuse it if its only Linux-ism is being fed by `mesa.cc`, else fork it) |
| `lifecycle.cc` | `emscripten_set_visibilitychange_callback` → `HALNotifySuspend/Resume` (`hal/lifecycle.h:38-63`); `HALPumpSuspendedEvents()` = no-op |

**P1.6 — suspended-branch `usleep`.** `game.cc:506` calls `usleep(16000)` when suspended. Under v1 ASYNCIFY this becomes `emscripten_sleep(16)` (guard with `#ifdef __EMSCRIPTEN__`); under v2 the suspended state simply returns from the tick callback.

**Exit criterion:** `task build-web` produces `wf_game.{html,js,wasm,data}` with zero link errors. Renderer not yet expected to draw.

---

## Phase 2 — First render

**P2.1 — `gfx/gl/emscripten_window.cc`** (new, ~100-150 LOC). Implements the same surface `mesa.cc` provides (enumerated from `mesa.cc` function definitions):

| mesa.cc function | Emscripten replacement |
|------------------|------------------------|
| `OpenMainWindow(char* title)` (`mesa.cc:124`) | `emscripten_webgl_create_context("#canvas", attrs)` with `majorVersion=2`, then `emscripten_webgl_make_context_current`; set `document.title` |
| `InitWindow(x, y, w, h)` (`mesa.cc:226`) | `emscripten_set_canvas_element_size` |
| `XEventLoop()` (`mesa.cc:495`) | poll gamepads (`emscripten_sample_gamepad_data`), nothing else — keyboard arrives via callbacks |
| `HALWindowCloseRequested()` (`mesa.cc:519`) | return a flag settable from JS (default 0 — a page has no close box) |
| `HALCloseWindow()` (`mesa.cc:525`) | no-op |
| `SetX11AutoRepeat` (`mesa.cc:100`) | no-op (DOM key events handle repeat) |

Buffer swap: implicit in the browser (the frame presents when the tick callback returns / ASYNCIFY yields) — verify `display.cc`'s PageFlip path degrades to a no-op glFlush.

**P2.2 — ASYNCIFY yield.** One line at the top of `WFGame::StepFrame()` (`game.cc:494`), `#ifdef __EMSCRIPTEN__`: `emscripten_sleep(0);` — returns control to the browser once per frame, which is also what presents the frame and fires input callbacks.

**P2.3 — first triangle.** Run `moon_site01.iff`; debug WebGL errors via the browser console (`-sGL_ASSERTIONS=1` in debug builds).

**Exit criterion:** the level renders and animates in Chrome and Firefox.

---

## Phase 3 — Assets + scripting boot

- `--preload-file` (P1.2) puts the level under `/` in MEMFS; `HALCreatePosixAssetAccessor()` (`hal/linux/platform_init.cc:54-57` pattern) reads it through plain POSIX calls — expected to work unmodified.
- zForth meta script (`shell.aib`) runs at boot via the existing `ScriptInterpreterFactory` path; nothing web-specific.
- `Module.arguments = ['-L', '/moon_site01.iff']` carries the level choice; later, multiple `--preload-file` entries (or `.data` packages per level page) serve different levels from one engine build.

**Exit criterion:** boot through meta script → level load → gameplay loop, no console errors.

---

## Phase 4 — Input

- Keyboard: `keydown`/`keyup` callbacks → arrow keys/WASD → `kBtnStepLeft`/`kBtnStepRight`/etc. word → `_HALSetJoystickButtons()`. Mind the side-scroller mapping (CLAUDE.md coordinate recipe) — verification step 3 covers it.
- Gamepad: `emscripten_get_gamepad_status` each tick from `XEventLoop()`-replacement; map axes/buttons like `hal/linux/input.cc` does for its joystick path.
- Prevent default on game keys (arrows scroll the page otherwise).

**Exit criterion:** keyboard + a USB pad both drive the player correctly.

---

## Phase 5 — Audio

- `audio/linux/` is pure miniaudio (audit: no ALSA includes anywhere in the directory) — compiles as-is; miniaudio's web backend outputs via Web Audio/AudioWorklet.
- Autoplay policy: miniaudio's Emscripten backend resumes the `AudioContext` on first user gesture; verify, and if the current miniaudio vendored version doesn't, add a one-line JS resume on first `keydown`/`click`.
- MIDI music (TinySoundFont, `audio/linux/music.cc`) loads through the AssetAccessor — works once Phase 3 lands. Loose-file MIDI (`level0.mid` from cwd) needs the files added to `--preload-file` until the existing "audio assets from IFF" TODO lands.

**Exit criterion:** SFX + music audible after first input; no autoplay warnings.

---

## Phase 6 — Persistence, shell, ship (v1 complete)

**P6.1 — Hi-scores.** `game/hscore.cc:43,60` does `fopen("qbert_hiscores.txt")` — the only non-debug runtime file write in the engine (audit; `actor.cc:158,172` reads `levels.txt`/`objects.id` but is designer/debug-only). Mount IDBFS at `/save` in `platform_init.cc` (pre-main JS or `EM_ASM`), point `kHiScoreFile` at `/save/qbert_hiscores.txt` under `__EMSCRIPTEN__`, call `FS.syncfs()` after save and after mount-restore at boot.

**P6.2 — HTML shell.** Custom shell (replaces the `SUFFIX .html` dev shell): canvas + click-to-start gate + load progress, per the investigation's mockup. Embed contract:

```html
<canvas id="canvas" width="1280" height="720"></canvas>
<script src="wf_game.js"></script>
<script>Module = { canvas: document.getElementById('canvas'),
                   arguments: ['-L', '/moon_site01.iff'] };</script>
```

**P6.3 — Deploy.** Static upload of `wf_game.{js,wasm,data}` + shell to the existing Cloudflare Pages site. No special headers needed (single-threaded build). Cost: $0.

**P6.4 — ASYNCIFY tax, v1 columns.** Run `-sASYNCIFY_ADVISE`, then add `-sASYNCIFY_ONLY` with the reported unwind chain; fill the investigation's profiling table columns 1-2 (size raw/gzip, instrumented count, frame p50/p95/p99, flamegraph share, startup time) per its method notes.

---

## Phase 7 — v2: main-loop inversion (committed scope)

1. Add a `WebFrameState` enum + members to `WFGame` (current state, disk file/TOC cursor, script pointer): `BOOT → META_SCRIPT → LOAD_LEVEL → IN_LEVEL → UNLOAD → META_SCRIPT|EXIT`.
2. Re-express `RunGameScript()` (`game.cc:233-268`) and `RunLevel()` (`game.cc:661-674`) as state transitions; the Forth meta script still runs to completion inside one `META_SCRIPT` tick (it's short — level selection only).
3. `hal/emscripten/platform_main.cc`: `emscripten_set_main_loop(TickOnce, 0, false)`; `TickOnce` dispatches on the state and calls `StepFrame()` in `IN_LEVEL`.
4. Remove `emscripten_sleep` (P2.2), drop `-sASYNCIFY` from link options, drop the P1.6 sleep.
5. Suspend: `emscripten_pause_main_loop()` / `resume` from the visibility callback instead of the suspended-branch spin.
6. Fill the v2 column of the profiling table; one-line summary of the v1→v2 delta in the investigation doc.
7. Keep the Linux build byte-identical in behaviour: the state machine must also drive the native `while` loop (same transitions, just iterated in a blocking loop) so there's one code path — this is the same shape iOS Phase 2C needs for `CADisplayLink`.

---

## Effort & cost

Per the investigation: v1 ≈ 9–15 working days, v2 ≈ 3–5 days, total ~3–4 weeks. Infra cost: $0 (static hosting on the existing Cloudflare Pages free tier; artifacts ≈ 7 MB).

## Out of scope

- wf-edit in the browser (WebRTC collab, editor UI) — separate effort.
- Threads/SharedArrayBuffer (engine is single-threaded; COOP/COEP headers not needed).
- WebGPU backend — WebGL 2 only.
- The `WF_POSIX` define cleanup (existing TODO) — this plan adds 3 `__EMSCRIPTEN__` exclusion sites and leaves the broader sweep alone.

---

## Verification

1. `task build-web` exits 0 and produces `wf_game.{js,wasm,data}` + shell; `wasm` + `data` total size recorded.
2. Chrome + Firefox via `task serve-web`: `moon_site01.iff` reaches an interactive frame, zero console errors.
3. Keyboard LEFT/RIGHT move the player screen-left/screen-right (side-scroller C=π/2 recipe holds); gamepad d-pad/stick does the same.
4. Audio (SFX + music) plays after first input; no `AudioContext was not allowed to start` warning.
5. Hide the tab 10 s, return: engine resumes, no delta-time explosion.
6. Set a hi-score, hard-reload the page: score persisted (IDBFS).
7. Page interactive < 10 s on DevTools "Fast 3G" throttling.
8. ASYNCIFY tax table v1 columns filled (naïve + `ASYNCIFY_ONLY`): size raw/gzip, instrumented-function count, frame p50/p95/p99, `asyncify_*` flamegraph share, startup-to-interactive.
9. **(v2)** Final link flags contain no `-sASYNCIFY`; loop driven by `emscripten_set_main_loop()`; v2 profiling column filled and v1-vs-v2 delta summarized in the investigation.
10. **(v2)** Completing a level transitions through the state machine to the next level without a page reload.
11. **(v2)** Linux native build still passes its normal run (`wf_game -L moon_site01.iff` boots and plays) — the inversion didn't fork behaviour.
