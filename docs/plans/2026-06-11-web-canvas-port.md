# Web/canvas port of wf_game (Emscripten)

**Date:** 2026-06-11
**Feasibility:** [investigation](../investigations/2026-06-11-web-canvas-embedding.md) (architecture, difficulty ranking, ASYNCIFY-tax profiling table)
**Scope:** v1 = playable build in a browser `<canvas>` via Emscripten + WebGL 2 (ASYNCIFY main loop); v2 = committed follow-up that inverts the main loop into a state machine and drops ASYNCIFY.

---

## Implementation status — v1 complete & browser-verified 2026-06-12

**v1 is functionally complete, browser-verified, and published.** The engine builds to wasm, boots, loads a level, renders a native-equivalent 3-D frame, takes keyboard input, and initialises audio (verified end-to-end in headless Chrome / SwiftShader WebGL 2). **Published to [`worldfoundry.org/v2/play/`](https://worldfoundry.org/v2/play/)** — a designed Astro page with a level switcher embedding the engine bundle (committed in the `worldfoundry.org` repo; goes live on the next `v*` deploy tag). Evidence in the Verification section below; screenshots `2026-06-11-web-first-render-snowgoons.png`, `2026-06-12-web-moon-site01-render.png`. This table is the live tracker.

| Step | Status | Note |
|------|--------|------|
| P1.1 emsdk Taskfile (`setup-emsdk`/`build-web`/`serve-web`) | ✓ done | `Taskfile.yml:356-378` |
| P1.2 CMake `elseif(EMSCRIPTEN)` — defines, `WF_DIRS`, `WF_SKIP`, link opts | ✓ done | `CMakeLists.txt:77,139,214,283,908` |
| P1.3 window-include chain + `host_gl_context.cc` skip | ✓ done | `gfx/gl/display.cc:592-600`, skip at `CMakeLists.txt:287` |
| P1.4 GLES-branch widening (5 sites) | ✓ done | `display.cc:32`, `renderer.hp:28`, `backend_modern.cc:19,23,44`, `wfprim.h:15,31` |
| P1.4 `backend_modern.cc:593` open item | ✓ resolved | Android-only `WFAndroidNotifySurfaceLost` EGL hook — left `__ANDROID__`-only |
| P1.5 `hal/emscripten/` | ✓ done (by reuse) | `platform.h` + `platform_main.cc` are web-only; **`input.cc`/`lifecycle.cc` were NOT forked** — `emscripten_window.cc` feeds the reused `hal/linux/{input,lifecycle,audio,asset_accessor_posix}.cc` via `_HALSetJoystickButtons`/`HALNotifySuspend` (`CMakeLists.txt:358-364`) |
| P1.6 suspended-branch `usleep` | ✓ n/a for v1 | left as `usleep(16000)` at `game.cc:518`; ASYNCIFY maps it to `emscripten_sleep` |
| P2.1 `gfx/gl/emscripten_window.cc` | ✓ done & verified | WebGL2 context created in-browser; renders (snowgoons) |
| P2.2 ASYNCIFY yield in `StepFrame()` | ✓ done | `game.cc:501-508` |
| Phase 3 assets + zForth boot | ✓ done & verified | `-standalone` level preloaded to MEMFS, POSIX accessor reads it, zForth boots, level loads |
| Phase 4 input (keyboard + gamepad) | ✓ done; kbd verified | ArrowRight moved the camera in-browser; gamepad coded (`emscripten_window.cc:153-193`), not hardware-tested |
| Phase 5 audio | ✓ done & verified | `miniaudio v0.11.25 ready` in-browser; click-to-start gesture unlocks `AudioContext` (no extra JS) |
| Phase 6 shell + persistence + ship | ✓ done | custom shell `web/shell.html` (click-to-start, load progress, `?level=` selector, container fullscreen); hi-score IDBFS (`hscore.cc`, `platform_main.cc`); P6.4 ASYNCIFY-tax measured (investigation table); **published to `worldfoundry.org/v2/play/`** via `task bundle-web` → Astro page + iframe (`worldfoundry.org` commit `d825379`; live on next `v*` tag) |
| Phase 7 v2 main-loop inversion | ☐ not started | committed follow-up; plan sequences it after v1 ships + is profiled |

### Bugs fixed during the implementation pass

1. **CMake link flags** — the Release LTO block passed native-lld flags (`--icf=safe`, `--export-dynamic-symbol=ANativeActivity_onCreate`) that emcc's `wasm-ld` rejects; the generator expression fired for the web build because emcc is Clang. Scoped to `if(NOT EMSCRIPTEN)`; web gets its own `-O3 -flto=thin` (`CMakeLists.txt`).
2. **WebGL2 texParameter on the default texture** — `WFInitGL` (`display.cc:622-625`) set wrap/filter with no texture bound; desktop/Android tolerate it, WebGL 2 errors `INVALID_OPERATION`. Skipped for web (every real texture sets its own params in `pixelmap.cc:197-224`).
3. **Wrong preload file + `-L` arg form** — the build preloaded the **LVAS asset-bundle** `moon_site01.iff`; the `-L` path needs the **`-standalone`** variant (complete L-chunk, magic `L4`). Reproduced identically on native — a doc bug, not a port bug. Also: `-L` wants the path joined as ONE token (`-L<path>`, `main.cc:210`), not `-L <path>` as the plan mockups showed. Shell + CMake preload corrected.
4. **Fullscreen rendered blank** — the shell's fullscreen button used Emscripten's `Module.requestFullscreen`, which wraps/resizes the canvas; the engine's fixed 640×480 GL surface then drew blank. Switched to the native Fullscreen API on the `#wf-stage` container with `object-fit: contain` on the canvas — the GL surface is untouched and just letterbox-scales (`web/shell.html`).
5. **`task build-web` was broken / status-bar level name hardcoded** — two cosmetic-but-real fixes: `build-web` aborted before `emcc` because Task's POSIX shell can't source `emsdk_env.sh` (now run via system bash), and the player status bar hardcoded "moon_site01" (now the selected level).

> **moon_site01 (resolved 2026-06-12):** the headline `moon_site01-standalone.iff` initially showed a black frame — its 1024² NAC terrain texture overflowed the default VRAM slot (`texture.cc:74` `RangeCheckExclusive`). **Not a web bug:** native needs the same VRAM-override switches (the `task run-moon` recipe). The shell now passes them per-level (`LEVEL_ARGS` → `--vram-width=4096 --vram-height=2048 --vram-slot-width=1024 --vram-slot-height=1024`), and moon renders in-browser — `screenshots/2026-06-12-web-moon-site01-render.png`.

---

## Decisions (resolved during planning)

### D1: Platform defines — reuse `cf_linux.h`, à la macOS

`pigsys/pigsys.hp:84-92` requires `__LINUX__`, `__ANDROID__`, or `WF_TARGET_*`; macOS/iOS reuse `cf_linux.h`, which `#define`s `__LINUX__`. The web build follows that precedent:

- CMake defines `WF_TARGET_WEB`; `pigsys.hp:84` gains `|| defined(WF_TARGET_WEB)` so `cf_linux.h` is selected. `__LINUX__` is therefore defined in the web build.
  - **As-built (2026-06-11):** the shipped build takes a simpler route — `pigsys.hp:84` is left **unchanged**, and `__LINUX__` is instead injected directly via `CMakeLists.txt:144` (`list(APPEND WF_DEFS WF_TARGET_WEB __LINUX__ …)`). Same net effect (`cf_linux.h` selected, `__LINUX__` defined); `pigsys.hp` is untouched. `WF_TARGET_WEB` rides along for any web-specific future guard.
- `__EMSCRIPTEN__` (compiler-provided) is the *exclusion* knob: every site where `__LINUX__` means "X11" rather than "POSIX" gets an `__EMSCRIPTEN__`-first branch or a `!defined(__EMSCRIPTEN__)` guard (enumerated in P1.3 below — the planning audit found 3 such sites; **implementation surfaced a 4th: the `strlwr` redeclaration at `cf_linux.h:52`, now `!defined(__EMSCRIPTEN__)`-guarded** because Emscripten's libc already declares it with a `char*` return. The other ~30 `__LINUX__` guards are POSIX-portable and Emscripten's musl libc satisfies them: `clock_gettime(CLOCK_MONOTONIC)`, `gettimeofday`, `<sys/time.h>`, `<unistd.h>` all exist).
- No new `cf_emscripten.h`. The alternative (clean header, no `__LINUX__`) would force edits at ~30 portable guard sites for zero behavioural gain. The existing `WF_POSIX` tech-debt TODO remains the proper long-term fix and is unchanged by this plan.

### D2: Source selection — mirror Linux, not macOS

Unlike macOS (which excludes `gfx/gl` + `gfx/glpipeline` and renders headless), the web build **keeps the full GL stack** and takes the GLES branch at each `#ifdef`, exactly like Android. `WF_DIRS` = Linux's list with `hal/linux` → `hal/emscripten`, plus explicit reuse of the portable `hal/linux/` files (the mechanism macOS already uses at `CMakeLists.txt:296-299`).

### D3: Window layer — new `gfx/gl/emscripten_window.cc`, included like `mesa.cc`

The window code is not a normal TU: `gfx/display.cc:45` → `#include <gfx/gl/display.cc>` → (at `:592`) `#include "android_window.cc"` (Android) or `#include "mesa.cc"` (`__LINUX__`). Because D1 defines `__LINUX__`, the new `__EMSCRIPTEN__` branch **must come before** the `__LINUX__` branch or the web build silently swallows X11 code.

### D4: Main loop — ASYNCIFY v1, state-machine inversion v2 (committed)

Per the investigation: v1 inserts one yield in `StepFrame()` and links `-sASYNCIFY` (later narrowed with `-sASYNCIFY_ONLY`); v2 hoists the two blocking loops (`game.cc:236` meta loop, `game.cc:677` level loop — the third loop at `game.cc:479` is `WF_ENABLE_EDITOR`-only and never builds for web) into a state machine driven by `emscripten_set_main_loop()`. The ASYNCIFY tax is measured at each step into the investigation's profiling table.

### D5: Scripting — zForth only

`WF_LUA_ENGINE=none`, `WF_JS_ENGINE=none`, `WF_WASM_ENGINE=none` (sidesteps WAMR's x86-64 inline asm entirely), `WF_ENABLE_EDITOR=OFF`, `WF_DEBUG_BRIDGE=OFF`, `WF_REST_API=OFF`, `WF_ENABLE_STEAM=OFF`.

---

## Phase 1 — Build skeleton (compiles + links)

**P1.1 — emsdk, vendored + pinned.** The [emsdk](https://github.com/emscripten-core/emsdk) *manager* (1.1 MB of scripts, no binaries) is vendored at tag **6.0.0** as `engine/vendor/emsdk-6.0.0/` — same convention as the other vendored deps. The toolchain binaries (~270 MB) are **not** committed: `.gitignore` covers `upstream/`, `downloads/`, `node/`, `.emscripten*`, and `task setup-emsdk` fetches them reproducibly (`./emsdk install 6.0.0 && ./emsdk activate 6.0.0` — version-addressed, idempotent). Bumping the toolchain = vendoring a new `emsdk-X.Y.Z/` dir + updating the pins in the Taskfile, in one commit.

New Taskfile entries:

```yaml
setup-emsdk:      # ./emsdk install 6.0.0 && ./emsdk activate 6.0.0 (status-guarded, idempotent)
build-web:        # deps: vendor-unpack, setup-emsdk; . emsdk_env.sh; emcmake cmake -B build-web; cmake --build
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
| `gfx/glpipeline/backend_modern.cc:593` | **resolved (no edit):** Android-only `WFAndroidNotifySurfaceLost` EGL-surface-lost hook, not a GLES header/shader path — stays `__ANDROID__`-only |

`gfx/glpipeline/backend_factory.cc` needs **no edit** — only iOS/macOS are special-cased; the `#else` already yields `ModernBackendInstance()`.

**P1.5 — `hal/emscripten/` (new directory).** Mirror of `hal/linux/` minus the reused files:

| File | Contents |
|------|----------|
| `platform.h` | minimal, like `hal/linux/platform.h` |
| `platform_main.cc` | `main(argc, argv)` → `HALStart(...)`; argv arrives from `Module.arguments` |
| `platform_init.cc` | `_PlatformSpecificInit/UnInit`, `FatalError` (→ `emscripten_console_error` + JS alert), `ParseWindowSwitches`, window-geometry globals; start from a copy of `hal/linux/platform_init.cc` with the FPE handler and X11 bits dropped |
| `input.cc` | `emscripten_set_keydown_callback`/`keyup` + Gamepad API polling → build the joystick-button word and hand it to the same `_HALSetJoystickButtons()` the X11 path uses (`hal/linux/input.cc` holds the state; reuse it if its only Linux-ism is being fed by `mesa.cc`, else fork it) |
| `lifecycle.cc` | `emscripten_set_visibilitychange_callback` → `HALNotifySuspend/Resume` (`hal/lifecycle.h:38-63`); `HALPumpSuspendedEvents()` = no-op |

**P1.6 — suspended-branch `usleep`.** `game.cc:518` calls `usleep(16000)` when suspended. **As-built:** left unchanged — under ASYNCIFY, Emscripten's libc implements `usleep` via `emscripten_sleep`, so the existing call yields correctly (comment at `game.cc:504`); no `#ifdef __EMSCRIPTEN__` edit needed for v1. Under v2 the suspended state simply returns from the tick callback.

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

**P2.2 — ASYNCIFY yield.** ✓ **Done** (`game.cc:501-508`). One line at the top of `WFGame::StepFrame()` (`game.cc:497`), `#ifdef __EMSCRIPTEN__`: `emscripten_sleep(0);` — returns control to the browser once per frame, which is also what presents the frame and fires input callbacks.

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
2. Re-express `RunGameScript()` (def `game.cc:176`; meta loop `game.cc:236-267`) and `RunLevel()` (def `game.cc:673`; `while` loop `game.cc:677-680`) as state transitions; the Forth meta script still runs to completion inside one `META_SCRIPT` tick (it's short — level selection only).
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

**Method (2026-06-12):** no interactive browser was available, so verification used an **automated headless harness**: Chrome (`/usr/bin/google-chrome`, `--headless=new --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`) driven by puppeteer-core against `python3 -m http.server` over `build-web/`, plus headless Node for boot/asset checks. SwiftShader gives a real WebGL 2 context, so render output is genuine. Firefox was not run.

1. `task build-web` exits 0 and produces `wf_game.{js,wasm,data}` + shell; `wasm` + `data` total size recorded.
   - **PASS.** Builds + links clean (after the `wasm-ld` flag fix). Release `-O3` artifact sizes:

     ```
     wf_game.wasm   raw 3,108,719   gz 982,501
     wf_game.js     raw   128,806   gz  34,344
     wf_game.data   raw 2,721,792   gz 484,030   (moon_site01-standalone + snowgoons-standalone preloaded)
     ```

2. Chrome + Firefox via `task serve-web`: `moon_site01.iff` reaches an interactive frame, zero console errors.
   - **PASS (both levels).** `?level=snowgoons-standalone` reaches an interactive, animating frame with **zero GL errors / zero asserts** — `screenshots/2026-06-11-web-first-render-snowgoons.png` (native-equivalent vs `2026-05-31-snowgoons-no-hud-regression-check.png`). **moon_site01 also renders** (`screenshots/2026-06-12-web-moon-site01-render.png`) once the shell passes its VRAM-override args (see the moon note above) — the plan's named `moon_site01.iff` was the wrong file (LVAS bundle); the `-standalone` variant + VRAM args is correct. Firefox not run.

3. Keyboard LEFT/RIGHT move the player screen-left/screen-right (side-scroller C=π/2 recipe holds); gamepad d-pad/stick does the same.
   - **PASS (keyboard).** Holding `ArrowRight` visibly translated the camera/scene between frames (`/tmp` before/during/after capture; before≠during). Gamepad path is coded (`emscripten_window.cc:153-193`) but not hardware-tested headlessly.

4. Audio (SFX + music) plays after first input; no `AudioContext was not allowed to start` warning.
   - **PASS (init).** Console shows `audio: miniaudio v0.11.25 ready` after the click-to-start gesture; no autoplay-blocked warning (the gate creates the `AudioContext` inside the gesture). Headless Node reports "running silent" — expected (no WebAudio). Actual SFX audibility not asserted headlessly.

5. Hide the tab 10 s, return: engine resumes, no delta-time explosion.
   - **PENDING (coded).** `VisibilityCallback` → `HALNotifySuspend/Resume` is wired (`emscripten_window.cc:98-107`); not exercised in the headless harness.

6. Set a hi-score, hard-reload the page: score persisted (IDBFS).
   - **PENDING (coded).** IDBFS mount + `FS.syncfs` wired (`platform_main.cc`, `hscore.cc` → `/save/qbert_hiscores.txt`). Not round-tripped: snowgoons doesn't set hi-scores (a qbert-family feature); needs a save+reload run on a qbert level.

7. Page interactive < 10 s on DevTools "Fast 3G" throttling.
   - **PENDING.** Not throttle-measured. On localhost the ~1.5 MB gzip wasm+js + ~0.5 MB gzip data is interactive in ~1-2 s.

8. ASYNCIFY tax table v1 columns filled (naïve + `ASYNCIFY_ONLY`): size raw/gzip, instrumented-function count, frame p50/p95/p99, `asyncify_*` flamegraph share, startup-to-interactive.
   - **PARTIAL.** Size row captured (step 1). The `-O3` link barely moved the wasm (compile-time `-O3` already dominates), which points at ASYNCIFY instrumentation as the remaining bulk — so `-sASYNCIFY_ADVISE` / `ASYNCIFY_ONLY` narrowing + the frame-time profiling rows remain to be run.

9. **(v2)** Final link flags contain no `-sASYNCIFY`; loop driven by `emscripten_set_main_loop()`; v2 profiling column filled and v1-vs-v2 delta summarized in the investigation.
   - **NOT STARTED** — Phase 7.
10. **(v2)** Completing a level transitions through the state machine to the next level without a page reload.
    - **NOT STARTED** — Phase 7.
11. **(v2)** Linux native build still passes its normal run (`wf_game -L moon_site01.iff` boots and plays) — the inversion didn't fork behaviour.
    - **NOT STARTED** — Phase 7. (Native `wf_game` parity at the level-load layer was incidentally confirmed: the LVAS-bundle mis-load asserted identically on native and web.)
