# Fix: abort on window close — second pass (REST API thread)

**Date:** 2026-04-17
**Status:** Complete

## Context

A prior fix ([`2026-04-17-fix-window-close-crash.md`](2026-04-17-fix-window-close-crash.md)) routed the WM `WM_DELETE_WINDOW` event to `sys_exit(0)`. Clicking the X no longer caused the WM to forcibly destroy the window out from under the game — but the process still aborted during shutdown:

```
sys_exit(0) called
Calling sys_call_atexit function
sys_call_atexit function called, num_atFuns = 1
Calling atexit function at address 0x...
calling exit with return code of 0
terminate called without an active exception
Aborted (core dumped)
```

The `terminate` fired *after* libc `exit()` was called — i.e. during global-static destruction.

## Root cause

`engine/stubs/rest_api.cc` holds a file-scope `std::thread gServerThread` that runs the cpp-httplib listener. The tidy shutdown in `RestApi_Stop()` (`gServer->stop()` + `join`) is only called from the normal game-loop exit path in `game.cc:331`, which the window-close path bypasses — `sys_exit()` calls `_sys_call_atexit_funs()` and then libc `exit()`.

`exit()` runs static destructors. `~std::thread()` on a joinable thread calls `std::terminate`.

## Fix (landed)

`engine/stubs/rest_api.cc`: register `RestApi_Stop` as a `sys_atexit` handler inside `RestApi_Start()`, so the server is stopped and the thread joined before the `gServerThread` destructor runs.

```cpp
#include <pigsys/pigsys.hp>     // sys_atexit
...
static bool atexitRegistered = false;
if (!atexitRegistered) {
    sys_atexit([](int) { RestApi_Stop(); });
    atexitRegistered = true;
}
```

## Verification

Launched `wf_game`, clicked the window X:

- `rest_api: server stopped` printed (the atexit handler fired and joined the thread).
- `num_atFuns = 2` (was 1 — the new handler is registered alongside `memcheck_shutdown`).
- No `terminate called without an active exception`.
- Process exited with code 0, no core dump.

## Why not just `detach()`?

`std::thread::detach()` would also silence the destructor, but abandons the HTTP server mid-listen — the socket + cpp-httplib state would leak into process teardown, and any in-flight request would be serviced against already-destroyed globals (`gBoxes`, `gBoxMutex`). Ordered shutdown via atexit is the cleaner fix.
