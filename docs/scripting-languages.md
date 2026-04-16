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
| Lua 5.4.8 | `WF_ENABLE_LUA=1` | ~224 KB | ~50 KB (`lua_State` + standard libs) |
| *Per-actor `_ENV` isolation — each actor script runs in its own environment table; globals don't leak between actors. Standard libs loaded: `base`, `math`, `string`, `table`, `coroutine`; no `io`, `os`, or `debug`. Coroutine return from a script enables multi-tick state machines (see §Coroutines below). Fennel can be layered on top without any engine change.* | | | |
| Fennel 1.6.1 | `WF_ENABLE_FENNEL=1` (requires Lua) | ~140 KB (embedded `.lua` data) | +0 (shares `lua_State`; compiler runs transiently) |
| *Lisp dialect that compiles to Lua at script load time; the Fennel compiler runs transiently and the resulting Lua bytecode executes in the shared `lua_State`. All Lua globals (`read_mailbox`, `write_mailbox`, `INDEXOF_*`) are directly accessible from Fennel without wrapping. Fennel and Lua can call each other freely. `_ENV` isolation applies identically.* | | | |
| JavaScript<br/>(QuickJS v0.14.0) | `WF_JS_ENGINE=quickjs` | ~938 KB | ~200 KB (`JSRuntime` + `JSContext` baseline) |
| *ES2020-compliant; generators, destructuring, optional chaining, `BigInt`, typed arrays, and full `Math` / `JSON` built-ins available. `async`/`await` compiles but is unnecessary in the tick model — use generators. Generator return from a script (`(function*() { ... })()`) enables multi-tick sequencing via `yield`; the engine advances the generator one step per tick. Fastest JS engine in the lineup. Mutually exclusive with JerryScript (`WF_JS_ENGINE` selects one).* | | | |
| JavaScript<br/>(JerryScript v3.0.0) | `WF_JS_ENGINE=jerryscript` | ~237 KB (wf-minimal profile) | <64 KB (configurable heap; IoT-targeted) |
| *ES5.1 target: no generators, no `let`/`const`, no arrow functions, no destructuring. No multi-tick script support — use per-tick `if`/state-variable patterns instead. Heap size is configurable at compile time (`JERRY_HEAP_SIZE`), making it suitable for constrained targets where QuickJS's 200 KB baseline is too large. Mutually exclusive with QuickJS (`WF_JS_ENGINE` selects one).* | | | |
| WebAssembly<br/>(wasm3 v0.5.0) | `WF_WASM_ENGINE=wasm3` | ~96 KB | ~10 KB (runtime only; WF scripts use no linear memory) |
| *Interpreter-only — no JIT; safe on all platforms including MIPS. WF scripts use only host imports (`read_mailbox`, `write_mailbox`) and no linear memory, so the 10 KB init cost is the complete runtime budget. `.wasm` modules stored base64-wrapped in iff text chunks, decoded at load time. Initial spike; planned for replacement by WAMR once parity is confirmed. Source languages: AssemblyScript, Rust, C, Zig, TinyGo, etc.* | | | |
| WebAssembly<br/>(WAMR 2.2.0) | `WF_WASM_ENGINE=wamr` | ~107 KB (classic interp, MinSizeRel) | ~60 KB (classic interpreter runtime; `os_malloc`-based in WF build) |
| *Classic interpreter mode in the WF build (`os_malloc`-based memory; no platform thread pool or JIT). Supports host-supplied `(global …)` imports so `INDEXOF_*` constants resolve at module instantiate time rather than baked as literals in WAT source — scripts are portable across levels without recompilation. `WF_WASM_ENGINE` selects exactly one wasm engine; wasm3 and WAMR are never both linked. AOT mode (`wamrc` offline compile step) is deferred to a later phase.* | | | |
| Forth<br/>(zForth — default) | `WF_FORTH_ENGINE=zforth` | ~7 KB (core + WF wrapper) | ~17 KB (`ZF_DICT_SIZE=16384` + stacks per WF `zfconf.h`) |
| Forth (ficl) | `WF_FORTH_ENGINE=ficl` | ~100 KB (BSD-2; ficl-3.06; 12 C files) | — |
| Forth (Atlast) | `WF_FORTH_ENGINE=atlast` | ~30 KB (public domain; 1 C file; `-DEXPORT`) | — |
| Forth (embed) | `WF_FORTH_ENGINE=embed` | ~5 KB VM (MIT; 16-bit cells; embed.c + image.c) | — |
| Forth (libforth) | `WF_FORTH_ENGINE=libforth` | ~50 KB (MIT; libforth.c; C-global bridge) | — |
| Forth (pForth) | `WF_FORTH_ENGINE=pforth` | ~120 KB (0-BSD; 12 C files; loads system.fth at init) | — |
| *Concatenative stack language; scripts compile to a compact bytecode dictionary at load time. WF's zForth build uses `ZF_DICT_SIZE=16384` (16 KB dictionary) and 4-byte cells (`ZF_CELL=int32_t`) for 32-bit fixed-point compatibility. Dictionary pre-loaded with `INDEXOF_*` constants and `read-mailbox` / `write-mailbox` host words. No GC; no heap allocation after init — real-time safe. `WF_FORTH_ENGINE` is a compile-time backend switch; the same Forth source runs unchanged on all backends. embed note: on PC dev, mailbox float values are truncated to 16-bit int; correct on the real fixed-point target. pForth note: loads `system.fth` from `engine/vendor/pforth-*/fth/` at init to build the full ANS word set (IF/ELSE/THEN, DO/LOOP, etc.). Runtime memory column (`—`) pending measured values.* | | | |
| Wren 0.4.0 | `WF_ENABLE_WREN=1` | ~146 KB | ~100 KB initial; GC trigger default 10 MB (**must be overridden** for 2 MB target — set `WrenConfiguration.initialHeapSize` / `minHeapSize`) |
| *Class-based OO with single inheritance; built-in Fiber support for multi-tick scripts. Assign `Fiber.new { ... }` to a module-level `var _thread` — the engine stores and resumes it once per tick, same model as Lua coroutines. Helper `Fn` objects called from inside the fiber can call `Fiber.yield()` freely. Mailbox access via foreign class `Env` (`Env.read_mailbox(idx)` / `Env.write_mailbox(idx, val)`); `INDEXOF_*` constants injected as module-level `var` declarations at engine init. GC heap defaults to 10 MB trigger — **must be overridden** before shipping on 2 MB hardware.* | | | |

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

