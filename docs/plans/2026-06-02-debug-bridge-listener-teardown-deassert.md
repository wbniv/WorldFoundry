# Plan — De-noise editor asserts: detach the debug-bridge listener thread

## Context

Any `assert` / `AssertMsg` / `exit(-1)` during a `wf-edit` or `wf_game` session
with the debug bridge running currently aborts with:

```
terminate called without an active exception
  … std::thread::~thread() at top of stack …
```

— **masking the real `AssertMsg`** (the actual file:line + message of what went
wrong). Cause: the debug bridge's listener is a *static, joinable* `std::thread`
([`engine/stubs/debug_server.cc:290`](../../engine/stubs/debug_server.cc)
`static std::thread gListenerThread;`), started at `:551`, joined only inside
`DebugServer_Stop()` (`:574`) which is registered via `sys_atexit` (`:555`). On
the `exit(-1)` path the C++ runtime runs static destructors during
`__run_exit_handlers` **before** the engine's `sys_atexit` `DebugServer_Stop`
join gets to run — and destroying a still-*joinable* `std::thread` calls
`std::terminate()` by language rule. So the terminate fires first and buries the
real assert.

This is a dev-experience multiplier: every assert during an editor/game session
currently lies about its cause. Fixing it de-noises the
[statplat move abort](../investigations/2026-05-25-wf-edit-statplat-move-abort.md)
investigation, the [`docs/BUGS.md`](../BUGS.md) mailbox-range case, and any
future assert. (TODO.md: "Make the debug-bridge listener teardown clean so
`exit()` doesn't `terminate`-mask the real cause.")

## Fix

**Detach the listener thread** right after starting it, so the static destructor
is always a no-op (non-joinable) regardless of whether `DebugServer_Stop` ran.
This is the same pattern the `handle_client` worker threads already use
([`debug_server.cc:540`](../../engine/stubs/debug_server.cc)
`std::thread(handle_client, cfd).detach()`).

> **Second offender found in verification:** the before/after test showed the
> terminate *persisted* after fixing `debug_server.cc` alone — the **REST API
> server** has the identical static joinable thread
> ([`rest_api.cc:170`](../../engine/stubs/rest_api.cc) `gServerThread`, started at
> `:281`, joined in `RestApi_Stop`), which it even *comments* as a known
> `std::terminate` hazard. It's the only other `static std::thread` /`.join()` in
> the `wf_game-dev` binary (grep-confirmed). Both are detached. `rest_api`'s
> `RestApi_Stop` also `delete`d its `httplib::Server` after the join; with the
> thread detached, that delete would race the in-flight `listen()` unwind, so
> Stop now `stop()`s and **leaks** the server (atexit-only → OS reclaims at exit)
> instead of deleting.

- `DebugServer_Start` (`:551`): add `gListenerThread.detach();` after creation,
  with a comment explaining the terminate-mask rationale.
- `DebugServer_Stop` (`:574`): drop the now-dead `if (joinable) join()` — clean
  shutdown still stops the loop via `gRunning=false` + `shutdown`/`close` of
  `gServerFd` (which unblocks the listener's `accept()`); the detached thread
  exits on its own. No new race: `listener_loop` only touches `gRunning` and
  `gClients` (the latter under `gQueueMutex`, which `DebugServer_Stop` also
  holds); it never touches the `gOriginals`/`gChangeStack`/… state that Stop
  clears.

Correct by construction (C++ standard: a detached `std::thread`'s destructor is
a no-op; a joinable one's calls `std::terminate`). The only behaviour change on
the clean path is that `DebugServer_Stop` no longer *waits* for the listener to
finish — fine for a debug stub, and `SO_REUSEADDR` is already set so a later
re-`Start` on the same port can't be blocked by a lingering bind.

## Verification

1. **Compile** the bridge-enabled binary (`task build-editor` builds `wf_game`
   with the debug bridge) — confirm it links clean and the binary mtime advances.
2. **Behavioural:** with the bridge listening, trigger an `AssertMsg`/`exit(-1)`
   (e.g. an out-of-range mailbox write via the bridge) and confirm stderr now
   shows the **real `AssertMsg`** (file:line + message) instead of
   `terminate called without an active exception` + `std::thread::~thread`.
   Capture the before/after stderr.
3. No regression to the clean path: a normal bridge session starts, serves a
   client, and exits without the terminate.

## Result (verified 2026-06-02)

Before/after on the same trigger (`set_mailbox 99999 idx1` → out-of-range read
→ `AssertMsg` → `exit(-1)`), via `tests/test_assert_no_terminate_mask.py`:

| | exit | `terminate called` | assert visible |
|---|---|---|---|
| **before** | `-6` (SIGABRT) | yes (masks the cause) | yes, buried |
| **after**  | `255` (clean exit) | **no** | yes — the `ASSERTION FAILED` box (`mailbox.cc:90`) is the clean last output |

Two offenders, both fixed: `debug_server.cc` `gListenerThread` and
`rest_api.cc` `gServerThread` (the latter was missed by a stub-mtime stale-skip
in the first rebuild — `rm`'d the `.o` to force it). Grep confirmed these are the
only two `static std::thread`/`.join()` in the `wf_game-dev` binary, and the
clean `exit=255` confirms no third offender. Regression-guarded by the test above.
