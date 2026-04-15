# Scripting languages in WF

The engine supports several scripting languages. **A build chooses any
subset** — Lua-only, JS-only, Lua + Fennel, QuickJS + wasm3, etc. No
language is mandatory; the scriptless build (no engines compiled in) is
valid too. Every engine targets the same embedded API —
`read_mailbox(idx[, actor])`, `write_mailbox(idx, value[, actor])`, and
the `INDEXOF_*` / `JOYSTICK_BUTTON_*` globals — so scripts authored in
one language call into the game identically to scripts authored in
another.

| Engine | Compile-time switch | Sigil | Notes |
|--------|--------------------|-------|-------|
| Lua 5.4 | `WF_ENABLE_LUA=1` (default on today; will become off-able) | *(no sigil — the fallthrough engine)* | |
| Fennel  | `WF_ENABLE_FENNEL=1` | `;` | Requires Lua (compiles to Lua); can't be selected without it. |
| QuickJS | `WF_JS_ENGINE=quickjs` | `//` | Mutually exclusive with JerryScript. |
| JerryScript | `WF_JS_ENGINE=jerryscript` | `//` | Mutually exclusive with QuickJS. |
| wasm3 | `WF_WASM_ENGINE=wasm3` | `#b64\n` | Source languages: hand-written `.wat`, AssemblyScript, Rust, C, Zig → `.wasm`. Stored as base64 in existing text chunks; `#b64\n` is the full sigil (bare `#` falls through to Lua so TCL shell comments in `cd.iff` keep working). |
| WAMR | `WF_WASM_ENGINE=wamr` | `#b64\n` | Same sigil and binary format as wasm3; `WF_WASM_ENGINE` selects exactly one. WAMR adds host-supplied `(global …)` imports so `INDEXOF_*` constants are resolved at instantiate time instead of baked as literals. |
| Forth | `WF_FORTH_ENGINE=zforth` (or `ficl`/`atlast`/`embed`/`libforth`/`pforth`) | `\` | Backend is a compile-time switch; same source runs on all backends. Dictionary pre-loaded with `INDEXOF_*` constants and `read-mailbox` / `write-mailbox` host words. |
| Wren | `WF_ENABLE_WREN=1` | `//wren\n` | Checked before generic `//` to avoid false dispatch to JS. Mailbox access via foreign class `Env` (`Env.read_mailbox` / `Env.write_mailbox`). |

The WebAssembly rows above show hand-written WAT for illustration, but nobody is expected
to author scripts in WAT directly. The value of the wasm target is the languages that
compile to `.wasm`: AssemblyScript, Rust, C, C++, Zig, Go (TinyGo), and any other
language with a wasm backend. Scripts in those languages compile to `.wasm` offline,
get base64-wrapped, and drop into an iff text chunk unchanged — the engine doesn't know
or care what source language produced the binary.

Dispatch is a leading-byte sniff: matching a sigil routes to that engine,
non-matching scripts go to the build's **fallthrough engine** (today Lua;
a future `WF_DEFAULT_ENGINE` knob lets a JS-only or wasm3-only build
declare a different fallthrough, or reject unsigilled scripts). Each
sigil is a syntax error in the other compiled-in languages, so a script
that meant for one engine never silently runs on another.

## Reference scripts: snowgoons player + director

Below are the same two gameplay scripts authored in every engine WF
supports (landed) or has designed (pending). The engines are independent
— a build picks any subset; the scripts only illustrate what each
language looks like, not what a single build must contain. Pending
engines are marked *(pending Phase D.x)* and will be smoke-tested and
de-marked when their Phase D task lands. Sigil-less scripts (Lua) only
run if Lua is compiled in.

### Player — forward raw joystick input to the input mailbox

**Lua:**
```lua
write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))
```

**Fennel:**
```fennel
;
(write_mailbox INDEXOF_INPUT (read_mailbox INDEXOF_HARDWARE_JOYSTICK1_RAW))
```

