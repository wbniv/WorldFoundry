# Implementation plan — engine external GL context (Phase 0b sub-task #2)

**Status:** DONE (commit `a907d79e`) — all 9 steps; host GL context + `HALRequestClose` + e2e harness.

Executes [`docs/plans/2026-05-18-engine-external-gl-context.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-18-engine-external-gl-context.md). That doc is the design + risks; this file is the per-commit execution checklist with corrections from current-code verification.

## Context

The parent plan was written 2026-05-18 with hand-resolved file:line citations. Spot-checks against `HEAD` (`5ecbcbe`) confirm every claim about `mesa.cc` (halDisplay@49, OpenMainWindow@117, attributeList@71, InitWindow@195, HALCloseWindow@480, XEventLoop@456, _closeRequested@57, ProcessXEvents close-button @326/@443, HALWindowCloseRequested@474), `display.cc` (Display::Display@288 calling InitWindow@302, WFInitGL@309, ~Display HALWindowCloseRequested gate@343), and `hal/_input.h:49` (`HALInjectJoystickButtons` shipped in `b0639c5`).

**Three deviations** from the parent plan, all build-system or testing layout:

1. **Linux impl file location.** Plan puts `host_gl_context.cc` at `wfsource/source/gfx/gl/`. But `gfx/gl/` is in `WF_DIRS` for both Linux *and* Android (CMakeLists.txt:80-88) — only iOS excludes it (line 89-102, comment: "X11/GLX stays out"). An unguarded Linux impl here would compile on Android and double-define against the mobile stubs the plan wants in `hal/android/lifecycle.cc`. **Fix**: guard the .cc body with `#if defined(__LINUX__) && !defined(__ANDROID__)`. Lightest deviation; keeps the file where the parent plan filed it.

2. **iOS stub file.** Parent plan says `hal/ios/native_app_entry.mm`. `hal/ios/lifecycle.mm` exists and is the natural symmetry to Android's `hal/android/lifecycle.cc` (where Android stubs go). **Fix**: put the iOS stubs in `hal/ios/lifecycle.mm`.

3. **Smoke-test harness location.** Parent plan says `tests/test_host_gl_context.cc`. `tests/` is Python pytest (`conftest.py`, `test_*.py`, `verify_smb_*.py`). The existing C++ executable build pattern is `engine/<target>/` with its own `build_<target>.sh` (see `engine/wf_game/` + `engine/build_game.sh`). **Fix**: new `engine/wf_host_gl_test/host_gl_test.cc` + `engine/build_host_gl_test.sh`. Optional Python wrapper under `tests/test_host_gl_context.py` can shell out to it and assert exit code (matches existing `verify_smb_walkthrough.py` pattern).

Everything else in the parent plan stands.

## Per-commit checklist

Each numbered step is one commit. Standing consent per [feedback_commit_without_asking](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_without_asking.md); commit at every phase boundary per [feedback_commit_after_each_phase](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md). After each commit, run `task build` and re-launch snowgoons to verify standalone path is unchanged.

### Step 1 — new header + Linux impl skeleton (no behaviour change yet)

Files:
- **NEW** `wfsource/source/gfx/host_gl_context.h` — `struct HostGLContext { void* display; unsigned long win; void* context; bool valid; };` plus `SetHostGLContext / GetHostGLContext / ClearHostGLContext` declarations and `HALRequestClose()` (declared here OR in `hal/lifecycle.h` — pick `hal/lifecycle.h` to keep `HALRequestClose` next to `HALWindowCloseRequested`/`HALCloseWindow`@52/57; the GL-context registry is the only thing the new gfx header declares). Header comment documents: required GLX visual attrs (`GLX_RGBA`, `GLX_DOUBLEBUFFER`, `GLX_DEPTH_SIZE ≥ 1`) cross-referencing `mesa.cc:71` `attributeList`; v1 single-`WFGame`-instance constraint.
- **NEW** `wfsource/source/gfx/gl/host_gl_context.cc` — file-scope `static HostGLContext g_hostCtx{};`; getters/setters/clear; `HALRequestClose()` sets the already-existing `_closeRequested` atomic from `mesa.cc:57` (declared `extern` here, since mesa.cc owns it). Wrap entire body in `#if defined(__LINUX__) && !defined(__ANDROID__)` so Android's glob doesn't pull it.
- **EDIT** `wfsource/source/hal/lifecycle.h` — add `void HALRequestClose(void);` declaration after line 52's `HALWindowCloseRequested`.
- **EDIT** `wfsource/source/hal/android/lifecycle.cc` — add `HALRequestClose()` no-op stub (mirrors `HALCloseWindow` no-op@64). Also add the three `Set/Get/ClearHostGLContext` no-op stubs returning `valid=false` from `Get`. Include `<gfx/host_gl_context.h>`.
- **EDIT** `wfsource/source/hal/ios/lifecycle.mm` — same set of stubs (Objective-C++ but identical C linkage).

Verify: `task build` succeeds. `wf_game` (snowgoons) runs unchanged. Symbols visible: `nm engine/wf_game | grep -E 'SetHostGLContext|HALRequestClose'`.

### Step 2 — `InitWindow` dispatches on `GetHostGLContext().valid`

Files:
- **EDIT** `wfsource/source/gfx/gl/mesa.cc:195` — change `InitWindow(...)` to:
  ```cpp
  bool InitWindow(int /*xPos*/, int /*yPos*/, int /*xSize*/, int /*ySize*/)
  {
      if (GetHostGLContext().valid)
          return InitWithExistingContext();   // implemented in step 3
      OpenMainWindow("World Foundry");
      return true;
  }
  ```
  For this commit, leave `InitWithExistingContext()` as a stub that asserts unreached + returns true so the if-branch compiles but never fires.
- Add `#include <gfx/host_gl_context.h>` near the existing `#include <hal/lifecycle.h>` at mesa.cc:30.

Verify: snowgoons standalone unchanged (no host context set → else-branch).

### Step 3 — implement `InitWithExistingContext`

Files:
- **EDIT** `wfsource/source/gfx/gl/mesa.cc` — implement (above `InitWindow`):
  ```cpp
  static bool InitWithExistingContext()
  {
      const HostGLContext h = GetHostGLContext();
      halDisplay.mainDisplay = static_cast<XDisplay*>(h.display);
      halDisplay.win         = static_cast<Window>(h.win);
      // visInfo stays nullptr — host already chose it; only PageFlip needs the GLXContext, not visInfo
      glXMakeCurrent(halDisplay.mainDisplay, halDisplay.win, static_cast<GLXContext>(h.context));
      AssertGLOK();
      return true;
  }
  ```
  Note: parent plan's risk #2 (glXMakeCurrent must happen before `WFInitGL`) is satisfied because `Display::Display` calls `InitWindow` (which now calls `InitWithExistingContext`) at line 302, *before* `WFInitGL()` at line 309.
- Keep the GLXContext pointer alive somewhere the destructor doesn't try to free it. The standalone path's `cx` is a local in `OpenMainWindow` and is implicitly bound via `glXMakeCurrent`; `HALCloseWindow` calls `glXMakeCurrent(None)` but never destroys the context. Host-owned path does the same (just doesn't run `HALCloseWindow` body — see step 4) so no extra storage needed.

Verify: snowgoons standalone unchanged. Cannot end-to-end test host path until step 7.

### Step 4 — early-bails in `HALCloseWindow` + `XEventLoop`

Files:
- **EDIT** `wfsource/source/gfx/gl/mesa.cc:456` — `XEventLoop`: at the very top, `if (GetHostGLContext().valid) return;`. (Editor reads X events from its own connection and routes input via `HALInjectJoystickButtons` from `b0639c5`.)
- **EDIT** `wfsource/source/gfx/gl/mesa.cc:480` — `HALCloseWindow`: at the top, `if (GetHostGLContext().valid) return;` *before* the existing `if (halDisplay.win)` guard. Host owns the window/display/context; engine must not destroy.

Verify: snowgoons standalone unchanged. Confirm window-manager X-button still cleanly exits (it goes through `ProcessXEvents` setting `_closeRequested`, then game loop polls `HALWindowCloseRequested`, then `Display` destructor runs, then `HALCloseWindow` actually destroys).

### Step 5 — `HALRequestClose` wired (host-driven close)

Files:
- **EDIT** `wfsource/source/gfx/gl/host_gl_context.cc` — implement `HALRequestClose()`:
  ```cpp
  extern std::atomic<int> _closeRequested;   // defined in mesa.cc:57
  extern "C" void HALRequestClose(void) { _closeRequested.store(1); }
  ```
  `_closeRequested` needs to lose its `static` qualifier at mesa.cc:57 (change to file-scope-but-not-static, or expose via a setter inside mesa.cc and call that from here). **Recommended**: drop `static` at mesa.cc:57 and declare `extern` in host_gl_context.cc. Simpler than another indirection layer. The atomic is the only thing that crosses the engine/host boundary; the registry handles are written once before `WFGame` constructor and read only on the engine thread thereafter, so they stay non-atomic per the parent plan's call.

Verify: snowgoons standalone path still uses X11 `WM_DELETE_WINDOW` → `ProcessXEvents` → `_closeRequested.store(1)` (mesa.cc:326/443 unchanged). Host path: `HALRequestClose()` from any thread sets the flag; next `HALWindowCloseRequested()` poll returns nonzero.

### Step 6 — Android + iOS stubs (compile-check only)

The stubs were drafted in step 1 to keep the symbol set consistent across platforms. This step is the compile-verification on those platforms:

- Android: `task build-cmake-android` (or whatever the current entry is) — should produce no new errors. Verify by `grep HALRequestClose` in linked .so symbols.
- iOS: Codemagic manual trigger per [project_codemagic_manual_trigger](../../.claude/projects/-home-will-WorldFoundry/memory/project_codemagic_manual_trigger.md). User triggers; we wait for sim-verify result. If sim-verify is green, mobile stubs are sound.

If iOS Codemagic build is gated on user-triggered manual run (it is), batch this step with the editor design doc update so the user only triggers once at the end.

### Step 7 — X11/GLX smoke-test harness

Files:
- **NEW** `engine/wf_host_gl_test/host_gl_test.cc` — minimal C++ program:
  - `XOpenDisplay(nullptr)`, `glXChooseVisual` with the exact same `attributeList` as `mesa.cc:71`, `glXCreateContext`, `XCreateWindow`, `XMapRaised`, `glXMakeCurrent`.
  - `SetHostGLContext({dpy, win, cx, true});`
  - `WFGame g(-1);` (verified ctor at `game.cc:63`: `WFGame(const int nStartingLevel)`).
  - Drive 60 frames. **Until sub-task #1 (frame-step API) lands**, use `g.RunLevel(...)` against the host context and tolerate the engine's `PageFlip`. **After sub-task #1 lands**, switch to `for (int i=0;i<60;++i) { g.StepFrame(false); glXSwapBuffers(dpy, win); }` per parent plan risk #6.
  - `HALRequestClose()` then `MEMORY_DELETE(HALLmalloc, &g)`.
  - Counter assertion: instrument `OpenMainWindow` with a `++g_openMainWindowCallCount` (debug-only, behind `#ifdef WF_HOST_GL_TEST_INSTRUMENTATION`) and assert in the harness that it stayed 0.
- **NEW** `engine/build_host_gl_test.sh` — mirrors `engine/build_game.sh` structure. Same compiler flags, links the same engine `.o` files plus `host_gl_test.cc`. `set -euo pipefail` per project convention.
- **OPTIONAL** `tests/test_host_gl_context.py` — pytest wrapper that runs the harness binary and asserts exit code == 0. Skip if `engine/wf_host_gl_test` binary not built. Matches existing `verify_smb_walkthrough.py` pattern.

Verify:
- Run harness: window opens (the test's own window), engine renders into it for 60 frames, clean teardown.
- `valgrind --error-exitcode=1 engine/wf_host_gl_test` — no leaks beyond the engine's existing baseline; specifically no double-free of host's Display/Window/Context (parent plan risk #4).
- Screenshot per [feedback_screenshots_for_proof](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md): capture the harness's window mid-loop.

### Step 8 — (deferred) ImGui manual smoke test

Per parent plan verification #3. Defer until sub-task #1 lands so the StepFrame path is exercised. Document the recipe in the parent plan's verification section but don't block this plan's completion on it. Optional GLFW dependency justifies separate sub-step.

### Step 9 — doc updates

- **EDIT** [`docs/plans/2026-05-18-engine-external-gl-context.md`](../../WorldFoundry.2026-new-level/docs/plans/2026-05-18-engine-external-gl-context.md) — change `**Status:** Parked (TODO)...` to `**Status:** Implemented {commit-hash}`. Per [feedback_plan_status_sync](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_status_sync.md), also update `wf-status.md` row.
- **EDIT** [`wf-status.md`](../../WorldFoundry.2026-new-level/wf-status.md) line 171 — change `**Parked**` → `**Implemented**`; prepend one-sentence paragraph to the Summary section (top of section, one sentence per [feedback_wf_status_paragraph_length](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_wf_status_paragraph_length.md) + [feedback_wf_status_rolling_summary](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_wf_status_rolling_summary.md)).
- **EDIT** [`docs/investigations/2026-05-18-collaborative-level-editor-design.md:754`](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) — mark Tier 1 Phase 0b sub-task #2 done with commit hashes.
- **EDIT** [`TODO.md:86`](../../WorldFoundry.2026-new-level/TODO.md) — strike or migrate sub-task #2 mention.

## Critical files reference

| Path | Role |
|---|---|
| [`wfsource/source/gfx/gl/mesa.cc`](../../WorldFoundry.2026-new-level/wfsource/source/gfx/gl/mesa.cc) | Edited in steps 2, 3, 4, 5. Textual-included by display.cc:238; not a standalone TU. |
| [`wfsource/source/gfx/gl/display.cc`](../../WorldFoundry.2026-new-level/wfsource/source/gfx/gl/display.cc) | Read-only reference. `Display::Display@288` calls `InitWindow@302` (now dispatching) then `WFInitGL@309`. |
| [`wfsource/source/hal/lifecycle.h`](../../WorldFoundry.2026-new-level/wfsource/source/hal/lifecycle.h) | Step 1 adds `HALRequestClose` declaration. |
| [`wfsource/source/hal/android/lifecycle.cc`](../../WorldFoundry.2026-new-level/wfsource/source/hal/android/lifecycle.cc) | Step 1 adds mobile stubs. |
| [`wfsource/source/hal/ios/lifecycle.mm`](../../WorldFoundry.2026-new-level/wfsource/source/hal/ios/lifecycle.mm) | Step 1 adds mobile stubs (Objective-C++). |
| [`wfsource/source/hal/_input.h:49`](../../WorldFoundry.2026-new-level/wfsource/source/hal/_input.h) | Read-only. `HALInjectJoystickButtons` already shipped (`b0639c5`); editor uses this for input. |
| [`wfsource/source/game/game.cc:63`](../../WorldFoundry.2026-new-level/wfsource/source/game/game.cc) | Read-only. `WFGame(const int nStartingLevel)` ctor confirmed; constructs `Display` at line 80. |
| [`CMakeLists.txt:80-150`](../../WorldFoundry.2026-new-level/CMakeLists.txt) | Read-only. WF_DIRS per platform; WF_SKIP for textual-included .cc files. Confirms `gfx/gl/` is iOS-excluded but Android-included → step 1's `#if defined(__LINUX__) && !defined(__ANDROID__)` guard. |
| [`engine/build_game.sh`](../../WorldFoundry.2026-new-level/engine/build_game.sh) | Step 7 template — mirror for `build_host_gl_test.sh`. |

## Verification end-to-end

1. After each step (1–6): `task build` succeeds; `engine/wf_game` (snowgoons) launches, walks one screen, X-button closes cleanly. No regressions.
2. Step 7: `engine/wf_host_gl_test` runs 60 frames; valgrind exit 0; screenshot captured.
3. Step 9: rendered preview of updated docs per [feedback_open_md_html_in_browser](../../.claude/projects/-home-will-WorldFoundry/memory/feedback_open_md_html_in_browser.md).

## Risks called out (already in parent plan; not re-litigating here)

GLX visual mismatch · `glXMakeCurrent` timing · destructor cleanup order · multi-`WFGame` v1 limit · sub-task #1 coupling · iOS/Android out of scope. See [parent plan §Risks](../../WorldFoundry.2026-new-level/docs/plans/2026-05-18-engine-external-gl-context.md#risks--things-to-watch).
