# Plan: Suppress intentional gServer LSan leak in rest_api.cc

## Context

Clicking X to close the moon level (or any `wf_game` session) exits with ASan's
LeakSanitizer aborting:

```
==169468==ERROR: LeakSanitizer: detected memory leaks
Direct leak of 824 byte(s) in 1 object(s) allocated from:
    RestApi_Start() engine/stubs/rest_api.cc:188
...
SUMMARY: AddressSanitizer: 11309 byte(s) leaked in 77 allocation(s)
```

Root cause: `RestApi_Stop()` intentionally does **not** `delete gServer` because
the thread running `gServer->listen()` is detached — deleting under it races
the `listen()` unwind (UAF). This tradeoff was documented in
[`docs/plans/2026-06-02-debug-bridge-listener-teardown-deassert.md`](2026-06-02-debug-bridge-listener-teardown-deassert.md).
The OS reclaims the allocation at process exit, but LSan sees it as a leak and
aborts, masking a clean exit as a crash.

The 11 KB of leaked objects are:

| Object | Size | Source |
|--------|------|--------|
| `httplib::Server` | 824 B | `rest_api.cc:188` `new httplib::Server()` |
| `RegexMatcher` + route vectors | ~10.5 KB | route registration calls (`.Get`, `.Post`, `.Patch`, `.Delete`) |

## Fix

Use `__lsan_ignore_object(gServer)` immediately after allocation. This is the
standard LSan API for declaring an intentional leak — LSan will not follow
references from it, so the `RegexMatcher` allocations reachable only through
`gServer` are also suppressed.

### Changes to `engine/stubs/rest_api.cc`

**1. Add include at top of file** (guarded so non-ASan builds compile clean):

```cpp
#if defined(__has_feature) && __has_feature(address_sanitizer)
#  include <sanitizer/lsan_interface.h>
#endif
```

**2. After `gServer = new httplib::Server();` (line 188):**

```cpp
#if defined(__has_feature) && __has_feature(address_sanitizer)
    __lsan_ignore_object(gServer);   // intentional leak — see RestApi_Stop comment
#endif
```

No other changes. `RestApi_Stop` comment already explains the leak rationale.

## Verification

1. `task build` — confirm clean compile (Debug + ASan)
2. `task run-moon`, then click X to close
3. `cat /tmp/wfgame_moon.log | grep -i leak` — must be empty
4. Process must exit cleanly (exit 0 or SIGTERM, not SIGABRT)
