# Plan: Lua 5.4 Interpreter Spike (snowgoons player + director)

**Date:** 2026-04-13
**Source investigation:** `docs/investigations/2026-04-14-scripting-language-replacement.md`
**Decision being spiked:** Lua 5.4 as the WF scripting language, replacing the stubbed `NullInterpreter` (and, in history, TCL).

## Context

The scripting-language investigation recommends **Lua 5.4** as the primary scripting runtime, with an optional Fennel layer for Lisp authors. The recommended next step is an afternoon spike that replaces the current `NullInterpreter` with a real `LuaInterpreter` and runs hand-ported scripts from the existing `snowgoons` level.

Why this matters now: the engine *does* run on Linux today (snowgoons loads and renders), but scripts silently no-op under `NullInterpreter`, so the player can't move and the director can't cut cameras. A working Lua spike would be the first time the Linux port of WF actually responds to input. It also shakes out three specific integration concerns in one pass:

1. C++ embedding API ergonomics (`lua_State`, `luaL_dostring`, C closures).
2. Mailbox marshalling via `read_mailbox` / `write_mailbox` C bindings that cross the Lua↔engine boundary.
3. The `AddConstantArray` name-injection mechanism — mapping the `INDEXOF_*` namespace into Lua globals without TCL's `Tcl_LinkVar`.

If the spike works cleanly, we commit to Lua for WF scripting and start the broader migration (Fennel layer, `.lev` script translator, SDK helpers). If it's awkward, we reopen the decision with data instead of theory.

## Scope

**In scope:**
- Build `wf_game` on this machine (prerequisite — currently not built here).
- New `wfsource/source/scripting/luainterpreter.{cc,hp}` implementing `ScriptInterpreter`.
- Wire `ScriptInterpreterFactory` to return `LuaInterpreter` (behind a build flag or flat replacement).
- Hand-port the snowgoons player script and director script from TCL to Lua, in `wflevels/snowgoons/snowgoons.lev` (TCL originals preserved as comments or backup).
- Run snowgoons end-to-end; verify joystick input moves the player and director-driven camshot changes take effect.

**Out of scope (deliberately):**
- Automatic TCL→Lua translator for all `.lev` files. Hand-port two scripts only.
- Fennel layer. Lua 5.4 only.
- Typed mailbox accessors (`read_actor` / `read_fixed` etc.). Raw `read_mailbox` / `write_mailbox` are enough to prove the mechanism.
- Wasm / Wren / other runtimes.
- Deleting `TCLInterpreter` source. Leave it in tree; just don't link it.

## Prerequisites (step 0)

Build recipe (from prior session notes):

```bash
# Build
cd wftools/wf_engine && bash build_game.sh

# Run (from wfsource/source/game where cd.iff lives)
cd wfsource/source/game
LD_LIBRARY_PATH=../../../wftools/wf_engine/libs DISPLAY=:0 \
  ../../../wftools/wf_engine/wf_game
```

`build_game.sh` uses the scripting + platform stubs in `wftools/wf_viewer/stubs/`. The engine is currently hardcoded to boot level 4 (snowgoons) with scripting disabled (`NullInterpreter`). Reproduce this baseline before touching Lua — that's the known-good regression target.

## Implementation

### 1. `LuaInterpreter` skeleton

**File:** `wfsource/source/scripting/luainterpreter.hp`

```cpp
#include "scriptinterpreter.hp"
struct lua_State;

class LuaInterpreter : public ScriptInterpreter {
public:
    LuaInterpreter(MailboxesManager& mgr, Memory& mem);
    ~LuaInterpreter() override;

    Scalar RunScript(const void* script, int objectIndex) override;
    void   AddConstantArray(IntArrayEntry* entryList) override;
    void   DeleteConstantArray(IntArrayEntry* entryList) override;

private:
    lua_State* _L;
    int        _currentObjectIndex;   // captured by read_mailbox / write_mailbox
};
```

**File:** `wfsource/source/scripting/luainterpreter.cc`

- Construct: `luaL_newstate()`, `luaL_openlibs()` (base/string/math/table — skip io/os for sandbox hygiene).
- Stash `this` in the Lua extra space (`lua_getextraspace(L)`) so C closures can recover it.
- Register `read_mailbox` and `write_mailbox` via `lua_register` as C functions that:
  - `luaL_checkinteger` the mailbox index argument,
  - fetch `_mailboxesManager.LookupMailboxes(_currentObjectIndex)`,
  - call `ReadMailbox(idx)` / `WriteMailbox(idx, Scalar::FromFloat(lua_tonumber(L, 2)))`,
  - push the `Scalar` result back as `lua_pushnumber`.
