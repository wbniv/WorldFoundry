# Lua remote step debugger — default Lua on in Linux debug build, then wire MobDebug

**Status:** Not started
**Date:** 2026-05-10

## Context

The [TODO.md](../../TODO.md) `LUA ENGINE` section has a single open item:

> Lua remote step debugger — MobDebug / LuaLS-DAP wired into `lua_engine`
> for in-game step debugging

Two things block it today:

1. The canonical Linux dev build (`task build` → `engine/build_game.sh`)
   explicitly turns Lua **off** via `Taskfile.yml:14`
   (`WF_LUA_ENGINE: none`). `engine/build_game.sh:81` would otherwise default
   to `lua54`. There's nothing for a debugger to attach to.
2. `lua_engine` (`engine/stubs/scripting_lua.cc`) installs no debug hook
   and exposes no transport for an IDE.

User intent (clarified this session):

- Default Lua on **only for the Linux debug build**. Android / iOS /
  Chromecast targets unchanged — the step debugger is a "dev on a real
  computer" feature, not a shipping one.
- An explicit `WF_LUA_ENGINE=none` env override must still win. We are
  changing a default, not making Lua mandatory. Preserves the "all engines
  optional" principle.
- Once Lua is reliably present in the dev binary, actually wire the
  debugger so a level designer can set breakpoints, step, and inspect
  locals from an editor while `wf_game` keeps a hot reload loop going.

Intended outcome: a developer running `task build && task wf` (or whatever
the standard launch flow is) can attach VS Code / ZeroBrane Studio to a
running `wf_game`, hit a breakpoint inside a Lua-authored level script (or
a Fennel-authored one — Fennel compiles through `lua_engine`, so it gets
breakpoints for free), step, inspect, and resume — without freezing the
engine more than the script's own frame budget.

## Approach (phased)

### Phase A — flip the Linux dev default (≈5 min)

Single edit, in `Taskfile.yml` `build` task env block:

```diff
   build:
     desc: "Build wf_game (Forth + Jolt; canonical config)"
     env:
-      WF_LUA_ENGINE: none
+      # Lua is linked into the Linux debug build so the in-engine Lua
+      # step debugger (MobDebug) has a host to bind to. Override with
+      # WF_LUA_ENGINE=none if you need a Forth-only binary.
       WF_ENABLE_FENNEL: "0"
       WF_JS_ENGINE: none
       WF_WASM_ENGINE: none
       WF_ENABLE_WREN: "0"
       WF_FORTH_ENGINE: zforth
       WF_PHYSICS_ENGINE: jolt
```

`engine/build_game.sh:81` already defaults `WF_LUA_ENGINE` to `lua54` when
unset, so removing the override is enough. A user passing
`WF_LUA_ENGINE=none task build` still wins (the env they pass takes
precedence over the Taskfile env block).

`WF_ENABLE_FENNEL` stays `0`. Fennel is a separate dialect built on top of
Lua; the debugger doesn't need it, and leaving it off keeps the build
narrow. `build_game.sh:82-84` already enforces the Fennel→Lua direction.

**Not touched in Phase A:**
- `CMakeLists.txt` — `CMakeLists.txt:16` already defaults to `lua54`. The
  Android/iOS override at lines 28–29 stays, so mobile keeps forcing Lua off.
- `engine/build_game.sh` — its own default at line 81 is correct already.

### Phase B — vendor MobDebug + LuaSocket, install debug hook (≈½ day)

Recommended debugger: **MobDebug** (`pkulchenko/MobDebug`). It is the
de-facto standard for embedded-Lua remote step debugging, works with
ZeroBrane Studio out of the box, and is supported by VS Code via the
`tomblind.local-lua-debugger-vscode` extension's MobDebug mode. It is one
Lua file (~50 KB) plus a single C dependency: LuaSocket. Both are MIT.

DBG.lua (`slembcke/debugger.lua`) was considered and dropped — it is
in-process REPL only, no separate-window/IDE support, which is exactly the
mode the user asked for. LuaLS-DAP was also considered; its server is
heavier and its remote-attach story for embedded hosts is less mature than
MobDebug's.

**Vendor steps:**
1. `engine/vendor/mobdebug/mobdebug.lua` — single-file drop from upstream
   tag (pin SHA in a `VERSION` sidecar).
2. `engine/vendor/luasocket-3.1.0/` — minimal subset (`src/auxiliar.c`,
   `buffer.c`, `compat.c`, `except.c`, `inet.c`, `io.c`, `luasocket.c`,
   `options.c`, `select.c`, `tcp.c`, `timeout.c`, `socket.lua`,
   `mime/{ltn12.lua,mime.lua,mime.c}`). Strip Windows + serial bits.
   Per memory `feedback_no_giant_vendor` this is well under the 40 MB
   cap — LuaSocket source is ~200 KB.

**Build wire-up (in `engine/build_game.sh`, mirroring the existing Lua
plug at lines 334–370):**
- Compile LuaSocket C sources as a static archive `libluasocket.a` under
  the same gated path (`case "$WF_LUA_ENGINE"` → `lua54`).
- Concatenate `mobdebug.lua` and `socket.lua` (+ `ltn12.lua`, `mime.lua`)
  into a `kMobDebugSource[]` byte array via the same generator that
  produces `kFennelSource` today (look for `fennel_embed` or similar in
  `build_game.sh`; reuse).
- Add a new define `WF_ENABLE_LUA_DEBUG` (separate from `WF_ENABLE_LUA`
  so a user can keep Lua but skip the debugger if they want). Default on
  when `WF_ENABLE_LUA` is on **and** `BUILDMODE_DEBUG` is set —
  i.e., dev-build-only.