A single conditional wait — "do X when Y becomes true" — is no better than
a per-tick `if` check. Coroutines earn their keep the moment there is a
**second** wait: without them, each additional phase needs an explicit state
variable and a new `if`/`elseif` branch that grows with every step. The
coroutine captures that state implicitly in the suspended function's execution
position, so the script reads as a linear sequence of authored events rather
than an inside-out state machine.

Tick-counting is used for timing. WF has a variable tick rate, so tick counts
are approximations. Once `INDEXOF_GAME_TIME_S` and `INDEXOF_DT` mailboxes are
available (deferred), replace tick loops with real-time accumulation.

Wren uses `var _thread = Fiber.new { ... }` to declare a multi-tick fiber.
JS (QuickJS) uses an immediately-invoked generator function `(function*() { ... })()`.
JerryScript (ES5.1) has no generator support and is omitted from these examples.
Forth (zForth) has no native coroutine — `zf_eval` runs to completion each tick and
resumable context save/restore is not implemented. Forth examples show the equivalent
per-tick state machine: phase and tick counters live in mailboxes (Forth `variable`
is append-only and would be re-allocated each tick). The pattern is `dup N = if ... fi`
dispatch per phase. `fi` terminates conditionals — zForth has no `then`.

**Triggered alarm sequence** — three ordered phases: wait for player to enter
zone, sound alarm for ~2 s, seal the door. Without a coroutine: explicit `state`
variable + one `if`/`elseif` branch per phase, growing with every new step.

