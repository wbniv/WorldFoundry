# Plan: Wren as a scripting engine option for World Foundry

**Date:** 2026-04-14
**Status:** **complete — landed 2026-04-15; smoke test passed 2026-04-16 (GROUND, no crashes).**
All phases complete. Vendor `wftools/vendor/wren-0.4.0/`; plug in
`scripting_wren.{hp,cc}` (`wren_engine` namespace); `//wren\n` dispatch
arm in `ScriptRouter::RunScript`; `scripts/patch_snowgoons_wren.py`;
reference scripts in `docs/scripting-languages.md`.
**Prior art:** `docs/plans/2026-04-14-pluggable-scripting-engine.md` (JS pattern), `docs/plans/2026-04-14-wasm3-scripting-engine.md` (wasm3 pattern)

## Context

WF supports a menu of compile-time-selected scripting engines — Lua, Fennel, QuickJS, JerryScript, wasm3 — all sharing the same `read_mailbox` / `write_mailbox` bridge. Adding Wren gives authors an object-oriented, class-based scripting option with a tiny binary footprint (~100 KB). Wren is designed specifically for C embedding (clean VM API, MIT license, single-file amalgamation), and is Tier 1 in the scripting-language investigation. Like all other WF engines it is independent of Lua — `WF_ENABLE_WREN=1` without `WF_ENABLE_LUA=1` is a supported configuration.

## Sigil: `//wren\n`

Wren uses `//` for line comments, so `//wren\n` (a Wren comment naming the engine) is idiomatic Wren and a Lua syntax error. This 7-char prefix is checked **before** the generic `//` JavaScript check in `RunScript`; JS still catches any `//` that does not match. The dispatch order becomes: `//wren\n` → Wren, `//` → JS, `#b64\n` → wasm3, `;` → Fennel, else → Lua fallthrough.

## Wren API divergence from other engines

Wren has no top-level functions — everything is a method on a class. The mailbox bridge therefore surfaces as a **foreign class `Env`** with static methods rather than bare globals:
- `Env.read_mailbox(idx)` — returns Num
- `Env.write_mailbox(idx, value)` — void

Constants (`INDEXOF_*`, `JOYSTICK_BUTTON_*`) are prepended as module-level `var` declarations in a preamble string built once at `WrenRuntimeInit()`. They are accessible as bare names in user scripts.

Example snowgoons player:
```wren
//wren
Env.write_mailbox(INDEXOF_INPUT, Env.read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))
```

Example snowgoons director:
```wren
//wren
var v
v = Env.read_mailbox(100); if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
v = Env.read_mailbox(99);  if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
v = Env.read_mailbox(98);  if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
```

## Implementation phases

### Phase 1 — Vendor Wren

Vendor Wren 0.4.0 single-file amalgamation from https://github.com/wren-lang/wren/releases/tag/0.4.0

Files needed from `single/`:
```
wftools/vendor/wren-0.4.0/
  src/
    wren.c     (amalgamation, ~7 000 lines)
    wren.h     (public API)
  LICENSE
```

Add to `wftools/vendor/README.md`:
```
| `wren-0.4.0/` | 0.4.0 | MIT | https://github.com/wren-lang/wren/releases/tag/0.4.0 |
```
And record the tarball SHA256 in the SHA256 section.

### Phase 2 — Plug header

**New file:** `wftools/wf_viewer/stubs/scripting_wren.hp`

```cpp
#pragma once
#ifdef WF_ENABLE_WREN

class MailboxesManager;
struct IntArrayEntry;

namespace wren_engine {
    void  Init(MailboxesManager& mgr);
    void  Shutdown();
    void  AddConstantArray(IntArrayEntry* entryList);
    void  DeleteConstantArray(IntArrayEntry* entryList);  // no-op (preamble rebuilt on add)
    float RunScript(const char* src, int objectIndex);
}

#endif // WF_ENABLE_WREN
```

### Phase 3 — Implementation

**New file:** `wftools/wf_viewer/stubs/scripting_wren.cc`

Key design points:

