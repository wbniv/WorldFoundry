# Scripting languages in WF

The engine supports several scripting languages. **A build chooses any
subset** — Lua-only, JS-only, Lua + Fennel, QuickJS + wasm3, etc. No
language is mandatory; the scriptless build (no engines compiled in) is
valid too. Every engine targets the same embedded API —
`read_mailbox(idx[, actor])`, `write_mailbox(idx, value[, actor])`, and
the `INDEXOF_*` / `JOYSTICK_BUTTON_*` globals — so scripts authored in
one language call into the game identically to scripts authored in
another.

The WebAssembly engines don't expect WAT to be authored directly. The value of the wasm target is the languages that compile to `.wasm`: AssemblyScript, Rust, C, C++, Zig, Go (TinyGo), and any other language with a wasm backend. Scripts in those languages compile to `.wasm` offline, get base64-wrapped, and drop into an iff text chunk unchanged.


## Integration surface

All languages ride on the same mailbox bridge, so the per-language cost is
(a) a runtime compiled into the binary, and (b) a dispatch discriminator in
`RunScript`. Adding a language should not require changes to the mailbox
machinery or level format. Runtime details (vendor paths, version, link
strategy) are in the per-engine plan docs in `docs/plans/`.

Binary cost figures are `.text` section size, compiled `-O2`, measured from object files (x86-64). RAM figures are from the current unstripped debug build and are indicative only.

| Language | Compile-time switch | Binary cost (.text, -O2) | RAM (init) |
|----------|---------------------|--------------------------|------------|
| Lua 5.4.8 | `WF_ENABLE_LUA=1` (default on today) | ~224 KB | ~50 KB (`lua_State` + standard libs) |
| *Per-actor `_ENV` isolation — each actor script runs in its own environment table; globals don't leak between actors. Standard libs loaded: `base`, `math`, `string`, `table`, `coroutine`; no `io`, `os`, or `debug`. Coroutine return from a script enables multi-tick state machines (see §Coroutines below). Fennel can be layered on top without any engine change.* | | | |
| Fennel 1.6.1 | `WF_ENABLE_FENNEL=1` (requires Lua) | ~140 KB (embedded `.lua` data) | +0 (shares `lua_State`; compiler runs transiently) |
| *Lisp dialect that compiles to Lua at script load time; the Fennel compiler runs transiently and the resulting Lua bytecode executes in the shared `lua_State`. All Lua globals (`read_mailbox`, `write_mailbox`, `INDEXOF_*`) are directly accessible from Fennel without wrapping. Fennel and Lua can call each other freely. `_ENV` isolation applies identically.* | | | |
| JavaScript<br/>(QuickJS v0.14.0) | `WF_JS_ENGINE=quickjs` | ~938 KB | ~200 KB (`JSRuntime` + `JSContext` baseline) |
| *ES2020-compliant; generators, destructuring, optional chaining, `BigInt`, typed arrays, and full `Math` / `JSON` built-ins available. `async`/`await` compiles but is unnecessary in the tick model — use generators or callbacks. Fastest JS engine in the lineup. Mutually exclusive with JerryScript (`WF_JS_ENGINE` selects one).* | | | |
| JavaScript<br/>(JerryScript v3.0.0) | `WF_JS_ENGINE=jerryscript` | — (TODO measure) | <64 KB (configurable heap; IoT-targeted) |
| *ES5.1 target: no generators, no `let`/`const`, no arrow functions, no destructuring. Heap size is configurable at compile time (`JERRY_HEAP_SIZE`), making it suitable for constrained targets where QuickJS's 200 KB baseline is too large. Mutually exclusive with QuickJS (`WF_JS_ENGINE` selects one).* | | | |
| WebAssembly<br/>(wasm3 v0.5.0) | `WF_WASM_ENGINE=wasm3` | ~96 KB | ~10 KB (runtime only; WF scripts use no linear memory) |
| *Interpreter-only — no JIT; safe on all platforms including MIPS. WF scripts use only host imports (`read_mailbox`, `write_mailbox`) and no linear memory, so the 10 KB init cost is the complete runtime budget. `.wasm` modules stored base64-wrapped in iff text chunks, decoded at load time. Initial spike; planned for replacement by WAMR once parity is confirmed. Source languages: AssemblyScript, Rust, C, Zig, TinyGo, etc.* | | | |
| WebAssembly<br/>(WAMR 2.2.0) | `WF_WASM_ENGINE=wamr` | — (TODO measure) | ~60 KB (classic interpreter runtime; `os_malloc`-based in WF build) |
| *Classic interpreter mode in the WF build (`os_malloc`-based memory; no platform thread pool or JIT). Supports host-supplied `(global …)` imports so `INDEXOF_*` constants resolve at module instantiate time rather than baked as literals in WAT source — scripts are portable across levels without recompilation. `WF_WASM_ENGINE` selects exactly one wasm engine; wasm3 and WAMR are never both linked. AOT mode (`wamrc` offline compile step) is deferred to a later phase.* | | | |
| Forth<br/>(zForth — default) | `WF_FORTH_ENGINE=zforth` | ~7 KB (core + WF wrapper) | ~17 KB (`ZF_DICT_SIZE=16384` + stacks per WF `zfconf.h`) |
| Forth (ficl) | `WF_FORTH_ENGINE=ficl` | ~100 KB est. (BSD-2; not yet built) | — |
| Forth (Atlast) | `WF_FORTH_ENGINE=atlast` | ~30 KB est. (public domain; not yet built) | — |
| Forth (embed) | `WF_FORTH_ENGINE=embed` | ~5 KB est. (MIT; 16-bit cells; not yet built) | — |
| Forth (libforth) | `WF_FORTH_ENGINE=libforth` | ~50 KB est. (MIT; not yet built) | — |
| Forth (pForth) | `WF_FORTH_ENGINE=pforth` | ~120 KB est. (0-BSD; not yet built) | — |
| *Concatenative stack language; scripts compile to a compact bytecode dictionary at load time. WF's zForth build uses `ZF_DICT_SIZE=16384` (16 KB dictionary) and 4-byte cells (`ZF_CELL=int32_t`) for 32-bit fixed-point compatibility. Dictionary pre-loaded with `INDEXOF_*` constants and `read-mailbox` / `write-mailbox` host words. No GC; no heap allocation after init — real-time safe. `WF_FORTH_ENGINE` is a compile-time backend switch; the same Forth source runs unchanged on all backends. Alternate backends (ficl, Atlast, embed, libforth, pForth) not yet built; zForth is the shipping default.* | | | |
| Wren 0.4.0 | `WF_ENABLE_WREN=1` | ~146 KB | ~100 KB initial; GC trigger default 10 MB (**must be overridden** for 2 MB target — set `WrenConfiguration.initialHeapSize` / `minHeapSize`) |
| *Class-based OO with single inheritance; built-in Fiber (coroutine) support for multi-tick scripts. Mailbox access via foreign class `Env` (`Env.read_mailbox(idx)` / `Env.write_mailbox(idx, val)`); `INDEXOF_*` constants injected as module-level `var` declarations at engine init. GC heap defaults to 10 MB trigger — **must be overridden** before shipping on 2 MB hardware.* | | | |