**Forth:**
```forth
\ snowgoons player
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
```
`read-mailbox ( idx -- val )` and `write-mailbox ( val idx -- )` are host words;
`INDEXOF_*` constants are loaded into the dictionary at engine init. Same source runs on
every backend (zForth, ficl, Atlast, embed, libforth, pForth) — backend is a compile-time
switch.

**Wren:**
```wren
//wren
Env.write_mailbox(INDEXOF_INPUT, Env.read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))
```
`INDEXOF_*` constants are injected as module-level `var` declarations at engine init;
mailbox access goes through the foreign class `Env` (Wren has no top-level functions).

**JavaScript (QuickJS / JerryScript):**
```javascript
// snowgoons player
write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW));
```
*JerryScript uses the same `//` sigil and identical source. `WF_JS_ENGINE` picks which runtime compiles in.*

**WebAssembly (wasm3), authored in WAT:**
```wat
;; INDEXOF_HARDWARE_JOYSTICK1_RAW = 1009   INDEXOF_INPUT = 3024
(module
  (import "env" "read_mailbox"  (func $read  (param i32) (result f32)))
  (import "env" "write_mailbox" (func $write (param i32 f32)))
  (func (export "main")
    i32.const 3024
    i32.const 1009
    call $read
    call $write))
```
Compiled via `wat2wasm` then base64'd and wrapped as `#b64\n<base64>` in the iff text
chunk. This script is *not* patched into the demo iff: the player's slot is 77 B, which
cannot hold even a minimal wasm module's base64 form (~108 B). `snowgoons_player.wasm`
is committed as a reference for when a binary IFF chunk type lands and frees the
base64 overhead. Sources: `wftools/vendor/wasm3-v0.5.0-wf/snowgoons_player.wat` (baked
literals), `wftools/vendor/wamr-2.2.0-wf/snowgoons_player.wat` (global-import version).

**WebAssembly (WAMR), authored in WAT:**
```wat
(module
  (import "consts" "INDEXOF_HARDWARE_JOYSTICK1_RAW" (global $raw i32))
  (import "consts" "INDEXOF_INPUT"                  (global $inp i32))
  (import "env"    "read_mailbox"  (func $read  (param i32) (result f32)))
  (import "env"    "write_mailbox" (func $write (param i32 f32)))
  (func (export "main")
    global.get $inp
    global.get $raw
    call $read
    call $write))
```
Same `.wat` authoring model as wasm3 but WAMR supports host-supplied `(global …)` imports,
so `INDEXOF_*` are resolved at instantiate time instead of being baked as literals.

### Director — switch camshot based on trigger mailboxes

**Lua:**
```lua
local v
v = read_mailbox(100); if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end
v = read_mailbox(99);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end
v = read_mailbox(98);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end
```

**Fennel:**
```fennel
;; snowgoons director
(let [v (read_mailbox 100)] (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))
(let [v (read_mailbox 99)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))
(let [v (read_mailbox 98)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))
```

**Forth:**
```forth
\ snowgoons director
: ?cam ( mb -- ) read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then ;
100 ?cam   99 ?cam   98 ?cam
```

**Wren:**
```wren
//wren
var v
v = Env.read_mailbox(100)
if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
v = Env.read_mailbox(99)
if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
v = Env.read_mailbox(98)
if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
```

**JavaScript (QuickJS / JerryScript):**
```javascript
// snowgoons director
var v;
v = read_mailbox(100); if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);
v = read_mailbox(99);  if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);
v = read_mailbox(98);  if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);
```
*JerryScript uses the same `//` sigil and identical source.*

