# Plan — Editor app shell (`wf-edit`: Dear ImGui host + embedded engine viewport + read-only Y.Doc)

**Date:** 2026-05-20
**Status:** **Acked 2026-05-20 (Option B). Implementing.** Vendoring confirmed; scope = shell **+ read-only Y.Doc** (Outliner reads the CRDT doc; viewport renders a normally-loaded level; the full CRDT→engine bridge is the next plan).
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

### 4. Read-only Y.Doc → Outliner (Option B)

- `levtree parse <level>.lev` (subprocess) → JSON → C++ parse → build `wfcrdt::Doc` (`content` = `OBJ` maps with field sub-data, per the CRDT schema).
- **Outliner lists actor names read from the `Doc`** (not from the engine `Level`). Selecting one shows its name in Properties.
- **Gate:** Outliner populated from the CRDT doc; counts match the level (snowgoons 36 / smb 22). Screenshot. ASan over the parse→Doc build.

### 5. Lifecycle + stability

- Window-close → `HALRequestClose()` → clean `UnloadLevel` + `WFGame` + `Doc` teardown (reuse [host-GL e2e/UnloadLevel LIFO learnings](2026-05-18-host-gl-e2e-harness-and-unload-fix.md)).
- ASan over open→load→step→unload→close; multi-cycle stability. X11 focus reaches ImGui (cf. [project_keyboard_focus_fix](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_keyboard_focus_fix.md)).

### 6. Docs + status sync

- Plan `**Status:**` → Done w/ actuals; [wf-status.md](../../wf-status.md) one-sentence Summary + Active row; [design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) "Editor shell" milestone done; next plan = the CRDT→engine bridge (Option C).

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
- **Property panel widgets** — `showAs`-driven dispatch over the OAD (x/y/z vec3 widget, dropdowns, colour, mailbox picker).
- **Networking/relay, chat, awareness/presence, blob storage, lobby** — separate design-doc milestones.
- **Wayland / mobile host embedding** — v2+.

---

## Cross-references

- Parent: [Collaborative editor design § v1 milestones](../investigations/2026-05-18-collaborative-level-editor-design.md) (line 657); mockups (line 27, 60); CRDT schema (line 425).
- Embed predecessors: [external GL context](2026-05-18-engine-external-gl-context.md), [frame-step API](2026-05-18-engine-frame-step-api.md), [host-GL e2e + UnloadLevel fix](2026-05-18-host-gl-e2e-harness-and-unload-fix.md).
- Backend: [engine mutation API](2026-05-19-engine-mutation-api.md), [`.lev`↔Y.Doc translator](2026-05-20-iff-lev-ydoc-translator.md), [wfcrdt wrapper](2026-05-19-wfcrdt-cpp-raii-wrapper.md).
- External: [Dear ImGui](https://github.com/ocornut/imgui), [GLFW](https://www.glfw.org/), [nlohmann/json](https://github.com/nlohmann/json), [ImGui docking](https://github.com/ocornut/imgui/wiki/Docking).
- Memory: [feedback_plans_before_implementation](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plans_before_implementation.md), [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md), [feedback_no_giant_vendor](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_no_giant_vendor.md), [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md), [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md), [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md), [project_engine_runnable](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_engine_runnable.md), [project_keyboard_focus_fix](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_keyboard_focus_fix.md), [project_tools_language](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_tools_language.md).