**Global state:**
```cpp
static MailboxesManager* g_mgr    = nullptr;
static int               g_curObj = 0;
static std::string       g_preamble;   // "var INDEXOF_INPUT = 3024\n..."

// WrenConfiguration template (foreign method bindings, write/error fn)
// stored as a file-scope struct, initialized once in WrenRuntimeInit()
static WrenConfiguration g_config;
```

**`wren_engine::Init(mgr)`:**
1. Store `mgr` in `g_mgr`.
2. `wrenInitConfiguration(&g_config)`.
3. Set `g_config.writeFn`, `g_config.errorFn` (stderr), `g_config.bindForeignMethodFn`.
4. `g_config.loadModuleFn = nullptr` (no imports needed — preamble approach).
5. `g_preamble` starts empty; `WrenAddConstantArray()` appends to it.

**`wren_engine::AddConstantArray(entryList)`:**
- Walk `IntArrayEntry*` and append `"var " + name + " = " + value + "\n"` to `g_preamble`.

**`wren_engine::RunScript(src, objectIndex)`:**
1. `g_curObj = objectIndex`.
2. Strip the `//wren\n` sigil line from `src`.
3. Build combined source: `g_preamble + "\n" + stripped_src`.
4. `WrenVM* vm = wrenNewVM(&g_config)`.
5. `wrenInterpret(vm, "wf", kWrenEnvSource)` — defines the `Env` foreign class.
6. `wrenInterpret(vm, "main", combined_source)`.
7. Retrieve return value via `wrenGetSlotDouble(vm, 0)` (or `0.0f` if no result / error).
8. `wrenFreeVM(vm)`. Return result as float.