**WebAssembly (wasm3), authored in WAT:**
```wat
(module
  (import "env" "read_mailbox"  (func $read  (param i32) (result f32)))
  (import "env" "write_mailbox" (func $write (param i32 f32)))
  (func $maybe (param $mb i32)
    (local $v f32)
    local.get $mb  call $read  local.tee $v
    f32.const 0  f32.ne
    if  i32.const 1021  local.get $v  call $write  end)
  (func (export "main")
    i32.const 100 call $maybe
    i32.const 99  call $maybe
    i32.const 98  call $maybe))
```
Compiled via `wat2wasm` then base64'd and wrapped as `#b64\n<base64>` in
the iff text chunk. `INDEXOF_CAMSHOT` is baked as the literal `1021` —
wasm3 has no host-side constant import surface (see plan §3).
Source lives at `wftools/vendor/wasm3-v0.5.0-wf/snowgoons_director.wat`;
patched into `wflevels/snowgoons.iff` by `scripts/patch_snowgoons_wasm.py`.

**WebAssembly (WAMR), authored in WAT:**
```wat
(module
  (import "consts" "INDEXOF_CAMSHOT" (global $cam i32))
  (import "env"    "read_mailbox"    (func $read  (param i32) (result f32)))
  (import "env"    "write_mailbox"   (func $write (param i32 f32)))
  (func $maybe (param $mb i32)
    (local $v f32)
    local.get $mb  call $read  local.tee $v
    f32.const 0  f32.ne
    if  global.get $cam  local.get $v  call $write  end)
  (func (export "main")
    i32.const 100 call $maybe
    i32.const 99  call $maybe
    i32.const 98  call $maybe))
```
WAMR supports host-supplied `(global …)` imports, so `INDEXOF_CAMSHOT` is resolved at
instantiate time instead of being baked as a literal.

## Integration surface

All languages ride on the same mailbox bridge, so the per-language cost is
(a) a runtime (bytes in `.rodata` or a linked library), and (b) a dispatch
discriminator in `RunScript`. Adding a language should not require changes
to the mailbox machinery or level format.

| Language | Sigil | Runtime | Compile-time switch | Binary cost | Status |
|----------|-------|---------|---------------------|-------------|--------|
| Lua 5.4  | *(none — fallthrough)* | vendored `wftools/vendor/lua-5.4.8/`, statically linked | `WF_ENABLE_LUA=1` (default on today) | linked lib | shipping |
| Fennel   | `;` | `fennel.lua` embedded via codegen (minified) | `WF_ENABLE_FENNEL=1` (requires Lua) | ~145 KB `.rodata` | shipping |
| JavaScript (QuickJS) | `//` | QuickJS v0.14.0 statically linked from `wftools/vendor/` | `WF_JS_ENGINE=quickjs` | ~1.2 MB unstripped (~350 KB target stripped) | shipping |
| JavaScript (JerryScript) | `//` | JerryScript v3.0.0 `wf-minimal` profile | `WF_JS_ENGINE=jerryscript` | ~80–90 KB lib | landed (build path); not yet smoke-tested |
| WebAssembly (wasm3) | `#b64\n` | wasm3 v0.5.0 (pure-C interpreter) | `WF_WASM_ENGINE=wasm3` | ~100 KB core at `-O2` unstripped (stripped binary delta ~136 KB including selftest + plug); upstream cites ~65 KB for stripped Cortex-M builds | shipping (spike) |
| WebAssembly (WAMR) | `#b64\n` | WAMR 2.2.0 classic interpreter (Apache-2.0); supports host-supplied `(global …)` imports for `INDEXOF_*` constants; WAT sources + compiled `.wasm` in `wamr-2.2.0-wf/` | `WF_WASM_ENGINE=wamr` | ~519 KB static lib (`-Os`); AOT planned (phase 2) | landed 2026-04-15 (interp; needs smoke test) |
| Forth (zForth) | `\` | zForth 4 KB core (MIT); ficl/Atlast/embed/libforth/pForth also supported | `WF_FORTH_ENGINE=zforth` (or ficl/atlast/embed/libforth/pforth) | ~4 KB .text (zForth) | landed 2026-04-15 |
| Wren | `//wren\n` | Wren 0.4.0 amalgamation | `WF_ENABLE_WREN=1` | ~150 KB .text | landed 2026-04-15 |

