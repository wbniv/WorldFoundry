# Plan — Editor app shell (`wf-edit`: Dear ImGui host + embedded engine viewport + read-only Y.Doc)

**Date:** 2026-05-20
**Status:** **DONE 2026-05-20 — shell complete (M1–M6).** Shell (M1) → embedded engine viewport (M2) → dockspace + panels (M3) → **read-only Y.Doc → Outliner (M4)** → **lifecycle + stability (M5)** → docs/status sync (M6). Next plan: the **CRDT→engine bridge (Option C)** — observe `Doc` edits → `wfmut` so the viewport reflects Y.Doc changes. `wf-edit` shells out to `levtree parse <lev>`, builds a `wfcrdt::Doc` (recursive chunk schema), and the Outliner lists actor names read back from the Doc — verified on snowgoons (36 actors; [screenshot](../../tests/screenshots/wfedit_m4_outliner.png), selection→Properties [screenshot](../../tests/screenshots/wfedit_m5_select.png)). **M5:** the **full editor lifecycle** (open→load→step×N→unload→close) is **ASan+UBSan+LeakSanitizer-clean** (no leaks, no suppressions) and stable across multi-cycle headless runs; window-close teardown is self-contained (RunEditor breaks its loop when the frame callback returns false → `UnloadLevel`), the frame callback is unregistered on shutdown. Built via `build-editor/` (CMake Debug; `-flto=thin` is Release/Clang-only). Remaining: M6 status sync. The full CRDT→engine bridge (Option C) is the next plan.
**Estimate:** ~1–2 weeks for the shell ([design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) line 657) + a few days for the read-only Y.Doc population. Kept on the average-programmer scale per [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md).
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

The collaborative editor's whole **backend** is in place:

| Layer | Status |
|---|---|
| Yrs C ABI (`libwfcrdt.a`) + wfcrdt C++ RAII wrapper | ✅ |
| `wfmut::` engine mutation API | ✅ |
| `.lev` ↔ Y.Doc translator (`levtree-rs`) | ✅ (2026-05-20) |
| Engine embed APIs (Phase 0b) | ✅ — [external GL context](2026-05-18-engine-external-gl-context.md) (`gfx/host_gl_context.h`, `InitWithExistingContext`), [frame-step API](2026-05-18-engine-frame-step-api.md) (`WFGame::StepFrame`/`LoadLevel`/`UnloadLevel`), `HALInjectJoystickButtons`, de-globaled `theGame` |

Missing is the **application that hosts it**: a windowed Dear ImGui app embedding the engine viewport. This plan delivers the shell — window + embedded viewport + dockspace + panels — **and** (Option B) a read-only Y.Doc: the level is loaded into a `wfcrdt::Doc` via `levtree` and the Outliner reads from it, proving the `levtree → Y.Doc` path in the app. The viewport still renders a **normally-loaded** level (`WFGame::LoadLevel`); wiring the Y.Doc *back into* the engine (observe → `wfmut`) is the next plan (the CRDT bridge).

### What exists to build on

- **`libwfengine.a`** — Phase-0a split; [`wf_host_gl_e2e_test`](../../CMakeLists.txt) (`engine/wf_host_gl_test/host_gl_e2e_test.cc`) is the precedent for an external `main()` linking `wfengine` + driving `StepFrame`.
- **The embed handshake** ([host_gl_context.h](../../wfsource/source/gfx/host_gl_context.h)): host `SetHostGLContext({display, win, context, valid:true})` **before** `WFGame` ctor; `mesa.cc::InitWindow` dispatches to `InitWithExistingContext`; `XEventLoop`/`HALCloseWindow` early-bail; close via `HALRequestClose()`. v1 single-`WFGame`.
- **`wfcrdt::Doc`** + **`levtree parse`** (`.lev` → chunk-tree JSON) — the two halves Option B glues together.

### Not yet present (this plan adds)

- **Dear ImGui** and a **windowing lib** — neither vendored; GLFW/SDL2 dev libs not installed (only GL 1.2 / Mesa). ImGui ships no X11 backend, so GLFW is required. (github is reachable — submodules work, as for [y-crdt/Corrosion](2026-05-18-yrs-c-abi-binding.md).)
- **A C++ JSON parser** — to read `levtree`'s JSON; the debug bridge exposes none reusable.
- **An editor-app entry point** — `WF_ENABLE_EDITOR` today merely renames `wf_game`→`wf-edit`; there is no app `main()`.

---

## Decisions

