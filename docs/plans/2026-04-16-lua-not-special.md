# Plan: Lua engine is not special — make it optional

**Date:** 2026-04-16
**Status:** Done
**Goal:** Lua is a peer engine, compiled in by `WF_LUA_ENGINE=lua54` (default) and absent when `WF_LUA_ENGINE=none`. No engine is hardcoded. Fennel depends on Lua; it is forced off when Lua is absent.

## Problem

All scripting engines except Lua are optional. The pattern for every other engine:

- `WF_JS_ENGINE=quickjs|jerryscript|none`
- `WF_WASM_ENGINE=wamr|wasm3|none`
- `WF_FORTH_ENGINE=zforth|ficl|…|none`
- `WF_ENABLE_WREN=0|1`

Lua breaks this pattern in two ways:

1. **`build_game.sh` line 110** hardcodes `-DWF_ENABLE_LUA` unconditionally.
2. **`scripting_stub.cc`** contains `lua_engine` as an inline namespace (lines ~104–420) rather than a separate TU like every other engine. The Lua `#include` directives (`lua.h`, `lualib.h`, `lauxlib.h`) and the vendor compilation loop in `build_game.sh` are also always active.

## Steps

### Step 1 — Extract `lua_engine` into `scripting_lua.cc`

Move the `lua_engine` namespace block (currently embedded in `scripting_stub.cc`) into `engine/stubs/scripting_lua.cc`. Pattern matches every other engine stub. `scripting_stub.cc` gets a forward declaration / include of the new file's public surface, guarded by `#ifdef WF_ENABLE_LUA`.

**Files changed:**
- `engine/stubs/scripting_stub.cc` — remove inline `lua_engine` block; add `#ifdef WF_ENABLE_LUA` guard around the lua includes and dispatch slot.
- `engine/stubs/scripting_lua.cc` — new file; the extracted `lua_engine` namespace + its `#include <lua.h>` etc.
- `engine/stubs/scripting_lua.hp` — new header declaring `lua_engine::RunScript` (mirrors `scripting_js.hp`, `scripting_wren.hp`, etc.).

### Step 2 — Add `WF_LUA_ENGINE` flag to `build_game.sh`

Mirror the pattern of `WF_JS_ENGINE` and `WF_WASM_ENGINE`:

```bash
WF_LUA_ENGINE="${WF_LUA_ENGINE:-lua54}"  # lua54 | none

case "$WF_LUA_ENGINE" in
    lua54)
        CXXFLAGS+=(-DWF_ENABLE_LUA -DWF_LUA_ENGINE_LUA54 -I"$LUA_DIR/src")
        # compile vendored Lua .c TUs (already in build_game.sh lines 298-305)
        # compile scripting_lua.cc
        ;;
    none)
        # nothing — Lua absent
        ;;
    *)
        echo "Unknown WF_LUA_ENGINE=$WF_LUA_ENGINE"; exit 1 ;;
esac
```

Move the Lua vendor compilation loop (currently unconditional at lines 298–305) inside the `lua54` branch.

**Fennel dependency:** Fennel runs on Lua; enabling Fennel implicitly enables Lua. Handle this at the preprocessor level, not the build script, so it is enforced regardless of build system:

```c
// In scripting_fennel.cc (or scripting_lua.cc top-of-file):
#ifdef WF_ENABLE_FENNEL
#  ifndef WF_ENABLE_LUA
#    define WF_ENABLE_LUA   // Fennel requires Lua; auto-enable
#  endif
#endif
```

The build script should still honour the dependency when assembling the TU list — if `WF_ENABLE_FENNEL=1`, force `WF_LUA_ENGINE=lua54` before evaluating the Lua case block so the vendor compilation and `-I` path are included.

### Step 3 — Update CMakeLists (when it exists)

When the CMake build (Phase 1 of the Android plan) is written, it must expose `WF_LUA_ENGINE` as a CMake variable with the same `lua54|none` semantics. The Android Forth-only preset sets `WF_LUA_ENGINE=none`.

**Note:** For now `build_game.sh` is the only build system; CMake does not exist yet. This step is a reminder to carry the flag forward correctly.

### Step 4 — Verify

1. **Default build** (`WF_LUA_ENGINE=lua54`): snowgoons works identically — Lua, Fennel, all sigils. No regression.
2. **Lua-off build** (`WF_LUA_ENGINE=none WF_ENABLE_FENNEL=0`): binary compiles, links, and snowgoons runs via the Forth path. No linker errors; no `lua_engine` symbols present.
3. **Fennel auto-disable**: `WF_LUA_ENGINE=none WF_ENABLE_FENNEL=1` prints the warning and builds successfully without Fennel.

## Critical files

| File | Change |
|------|--------|
| `engine/stubs/scripting_stub.cc` | Remove inline `lua_engine`; guard Lua dispatch slot with `#ifdef WF_ENABLE_LUA` |
| `engine/stubs/scripting_lua.cc` | New — extracted `lua_engine` namespace |
| `engine/stubs/scripting_lua.hp` | New — header declaring `lua_engine::RunScript` |
| `engine/build_game.sh` | Replace hardcoded `-DWF_ENABLE_LUA` with `WF_LUA_ENGINE` case block; move vendor Lua loop inside it; add Fennel guard |

## Out of scope

- Alternative Lua versions (5.1, 5.3, LuaJIT) — the flag name is `WF_LUA_ENGINE` to leave room, but only `lua54` and `none` are implemented here.
- Fennel without Lua — impossible; not attempted.