- `RunScript`: set `_currentObjectIndex = objectIndex`, call `luaL_dostring(_L, (const char*)script)`. On error, log via the engine's logging primitive and return `Scalar::FromInt(0)`. On success, pop any numeric return and convert to `Scalar`.
- `AddConstantArray`: iterate `entryList` until `name==NULL`, `lua_pushinteger(value); lua_setglobal(name)`.
- `DeleteConstantArray`: iterate, `lua_pushnil; lua_setglobal(name)`.

Reference existing TCL implementation at `wfsource/source/scripting/tcl.cc:12-238` for the pattern — Lua version is shorter because we don't need `Tcl_LinkVar`'s write-back semantics.

### 2. Factory swap

**File:** `wfsource/source/scripting/scriptinterpreter.cc:62-68`

Replace the `TCLInterpreter` instantiation with `LuaInterpreter`. Guard behind `WF_SCRIPTING_LUA` macro if we want a side-by-side toggle; otherwise just change the body.

Confirm what the current `NullInterpreter` build is doing — there's likely another factory override somewhere (based on the project memory that snowgoons ran with `NullInterpreter`). Find it and redirect it to `LuaInterpreter` in the same spot.

### 3. Makefile

**File:** `wfsource/source/scripting/Makefile`

- Add `luainterpreter.cc` to the library source list.
- Link `-llua5.4` for the game executable (not the scripting `.a` itself — the lib just needs `<lua.h>` on the include path).
- System deps: `apt install liblua5.4-dev liblua5.4-0`.

### 4. Hand-port the two snowgoons scripts

**File:** `wflevels/snowgoons/snowgoons.lev`

Identify the two script blocks. Per the explore report, the director block is around lines 3072-3080. Find the player script similarly.

Replace TCL source with Lua source in-place. Preserve the TCL original as a quoted comment block in the same attribute string, or duplicate the file as `snowgoons.lev.tcl` for safety.

TCL originals:
```tcl
# Player
write-mailbox $INDEXOF_INPUT [read-mailbox $INDEXOF_HARDWARE_JOYSTICK1_RAW]

# Director
if { [read-mailbox 100] } { write-mailbox $INDEXOF_CAMSHOT [read-mailbox 100] }
if { [read-mailbox 99]  } { write-mailbox $INDEXOF_CAMSHOT [read-mailbox 99] }
if { [read-mailbox 98]  } { write-mailbox $INDEXOF_CAMSHOT [read-mailbox 98] }
```

Lua ports:
```lua
-- Player
write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))

-- Director
local v
v = read_mailbox(100); if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end
v = read_mailbox(99);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end
v = read_mailbox(98);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end
```

Note: TCL `if { [read-mailbox N] }` is truthy on any non-zero scalar — Lua's `if v` is truthy even for `0`, so we need `v ~= 0`. Easy trap.

## Verification

- Build: `wf_game` compiles, links against `-llua5.4`, produces a binary.
- Launch snowgoons with the Lua-backed engine.
- **Player check:** move joystick / press arrow keys. Player actor responds (moves / jumps per snowgoons' existing `Mobility == Physics` rules).
- **Director check:** whatever snowgoons gameplay writes to mailboxes 98/99/100 (likely triggers / room transitions) causes the camera to cut to the referenced camshot.
- **Error-path check:** deliberately introduce a Lua syntax error in the player script; confirm the engine logs the error and keeps running rather than crashing.
- **Regression:** render still works, no new crashes, frame rate unchanged within noise.

## Critical files

- `wfsource/source/scripting/scriptinterpreter.hp` — interface.
- `wfsource/source/scripting/scriptinterpreter.cc:62-68` — factory to swap.
- `wfsource/source/scripting/tcl.cc:12-238` — reference implementation; mirror its shape.
- `wfsource/source/mailbox/mailbox.hp:58-112` — `Mailboxes` / `MailboxesManager` API.
- `wfsource/source/mailbox/mailbox.inc` — `MAILBOXENTRY` macro source for `INDEXOF_*` names.
- `wfsource/source/scripting/Makefile` — add `luainterpreter.cc`, link Lua.
- `wflevels/snowgoons/snowgoons.lev:~3072-3080` — director script; player script nearby.
- `wfsource/source/game/game.cc:136-215` — script dispatch loop (read-only, for understanding).

## Deliverable

- `LuaInterpreter` committed and linked in `wf_game`.
- Snowgoons player script and director script ported to Lua, running in-game.
- Build notes for `wf_game` on Linux captured in a permanent doc.
- One-paragraph postmortem in this plan's commit message or a follow-up doc: what felt clean, what felt awkward, go/no-go for Lua as the permanent choice.

## Open questions

1. Which object in snowgoons runs the director script — specific actor name, or the per-frame game-level SHELL script? Needed to locate the right script block. (Discover via `grep` on `snowgoons.lev`; not blocking.)

Branch policy: spike lives on `master`.
