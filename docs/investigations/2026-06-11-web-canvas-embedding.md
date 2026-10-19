# Embedding the World Foundry engine in a web page

**Date:** 2026-06-11
**Question:** Can `wf_game` run in a browser `<canvas>`? How, what does it look like, what are the hard parts, and how long would it take?

---

## Verdict

**Yes — and the engine is unusually well positioned for it.** The path is Emscripten → WebAssembly + WebGL 2, reusing the existing Android GLES3 render path. The codebase survey found no blocking dependencies:

- **Single-threaded game runtime** — no pthread/Worker conversion needed (the only threaded code is wf-edit's WebRTC collab layer, which is editor-only and already excluded by `WF_ENABLE_EDITOR=OFF`).
- **Modern shader pipeline** — the production renderer (`wfsource/source/gfx/glpipeline/`) has zero desktop-only GL calls (no `glBegin`, `glPushMatrix`, display lists). The Android build already targets GLES 3.0, which is exactly WebGL 2's feature set. The remaining `glBegin` usage lives only in the `DESIGNER_CHEATS` debug HUD (`wfsource/source/gfx/gl/display.cc:387` etc.).
- **Tiny asset bundles** — `cd_full.iff` is 4.6 MB, single levels 1.9–3.3 MB. Trivially web-deliverable; no streaming infrastructure required.
- **Portable dependencies** — Jolt 5.5.0 (pure C++), zForth (pure C), miniaudio 0.11.25 (**ships a Web Audio / Emscripten backend**), STB headers. Lua/QuickJS/Wren also compile cleanly to wasm if wanted later. Only WAMR has x86-64 inline asm (`CMakeLists.txt:388`), and it's simplest to build the web target Forth-only.
- **Clean HAL seam** — platform code is isolated under `wfsource/source/hal/<platform>/` (Linux 837 LOC, Android 808 LOC) and selected by a CMake `if(ANDROID)/elseif(IOS)/...` block (`CMakeLists.txt:665–690`). A `hal/emscripten/` directory slots in the same way, est. 300–500 LOC.

**Estimated effort: ~2–3 weeks to a shippable v1** (ASYNCIFY main loop), with a first-render milestone inside week 1, **plus a committed ~1-week v2 that replaces ASYNCIFY with a proper state-machine main loop**. The inversion is required scope — ASYNCIFY is a shipping vehicle for v1, not the end state. Breakdown below.

---

## How: the architecture

```
┌─────────────────────────────────────────────────────────┐
│ Browser                                                  │
│  ┌────────────────────────────────────────────────────┐  │
│  │ index.html                                          │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │ <canvas id="canvas">                          │   │  │
│  │  │                                                │   │  │
│  │  │   WebGL2 context ◀── GLES3 calls ◀─┐           │   │  │
│  │  └────────────────────────────────────│──────────┘   │  │
│  │                                        │              │  │
│  │  wf_game.js (Emscripten glue)          │              │  │
│  │  wf_game.wasm ── engine + Jolt + zForth + miniaudio   │  │
│  │  wf_game.data ── cd.iff preloaded into MEMFS          │  │
│  │                                                       │  │
│  │  requestAnimationFrame ──▶ StepFrame()                │  │
│  │  KeyboardEvent/Gamepad  ──▶ hal/emscripten/input.cc   │  │
│  │  Web Audio              ◀── miniaudio backend         │  │
│  │  IndexedDB (IDBFS)      ◀── savegames                 │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

Five pieces of work:

### 1. CMake `if(EMSCRIPTEN)` block

Emscripten ships its own CMake toolchain file; the build becomes:

```sh
emcmake cmake -B build-web -DCMAKE_BUILD_TYPE=Release
cmake --build build-web
```

The new block mirrors the Android one: select `hal hal/emscripten` in `WF_DIRS`, force `WF_ENABLE_EDITOR=OFF`, `WF_DEBUG_BRIDGE=OFF`, `WF_REST_API=OFF`, scripting = zForth only (skip WAMR's inline asm entirely). Link flags: `-sMAX_WEBGL_VERSION=2 -sASYNCIFY --preload-file cd.iff`.

### 2. `wfsource/source/hal/emscripten/` (new, ~300–500 LOC)

By analogy with `hal/android/`:

| File | Replaces | Approach |
|------|----------|----------|
| `platform.cc` | X11/EGL init | `emscripten_webgl_create_context()` on `#canvas` ([html5.h API](https://emscripten.org/docs/api_reference/html5.h.html)) |
| `asset_accessor_mem.cc` | `asset_accessor_posix.cc` | Read from MEMFS (`--preload-file` puts cd.iff there); plain POSIX `open/read` works as-is, so this may be a thin alias |
| `input.cc` | X11 key events | `emscripten_set_keydown_callback` + Gamepad API → existing `kBtn*` mapping |
| `audio.cc` | ALSA init | Reuse `audio/linux/` wrappers — miniaudio's Emscripten backend does the work; one tweak: Web Audio must start after a user gesture (resume `AudioContext` on first click/keypress) |
| `lifecycle.cc` | suspend/resume | Wire `visibilitychange` to the existing `HALNotifySuspend()` hooks (`wfsource/source/hal/lifecycle.h:38–63`) |

### 3. GL header selection

`wfsource/source/gfx/gl/display.cc:32–38` picks `<GLES3/gl3.h>` for `__ANDROID__`, desktop `<GL/gl.h>` otherwise. Widen the condition to `defined(__ANDROID__) || defined(__EMSCRIPTEN__)` — Emscripten ships the GLES3 headers and maps them onto WebGL 2. The `RENDERER_GLES`/`RENDERER_PIPELINE_GLES` defines from the Android branch of `CMakeLists.txt:111–128` apply unchanged.

### 4. Main loop (the one real refactor — see Difficulties)

Browsers never let a page block: the engine must return to the event loop every frame so `requestAnimationFrame` drives rendering. The engine's loop is nested three deep and blocking:

- `RunGameScript()` — `for(;;)` meta loop, runs the Forth shell script then a level (`wfsource/source/game/game.cc:233–268`)
- `RunLevel()` — `while(!LevelDone()...)` (`game.cc:661–674`)
- `StepFrame()` — one update+render tick (`game.cc:494–640`)

**v1: ASYNCIFY (shipping vehicle, not end state).** Emscripten's [ASYNCIFY](https://emscripten.org/docs/porting/asyncify.html) instruments the wasm so a deep call stack can unwind to the browser and resume next frame — insert one `emscripten_sleep(0)` in `StepFrame()` and the nested loops work unmodified. Cost: ~30–50 % larger wasm and CPU overhead on every unwind/rewind. Acceptable to get v1 in front of people quickly; not acceptable to keep.

**v2: state-machine inversion (committed scope).** Restructure into a state machine driven by `emscripten_set_main_loop()`:

```
BOOT → META_SCRIPT → LOAD_LEVEL → IN_LEVEL ─┬→ UNLOAD → META_SCRIPT (next level)
                          (one rAF tick each ⤴)  └→ EXIT
```

The scope is exactly two loops — the editor's frame loop at `game.cc:476` is `WF_ENABLE_EDITOR`-only and excluded from the web build:

1. `RunGameScript()`'s `for(;;)` meta loop (`game.cc:233–268`). The Forth meta script (`interpreter->RunScript`) runs to completion to select the next level — it's short and can execute synchronously inside one callback (`META_SCRIPT` state), so the Forth interpreter itself doesn't need to become resumable.
2. `RunLevel()`'s `while(!LevelDone() && ContinueRequested() && ...)` (`game.cc:661–674`). Its loop condition becomes the `IN_LEVEL → UNLOAD` transition.

`StepFrame()` already exists as a clean single-tick function, so the work is hoisting the loop state (current level, disk file/TOC cursor, script pointer) into `WFGame` members and adding the transition logic. Bonus beyond dropping the ASYNCIFY tax: the inverted loop benefits the other callback-driven platforms too — iOS Phase 2C needs exactly this shape for its `CADisplayLink` tick, so this refactor pays twice.

### Profiling: quantifying the ASYNCIFY tax

ASYNCIFY's cost has two components, and v1→v2 is a natural A/B experiment — measure both sides and record the numbers in this doc.

**What ASYNCIFY costs (mechanism):**

- **Code size:** every function that can be on the stack during an unwind gets instrumented with save/restore logic. The [Emscripten docs](https://emscripten.org/docs/porting/asyncify.html) cite roughly **+50 % wasm size** on instrumented code in the typical case; whole-binary impact depends on how much of the call graph is reachable from the yield point.
- **Runtime:** instrumented functions carry extra branching even when not unwinding, and each frame pays a full stack unwind + rewind through the `RunGameScript → RunScript → RunLevel → StepFrame` chain. Published worst cases approach ~2× on hot instrumented code; our yield is once per frame at the bottom of a shallow chain, so the expected hit is far smaller — but that's exactly the claim to verify, not assume.

**Containment knobs (apply in v1, before measuring):**

- `-sASYNCIFY_ADVISE` — build-time report of every function being instrumented and why (which call edge makes it unwind-reachable). Run this first; paste the list here.
- `-sASYNCIFY_ONLY=[...]` — whitelist only the actual unwind chain (`main`, `HALStart`, `PIGSMain`, `WFGame::RunGameScript`, `WFGame::RunLevel`, `WFGame::StepFrame`, the zForth `RunScript` path). Since `emscripten_sleep(0)` lives at a known single point, the indirect-call blowup (ASYNCIFY's usual size killer) is *in principle* avoidable. **Measured outcome (see Results): not viable** — `HALStart` reaches `RunGameScript` through PIGS function-pointer task dispatch, so an indirect frame is genuinely on the unwind stack. The narrowing can't be proven safe without restructuring, which is what v2 does anyway.

**Measurements to capture (fill in during implementation):**

| Metric | How | v1 ASYNCIFY (naïve) | v1 + `ASYNCIFY_ONLY` | v2 inverted |
|--------|-----|--------------------:|---------------------:|------------:|
| `wf_game.wasm` size (raw / gzip) | `ls -l`, `gzip -9 \| wc -c` | **3.11 MB / 982 KB** | n/a (see note) | _TBD (Phase 7)_ |
| Instrumented function count | `-sASYNCIFY_ADVISE` output | **3,995** | n/a (see note) | 0 |
| Frame time p50 / p95 / p99 (ms) | `performance.now()` around the tick, 60 s capture | _needs real-GPU browser_ | n/a | _TBD (Phase 7)_ |
| Unwind/rewind share of frame | Chrome DevTools Performance with `--profiling-funcs` build | _needs real-GPU browser_ | n/a | n/a |
| Startup → first interactive frame (ms) | `performance.mark()` at `onRuntimeInitialized` | ~1–2 s on localhost (not throttle-measured) | n/a | _TBD (Phase 7)_ |

**Results (2026-06-12, measured on the `-O3` web build):**

- **Size:** `wf_game.wasm` is **3,108,719 B raw / 982,501 B gz**. Adding link-time `-O3` over the compile-time `-O3` objects barely moved it — the bulk is ASYNCIFY instrumentation, not unoptimised code.
- **Instrumentation:** `-sASYNCIFY_ADVISE` reports **3,995 instrumented functions**. Only **4** are `invoke_*` indirect-call trampolines — but those four imports "can change the state", so ASYNCIFY's initial scan instruments their whole reachable closure (Jolt hash tables, STL, etc.). This is the indirect-call blowup the plan flagged.
- **`ASYNCIFY_ONLY` is not viable as written.** The hoped-for whitelist (`main` → `HALStart` → `RunGameScript` → `RunLevel` → `StepFrame`) is real, but `HALStart` reaches `RunGameScript` (`main.cc:471`) **through PIGS's function-pointer task/message dispatch**, so the unwind stack genuinely includes an indirect frame. Neither `ASYNCIFY_ONLY` nor `ASYNCIFY_IGNORE_INDIRECT` is provably safe without restructuring that dispatch — applying either blindly risks silent state corruption. **This is the empirical case for v2:** the state-machine inversion (Phase 7) removes ASYNCIFY entirely instead of fighting its closure, and is the correct end state — exactly as the plan committed.
- **Frame-time / flamegraph rows** require a real-GPU browser run; the headless SwiftShader rasteriser used for render verification is CPU-bound and unrepresentative of frame cadence, so quoting its numbers would mislead. Deferred to a manual capture (and the v2 A/B).

Method notes: build with `--profiling-funcs` (keeps function names in the wasm) for the flamegraph runs only — strip it for the size measurements. Use the same level, same machine, same Chrome version across columns. 60 s capture, discard the first 5 s (JIT warm-up). The v1↔v2 size/instrumentation delta lands with Phase 7.

### 5. HTML shell + hosting

Static files only — `index.html`, `wf_game.js`, `wf_game.wasm`, `wf_game.data`. Hosting fits the existing Cloudflare Pages pipeline (worldfoundry site); needs two response headers if we ever enable threads (`Cross-Origin-Opener-Policy` / `Cross-Origin-Embedder-Policy`), none for the single-threaded build. Cost: $0 on the free tier at these sizes.

---

## What it looks like

### The page

```
┌──────────────────────────────────────────────────────┐
│  World Foundry — moon_site01                          │
│  ┌────────────────────────────────────────────────┐   │
│  │                                                │   │
│  │                                                │   │
│  │              ▶ Click to start                  │   │  ← user-gesture gate
│  │            (canvas, 16:9, WebGL2)              │   │    (unlocks audio)
│  │                                                │   │
│  │                                                │   │
│  └────────────────────────────────────────────────┘   │
│  Loading cd.iff ▓▓▓▓▓▓▓▓▓░░░░ 72%        🔊  ⛶       │
└──────────────────────────────────────────────────────┘
```

### The embed (any site, including itch.io-style iframes)

```html
<canvas id="canvas" width="1280" height="720"></canvas>
<script src="wf_game.js"></script>
<script>
  Module = { canvas: document.getElementById('canvas'),
             arguments: ['-L', 'moon_site01.iff'] };
</script>
```

The existing `-L <level>.iff` CLI convention carries over via `Module.arguments`, so one build can serve many level pages.

### Player-visible behaviour

- ~7 MB total download (wasm + 4.6 MB cd.iff), loads in a few seconds on any reasonable connection
- Keyboard (arrows/WASD → `kBtnStepLeft`/`kBtnStepRight` etc.) and USB/Bluetooth gamepads via the Gamepad API
- Audio starts on first input (browser autoplay policy)
- Tab-hidden → engine suspends via the existing lifecycle hooks; tab-visible → resumes
- Savegames persist in IndexedDB via Emscripten's IDBFS (the `savegame/linux/` POSIX code works against it after an `FS.mount` + sync)

---

## Biggest difficulties (ranked)

| # | Difficulty | Severity | Mitigation |
|---|-----------|----------|------------|
| 1 | **Blocking nested main loop** — browsers require returning to the event loop every frame; `RunGameScript`→`RunLevel`→`StepFrame` never returns | High (the core refactor) | ASYNCIFY ships v1 (near-zero code change); **committed v2** replaces it with the state-machine inversion above |
| 2 | **X11/GLX window path** — `gfx/gl/mesa.cc:133–160` does raw `XOpenDisplay`/`glXCreateContext`; no SDL/GLFW layer to lean on | Medium | Bypass entirely: `hal/emscripten/platform.cc` creates the context with one `emscripten_webgl_create_context()` call |
| 3 | **Desktop-GL residue** — Linux build compiles against `<GL/gl.h>`; debug HUD uses `glBegin` | Medium‑low | Production pipeline verified clean (grep of `glpipeline/` found zero fixed-function calls); take the Android `GLES3` branch and leave `DESIGNER_CHEATS` off for web |
| 4 | **Input mapping** — keyboard/gamepad arrive as DOM events, not X11 | Low | `emscripten/html5.h` callbacks → existing `kBtn*` enum; Gamepad API is poll-based, matching the engine's per-frame input read |
| 5 | **Audio autoplay policy** — `AudioContext` is suspended until a user gesture | Low | "Click to start" gate; miniaudio handles the backend |
| 6 | **Savegames / non-asset file I/O** — POSIX writes need a persistent FS | Low | IDBFS mount + `FS.syncfs` after save; MIDI files ride inside the preload bundle |
| 7 | **WAMR inline x86-64 asm** | Nil | Don't build it for web; zForth is the canonical scripting engine anyway |


> **Superseded 2026-08-26 (row 5).** The "click to start" gate is gone — the
> engine now autostarts from `onRuntimeInitialized`. Audio no longer rides on
> the start gesture: `web/shell.html` wraps `AudioContext` to capture every
> context miniaudio builds and resumes them on the visitor's first
> pointer/key/touch event. The rest of this table still holds.

Not difficulties (verified, pleasant surprises): no threading in the game runtime, no networking in the game runtime, miniaudio already has the Web Audio backend, asset bundles are megabytes not gigabytes, and the AssetAccessor abstraction (`wfsource/source/hal/asset_accessor.hp:41–60`) means asset loading may "just work" through MEMFS with the existing POSIX accessor.

---

## Effort estimate

| Phase | Work | Estimate |
|-------|------|----------|
| 1. Build skeleton | emsdk setup, CMake `if(EMSCRIPTEN)` block, stub HAL dir, link successfully | 2–3 days |
| 2. First render | WebGL2 context, GLES3 header path, ASYNCIFY loop, static scene on canvas | 2–4 days |
| 3. Assets + scripting | `--preload-file cd.iff`, zForth meta script boots, level loads | 1–2 days |
| 4. Input | Keyboard + gamepad → `kBtn*` | 1–2 days |
| 5. Audio | miniaudio Web Audio + gesture gate | 0.5–1 day |
| 6. Polish + ship | Lifecycle/visibility, IDBFS saves, HTML shell, deploy to Pages | 2–3 days |
| **v1 total** | | **~9–15 working days (2–3 weeks)** |
| 7. **v2: main-loop inversion** (committed, not contingent) | State machine in `WFGame`, hoist loop state, drop `-sASYNCIFY`, re-verify | 3–5 days |
| **v1 + v2 total** | | **~12–20 working days (3–4 weeks)** |

Risk buffer lives mostly in phase 2: if the GLES3 pipeline trips on a WebGL 2 restriction the Android driver tolerated (e.g. unsupported texture format, non-constant loop index in a shader), add 2–3 days of shader/format fixes.

---

## Verification (for the implementation pass)

1. `emcmake cmake -B build-web && cmake --build build-web` exits 0 and produces `wf_game.{js,wasm,data}`.
2. `python3 -m http.server` + Chrome and Firefox: `moon_site01.iff` reaches an interactive frame with no console errors; screenshot attached.
3. Keyboard left/right moves the player the correct screen direction (side-scroller recipe: C=π/2 mapping holds in browser).
4. Audio plays after first click; no `AudioContext was not allowed to start` warning remains.
5. Hide tab 10 s, return: engine resumed, no time-step explosion (delta-time clamped).
6. Save, reload page, load: savegame persisted via IDBFS.
7. `wf_game.wasm` + `.data` total size recorded; page interactive < 10 s on throttled "Fast 3G" profile.
8. ASYNCIFY tax table (Profiling section above) filled in for the v1 columns: wasm size raw/gzip, instrumented-function count from `-sASYNCIFY_ADVISE`, frame-time p50/p95/p99, flamegraph share of `asyncify_*` frames.
9. **(v2)** Final link flags contain no `-sASYNCIFY`; loop driven by `emscripten_set_main_loop()`; v2 column of the tax table filled in and the v1-vs-v2 delta summarized in one line.
10. **(v2)** Level transition works through the state machine: completing a level returns to the meta script and loads the next level without a page reload.

---

## References

- Emscripten html5.h API (context, input, visibility): [emscripten.org/docs/api_reference/html5.h.html](https://emscripten.org/docs/api_reference/html5.h.html)
- ASYNCIFY: [emscripten.org/docs/porting/asyncify.html](https://emscripten.org/docs/porting/asyncify.html)
- Emscripten + WebGL2/GLES3 notes: [emscripten.org/docs/porting/multimedia_and_graphics/OpenGL-support.html](https://emscripten.org/docs/porting/multimedia_and_graphics/OpenGL-support.html)
- miniaudio backends (Web Audio listed): [miniaud.io/docs/manual/index.html](https://miniaud.io/docs/manual/index.html)
- Emscripten file packaging (`--preload-file`, IDBFS): [emscripten.org/docs/porting/files/packaging_files.html](https://emscripten.org/docs/porting/files/packaging_files.html)