None of these rows describe a dependency on any other row. The only
exception is Fennel, which compiles to Lua and therefore can't be
selected without Lua. Every other combination — QuickJS without Lua,
wasm3 without Lua, JerryScript + wasm3 with no Lua or Fennel — is a
supported build configuration.

## Coroutines — multi-tick scripts

By default a script runs to completion in one tick and returns a number.
Scripts that need to span multiple ticks — AI state machines, cutscenes,
dialogue sequences, timed events — can return a coroutine thread instead.
`lua_engine` detects this and resumes the thread once per tick until it
finishes.

### How it works

On the first tick the script function is called normally. If it returns a
coroutine thread (`coroutine.create(fn)`), that thread is stored and resumed
immediately. On every subsequent tick, instead of re-calling the function,
`lua_engine::RunScript` resumes the stored thread. When the thread returns
(falls off the end of its function body) or errors, the ref is cleared and
the script reverts to normal per-tick calling.

A yielded value is used as the `RunScript` return for that tick — useful if
the script controls a mailbox write from inside the loop.

### Example patterns

**Wait N ticks:**
```lua
return coroutine.create(function()
    for _ = 1, 60 do          -- hold for 60 ticks (~2 s at 30 Hz)
        coroutine.yield()
    end
    write_mailbox(INDEXOF_CAMSHOT, 3)
end)
```

**Repeating state machine:**
```lua
return coroutine.create(function()
    while true do
        -- PATROL
        write_mailbox(INDEXOF_AI_STATE, 1)
        for _ = 1, 90 do coroutine.yield() end

        -- ALERT
        write_mailbox(INDEXOF_AI_STATE, 2)
        for _ = 1, 30 do coroutine.yield() end
    end
end)
```

**Wait for condition:**
```lua
return coroutine.create(function()
    -- Wait until trigger mailbox fires
    while read_mailbox(INDEXOF_TRIGGER_A) == 0 do
        coroutine.yield()
    end
    write_mailbox(INDEXOF_CAMSHOT, 5)
    write_mailbox(INDEXOF_MUSIC, 2)
end)
```

**Fennel equivalent (`;` sigil):**
```fennel
; cutscene — hold camera on shot 7 for 120 ticks then cut to shot 1
(coroutine.create
  (fn []
    (write-mailbox INDEXOF_CAMSHOT 7)
    (for [_ 1 120] (coroutine.yield))
    (write-mailbox INDEXOF_CAMSHOT 1)))
```

### Rules

- Use `coroutine.create(fn)`, not `coroutine.wrap(fn)`. `coroutine.wrap`
  returns a plain function, not a thread, so the engine won't detect it.
- A script that never returns a thread is unaffected — plain per-tick
  execution is unchanged.
- If a coroutine errors, it is cleared and the script restarts from scratch
  on the next tick (returning a fresh coroutine if desired).
- Per-actor `_ENV` isolation applies inside coroutines — locals written
  inside the coroutine are private to that actor.
- Only one coroutine per actor at a time. Returning a new thread while one
  is running is not supported; the new thread would only be picked up after
  the current one finishes or errors.

## Notes for future languages

- **Sigil choice.** Pick a byte that's (a) idiomatic in the language, (b)
  invalid/unused in Lua at position 0. `;` (Fennel), `\0asm` (wasm binary
  magic, 4 bytes), and a dedicated prefix byte like `#!js` or `$js` are all
  reasonable. Two-character sigils (`//`) collide with Lua's division
  operator at parse time, so they need to be on their own line.

- **No filesystem.** WF targets environments without host filesystems.
  Interpreter runtimes must be embedded in the binary (`luaL_loadbuffer` or
  similar) — not loaded from disk. Pay the binary cost once at build time,
  gate it behind a compile switch so lean builds opt out.

- **Shared C API surface.** `read_mailbox` / `write_mailbox` are the only
  cross-language touchpoints today. New languages should bind to the same
  pair (and the same constant globals) so the level format stays one format
  regardless of script language.