> **Note:** Per-call `wrenNewVM`/`wrenFreeVM` is chosen for the spike for simplicity (matches wasm3's per-call parse/instantiate pattern). A persistent-VM optimization can follow if profiling shows it as a bottleneck.

**Foreign method binder (`g_config.bindForeignMethodFn`):**
```cpp
WrenForeignMethodFn bind(WrenVM*, const char* module,
                          const char* className, bool isStatic,
                          const char* signature) {
    if (strcmp(className, "Env") == 0 && isStatic) {
        if (strcmp(signature, "read_mailbox(_)")    == 0) return wren_read_mailbox;
        if (strcmp(signature, "write_mailbox(_,_)") == 0) return wren_write_mailbox;
    }
    return nullptr;
}
```

**Foreign method implementations:**
```cpp
void wren_read_mailbox(WrenVM* vm) {
    int idx = (int)wrenGetSlotDouble(vm, 1);
    float v = g_mgr->ReadMailbox(idx, g_curObj);
    wrenSetSlotDouble(vm, 0, v);
}
void wren_write_mailbox(WrenVM* vm) {
    int idx = (int)wrenGetSlotDouble(vm, 1);
    float val = (float)wrenGetSlotDouble(vm, 2);
    g_mgr->WriteMailbox(idx, val, g_curObj);
}
```

**`kWrenEnvSource` constant (embedded as `static const char[]`):**
```wren
class Env {
  foreign static read_mailbox(idx)
  foreign static write_mailbox(idx, value)
}
```

### Phase 4 — Dispatch in `ScriptRouter` (`scripting_stub.cc`)

**File:** `wftools/wf_viewer/stubs/scripting_stub.cc`

1. Add include at top (guarded):
```cpp
#ifdef WF_ENABLE_WREN
#include "scripting_wren.hp"
#endif
```

2. In `ScriptRouter::ScriptRouter()` (alongside `lua_engine::Init`, `js_engine::Init`, `wasm3_engine::Init`):
```cpp
#ifdef WF_ENABLE_WREN
    wren_engine::Init(mgr);
#endif
```

3. In `ScriptRouter::~ScriptRouter()` (reverse order):
```cpp
#ifdef WF_ENABLE_WREN
    wren_engine::Shutdown();
#endif
```

4. In `ScriptRouter::AddConstantArray(entryList)`:
```cpp
#ifdef WF_ENABLE_WREN
    wren_engine::AddConstantArray(entryList);
#endif
```

5. In `ScriptRouter::DeleteConstantArray(entryList)`:
```cpp
#ifdef WF_ENABLE_WREN
    wren_engine::DeleteConstantArray(entryList);
#endif
```

6. In `ScriptRouter::RunScript()`, insert **before** the `//` JS block (the `//wren\n` prefix must match before the shorter `//`):
```cpp
#ifdef WF_ENABLE_WREN
    {
        const char* p = src;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (p[0]=='/' && p[1]=='/' && p[2]=='w' && p[3]=='r'
            && p[4]=='e' && p[5]=='n' && p[6]=='\n') {
            return Scalar::FromFloat(wren_engine::RunScript(src, objectIndex));
        }
    }
#endif
```

### Phase 5 — Build system

**File:** `wftools/wf_engine/build_game.sh`

1. Near the top where feature flags are declared (~line 35):
```bash
WF_ENABLE_WREN="${WF_ENABLE_WREN:-0}"
WREN_DIR="$VENDOR/wren-0.4.0"
```

2. Add to `CXXFLAGS` conditionally (after the other engine includes):
```bash
[[ "$WF_ENABLE_WREN" == "1" ]] && CXXFLAGS+=(-DWF_ENABLE_WREN -I"$WREN_DIR/src")
```

3. Add compilation block (after the wasm3 section, before the link step):
```bash
if [[ "$WF_ENABLE_WREN" == "1" ]]; then
    echo "  CC (stub) scripting_wren.cc"
    g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_wren.cc" \
        -o "$OUT/stubs__scripting_wren.o"
    OBJS+=("$OUT/stubs__scripting_wren.o")

    echo "  CC (vendor) wren.c"
    gcc -std=c11 -O2 -w -I"$WREN_DIR/src" \
        -c "$WREN_DIR/src/wren.c" -o "$OUT/wren__wren.o"
    OBJS+=("$OUT/wren__wren.o")
fi
```

### Phase 6 — Documentation

**File:** `docs/scripting-languages.md`

Add row to both engine tables:
```
| Wren 0.4 | `//wren\n` | `WF_ENABLE_WREN=1` | vendored `wftools/vendor/wren-0.4.0/`, single amalgamation | ~100 KB | spike |
```

Add snowgoons player + director examples in Wren to the reference scripts section.

Note in the "Notes for future languages" section: Wren's foreign-class model means mailbox functions surface as `Env.read_mailbox(idx)` rather than bare `read_mailbox(idx)` — an intentional divergence from the Lua/JS/wasm3 surface.

### Phase 7 — Snowgoons demo scripts

**New file:** `scripts/patch_snowgoons_wren.py`

Following the same pattern as `patch_snowgoons_lua.py` / `patch_snowgoons_fennel.py`:
- Write the Wren player + director scripts as strings.
- Patch them into the snowgoons IFF script slots (byte-for-byte replacement, same size constraint as other patchers — document slot size vs. script size).

## Critical files

| File | Action |
|------|--------|
| `wftools/vendor/wren-0.4.0/` | Create (vendor tarball) |
| `wftools/vendor/README.md` | Add row + SHA256 |
| `wftools/wf_viewer/stubs/scripting_wren.hp` | Create (plug ABI header) |
| `wftools/wf_viewer/stubs/scripting_wren.cc` | Create (implementation) |
| `wftools/wf_viewer/stubs/scripting_stub.cc` | Add dispatch block + lifecycle hooks |
| `wftools/wf_engine/build_game.sh` | Add `WF_ENABLE_WREN` flag + compile block |
| `docs/scripting-languages.md` | Add Wren row + reference scripts |
| `scripts/patch_snowgoons_wren.py` | Create patcher |

## Verification

1. **Default build (no Wren):** `./wftools/wf_engine/build_game.sh` — zero footprint change.
2. **Wren build:** `WF_ENABLE_WREN=1 ./wftools/wf_engine/build_game.sh` — compiles cleanly.
3. **Selftest:** minimal Wren script (`//wren\nEnv.write_mailbox(0, 42.0)`) verified in a `WrenRunScript` unit call; confirm the foreign method is reached and the return is correct.
4. **Snowgoons integration:** patch Wren scripts into snowgoons IFF via `scripts/patch_snowgoons_wren.py`, launch `wf_game`, confirm director switches camshot on triggers and player forwards joystick input.
5. **Binary delta:** `size wf_game` before/after — expect ~100 KB increase with `WF_ENABLE_WREN=1`.