| # | Decision | Choice | Reason |
|---|---|---|---|
| D1 | The app binary | **`wf-edit` = the editor application** (new target, own `main()`, links `libwfengine.a` + GLFW + ImGui + `libwfcrdt.a`). **`wf_game` stays the engine runtime** — drop the placeholder `OUTPUT_NAME` rename. | Per Will: `wf-edit` *is* the editor, `wf_game` *is* the game-engine runtime. The current rename conflated them; this plan separates them cleanly (the Phase-0a static lib + the `wf_host_gl_e2e_test` precedent make the new target straightforward). |
| D2 | Windowing | **Vendor GLFW** (submodule); `GLFW_EXPOSE_NATIVE_X11`/`GLX` → extract `Display*`/`Window`/`GLXContext` → `SetHostGLContext`. | ImGui's standard backend; small (< the [no-giant-vendor cap](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_no_giant_vendor.md)); builds against the present X11/GL libs. Raw X11 would mean hand-writing an ImGui platform backend — rejected. |
| D3 | UI toolkit | **Vendor Dear ImGui** (submodule) + `imgui_impl_glfw` + `imgui_impl_opengl3`. `imgui_markdown` deferred to the chat plan. | Design doc's locked v1 choice. |
| D4 | Embedding model | GLFW owns window+GLX context → `SetHostGLContext` **before** `WFGame` ctor → loop: `glfwPollEvents` → `StepFrame(false)` → ImGui new-frame/panels/render → `glfwSwapBuffers`. First cut: engine fullscreen + ImGui overlay; then engine→FBO→`ImGui::Image` in a Viewport panel. | Matches the host_gl_context handshake exactly. |
| D5 | Read-only Y.Doc (Option B) | Editor runs `levtree parse <level>.lev` (subprocess, as the build pipeline shells out to its tools) → JSON → parse in C++ → build a `wfcrdt::Doc` (`content` = array of `OBJ` maps, per the CRDT schema). The **Outliner reads actor names from the `Doc`**. | Proves `levtree → Y.Doc` in the app without the bridge. Subprocess keeps the engine/editor [Rust-free](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md) at the link level. Editor build enables `WF_ENABLE_CRDT` (it owns the Doc). |
| D6 | JSON parser | **Vendor a header-only JSON lib** (nlohmann/json single header) for the C++ side of D5. | Tiny, single file; no reusable JSON util in the engine. Confirm during impl that nothing simpler already links. |
| D7 | Viewport ≠ Y.Doc (v1) | The viewport renders the level the **engine** loaded (`WFGame::LoadLevel`). The Y.Doc is read-only and drives only the Outliner. Making the viewport reflect the Y.Doc (observe → `wfmut`) is **Option C, the next plan**. | Keeps this plan bounded; the CRDT→engine bridge is its own substantial piece. The viewport and Outliner show the *same* level, not yet bidirectionally wired. |
| D8 | Build gating | GLFW/ImGui/JSON/`wf-edit` build **only** under `WF_ENABLE_EDITOR=ON` (which also turns on `WF_ENABLE_CRDT`). Default `task build` stays engine-only, byte-identical to today. | Matches established editor-stack gating; shipped game builds carry none of it. |
| D9 | Platform | **Linux/X11 only for v1.** | `host_gl_context` is X11/GLX; matches the [external-GL plan's D8](2026-05-18-engine-external-gl-context.md). |

---

## Milestones (each its own commit, per [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md))

### 1. Vendor toolkit + empty window

- GLFW + Dear ImGui submodules (`third_party/{glfw,imgui}`); vendor the JSON header.
- New `wf-edit` target (`engine/wf_edit/main.cc` + CMake) under `WF_ENABLE_EDITOR`, linking GLFW + ImGui. **No engine yet.** Drop the `wf_game`→`wf-edit` `OUTPUT_NAME` rename so `wf_game` keeps its name.
- Open a GLFW window; ImGui frame loop drawing one "WF Editor" window; `glfwSwapBuffers`.
- **Gate:** default `task build` unchanged/engine-only; `WF_ENABLE_EDITOR=ON` builds `wf-edit` that opens a window. Screenshot ([feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md)).

### 2. Embed the engine viewport (fullscreen) — the tracer bullet

- Extract GLFW native handles → `SetHostGLContext({…, valid:true})` **before** `WFGame` ctor.
- Construct `WFGame`, `LoadLevel("snowgoons-blender")` (fallback `smb_w1_1`).
- Loop: `glfwPollEvents` → `StepFrame(false)` → ImGui overlay (FPS, level name) → render → `glfwSwapBuffers`.
- **Gate:** window shows **live engine pixels + ImGui overlay**. Screenshot. Proves the embed handshake end-to-end (the [external-GL plan's deferred ImGui smoke #3](2026-05-18-engine-external-gl-context.md)).

### 3. Dockspace + viewport panel + stub Properties

- ImGui docking; dockspace: **Viewport** (center), **Outliner** (left), **Properties** (right).
- Engine → **FBO** → `ImGui::Image` in the Viewport. **Risk/possible engine change:** confirm `StepFrame` renders into the bound framebuffer; if the GL backend hard-binds FBO 0, add a host-FBO hook (root-cause per [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md), not a workaround).
- Properties: placeholder showing the selected actor's name.
- **Gate:** dockable layout, engine live in the Viewport. Screenshot.

### 4. Read-only Y.Doc → Outliner (Option B) — ✅ DONE 2026-05-20

- `levtree parse <level>.lev` (subprocess via `popen`) → JSON (vendored [nlohmann/json](../../third_party/json/README.md) v3.11.3) → build `wfcrdt::Doc` in [`engine/wf_edit/level_doc.cc`](../../engine/wf_edit/level_doc.cc): `meta { level_name, format_version }` + `content` = `Y.Array<chunk>`, each chunk the recursive `Y.Map { chunk_type, children|text }` node, LVL wrapper dropped.
- **Outliner lists actor names read back from the `Doc`** (each top-level chunk's `NAME` child text), `--leveltree=` selectable, defaulting to snowgoons-blender (matches the viewport `--level=`, per D7). Selecting one shows its name in Properties.
- **Gate met:** Outliner shows **36** actors for snowgoons, sourced from the CRDT doc ([screenshot](../../tests/screenshots/wfedit_m4_outliner.png)); ASan+UBSan clean over `LoadLevelTreeIntoDoc`→`ReadActorNames`. (The gate's "smb 22" reference is live: `smb_w1_1.lev` is under active authoring — the loader matches the file's current OBJ count whatever it is.)
- **Notes for M5+:** built in `build-editor/` (CMake **Debug** + GCC; the engine's `-flto=thin` Release flag is Clang-only). The `wfcrdt::Input::Kind` enum's `Bool` enumerator was renamed `Boolean` — Xlib's `#define Bool int` (pulled in ahead of `wfcrdt.hpp` in the editor) would otherwise mangle it; `Map`/`Array::valid()` added for the nested-read views. Required the [yffi nested-map workaround](2026-05-19-wfcrdt-cpp-raii-wrapper.md) (prefilled `yinput_ymap` loops in yrs 0.9.3).

### 5. Lifecycle + stability — ✅ DONE 2026-05-20 (~40 min wall-clock, much of it the full ASan rebuild + verification)

- **Window-close teardown is self-contained** — no `HALRequestClose()` needed for approach (a): `editor_frame` returns false on `glfwWindowShouldClose`, `WFGame::RunEditor` breaks its loop and runs `UnloadLevel()` + diskfile delete; `main()` then unregisters the frame callback (`SetEditorFrameCallback(nullptr,nullptr)` so the engine's stored `ctx` can't dangle past scope), clears the host-GL registry, and tears down ImGui/GLFW. The `Doc` (a `main`-scope local) is destroyed last. (`HALRequestClose` remains the standalone/engine-polled close path; RunEditor doesn't poll it.)
- **ASan+UBSan+LeakSanitizer-clean** over the **full editor lifecycle** open→load→step×10→unload→close (`build-editor-asan/`, `-DWF_ASAN=ON`): 0 sanitizer reports in 1679 log lines, **no suppressions** — engine + Jolt + ImGui + GLFW + CRDT all clean. Multi-cycle: 5 back-to-back headless runs, all 36-actor + clean-exit.
- **X11 focus → ImGui:** GLFW owns the window and installs the ImGui platform callbacks (`ImGui_ImplGlfw_InitForOpenGL(win, true)`); mesa.cc adopts the existing context and early-bails on window ops, so it never calls `XSetInputFocus` on the GLFW window — the [keyboard-focus-fix](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_keyboard_focus_fix.md) `BadMatch` path doesn't apply here. (Live keystroke/click confirmation is an interactive check; the `--select=N` headless aid exercises the Outliner→Properties data path.)

### 6. Docs + status sync — ✅ DONE 2026-05-20

- Plan `**Status:**` → Done; [wf-status.md](../../wf-status.md) Summary bullet + Active row updated to M1–M6; next plan = the CRDT→engine bridge (Option C). Shipped in commits `942db60` (M1) … `08e2590` (M4), `51d6639` (M5). Spin-off: [Debug builds default to ASan+UBSan](../../CMakeLists.txt) (`8a0ddf0`) — surfaced while ASan-verifying the editor lifecycle. (The [design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) editor-shell milestone tick is left to whoever is mid-authoring its property-panel section — not touched here to avoid colliding with that in-flight work.)

> The full **record/replay session demo** is the capstone of the *whole* editor effort, not this shell — see the [design doc roadmap's closing § Capstone demo](../investigations/2026-05-18-collaborative-level-editor-design.md). M6 is the last milestone of this plan; a screenshot is its proof.

---

## Verification

1. **Default build untouched** — `WF_ENABLE_EDITOR` OFF → same engine binaries, no GLFW/ImGui/JSON symbols.
2. **`WF_ENABLE_EDITOR=ON` builds `wf-edit`** (+ `WF_ENABLE_CRDT`), links engine + GLFW + ImGui + wfcrdt.
3. **Engine renders in-window (step 2) + in a docked panel (step 3); Outliner from the Y.Doc (step 4)** — screenshots ([feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md)); engine is [runnable on Linux](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_engine_runnable.md).
4. **ASan clean** + **clean shutdown** on window close.

---

## Critical files

**Create:** `engine/wf_edit/main.cc` (+ Outliner/Properties/Viewport panels), CMake target + submodule/JSON wiring, `third_party/{glfw,imgui}` + the JSON header, this plan.
**Read (no edits):** [host_gl_context.h](../../wfsource/source/gfx/host_gl_context.h), [mesa.cc](../../wfsource/source/gfx/gl/mesa.cc) (`InitWithExistingContext`), `engine/wf_host_gl_test/host_gl_e2e_test.cc`, [game.cc](../../wfsource/source/game/game.cc) (`StepFrame`/`LoadLevel`), [wfcrdt.hpp](../../engine/crdt/wfcrdt.hpp), [levtree-rs](../../wftools/levtree-rs/).
**Modify:** `CMakeLists.txt` (the `WF_ENABLE_EDITOR` block — new `wf-edit` target, drop the rename, imply `WF_ENABLE_CRDT`), step-6 docs.

---

## Out of scope (each its own later plan)

- **CRDT→engine bridge (Option C)** — observe `Doc` changes → `wfmut`; viewport reflects Y.Doc edits; the next plan.
- **Property panel widgets** — `(ButtonType × showAs)`-keyed dispatch over the OAD. The full widget taxonomy, per-type mockups, and prior-art grounding (the deleted `wfmaxplugins/attrib/` editor + the live `wf_blender` add-on + the [coverage audit](../investigations/2026-04-13-showas-coverage.md)) live in the [design doc § "Prior art" / "Widget gallery"](../investigations/2026-05-18-collaborative-level-editor-design.md). A later plan; the CRDT→engine bridge (Option C) comes first.
- **Networking/relay, chat, awareness/presence, blob storage, lobby** — separate design-doc milestones.
- **Wayland / mobile host embedding** — v2+.

---

## Cross-references

- Parent: [Collaborative editor design § v1 milestones](../investigations/2026-05-18-collaborative-level-editor-design.md) (line 657); mockups (line 27, 60); CRDT schema (line 425).
- Embed predecessors: [external GL context](2026-05-18-engine-external-gl-context.md), [frame-step API](2026-05-18-engine-frame-step-api.md), [host-GL e2e + UnloadLevel fix](2026-05-18-host-gl-e2e-harness-and-unload-fix.md).
- Backend: [engine mutation API](2026-05-19-engine-mutation-api.md), [`.lev`↔Y.Doc translator](2026-05-20-iff-lev-ydoc-translator.md), [wfcrdt wrapper](2026-05-19-wfcrdt-cpp-raii-wrapper.md).
- External: [Dear ImGui](https://github.com/ocornut/imgui), [GLFW](https://www.glfw.org/), [nlohmann/json](https://github.com/nlohmann/json), [ImGui docking](https://github.com/ocornut/imgui/wiki/Docking).
- Memory: [feedback_plans_before_implementation](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plans_before_implementation.md), [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md), [feedback_no_giant_vendor](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_no_giant_vendor.md), [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md), [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md), [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md), [project_engine_runnable](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_engine_runnable.md), [project_keyboard_focus_fix](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_keyboard_focus_fix.md), [project_tools_language](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md).
