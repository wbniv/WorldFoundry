# Audit: joinable threads that could `std::terminate`-mask a real assert

**Date:** 2026-06-13
**Trigger:** Follow-up to the debug-bridge fix ([`15801ebc`](https://github.com/wbniv/WorldFoundry/commit/15801ebc)) — sweep the engine for *other* threads that could reproduce the same "terminate called without an active exception" masking, and harden against the class.

## The failure mode

An engine `AssertMsg` calls `exit(-1)` (`wfsource/source/pigsys/assert.cc:48`). `exit()`
runs C++ **static destructors** + `sys_atexit` handlers (LIFO,
`wfsource/source/pigsys/_atexit.cc`) but does **not** unwind the stack. Therefore:

- Only **static/global** `std::thread` objects (or threads owned by static/global
  objects) have their destructors run at `exit(-1)`.
- If such a thread is still **joinable** when destroyed → `std::terminate()` → a bogus
  "terminate called without an active exception" + `std::thread::~thread` at the top of
  stack, **masking the real assert**.
- The order matters: static destructors run **before** `sys_atexit` handlers, so a
  `sys_atexit`-registered `Stop()`/`join()` is *not* guaranteed to run first — which is
  why `debug_server`/`rest_api` detach rather than rely on the atexit join.
- Stack/heap-local thread objects are **not** at risk from this path (`exit()` doesn't
  destroy them).

## Thread inventory (non-vendored WF C++)

| Thread | File | Storage | Teardown | Verdict |
|--------|------|---------|----------|---------|
| `gListenerThread` | `engine/stubs/debug_server.cc:561` | file-static | `.detach()` | **safe** (fixed `15801ebc`) |
| `gServerThread` | `engine/stubs/rest_api.cc:309` | file-static | `.detach()` | **safe** (same pattern) |
| `handle_client(...)` | `debug_server.cc:540` | temporary | `.detach()` | **safe** |
| `BridgeHost::_reader` | `engine/.../pilot/host_bridge.cc` | member of stack-local `BridgeHost` | `.join()` in dtor | **safe** (not destroyed by `exit()`) |
| `EditorCtx::relay_reconnect_thread` | `engine/wf_edit/main.cc` | member of stack-local `EditorCtx` | `.join()` before scope exit | **safe** |
| `VideoChat::cap_thread_` | `engine/wf_edit/video_track.cc` | member of stack-local `VideoChat` | `.join()` in `Stop()`/dtor | **safe** |
| connector | `engine/wf_edit/main.cc` | stack-local | `.join()` same scope | **safe** |

`std::thread::id g_gameThread` (`wfmut.cpp`) is a value type, not a joinable thread — not a risk.

## Conclusion

**The codebase is currently free of the terminate-masking hazard.** The only static
threads (`debug_server`, `rest_api`) are already detached; every other thread is a member
of a stack-local object joined in its destructor before `main()` returns, so `exit(-1)`
never destroys a joinable one. **Nothing to detach.**

## Hardening (the durable fix)

A point-in-time "clean" audit doesn't protect against a *future* joinable static thread,
an unhandled exception, or a `noexcept` violation. The durable defense — a de-noising
`std::set_terminate` handler that dumps the real cause + backtrace before aborting —
existed **only in `wf_edit`**. `wf_game` (the main engine, where the cited bugs run:
statplat abort, the [BUGS.md](../BUGS.md) mailbox-range case) had none.

Fix: factor the handler into a shared `Sys_InstallTerminateHandler(appName)` in
`wfsource/source/pigsys/fatal.cc` (auto-globbed into the `wfengine` lib that both
binaries link), install it first thing in `wf_game` (linux/macos/emscripten mains) and
`wf_edit` (replacing its inline copy), and guard the backtrace for portability
(`__has_include(<execinfo.h>) && !__EMSCRIPTEN__`). Regression guard: `wf_edit_terminate`
ctest triggers `std::terminate()` (no active exception → the exact masking branch) and
asserts the de-noising cause line reaches stderr. See
[plan](../plans/) and the feature commit.

## Verification

Build (reconfigure re-globs `pigsys/` → `fatal.cc` enters `wfengine`):
```
$ cmake -S . -B build-editor … && cmake --build build-editor --target wf_edit wf_game connect_retry_test
[100%] Built target wf_edit
[100%] Built target wf_game     # linux platform_main.cc install + fatal.cc compile/link
Built target connect_retry_test
```

The shared handler fires for `wf_edit` (and `wf_game` links the same symbol):
```
$ WF_EDIT_TERMINATE_TEST=1 ./build-editor/wf-edit
[terminate-test] deliberately calling std::terminate
=== wf-edit: std::terminate fired ===
  no active exception (likely joinable std::thread destroyed without join, or noexcept function throwing)
  backtrace (8 frames):
  …
=== aborting ===
```
The grep marker `no active exception` is unique to our handler — libstdc++'s default
prints "terminate called *without an* active exception", so the test fails if the
handler isn't installed (it bites).

ctest — terminate guard + no A/V regression:
```
$ ctest --test-dir build-editor -R 'wf_edit_(terminate|pli|video_race|mesh|turn|connect_retry)'
100% tests passed, 0 tests failed out of 6
```
