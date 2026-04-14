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
| wasm3 | `WF_WASM_ENGINE=wasm3` | `#` | Planned. |

Dispatch is a leading-byte sniff: matching a sigil routes to that engine,
non-matching scripts go to the build's **fallthrough engine** (today Lua;
a future `WF_DEFAULT_ENGINE` knob lets a JS-only or wasm3-only build
declare a different fallthrough, or reject unsigilled scripts). Each
sigil is a syntax error in the other compiled-in languages, so a script
that meant for one engine never silently runs on another.

## Reference scripts: snowgoons player + director

Below are the same two gameplay scripts authored in every engine WF
currently supports. The engines are independent — a build can pick any
combination; the script set below only illustrates what each language
looks like, not what a single build must contain. Fennel, QuickJS, and
JerryScript each use a sigil; Lua scripts are sigil-less and only run if
Lua is compiled in.

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

**JavaScript (QuickJS):**
```javascript
// snowgoons player
write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW));
```

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

**JavaScript (QuickJS):**
```javascript
// snowgoons director
var v;
v = read_mailbox(100); if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);
v = read_mailbox(99);  if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);
v = read_mailbox(98);  if (v !== 0) write_mailbox(INDEXOF_CAMSHOT, v);
```

## Integration surface

All languages ride on the same mailbox bridge, so the per-language cost is
(a) a runtime (bytes in `.rodata` or a linked library), and (b) a dispatch
discriminator in `RunScript`. Adding a language should not require changes
to the mailbox machinery or level format.

| Language | Sigil | Runtime | Compile-time switch | Binary cost | Status |
|----------|-------|---------|---------------------|-------------|--------|
| Lua 5.4  | *(none — fallthrough)* | `-llua5.4` (system) → to-vendor | `WF_ENABLE_LUA=1` (default on today) | linked lib | shipping |
| Fennel   | `;` | `fennel.lua` embedded via codegen (minified) | `WF_ENABLE_FENNEL=1` (requires Lua) | ~145 KB `.rodata` | shipping |
| JavaScript (QuickJS) | `//` | QuickJS v0.14.0 statically linked from `wftools/vendor/` | `WF_JS_ENGINE=quickjs` | ~1.2 MB unstripped (~350 KB target stripped) | shipping |
| JavaScript (JerryScript) | `//` | JerryScript v3.0.0 `wf-minimal` profile | `WF_JS_ENGINE=jerryscript` | ~80–90 KB lib | landed (build path); not yet smoke-tested |
| WebAssembly | `#` | wasm3 v0.5.0 (interpreter) | `WF_WASM_ENGINE=wasm3` | ~65 KB core | planned |

None of these rows describe a dependency on any other row. The only
exception is Fennel, which compiles to Lua and therefore can't be
selected without Lua. Every other combination — QuickJS without Lua,
wasm3 without Lua, JerryScript + wasm3 with no Lua or Fennel — is a
supported build configuration.

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

- `wftools/wf_viewer/stubs/scripting_stub.cc` — `LuaInterpreter` + sigil
  dispatch.
- `wftools/wf_viewer/stubs/scripting_js.hp` — JS engine plug ABI.
- `wftools/wf_viewer/stubs/scripting_quickjs.cc` — QuickJS implementation.
- `wftools/wf_viewer/stubs/scripting_jerryscript.cc` — JerryScript implementation.
- `wftools/wf_viewer/stubs/fennel.lua` — vendored Fennel 1.6.1.
- `wftools/vendor/quickjs-v0.14.0/`, `wftools/vendor/jerryscript-v3.0.0/` — vendored JS engines.
- `scripts/minify_lua.py` — Lua source minifier (used on `fennel.lua`).
- `scripts/patch_snowgoons_lua.py` — TCL → Lua byte-preserving patcher.
- `scripts/patch_snowgoons_fennel.py` — Lua → Fennel byte-preserving patcher.
- `docs/plans/2026-04-13-lua-interpreter-spike.md` — Lua spike plan.
- `docs/plans/2026-04-14-fennel-on-lua.md` — Fennel-on-Lua spike plan.
- `docs/plans/2026-04-14-pluggable-scripting-engine.md` — JS engine plan.
