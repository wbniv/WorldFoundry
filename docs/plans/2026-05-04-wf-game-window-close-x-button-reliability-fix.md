# Plan — wf_game window-close (X button) reliability fix

**Status:** DONE — Phase 1 (`_closeRequested` flag + `HALWindowCloseRequested()`) landed in commit `987e80fe`; Phase 2 deferred as planned.

## Phases

- **Phase 1 — close-button flag.** Replace mid-frame `sys_exit(0)` with a polled `_closeRequested` atomic; main loop exits cleanly. Status: **landed.**
- **Phase 2 — completeness.** Two follow-ups now in scope at the user's request:
  - **2a. Pump X events during level load / asset reload** — today the close button has zero effect during multi-second load stalls because `XEventLoop()` only runs from `Display::PageFlip()` inside the main loop. Two implementation options: (i) sprinkle `XEventLoop()` calls into long-running load code paths (cheap, intrusive — touches every loader), or (ii) move X event polling onto a dedicated thread with `XInitThreads()` and a mutex around X calls (cleaner, more invasive). Recommendation: start with (i) at a small set of well-known stall points (level load, texture upload, asset bundle scan) and only escalate to (ii) if that turns out to be whack-a-mole. Either way the fix is gated on the Phase-1 flag — events still just set `_closeRequested` and the load completes; the loop then exits on first iteration.
  - **2b. Migrate keyboard-ESC `sys_exit(0)` to the same flag.** `mesa.cc:310` keeps the original mid-event `sys_exit(0)` shortcut for the ESC key. Same crash mode as the X button (just less reproducible because pressing ESC doesn't cross WM-event boundaries). Change to `_closeRequested.store(1)` for consistency. ~1 line.

## Context

When the user clicks the window-manager **X (close)** button on the wf_game window (Linux, X11 via Mesa), the application sometimes does not close cleanly. The window can become unresponsive, appear stuck open, or partially terminate — the user reported "I cannot always close the window using the x button."

## Root cause

The X-close path takes a shortcut that runs `exit()` from inside the X event handler, mid-frame.

Code trace:
- Window setup registers `WM_DELETE_WINDOW` correctly via `XSetWMProtocols` at `wfsource/source/gfx/gl/mesa.cc:140-141`.
- Per-frame X event pump: `XEventLoop()` at `mesa.cc:440-455`, called from `Display::PageFlip()` at `wfsource/source/gfx/gl/display.cc:451-453`, which runs **every frame** unconditionally in the main loop (`wfsource/source/game/game.cc:343`).
- The close-button event lands in `ProcessXEvents` at `mesa.cc:425-428`:
  ```cpp
  case ClientMessage:
      if ((Atom)event.xclient.data.l[0] == _wmDeleteWindow)
          sys_exit(0);   // ← problem
      break;
  ```
- `sys_exit()` (`wfsource/source/pigsys/pigsys.cc:462`) runs all `sys_atexit` handlers — including `_atExitTermDisplay` (`mesa.cc:96-112`) — and then calls libc `exit()`. All of this fires from inside `Display::PageFlip()`, mid-frame.

Why this is unreliable:
- We're mid-frame when `exit()` is called; render/asset/audio state is partially valid. Atexit handlers see torn-down dependencies and can wedge or crash silently.
- Background threads (debug bridge listener on 7777, REST API listener on 8765, audio thread) keep the process alive after `exit()` returns from `main()`-ish context.
- X events are **not pumped** during long stalls outside the main loop (level load, asset reload, the post-loop `PageFlip` cleanup at `game.cc:348-349`). During those windows clicking X does nothing; once the loop resumes, the click then triggers the broken mid-frame `exit()` path. Both effects together produce the "sometimes works, sometimes doesn't" symptom.

## Fix

Replace the in-handler `sys_exit(0)` with a "close requested" flag the main game loop polls — the standard pattern (SDL_QUIT, `glfwWindowShouldClose`).

### File 1: `wfsource/source/gfx/gl/mesa.cc`

- Add a file-scope `static std::atomic<bool> _closeRequested{false};` near the other globals (the existing `halDisplay`, `_wmDeleteWindow` cluster around line 60-80).
- In `ProcessXEvents` at line 425-428, change `sys_exit(0)` to `_closeRequested.store(true);`.
- Define an exported accessor at the bottom of the file:
  ```cpp
  extern "C" bool HALWindowCloseRequested() { return _closeRequested.load(); }
  ```

### File 2: HAL header

- Find the existing HAL function declarations (likely `engine/include/hal/hal.h` or a sibling header — confirmed by `HALPumpSuspendedEvents`, `HALIsSuspended` already declared somewhere `game.cc` includes). Add:
  ```cpp
  bool HALWindowCloseRequested();
  ```
- For non-Linux/Android targets that don't have an X event loop, provide an inline stub returning `false` in the appropriate platform-specific section (or a default weak symbol).

### File 3: `wfsource/source/game/game.cc`

- Extend the main loop condition at line 278:
  ```cpp
  while ( !_curLevel->done() && _bContinue && !HALWindowCloseRequested() )
  ```
- This lets the existing loop-exit path run normally: post-loop `PageFlip` × 2 (line 348-349), `RestApi_Stop`, `DebugServer_Stop`, level destruction, return from `RunLevel`. Standard shutdown.

### Why this is enough

- The flag is set on the same thread that polls it (XEventLoop runs from the game thread inside PageFlip), but `std::atomic<bool>` is harmless and future-proof if we ever pump events from another thread.
- The fix doesn't touch the level load / asset load paths. **Known limitation:** X-button clicks during a long load still won't take effect until the load completes and the main loop runs again. That's a separate, larger fix (sprinkling event-pump calls into load code or adding a dedicated event thread); not in scope for this change.
- The keyboard-ESC `sys_exit(0)` at `mesa.cc:310` could be migrated to the flag too for consistency, but ESC seems to work today, so leave it alone unless the user requests it.

## Files to modify

| File | Change |
|------|--------|
| `wfsource/source/gfx/gl/mesa.cc` | Add `_closeRequested` atomic, swap `sys_exit(0)` for flag set, add accessor |
| HAL header (path TBD on first read) | Declare `HALWindowCloseRequested()` |
| `wfsource/source/game/game.cc` | Extend main-loop condition |

## Verification

1. **Build:** `cd engine && ./build_game.sh` — must succeed with no warnings on the new atomic include / accessor.
2. **Happy path:** `task run-debug -- wflevels/qbert_practice-standalone.iff`, wait for the game to render, click X. Expected: window closes cleanly, process exits with code 0, no zombie debug-bridge socket on 7778.
3. **Mid-frame:** repeat ×5 with the game actively rendering (player moving). Expected: clean close every time.
4. **During load (known limitation):** click X during the first second of launch (before "Entering main game loop"). Expected: window closes once load completes (not instantly). If that's not acceptable, the follow-up scope is larger and we should re-plan.
5. **Pytest regression:** `cd tests && DISPLAY=:0 python3 -m pytest -v` — the existing 10 bridge tests must still pass (the conftest fixture closes the engine via SIGTERM, not the X button, so it's unaffected — but worth confirming nothing regressed).

## Out of scope

- The unrelated mailbox-999 crash found while debugging Phase B2 — separate fix.

(Items previously listed here — pumping X during load, ESC-key flag migration — were promoted to Phase 2 above.)
