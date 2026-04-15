# Plan: lua_engine — correctness and performance fixes

**Date:** 2026-04-15
**Status:** **landed 2026-04-15 (fixes #1–#6 all complete; smoke test pending HAL cleanup).**
**File:** `wftools/wf_viewer/stubs/scripting_stub.cc` (`lua_engine` namespace)

> **Convention note.** This plan's `lua_engine` namespace is the canonical
> shape for every WF scripting-engine plug: five free functions (`Init`,
> `Shutdown`, `AddConstantArray`, `DeleteConstantArray`, `RunScript`) in
> a file-scope `<engine>_engine` namespace, module-level globals instead
> of member variables, lifecycle driven by `ScriptRouter`. The
> retargeting of every other scripting-engine plan onto this convention
> is tracked in `docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md`.

## Problems

### 1. `luaL_dostring` re-parses every tick (performance)

`lua_engine::RunScript` calls `luaL_dostring(gL, src)` on every invocation.
`luaL_dostring` is `luaL_loadstring` + `lua_pcall` — it lexes, parses, and generates
bytecode every single call. For a level with 30 actors each running a script at 30 Hz,
that is ~900 redundant compilations per second.

Fix: compile once per unique source string, store the bytecode as a `lua_Function` in
the registry (`luaL_ref`), call it by ref on subsequent ticks.

Cache key: the raw `const char*` pointer works for WF because each actor's script string
lives in the level IFF block for the lifetime of the level. No hashing needed — pointer
equality is sufficient. A `std::unordered_map<const char*, int>` (pointer → registry ref)
is enough.

```cpp
// In lua_engine state:
static std::unordered_map<const char*, int> gScriptRefs;

// In RunScript, before the #ifdef Fennel block:
auto it = gScriptRefs.find(src);
int fnRef = LUA_NOREF;
if (it != gScriptRefs.end()) {
    fnRef = it->second;
} else {
    if (luaL_loadstring(gL, src) != LUA_OK) {
        fprintf(stderr, "lua compile error: %s\n  script: %.80s\n",
                lua_tostring(gL, -1), src);
        lua_pop(gL, 1);
        return 0.0f;
    }
    fnRef = luaL_ref(gL, LUA_REGISTRYINDEX);
    gScriptRefs[src] = fnRef;
}
lua_rawgeti(gL, LUA_REGISTRYINDEX, fnRef);
if (lua_pcall(gL, 0, 1, 0) != LUA_OK) { ... }
```

Cache must be cleared in `Shutdown()` (`luaL_unref` each ref, then clear the map).

### 2. No per-actor state — globals leak between actors (correctness)

All actors share a single `lua_State` with a single global table. If an actor script
writes `phase = 3` (intending a local state variable but forgetting `local`), every other
actor sees `phase == 3` on its next tick. In real gameplay scripts — AI state machines,
cutscenes, dialogue — this will cause mysterious action-at-a-distance bugs.

Fix: give each actor its own environment table (`_ENV` in Lua 5.4), chained to the
shared globals so that `read_mailbox`, `write_mailbox`, and `INDEXOF_*` constants remain
visible without copying them.

```
actor_env.__index = _G      -- fallthrough reads hit shared globals
actor_env.__newindex = actor_env   -- writes stay in actor_env (opt-in)
```

Create per-actor env tables keyed by `objectIndex`. Store them in the Lua registry.
When `RunScript` loads the cached function ref, set its `_ENV` upvalue before calling:

```cpp
// push the actor env table (create on first use):
lua_rawgeti(gL, LUA_REGISTRYINDEX, gActorEnvRefs[objectIndex]);
// set upvalue 1 (_ENV) of the function:
lua_setupvalue(gL, -2, 1);
lua_pcall(gL, 0, 1, 0);
```

`gActorEnvRefs` can be a `std::unordered_map<int, int>` (objectIndex → registry ref).

Actor env creation:
```lua
-- from C:
lua_newtable(gL);                     // env table
lua_newtable(gL);                     // metatable
lua_pushglobaltable(gL);
lua_setfield(gL, -2, "__index");      // fallthrough reads
lua_setmetatable(gL, -2);
int ref = luaL_ref(gL, LUA_REGISTRYINDEX);
gActorEnvRefs[objectIndex] = ref;
```

Actor env tables must be freed in `Shutdown()`.

**Interaction with fix #1:** compilation cache and env cache are orthogonal. The compiled
function is cloned per-call (push ref, upvalue swap), not shared. This is the standard
Lua 5.4 pattern for per-instance scripting.

### 3. Fennel `fennel.eval` re-compiles every tick (performance)

The Fennel path calls `fennel.eval(src)` which runs the full Fennel compiler on every
invocation, just like `luaL_dostring`. For anything beyond a one-liner, this is expensive.

Fix: replace `fennel.eval` with a two-step approach:
1. On first call for a given script pointer: call `fennel.compileString(src)` → get Lua
   source string → `luaL_loadstring` → `luaL_ref`. Store in the same `gScriptRefs` map
   (Fennel and Lua refs live side-by-side since the dispatch is by sigil before cache
   lookup).
2. On subsequent calls: call by ref, same as fix #1.

The Fennel Lua API:
```lua
-- fennel.compileString(src) → lua_source_string
-- errors bubble as Lua error objects
```

From C:
```cpp
// First call:
lua_rawgeti(gL, LUA_REGISTRYINDEX, gFennelCompileRef);  // fennel.compileString
lua_pushstring(gL, src);
if (lua_pcall(gL, 1, 1, 0) != LUA_OK) { ... error ... }
size_t len;
const char* lua_src = lua_tolstring(gL, -1, &len);
if (luaL_loadbuffer(gL, lua_src, len, src) != LUA_OK) { ... error ... }
lua_remove(gL, -2);  // pop lua_src string
int fnRef = luaL_ref(gL, LUA_REGISTRYINDEX);
gScriptRefs[src] = fnRef;
```

Need a second cached ref: `gFennelCompileRef` (for `fennel.compileString`), loaded in
`Init` alongside `gFennelEvalRef`.

### 4. Debug `fprintf` on every mailbox read/write (noise + performance)

`lua_read_mailbox` and `lua_write_mailbox` both call `std::fprintf(stderr, ...)` on
every invocation. A player script runs `read_mailbox` + `write_mailbox` at 30 Hz;
that is 60 stderr writes per second from one actor alone.

Fix: gate behind `WF_SCRIPT_DEBUG`:

```cpp
#ifdef WF_SCRIPT_DEBUG
    std::fprintf(stderr, "  lua read_mailbox(%ld, actor=%d) -> %g\n", ...);
#endif
```

`WF_SCRIPT_DEBUG` is not currently defined anywhere; it would only be set by a developer
explicitly adding `-DWF_SCRIPT_DEBUG` to their build.

### 5. `luaL_openlibs` exposes `io` and `os` (sandbox)

`luaL_openlibs` opens all standard libraries including `io` (file I/O) and `os`
(process/environment). Game scripts have no legitimate need for these. Leaving them open
means a script bug (or a malicious level file) can read/write arbitrary files.

Fix: replace `luaL_openlibs` with selective opens:

```cpp
static const luaL_Reg safe_libs[] = {
    { LUA_GNAME,       luaopen_base    },
    { LUA_STRLIBNAME,  luaopen_string  },
    { LUA_MATHLIBNAME, luaopen_math    },
    { LUA_TABLIBNAME,  luaopen_table   },
    { LUA_UTF8LIBNAME, luaopen_utf8    },
    { LUA_COLIBNAME,   luaopen_coroutine },
    { NULL, NULL }
};
for (const luaL_Reg* lib = safe_libs; lib->func; lib++) {
    luaL_requiref(gL, lib->name, lib->func, 1);
    lua_pop(gL, 1);
}
```

`coroutine` is included deliberately — it is needed for fix #6 and has no I/O risk.

### 6. No multi-tick script continuations (missing feature)

The current model assumes each script returns in one call. Real gameplay scripts need to
span ticks: an AI state machine that waits 2 seconds, a cutscene that holds a camera
for 180 frames, a dialogue sequence that yields until the player presses a button.

`luaL_dostring` / `lua_pcall` run to completion in one tick. There is no way to
`coroutine.yield` back to C and resume next tick under the current call model.

Fix: for actors that return a coroutine thread, store it in the actor's env table and
`lua_resume` it on subsequent ticks instead of re-calling the function:

```
First tick:  load + call → script returns coroutine.wrap(fn) or coroutine itself
             → store thread ref in actor env
Next ticks:  lua_resume(thread, nargs=0)
             if status == LUA_YIELD: keep thread for next tick
             if status == LUA_OK:   thread finished; clear ref; back to direct call
             if status == error:    log; clear ref
```

Scripts that do not return a coroutine are unaffected (current behaviour preserved).

This is an additive change on top of fixes #1 and #2.

**Scope note:** this fix is larger than the others and can be deferred. Fixes #1–#5 are
independent of #6 and should land first.

## Implementation order

| Priority | Fix | Risk | Effort |
|----------|-----|------|--------|
| 1 | #4 — remove debug prints | None | 5 min |
| 2 | #5 — sandbox stdlib | Low | 15 min |
| 3 | #1 — script compilation cache | Low | 1 h |
| 4 | #2 — per-actor environment | Medium | 2 h |
| 5 | #3 — Fennel pre-compilation | Low (dep on #1) | 1 h |
| 6 | #6 — coroutine continuations | High | half-day |

Fixes #4 and #5 are zero-risk cleanups — do them immediately.
Fixes #1, #2, #3 together are "Lua engine hardening" and should land as one commit.
Fix #6 is a new feature; land separately after verifying #1–#5 don't regress anything.

## Verification

For each fix, the regression target is:
- `task build` compiles clean
- `task run-level -- wflevels/snowgoons.iff` — player moves, director cuts cameras,
  `fennel: loaded` appears in stderr
- Fennel player script (`;`-prefixed) and Lua director script both run without error

For fix #6 specifically: write a test actor script that yields once and resumes. Verify
the resumed tick sees the prior local state.

## Files to change

Only `wftools/wf_viewer/stubs/scripting_stub.cc` needs to change for fixes #1–#5.
Fix #6 may also touch `scripting_stub.cc` only, or may introduce a small helper header
if the coroutine management gets complex.

## As built (2026-04-15)

Fixes #1–#5 implemented in a single commit to `scripting_stub.cc`. Fix #6 (coroutines) implemented in a follow-up commit.

**Changes made:**

- **#4** — `lua_read_mailbox` / `lua_write_mailbox` `fprintf` calls gated on `WF_SCRIPT_DEBUG`.
- **#5** — `luaL_openlibs` replaced with selective opens: `base`, `string`, `math`, `table`,
  `utf8`, `coroutine`. `io` and `os` excluded.
- **#1** — `gScriptRefs: unordered_map<const char*, int>` added. `luaL_dostring` replaced
  with `luaL_loadstring` → `luaL_ref` on first call; `lua_rawgeti` + `lua_pcall` on
  subsequent calls. Cache cleared (with `luaL_unref`) in `Shutdown`.
- **#2** — `gActorEnvRefs: unordered_map<int, int>` added. `GetOrCreateActorEnv(objectIndex)`
  creates a table with `__index = _G` metatable on first use; `lua_setupvalue(gL, -2, 1)`
  swaps in the per-actor `_ENV` before each `lua_pcall`. Env tables freed in `Shutdown`.
- **#3** — `gFennelCompileRef` cached alongside `gFennelEvalRef` in `Init` (pointing to
  `fennel.compileString`). Fennel path now compiles to Lua source via `compileString`,
  loads with `luaL_loadbuffer`, stores compiled function in `gScriptRefs` (shared with
  Lua cache). Per-actor `_ENV` applied identically to Fennel functions.