- **Cost of polyglot dispatch.** The sigil sniff in `RunScript` is
  O(leading-whitespace) and runs per script call. Each new language adds
  one discriminator check. Don't regress this to a regex or a language
  probe; stay with first-byte tests.

## Files

- `wftools/wf_viewer/stubs/scripting_stub.cc` — `ScriptRouter` + sigil dispatch + `lua_engine` namespace.
- `wftools/wf_viewer/stubs/scripting_js.hp` — JS engine plug ABI (`js_engine` namespace).
- `wftools/wf_viewer/stubs/scripting_quickjs.cc` — QuickJS implementation.
- `wftools/wf_viewer/stubs/scripting_jerryscript.cc` — JerryScript implementation.
- `wftools/wf_viewer/stubs/fennel.lua` — vendored Fennel 1.6.1.
- `wftools/vendor/quickjs-v0.14.0/`, `wftools/vendor/jerryscript-v3.0.0/` — vendored JS engines.
- `wftools/wf_viewer/stubs/scripting_wasm3.hp`/`.cc` — wasm3 plug (`wasm3_engine` namespace).
- `wftools/vendor/wasm3-v0.5.0/` — vendored wasm3 interpreter.
- `wftools/vendor/wasm3-v0.5.0-wf/` — selftest + snowgoons WAT sources (baked literals) + compiled `.wasm` artifacts.
- `wftools/wf_viewer/stubs/scripting_wamr.hp`/`.cc` — WAMR plug (`wamr_engine` namespace, wasm-C-API).
- `wftools/vendor/wamr-2.2.0/` — vendored WAMR 2.2.0 source.
- `wftools/vendor/wamr-2.2.0-wf/` — snowgoons WAT sources (global-import version) + compiled `.wasm` artifacts.
- `wftools/wf_viewer/stubs/scripting_forth.hp` — Forth engine plug ABI (`forth_engine` namespace).
- `wftools/wf_viewer/stubs/scripting_zforth.cc` — zForth default backend; `zfconf.h` config.
- `wftools/vendor/zforth-*/` (+ `ficl`, `atlast`, `embed`, `libforth`, `pforth`) — vendored Forth engines.
- `wftools/wf_viewer/stubs/scripting_wren.hp`/`.cc` — Wren plug (`wren_engine` namespace).
- `wftools/vendor/wren-0.4.0/` — vendored Wren 0.4.0 amalgamation.
- `scripts/minify_lua.py` — Lua source minifier (used on `fennel.lua`).
- `scripts/patch_snowgoons_lua.py` — TCL → Lua byte-preserving patcher.
- `scripts/patch_snowgoons_fennel.py` — Lua → Fennel byte-preserving patcher.
- `scripts/patch_snowgoons_wasm.py` — Fennel/Lua → wasm3 (director only) patcher.
- `scripts/patch_snowgoons_wamr.py` — any form → WAMR wasm (director only) patcher; prefers `wamr-2.2.0-wf/snowgoons_director.wasm`.
- `scripts/patch_snowgoons_forth.py` — any form → Forth `\`-sigil patcher.
- `scripts/patch_snowgoons_wren.py` — any form → Wren `//wren\n`-sigil patcher.
- `scripts/patch_snowgoons_js.py` — any form → JS `//` patcher.
- `docs/plans/2026-04-13-lua-interpreter-spike.md` — Lua spike plan.
- `docs/plans/2026-04-14-fennel-on-lua.md` — Fennel-on-Lua spike plan.
- `docs/plans/2026-04-14-pluggable-scripting-engine.md` — JS engine plan.
- `docs/plans/2026-04-14-wasm3-scripting-engine.md` — wasm3 spike plan.
- `docs/plans/2026-04-14-wamr-dev-aot-ship.md` — WAMR interp + AOT plan.
- `docs/plans/2026-04-14-wren-scripting-engine.md` — Wren plan.
- `docs/plans/2026-04-14-forth-scripting-engine.md` — Forth (multi-backend) plan.