**Hook installation in `engine/stubs/scripting_lua.cc`:**
- In `lua_engine::Init`, after the safe-libs block and the C-closure
  registration, if `WF_ENABLE_LUA_DEBUG` is defined:
  - Add `socket` C library to `package.preload` (LuaSocket's standard
    embedding pattern: `luaopen_socket_core`).
  - Load `kMobDebugSource[]` via `luaL_loadbuffer` + `lua_pcall`.
  - Read host/port from env (`WF_LUA_DEBUG_HOST` / `WF_LUA_DEBUG_PORT`),
    defaults `localhost` / `8172` (MobDebug standard).
  - Call `mobdebug.start(host, port)` — non-blocking; MobDebug only
    actually connects on first `coroutine.yield` / breakpoint check.
- No change needed in `RunScript` — MobDebug installs its own
  `debug.sethook`, which Lua 5.4 calls automatically inside `lua_pcall`.

**Sandbox:** today `Init` only opens "safe" libraries (no `io`, no `os`).
MobDebug needs `os.time` and `io.stdout`; either expose narrow shims, or
gate the full `io`/`os` library on `WF_ENABLE_LUA_DEBUG`. The latter is
fine — debug builds aren't a security boundary.

### Phase C — IDE launch config + smoke test (≈1 h)

- `.vscode/launch.json` example (committed) for
  `tomblind.local-lua-debugger-vscode` in `mobdebug` mode, pointing at
  `localhost:8172`.
- `docs/dev/lua-step-debugging.md` — one-page how-to (start engine, hit
  Run-and-Debug in VS Code, breakpoint in a `.lua` script under
  `wflevels/snowgoons/`).
- Smoke test: drop a one-line Lua script into `snowgoons` (or qbert if
  it has Lua scripts by then), set a breakpoint, confirm hit + step +
  inspect + resume returns control to the game thread without leaking.

## Files Touched

- `Taskfile.yml` — Phase A.
- `engine/build_game.sh` — Phase B vendor wiring + `WF_ENABLE_LUA_DEBUG`
  gate.
- `engine/stubs/scripting_lua.cc` — Phase B hook install in `Init`.
- `engine/stubs/scripting_lua.hp` — possibly expose a `DebugAttached()`
  accessor (only if needed by frame loop; probably not).
- `engine/vendor/mobdebug/` — new directory.
- `engine/vendor/luasocket-3.1.0/` — new directory.
- `.vscode/launch.json` — Phase C.
- `docs/dev/lua-step-debugging.md` — Phase C.
- [TODO.md](../../TODO.md) `LUA ENGINE` section — mark item complete
  after Phase C verifies end-to-end.
- [wf-status.md](../../wf-status.md) — prepend one-sentence summary at
  top of Summary section per `feedback_wf_status_rolling_summary` and
  `feedback_wf_status_paragraph_length`.

## Files Deliberately Not Touched

- `CMakeLists.txt` mobile override at lines 28–29 — Android/iOS keep
  forcing Lua off; debugger is dev-only.
- `engine/build_game.sh:81` default — stays `lua54`; the Taskfile
  override is the only thing changing.
- `engine/stubs/debug_server.cc` — separate TCP/JSON bridge (port 7777)
  for Blender hot-reload; MobDebug runs on its own port (8172) so the two
  channels don't collide.

## Open Questions

1. **LuaSocket vs. reuse existing debug bridge.** `engine/stubs/debug_server.cc`
   already runs a TCP listener for the Blender hot-reload protocol. We
   could in principle multiplex MobDebug traffic over that and skip
   LuaSocket entirely. Trade-off: avoids vendoring ~200 KB of C, but
   requires a custom Lua transport that pretends to be `socket.tcp` —
   meaningful work, easy to get subtly wrong, and breaks compatibility
   with stock MobDebug clients. **Recommendation: vendor LuaSocket** unless
   the user has a strong objection.
2. **Pause-while-debugging behavior.** A breakpoint inside a script
   blocks the game thread (per `feedback_variable_tick_rate_loadbearing`
   in [memory], tick rate is variable so the engine will see a giant dt
   spike on resume). Options: (a) clamp dt after resume, (b) accept the
   spike, (c) run scripts on a separate thread (large refactor). Phase C
   should ship with (a) — a single-line dt clamp in the script-call site.

## Verification

After Phase A:
1. `task build` — links `liblua54.a`; build log shows `CC lapi.c` etc.
2. `nm wfsource/source/game/wf_game | grep -E 'lua_State|lua_pcall'` —
   Lua runtime symbols present.
3. `wf_game -Lsnowgoons.iff` — boots and plays normally (regression check).
4. `WF_LUA_ENGINE=none task build` — confirm override wins; Lua symbols
   absent.

After Phase B:
5. Build log shows MobDebug + LuaSocket sources compiling under
   `WF_ENABLE_LUA_DEBUG`.
6. `wf_game` startup logs `mobdebug: listening on :8172` (or similar);
   `ss -tlnp | grep 8172` confirms the port is open.
7. With no client connected, scripts run normally with no measurable
   per-frame overhead (MobDebug's hook is no-op until a client attaches).

After Phase C:
8. From VS Code, "Run and Debug" → "Lua: attach to wf_game" connects.
9. Drop a breakpoint in a Lua-authored level script. Trigger the actor.
   VS Code halts on the line, shows locals, accepts step-over and
   continue. Engine resumes cleanly with no dt-spike crash.
10. Detach client, confirm engine keeps running and breakpoint is
    cleared.
11. Re-attach, hit breakpoint again — proves the hook stays installed
    across detach cycles.
12. Verify Android build still excludes Lua: `task build-cmake-android`
    log must not include `lapi.c`.