None of these rows describe a dependency on any other row. The only
exception is Fennel, which compiles to Lua and therefore can't be
selected without Lua. Every other combination — QuickJS without Lua,
wasm3 without Lua, JerryScript + wasm3 with no Lua or Fennel — is a
supported build configuration.

**All engines are currently enabled in the dev build.** For a shipping
binary, compile in only the language(s) your scripts actually use — each
engine adds 5–978 KB to `.text`. A game scripted entirely in Lua needs
only `WF_ENABLE_LUA=1`; a Forth-scripted game needs only
`WF_FORTH_ENGINE=zforth`. The scriptless build (no flags set) is also
valid for games that need no scripting at all.

## Reference scripts: snowgoons player + director

The same two gameplay scripts in each language. All access identical mailbox indices — the language is the only variable.

| Language | Player | Director |
|----------|--------|----------|
| Lua 5.4 | <pre>write_mailbox(INDEXOF_INPUT,&#10;  read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))</pre> | <pre>local v&#10;v = read_mailbox(100); if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end&#10;v = read_mailbox(99);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end&#10;v = read_mailbox(98);  if v ~= 0 then write_mailbox(INDEXOF_CAMSHOT, v) end</pre> |
| Fennel | <pre>(write_mailbox INDEXOF_INPUT&#10;  (read_mailbox INDEXOF_HARDWARE_JOYSTICK1_RAW))</pre> | <pre>(let [v (read_mailbox 100)] (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))&#10;(let [v (read_mailbox 99)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))&#10;(let [v (read_mailbox 98)]  (when (not= v 0) (write_mailbox INDEXOF_CAMSHOT v)))</pre> |
| JavaScript<br/>(QuickJS / JerryScript) | <pre>write_mailbox(INDEXOF_INPUT,&#10;  read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW));</pre> | <pre>var v;&#10;v = read_mailbox(100); if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);&#10;v = read_mailbox(99);  if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);&#10;v = read_mailbox(98);  if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);</pre> |
| WebAssembly<br/>(wasm3) | <pre>;; INDEXOF_HARDWARE_JOYSTICK1_RAW=1009  INDEXOF_INPUT=3024&#10;(module&#10;  (import "env" "read_mailbox"  (func $read  (param i32) (result f32)))&#10;  (import "env" "write_mailbox" (func $write (param i32 f32)))&#10;  (func (export "main")&#10;    i32.const 3024  i32.const 1009&#10;    call $read  call $write))</pre> | <pre>(module&#10;  (import "env" "read_mailbox"  (func $read  (param i32) (result f32)))&#10;  (import "env" "write_mailbox" (func $write (param i32 f32)))&#10;  (func $maybe (param $mb i32) (local $v f32)&#10;    local.get $mb  call $read  local.tee $v&#10;    f32.const 0  f32.ne&#10;    if  i32.const 1021  local.get $v  call $write  end)&#10;  (func (export "main")&#10;    i32.const 100 call $maybe&#10;    i32.const 99  call $maybe&#10;    i32.const 98  call $maybe))</pre> |
| WebAssembly<br/>(WAMR) | <pre>(module&#10;  (import "consts" "INDEXOF_HARDWARE_JOYSTICK1_RAW" (global $raw i32))&#10;  (import "consts" "INDEXOF_INPUT"                  (global $inp i32))&#10;  (import "env"    "read_mailbox"  (func $read  (param i32) (result f32)))&#10;  (import "env"    "write_mailbox" (func $write (param i32 f32)))&#10;  (func (export "main")&#10;    global.get $inp  global.get $raw&#10;    call $read  call $write))</pre> | <pre>(module&#10;  (import "consts" "INDEXOF_CAMSHOT" (global $cam i32))&#10;  (import "env"    "read_mailbox"    (func $read  (param i32) (result f32)))&#10;  (import "env"    "write_mailbox"   (func $write (param i32 f32)))&#10;  (func $maybe (param $mb i32) (local $v f32)&#10;    local.get $mb  call $read  local.tee $v&#10;    f32.const 0  f32.ne&#10;    if  global.get $cam  local.get $v  call $write  end)&#10;  (func (export "main")&#10;    i32.const 100 call $maybe&#10;    i32.const 99  call $maybe&#10;    i32.const 98  call $maybe))</pre> |
| *`INDEXOF_*` constants resolved via host-supplied `(global …)` imports at instantiate time; no baked literals.* | | |
| Forth (zForth) | <pre>INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox</pre> | <pre>: ?cam ( mb -- ) read-mailbox dup 0 &lt;&gt; if INDEXOF_CAMSHOT write-mailbox else drop then ;&#10;100 ?cam   99 ?cam   98 ?cam</pre> |
| Wren | <pre>Env.write_mailbox(INDEXOF_INPUT,&#10;  Env.read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))</pre> | <pre>var v&#10;v = Env.read_mailbox(100)&#10;if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)&#10;v = Env.read_mailbox(99)&#10;if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)&#10;v = Env.read_mailbox(98)&#10;if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)</pre> |

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

All examples below use tick-counting for timing (`for _ = 1, N`). WF has a
variable tick rate, so tick counts are approximations. Once `INDEXOF_GAME_TIME_S`
and `INDEXOF_DT` mailboxes are available (deferred), replace tick loops with
real-time accumulation.

**Wait for condition, then act:**
```lua
return coroutine.create(function()
    while read_mailbox(INDEXOF_TRIGGER_A) == 0 do
        coroutine.yield()
    end
    write_mailbox(INDEXOF_CAMSHOT, 5)
    write_mailbox(INDEXOF_MUSIC, 2)
end)
```

**NPC patrol — walks to waypoints, idles between them:**
```lua
return coroutine.create(function()
    while true do
        -- Walk to waypoint A, wait until arrived
        write_mailbox(INDEXOF_AI_DEST, WAYPOINT_A)
        write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)
        repeat coroutine.yield()
        until read_mailbox(INDEXOF_AT_DEST) ~= 0

        -- Idle at A for ~3 s
        write_mailbox(INDEXOF_AI_STATE, STATE_IDLE)
        for _ = 1, 90 do coroutine.yield() end

        -- Walk to waypoint B
        write_mailbox(INDEXOF_AI_DEST, WAYPOINT_B)
        write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)
        repeat coroutine.yield()
        until read_mailbox(INDEXOF_AT_DEST) ~= 0

        for _ = 1, 90 do coroutine.yield() end
    end
end)
```

The same logic as a tick-based state machine needs an explicit `state` variable,
transition guards in every branch, and the loop structure inverted — the
coroutine reads top-to-bottom as the authored sequence of events.

**Cutscene sequencer — timed camera cuts:**
```lua
return coroutine.create(function()
    local function hold(shot, ticks)
        write_mailbox(INDEXOF_CAMSHOT, shot)
        for _ = 1, ticks do coroutine.yield() end
    end
    local function wait_trigger(mb)
        repeat coroutine.yield() until read_mailbox(mb) ~= 0
    end

    wait_trigger(INDEXOF_CUTSCENE_START)
    hold(1, 60)    -- establishing shot ~2 s
    hold(2, 45)    -- cut to character ~1.5 s
    hold(3, 90)    -- reaction ~3 s
    hold(1, 30)    -- back to wide ~1 s
    write_mailbox(INDEXOF_CUTSCENE_DONE, 1)
end)
```

**Door — waits for player, plays open animation, stays open:**
```lua
return coroutine.create(function()
    -- Wait until player is close
    repeat coroutine.yield()
    until read_mailbox(INDEXOF_PLAYER_DIST) < 100

    -- Step through open animation frames
    for frame = 0, 7 do
        write_mailbox(INDEXOF_DOOR_FRAME, frame)
        coroutine.yield()
        coroutine.yield()   -- 2 ticks per frame
    end

    write_mailbox(INDEXOF_DOOR_OPEN, 1)
    -- script ends; mailbox persists; door stays open
end)
```

### Fennel equivalents

The same four patterns in Fennel. `coroutine.create`, `coroutine.yield`, and
all mailbox globals are the same — only the syntax changes.

**Wait for condition:**
```fennel
(coroutine.create
  (fn []
    (while (= (read_mailbox INDEXOF_TRIGGER_A) 0) (coroutine.yield))
    (write_mailbox INDEXOF_CAMSHOT 5)
    (write_mailbox INDEXOF_MUSIC 2)))
```

**NPC patrol:**
```fennel
(coroutine.create
  (fn []
    (while true
      (write_mailbox INDEXOF_AI_DEST WAYPOINT_A)
      (write_mailbox INDEXOF_AI_STATE STATE_WALKING)
      (while (= (read_mailbox INDEXOF_AT_DEST) 0) (coroutine.yield))

      (write_mailbox INDEXOF_AI_STATE STATE_IDLE)
      (for [_ 1 90] (coroutine.yield))

      (write_mailbox INDEXOF_AI_DEST WAYPOINT_B)
      (write_mailbox INDEXOF_AI_STATE STATE_WALKING)
      (while (= (read_mailbox INDEXOF_AT_DEST) 0) (coroutine.yield))

      (for [_ 1 90] (coroutine.yield)))))
```

**Cutscene sequencer:**
```fennel
(coroutine.create
  (fn []
    (let [hold (fn [shot ticks]
                 (write_mailbox INDEXOF_CAMSHOT shot)
                 (for [_ 1 ticks] (coroutine.yield)))
          wait-trigger (fn [mb]
                         (while (= (read_mailbox mb) 0) (coroutine.yield)))]
      (wait-trigger INDEXOF_CUTSCENE_START)
      (hold 1 60)
      (hold 2 45)
      (hold 3 90)
      (hold 1 30)
      (write_mailbox INDEXOF_CUTSCENE_DONE 1))))
```

**Door:**
```fennel
(coroutine.create
  (fn []
    (while (>= (read_mailbox INDEXOF_PLAYER_DIST) 100) (coroutine.yield))
    (for [frame 0 7]
      (write_mailbox INDEXOF_DOOR_FRAME frame)
      (coroutine.yield)
      (coroutine.yield))
    (write_mailbox INDEXOF_DOOR_OPEN 1)))
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

- **No filesystem.** WF targets environments without host filesystems.
  Interpreter runtimes must be embedded in the binary (`luaL_loadbuffer` or
  similar) — not loaded from disk. Pay the binary cost once at build time,
  gate it behind a compile switch so lean builds opt out.

- **Shared C API surface.** `read_mailbox` / `write_mailbox` are the only
  cross-language touchpoints today. New languages should bind to the same
  pair (and the same constant globals) so the level format stays one format
  regardless of script language.


## Files

- `wftools/wf_viewer/stubs/scripting_stub.cc` — `ScriptRouter`, `lua_engine`, Fennel sub-dispatch.
- `wftools/wf_viewer/stubs/scripting_{js,quickjs,jerryscript,wasm3,wamr,forth,wren}.{hp,cc}` — per-engine plugs.
- `wftools/wf_viewer/stubs/fennel.lua` — vendored Fennel 1.6.1 (minified by `scripts/minify_lua.py`).
- `wftools/vendor/{quickjs-v0.14.0,jerryscript-v3.0.0,wasm3-v0.5.0,wamr-2.2.0,wren-0.4.0,zforth-*,ficl,atlast,embed,libforth,pforth}/` — vendored runtimes.
- `scripts/patch_snowgoons_*.py` — per-language snowgoons iff patchers.
- `docs/plans/2026-04-1{3,4}-*.md` — per-engine spike/integration plans.
