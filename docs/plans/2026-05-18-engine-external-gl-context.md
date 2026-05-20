# Engine external GL context — accept editor-owned `XDisplay*` / `Window` / `GLXContext`

**Status:** Implemented 2026-05-18 (commits `151e2fe`, `2193f77`, `50807a9`, `a68b119`, `3f80c58`, `a816e3b`). Sub-task #2 of Phase 0b in the [collaborative editor design doc](../investigations/2026-05-18-collaborative-level-editor-design.md). Standalone `wf_game` unchanged; new `gfx/host_gl_context.h` lets an editor host register its own `XDisplay*` / `Window` / `GLXContext`, mesa.cc dispatches `InitWindow` accordingly, and `HALCloseWindow` / `XEventLoop` early-bail when host-owned. Mobile (Android / iOS) gets no-op stubs. Smoke test at `engine/wf_host_gl_test/`. Follow-up tracked in [TODO.md](../../TODO.md): end-to-end WFGame integration test needs `main()` lifted out of `libwfengine.a` (or a `-Wl,--allow-multiple-definition` workaround).

## Context

Today the engine owns its [X11](https://www.x.org/wiki/) connection, [GLX](https://en.wikipedia.org/wiki/GLX) context, and `Window`. [`OpenMainWindow`](../../wfsource/source/gfx/gl/mesa.cc) at [mesa.cc:117](../../wfsource/source/gfx/gl/mesa.cc) calls `XOpenDisplay(NULL)` → `glXChooseVisual` → `glXCreateContext` → `XCreateWindow` → `XMapRaised`. This is invoked from [`Display::Display`](../../wfsource/source/gfx/gl/display.cc) at line 288 via `InitWindow(xPos, yPos, _halWindowWidth, _halWindowHeight)`. The `halDisplay` global ([mesa.cc:49](../../wfsource/source/gfx/gl/mesa.cc)) stores the three handles.

For an editor that embeds the engine into a [Dear ImGui](https://github.com/ocornut/imgui) overlay or [Qt](https://www.qt.io/) `QOpenGLWidget`, the editor already owns:

- The X11 `Display*` (its application-level connection).
- The `Window` (its widget).
- The `GLXContext` (shared with ImGui's draw state).

The engine needs an alternative initialisation path that accepts these as host-supplied parameters instead of creating its own. The standalone `wf_game` path stays unchanged.

## Architectural approach

1. **Two-path init in `mesa.cc`.** Existing `OpenMainWindow(title)` keeps creating everything from scratch. New `InitWithExistingContext(XDisplay*, Window, GLXContext)` skips X / GLX / window creation, stores the host-supplied handles in `halDisplay`, makes the context current, runs the GL init that `OpenMainWindow` did after its `glXCreateContext`.

2. **`InitWindow` dispatches.** Today `InitWindow(xPos, yPos, xSize, ySize)` (called from `Display::Display`) is a thin wrapper around `OpenMainWindow("World Foundry")`. Replace with `if (GetHostGLContext().valid) InitWithExistingContext(...); else OpenMainWindow("World Foundry");`. File-scope `gHostOwnedContext` is populated by an explicit host-side call before `Display::Display` runs.

3. **Public opaque API for the host.** New header [`wfsource/source/gfx/host_gl_context.h`](../../wfsource/source/gfx/host_gl_context.h) uses `void*` to avoid leaking X11 / GLX types into engine-public headers (and to keep iOS / Android translation units happy when they include the header for their no-op stubs):
   ```cpp
   struct HostGLContext {
       void* display;     // (XDisplay*) — cast inside the GL backend
       unsigned long win; // Window — XID is unsigned long
       void* context;     // (GLXContext)
       bool  valid;
   };
   void SetHostGLContext(const HostGLContext&);
   HostGLContext GetHostGLContext();
   void ClearHostGLContext();
   ```
   Editor calls `SetHostGLContext(...)` after creating its own GL context but before constructing `WFGame` (which constructs `Display`).

4. **`HALCloseWindow` early-bails in host-owned mode.** Today it does `glXMakeCurrent(None) + XDestroyWindow + XCloseDisplay`. In host-owned mode the host owns those resources; add `if (GetHostGLContext().valid) return;` at the top of [`HALCloseWindow`](../../wfsource/source/gfx/gl/mesa.cc).

5. **`XEventLoop` early-bails in host-owned mode.** Today it runs `XPending` + `XNextEvent` against `halDisplay.mainDisplay`. With editor-owned context, the editor reads events from its own X11 connection and routes input via the already-shipped [`HALInjectJoystickButtons`](../../wfsource/source/hal/_input.h) from Phase 0b sub-task #3 (commit `b0639c5`). Engine's `XEventLoop` becomes a no-op; add `if (GetHostGLContext().valid) return;` at the top.

6. **`_closeRequested` becomes host-driven.** Today set by `WM_DELETE_WINDOW` in `ProcessXEvents`. Add `HALRequestClose()` (free function in [`hal/lifecycle.h`](../../wfsource/source/hal/lifecycle.h)) that the editor calls when it wants the next `HALWindowCloseRequested()` poll to return true. Implemented in mesa.cc by setting the existing `_closeRequested` atomic.

7. **Title and geometry are host-only in standalone mode.** Hardcoded `"World Foundry"` title and `_halWindowWidth` / `_halWindowHeight` only apply when the engine creates its own window. Host-owned mode uses whatever the editor's widget already is — engine doesn't try to resize / rename it.

8. **Linux-only for v1.** [Android](https://developer.android.com/) `NativeActivity` creates EGL on its own; [iOS](https://developer.apple.com/ios/) [Metal](https://developer.apple.com/metal/) is a different backend entirely. Mobile platforms stub `Set/Get/ClearHostGLContext` and `HALRequestClose` to no-ops with `valid=false`. The editor runs on Linux for v1; mobile-host embedding is a v2+ concern.

## Files modified

| File | Change |
|---|---|
| [wfsource/source/gfx/host_gl_context.h](../../wfsource/source/gfx/host_gl_context.h) | NEW — public opaque interface for host context registration. |
| [wfsource/source/gfx/gl/host_gl_context.cc](../../wfsource/source/gfx/gl/host_gl_context.cc) | NEW — implements `Set/Get/ClearHostGLContext` and `HALRequestClose`. File-scope statics (called before `Display::Display` then read by mesa.cc on the same thread — no atomics needed for the context handles; `_closeRequested` stays atomic since it crosses an X11 event-handler boundary). |
| [wfsource/source/gfx/gl/mesa.cc](../../wfsource/source/gfx/gl/mesa.cc) | Add `static void InitWithExistingContext(XDisplay*, Window, GLXContext)`. Change `InitWindow` to dispatch on `GetHostGLContext().valid`. Add early-bail in `HALCloseWindow` and `XEventLoop` for host-owned mode. |
| [wfsource/source/gfx/gl/display.cc](../../wfsource/source/gfx/gl/display.cc) | No change — `Display::Display` keeps calling `InitWindow`; dispatch happens inside mesa.cc. |
| [wfsource/source/hal/lifecycle.h](../../wfsource/source/hal/lifecycle.h) | Add `void HALRequestClose();` declaration alongside `HALWindowCloseRequested`. |
| [wfsource/source/hal/android/lifecycle.cc](../../wfsource/source/hal/android/lifecycle.cc), [wfsource/source/hal/ios/native_app_entry.mm](../../wfsource/source/hal/ios/native_app_entry.mm) | Stub `HALRequestClose()` as a no-op (mobile is single-window standalone). Host-GL-context functions on mobile return `valid=false`. |

## Verification

1. **Standalone unchanged.** Run snowgoons + qbert_practice + smb_w1_1 in `wf_game`. Window opens, GL works, input works, X11 close button cleanly shuts down. No regression.

2. **Host-owned smoke test (X11/GLX only).** New `tests/test_host_gl_context.cc` that:
    - Creates an X11 Display, Window, GLXContext via the standard [Xlib](https://en.wikipedia.org/wiki/Xlib) / GLX API (no ImGui, no Qt — keep deps minimal).
    - Calls `SetHostGLContext({dpy, win, cx, true})`.
    - Constructs `WFGame g(-1)`, loads `smb_w1_1.iff`.
    - Loops `g.StepFrame(false); glXSwapBuffers(dpy, win);` for 60 frames (depends on sub-task #1 being landed; if not, drive via `RunLevel` against host context).
    - Calls `HALRequestClose()` then `MEMORY_DELETE(HALLmalloc, ...)` to shut down.
    - Instrumentation counter asserts `XOpenDisplay` was never called inside the engine.

3. **ImGui integration smoke test (manual).** Tiny standalone ImGui program under `tests/`: opens its own [GLFW](https://www.glfw.org/) window, calls `SetHostGLContext`, drives engine via `StepFrame(false)`, draws an ImGui overlay on top, calls `glfwSwapBuffers`. Visual confirmation per [feedback_screenshots_for_proof](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md): in-game screenshot showing engine pixels with ImGui widgets overlaid.

4. **Teardown sanity (valgrind).** Host-owned smoke test through valgrind. `~Display` in host-owned mode must NOT double-free the host's window/context. Standalone mode unchanged.

## Risks / things to watch

- **GLX visual mismatch.** The engine's `OpenMainWindow` picks a specific `attributeList` ([mesa.cc:71](../../wfsource/source/gfx/gl/mesa.cc)) — `GLX_RGBA`, `GLX_DOUBLEBUFFER`, `GLX_DEPTH_SIZE >= 1`. Host's `GLXContext` may have been created with different attributes (smaller depth, no double-buffer). Document the required visual attrs in `host_gl_context.h`; smoke test #2 uses the same attrs the engine would have picked.

- **`glXMakeCurrent` timing.** Host-owned mode needs the engine to call `glXMakeCurrent(dpy, win, cx)` before any GL call. `WFInitGL()` (called from `Display::Display` after `InitWindow`) does initial GL queries — the makeCurrent must happen inside `InitWithExistingContext` before `WFInitGL` runs. Verify GL state queries inside `WFInitGL` see the host context, not GL's default zero state.

- **Cleanup order in destructor.** Standalone: `HALCloseWindow` destroys window, then `~Display` runs the final two `PageFlip` calls against the now-dead context (today gated by `if (!HALWindowCloseRequested())` at [display.cc:343](../../wfsource/source/gfx/gl/display.cc)). Host-owned: `~Display` runs but `HALCloseWindow` early-bails, leaving the host window intact — the two `PageFlip` calls execute against a live host context. That's fine but verify the existing `HALWindowCloseRequested` gate doesn't skip them in host mode (it shouldn't — host normally hasn't requested close before `~Display`).

- **Multiple `WFGame` instances.** Tier 1 verdict is v1 single-instance, but a future "two viewports into the same scene" feature would have two `WFGame`s sharing one HAL and one `gHostOwnedContext`. Document v1 single-instance constraint in `host_gl_context.h` header comment.

- **Coupling with sub-task #3 (input injection).** Already shipped (`b0639c5`). Host-owned mode means engine's `XEventLoop` no-ops; input comes only via `HALInjectJoystickButtons`. The ground for that is laid; verify the host harness in step 7 actually drives input via the new entry point.

- **Coupling with sub-task #1 (frame-step API).** Independent code-wise. But the host-owned path most naturally calls `StepFrame(do_swap=false)` and then `glXSwapBuffers(host_dpy, host_win)` itself; with sub-task #1 not yet landed, the host smoke test temporarily uses `RunLevel` and tolerates the engine's `PageFlip`. Switch to `StepFrame` once both land.

- **iOS / Android.** Out of scope. Mobile creates GL via NativeActivity (EGL) / Metal differently; host-owned mode is a Linux/X11 desktop concern. Stubs return `valid=false`; no behavioural change on mobile.

## Implementation sequence

Each numbered step is its own commit per [feedback_commit_after_each_phase](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md).

1. **New `host_gl_context.h` + `host_gl_context.cc`.** File-scope statics + getter/setter/clear. `HALRequestClose()` stub (sets `_closeRequested`; mesa.cc keeps the atomic). Compile-check; standalone still builds and runs unchanged.
2. **Refactor `mesa.cc` `InitWindow` dispatch.** `InitWindow` calls `OpenMainWindow` if no host context, else (placeholder) calls `OpenMainWindow` anyway. Verify standalone unchanged (the if-branch never fires).
3. **Implement `InitWithExistingContext`.** Take Display / Window / GLXContext from `GetHostGLContext()`; populate `halDisplay`; `glXMakeCurrent` + `AssertGLOK`. Wire to `InitWindow` dispatch. Compile-check; standalone unchanged.
4. **Early-bails in `HALCloseWindow` and `XEventLoop`.** `if (GetHostGLContext().valid) return;` at the top of each. Standalone unchanged.
5. **Wire `HALRequestClose` to `_closeRequested` atomic.** Editor's close sets this; standalone path still uses the X11 `WM_DELETE_WINDOW` handler.
6. **Mobile stubs for `Set/Get/ClearHostGLContext` and `HALRequestClose`.** Compile-check Android + iOS builds.
7. **Smoke test #2 (X11/GLX harness).** Standalone test program creates context, drives engine for 60 frames, tears down cleanly through valgrind.
8. **(After sub-task #1 lands)** Switch smoke test to `StepFrame(false)`; add the ImGui manual smoke test (#3 above).
9. **Update editor design doc.** Mark Phase 0b sub-task #2 done with commit hashes in the [Tier 1 entry](../investigations/2026-05-18-collaborative-level-editor-design.md). Move corresponding [TODO.md](../../TODO.md) entry to done.