| Language | Script |
|----------|--------|
| Lua | <pre>return coroutine.create(function()&#10;    repeat coroutine.yield()&#10;    until read_mailbox(INDEXOF_TRIGGER_A) ~= 0&#10;&#10;    write_mailbox(INDEXOF_ALARM, 1)&#10;    for _ = 1, 60 do coroutine.yield() end&#10;&#10;    write_mailbox(INDEXOF_ALARM, 0)&#10;    write_mailbox(INDEXOF_DOOR_LOCKED, 1)&#10;end)</pre> |
| Fennel | <pre>(coroutine.create&#10;  (fn []&#10;    (while (= (read_mailbox INDEXOF_TRIGGER_A) 0)&#10;      (coroutine.yield))&#10;&#10;    (write_mailbox INDEXOF_ALARM 1)&#10;    (for [_ 1 60] (coroutine.yield))&#10;&#10;    (write_mailbox INDEXOF_ALARM 0)&#10;    (write_mailbox INDEXOF_DOOR_LOCKED 1)))</pre> |
| Wren | <pre>var _thread = Fiber.new {&#10;    while (Env.read_mailbox(INDEXOF_TRIGGER_A) == 0) Fiber.yield()&#10;&#10;    Env.write_mailbox(INDEXOF_ALARM, 1)&#10;    var i = 0&#10;    while (i &lt; 60) { Fiber.yield(); i = i + 1 }&#10;&#10;    Env.write_mailbox(INDEXOF_ALARM, 0)&#10;    Env.write_mailbox(INDEXOF_DOOR_LOCKED, 1)&#10;}</pre> |
| JS (QuickJS) | <pre>(function*() {&#10;    while (read_mailbox(INDEXOF_TRIGGER_A) == 0) yield&#10;&#10;    write_mailbox(INDEXOF_ALARM, 1)&#10;    for (let i = 0; i &lt; 60; i++) yield&#10;&#10;    write_mailbox(INDEXOF_ALARM, 0)&#10;    write_mailbox(INDEXOF_DOOR_LOCKED, 1)&#10;})()</pre> |
| Forth (zForth) | <pre>INDEXOF_PHASE read-mailbox&#10;dup 0 = if&#10;  INDEXOF_TRIGGER_A read-mailbox 0 &lt;&gt; if&#10;    1 INDEXOF_ALARM write-mailbox&#10;    0 INDEXOF_TICKS write-mailbox&#10;    1 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;dup 1 = if&#10;  INDEXOF_TICKS read-mailbox 1 + dup INDEXOF_TICKS write-mailbox&#10;  60 &gt;= if&#10;    0 INDEXOF_ALARM write-mailbox&#10;    1 INDEXOF_DOOR_LOCKED write-mailbox&#10;    2 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;drop</pre> |

**NPC patrol** — walk A → idle → walk B → idle → repeat. The state machine
equivalent needs an explicit state variable and a separate branch per leg; the
coroutine reads top-to-bottom as the authored sequence.

| Language | Script |
|----------|--------|
| Lua | <pre>return coroutine.create(function()&#10;    while true do&#10;        write_mailbox(INDEXOF_AI_DEST, WAYPOINT_A)&#10;        write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)&#10;        repeat coroutine.yield()&#10;        until read_mailbox(INDEXOF_AT_DEST) ~= 0&#10;&#10;        write_mailbox(INDEXOF_AI_STATE, STATE_IDLE)&#10;        for _ = 1, 90 do coroutine.yield() end&#10;&#10;        write_mailbox(INDEXOF_AI_DEST, WAYPOINT_B)&#10;        write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)&#10;        repeat coroutine.yield()&#10;        until read_mailbox(INDEXOF_AT_DEST) ~= 0&#10;&#10;        for _ = 1, 90 do coroutine.yield() end&#10;    end&#10;end)</pre> |
| Fennel | <pre>(coroutine.create&#10;  (fn []&#10;    (while true&#10;      (write_mailbox INDEXOF_AI_DEST WAYPOINT_A)&#10;      (write_mailbox INDEXOF_AI_STATE STATE_WALKING)&#10;      (while (= (read_mailbox INDEXOF_AT_DEST) 0)&#10;        (coroutine.yield))&#10;&#10;      (write_mailbox INDEXOF_AI_STATE STATE_IDLE)&#10;      (for [_ 1 90] (coroutine.yield))&#10;&#10;      (write_mailbox INDEXOF_AI_DEST WAYPOINT_B)&#10;      (write_mailbox INDEXOF_AI_STATE STATE_WALKING)&#10;      (while (= (read_mailbox INDEXOF_AT_DEST) 0)&#10;        (coroutine.yield))&#10;&#10;      (for [_ 1 90] (coroutine.yield)))))</pre> |
| Wren | <pre>var _thread = Fiber.new {&#10;    while (true) {&#10;        Env.write_mailbox(INDEXOF_AI_DEST, WAYPOINT_A)&#10;        Env.write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)&#10;        while (Env.read_mailbox(INDEXOF_AT_DEST) == 0) Fiber.yield()&#10;&#10;        Env.write_mailbox(INDEXOF_AI_STATE, STATE_IDLE)&#10;        var i = 0&#10;        while (i &lt; 90) { Fiber.yield(); i = i + 1 }&#10;&#10;        Env.write_mailbox(INDEXOF_AI_DEST, WAYPOINT_B)&#10;        Env.write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)&#10;        while (Env.read_mailbox(INDEXOF_AT_DEST) == 0) Fiber.yield()&#10;&#10;        i = 0&#10;        while (i &lt; 90) { Fiber.yield(); i = i + 1 }&#10;    }&#10;}</pre> |
| JS (QuickJS) | <pre>(function*() {&#10;    while (true) {&#10;        write_mailbox(INDEXOF_AI_DEST, WAYPOINT_A)&#10;        write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)&#10;        while (read_mailbox(INDEXOF_AT_DEST) == 0) yield&#10;&#10;        write_mailbox(INDEXOF_AI_STATE, STATE_IDLE)&#10;        for (let i = 0; i &lt; 90; i++) yield&#10;&#10;        write_mailbox(INDEXOF_AI_DEST, WAYPOINT_B)&#10;        write_mailbox(INDEXOF_AI_STATE, STATE_WALKING)&#10;        while (read_mailbox(INDEXOF_AT_DEST) == 0) yield&#10;&#10;        for (let i = 0; i &lt; 90; i++) yield&#10;    }&#10;})()</pre> |
| Forth (zForth) | <pre>INDEXOF_PHASE read-mailbox&#10;dup 0 = if&#10;  WAYPOINT_A INDEXOF_AI_DEST write-mailbox&#10;  STATE_WALKING INDEXOF_AI_STATE write-mailbox&#10;  1 INDEXOF_PHASE write-mailbox&#10;fi&#10;dup 1 = if&#10;  INDEXOF_AT_DEST read-mailbox 0 &lt;&gt; if&#10;    STATE_IDLE INDEXOF_AI_STATE write-mailbox&#10;    0 INDEXOF_TICKS write-mailbox&#10;    2 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;dup 2 = if&#10;  INDEXOF_TICKS read-mailbox 1 + dup INDEXOF_TICKS write-mailbox&#10;  90 &gt;= if&#10;    WAYPOINT_B INDEXOF_AI_DEST write-mailbox&#10;    STATE_WALKING INDEXOF_AI_STATE write-mailbox&#10;    3 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;dup 3 = if&#10;  INDEXOF_AT_DEST read-mailbox 0 &lt;&gt; if&#10;    STATE_IDLE INDEXOF_AI_STATE write-mailbox&#10;    0 INDEXOF_TICKS write-mailbox&#10;    4 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;dup 4 = if&#10;  INDEXOF_TICKS read-mailbox 1 + dup INDEXOF_TICKS write-mailbox&#10;  90 &gt;= if  0 INDEXOF_PHASE write-mailbox  fi&#10;fi&#10;drop</pre> |

**Cutscene sequencer** — gate on trigger, timed camera cuts, signal completion.
Helper functions inline keep the sequence readable. JS uses `yield*` to delegate
yields from inner generator helpers into the outer one.

| Language | Script |
|----------|--------|
| Lua | <pre>return coroutine.create(function()&#10;    local function hold(shot, ticks)&#10;        write_mailbox(INDEXOF_CAMSHOT, shot)&#10;        for _ = 1, ticks do coroutine.yield() end&#10;    end&#10;    local function wait_trigger(mb)&#10;        repeat coroutine.yield()&#10;        until read_mailbox(mb) ~= 0&#10;    end&#10;&#10;    wait_trigger(INDEXOF_CUTSCENE_START)&#10;    hold(1, 60)  -- establishing ~2 s&#10;    hold(2, 45)  -- character ~1.5 s&#10;    hold(3, 90)  -- reaction ~3 s&#10;    hold(1, 30)  -- wide ~1 s&#10;    write_mailbox(INDEXOF_CUTSCENE_DONE, 1)&#10;end)</pre> |
| Fennel | <pre>(coroutine.create&#10;  (fn []&#10;    (let [hold&#10;          (fn [shot ticks]&#10;            (write_mailbox INDEXOF_CAMSHOT shot)&#10;            (for [_ 1 ticks] (coroutine.yield)))&#10;          wait-trigger&#10;          (fn [mb]&#10;            (while (= (read_mailbox mb) 0)&#10;              (coroutine.yield)))]&#10;      (wait-trigger INDEXOF_CUTSCENE_START)&#10;      (hold 1 60)&#10;      (hold 2 45)&#10;      (hold 3 90)&#10;      (hold 1 30)&#10;      (write_mailbox INDEXOF_CUTSCENE_DONE 1))))</pre> |
| Wren | <pre>var hold = Fn.new {|shot, ticks|&#10;    Env.write_mailbox(INDEXOF_CAMSHOT, shot)&#10;    var i = 0&#10;    while (i &lt; ticks) { Fiber.yield(); i = i + 1 }&#10;}&#10;var waitTrigger = Fn.new {|mb|&#10;    while (Env.read_mailbox(mb) == 0) Fiber.yield()&#10;}&#10;&#10;var _thread = Fiber.new {&#10;    waitTrigger.call(INDEXOF_CUTSCENE_START)&#10;    hold.call(1, 60)&#10;    hold.call(2, 45)&#10;    hold.call(3, 90)&#10;    hold.call(1, 30)&#10;    Env.write_mailbox(INDEXOF_CUTSCENE_DONE, 1)&#10;}</pre> |
| JS (QuickJS) | <pre>(function*() {&#10;    function* hold(shot, ticks) {&#10;        write_mailbox(INDEXOF_CAMSHOT, shot)&#10;        for (let i = 0; i &lt; ticks; i++) yield&#10;    }&#10;    function* waitTrigger(mb) {&#10;        while (read_mailbox(mb) == 0) yield&#10;    }&#10;&#10;    yield* waitTrigger(INDEXOF_CUTSCENE_START)&#10;    yield* hold(1, 60)&#10;    yield* hold(2, 45)&#10;    yield* hold(3, 90)&#10;    yield* hold(1, 30)&#10;    write_mailbox(INDEXOF_CUTSCENE_DONE, 1)&#10;})()</pre> |
| Forth (zForth) | <pre>INDEXOF_PHASE read-mailbox&#10;dup 0 = if&#10;  INDEXOF_CUTSCENE_START read-mailbox 0 &lt;&gt; if&#10;    1 INDEXOF_CAMSHOT write-mailbox&#10;    0 INDEXOF_TICKS write-mailbox&#10;    1 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;dup 1 = if&#10;  INDEXOF_TICKS read-mailbox 1 + dup INDEXOF_TICKS write-mailbox&#10;  60 &gt;= if  2 INDEXOF_CAMSHOT write-mailbox  0 INDEXOF_TICKS write-mailbox  2 INDEXOF_PHASE write-mailbox  fi&#10;fi&#10;dup 2 = if&#10;  INDEXOF_TICKS read-mailbox 1 + dup INDEXOF_TICKS write-mailbox&#10;  45 &gt;= if  3 INDEXOF_CAMSHOT write-mailbox  0 INDEXOF_TICKS write-mailbox  3 INDEXOF_PHASE write-mailbox  fi&#10;fi&#10;dup 3 = if&#10;  INDEXOF_TICKS read-mailbox 1 + dup INDEXOF_TICKS write-mailbox&#10;  90 &gt;= if  1 INDEXOF_CAMSHOT write-mailbox  0 INDEXOF_TICKS write-mailbox  4 INDEXOF_PHASE write-mailbox  fi&#10;fi&#10;dup 4 = if&#10;  INDEXOF_TICKS read-mailbox 1 + dup INDEXOF_TICKS write-mailbox&#10;  30 &gt;= if  1 INDEXOF_CUTSCENE_DONE write-mailbox  5 INDEXOF_PHASE write-mailbox  fi&#10;fi&#10;drop</pre> |

**Door** — wait for player proximity, step through open animation, stay open.
Script ends; mailbox persists.

| Language | Script |
|----------|--------|
| Lua | <pre>return coroutine.create(function()&#10;    repeat coroutine.yield()&#10;    until read_mailbox(INDEXOF_PLAYER_DIST) &lt; 100&#10;&#10;    for frame = 0, 7 do&#10;        write_mailbox(INDEXOF_DOOR_FRAME, frame)&#10;        coroutine.yield()&#10;        coroutine.yield()  -- 2 ticks per frame&#10;    end&#10;&#10;    write_mailbox(INDEXOF_DOOR_OPEN, 1)&#10;end)</pre> |
| Fennel | <pre>(coroutine.create&#10;  (fn []&#10;    (while (>= (read_mailbox INDEXOF_PLAYER_DIST) 100)&#10;      (coroutine.yield))&#10;    (for [frame 0 7]&#10;      (write_mailbox INDEXOF_DOOR_FRAME frame)&#10;      (coroutine.yield)&#10;      (coroutine.yield))&#10;    (write_mailbox INDEXOF_DOOR_OPEN 1)))</pre> |
| Wren | <pre>var _thread = Fiber.new {&#10;    while (Env.read_mailbox(INDEXOF_PLAYER_DIST) >= 100) Fiber.yield()&#10;&#10;    var frame = 0&#10;    while (frame &lt;= 7) {&#10;        Env.write_mailbox(INDEXOF_DOOR_FRAME, frame)&#10;        Fiber.yield()&#10;        Fiber.yield()&#10;        frame = frame + 1&#10;    }&#10;&#10;    Env.write_mailbox(INDEXOF_DOOR_OPEN, 1)&#10;}</pre> |
| JS (QuickJS) | <pre>(function*() {&#10;    while (read_mailbox(INDEXOF_PLAYER_DIST) >= 100) yield&#10;&#10;    for (let frame = 0; frame &lt;= 7; frame++) {&#10;        write_mailbox(INDEXOF_DOOR_FRAME, frame)&#10;        yield&#10;        yield&#10;    }&#10;&#10;    write_mailbox(INDEXOF_DOOR_OPEN, 1)&#10;})()</pre> |
| Forth (zForth) | <pre>\ 1 tick per frame; for 2 ticks/frame add an INDEXOF_SUBTICK mailbox&#10;INDEXOF_PHASE read-mailbox&#10;dup 0 = if&#10;  INDEXOF_PLAYER_DIST read-mailbox 100 &lt; if&#10;    0 INDEXOF_DOOR_FRAME write-mailbox&#10;    1 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;dup 1 = if&#10;  INDEXOF_DOOR_FRAME read-mailbox 1 + dup INDEXOF_DOOR_FRAME write-mailbox&#10;  8 &gt;= if&#10;    1 INDEXOF_DOOR_OPEN write-mailbox&#10;    2 INDEXOF_PHASE write-mailbox&#10;  fi&#10;fi&#10;drop</pre> |

### Rules

- **Lua/Fennel**: return `coroutine.create(fn)`, not `coroutine.wrap(fn)`.
  `coroutine.wrap` returns a plain function, not a thread; the engine won't
  detect it.
- **Wren**: assign `Fiber.new { ... }` to a module-level variable named
  `_thread`. Helper `Fn` objects called from inside the fiber can call
  `Fiber.yield()` freely — it yields the enclosing fiber regardless of call depth.
- **JS (QuickJS)**: evaluate to a generator via `(function*() { ... })()`.
  Helper generator functions called with `yield*` delegate their yields into
  the outer generator. JerryScript (ES5.1) has no generators; use per-tick
  `if`/state-variable patterns instead.
- **Forth (zForth)**: no native coroutine. Use `dup N = if ... fi` dispatch
  keyed on an `INDEXOF_PHASE` mailbox; tick counts in a second scratch mailbox.
  Do not define words inside game scripts — the zForth dictionary is
  append-only and re-definitions accumulate each tick. `fi` closes conditionals,
  not `then`. Engine-level YIELD (snapshot/restore of `zf_ctx` across ticks)
  would enable linear coroutine syntax and is a future feature.
- A script that never returns a thread/fiber/generator is unaffected — plain
  per-tick execution is unchanged.
- On error or completion the actor reverts to normal per-tick execution.
- Per-actor isolation applies inside suspended coroutines/fibers/generators —
  locals are private to that actor.
- Only one suspended thread per actor at a time.

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

- `wftools/engine/stubs/scripting_stub.cc` — `ScriptRouter`, `lua_engine`, Fennel sub-dispatch.
- `wftools/engine/stubs/scripting_{js,quickjs,jerryscript,wasm3,wamr,forth,wren}.{hp,cc}` — per-engine plugs.
- `wftools/engine/stubs/fennel.lua` — vendored Fennel 1.6.1 (minified by `scripts/minify_lua.py`).
- `engine/vendor/{quickjs-v0.14.0,jerryscript-v3.0.0,wasm3-v0.5.0,wamr-2.2.0,wren-0.4.0,zforth-*,ficl,atlast,embed,libforth,pforth}/` — vendored runtimes.
- `scripts/patch_snowgoons_*.py` — per-language snowgoons iff patchers.
- `docs/plans/2026-04-1{3,4}-*.md` — per-engine spike/integration plans.