**Note:** Fennel `eval` ref (`gFennelEvalRef`) is still cached in `Init` for now but
is no longer used at runtime — only `gFennelCompileRef` is called. Can be removed in a
cleanup pass.

**Sandbox correction:** `package` was added to `kSafeLibs` after smoke testing revealed
that Fennel uses `package.loaded` for module registration and fails to initialise without
it (`fennel: load failed: attempt to index a nil value (global 'package')`). `io` and
`os` remain excluded.

No other files are affected.

**Fix #6 (coroutines) — as built:**

- `gActorThreadRefs: unordered_map<int, int>` (objectIndex → registry ref) tracks live
  coroutine threads.
- `ResumeThread(objectIndex, threadRef, thread)` — resumes a thread, reads yield/return
  value from thread stack, clears ref on `LUA_OK` or error.
- `HandlePCallResult(objectIndex)` — after any successful `lua_pcall`, detects if the
  return value is a thread (`LUA_TTHREAD`); if so, stores it and calls `ResumeThread`
  for the first tick. Otherwise returns the numeric result.
- `RunScript` checks `gActorThreadRefs` before the compile+call path; active threads
  skip re-evaluation entirely.
- Both Lua and Fennel paths use `HandlePCallResult` — coroutine detection is uniform.
- `Shutdown` unrefs all thread refs before `lua_close`.
- Usage: scripts return `coroutine.create(fn)` (not `coroutine.wrap`). Plain scripts
  that return a number are unaffected.
- Documented in `docs/scripting-languages.md` under "Coroutines — multi-tick scripts"
  with four example patterns: wait-N-ticks, repeating state machine, wait-for-condition,
  and Fennel equivalent.
