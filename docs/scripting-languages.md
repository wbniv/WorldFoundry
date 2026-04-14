# Scripting languages in WF

The engine today speaks two scripting languages through a single
`LuaInterpreter`: **Lua 5.4** (default) and **Fennel** (Lisp → Lua,
compile-time opt-in via `WF_ENABLE_FENNEL=1`). Both target the same embedded
API — `read_mailbox(idx[, actor])`, `write_mailbox(idx, value[, actor])`,
and the `INDEXOF_*` / `JOYSTICK_BUTTON_*` globals.

Dispatch is a one-byte sniff in `LuaInterpreter::RunScript`: if the first
non-whitespace byte is `;` the script goes through `fennel.eval`; otherwise
it runs as Lua. `;` is a Lisp comment AND a Lua syntax error, so there's no
ambiguity and no markup tax.

## Reference scripts: snowgoons player + director

Every script has to start with `;` to reach the Fennel path. For scripts
that need to fit in a byte-preserving patch (same size as the TCL
predecessor), the `;` can stand alone on the first line.

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

## Integration surface

All languages ride on the same mailbox bridge, so the per-language cost is
(a) a runtime (bytes in `.rodata` or a linked library), and (b) a dispatch
discriminator in `RunScript`. Adding a language should not require changes
to the mailbox machinery or level format.

| Language | Sigil | Runtime | Compile-time switch | Binary cost | Status |
|----------|-------|---------|---------------------|-------------|--------|
| Lua 5.4  | *(default)* | `-llua5.4` (system) → to-vendor | always on | linked lib | shipping |
| Fennel   | `;` | `fennel.lua` embedded via codegen (minified) | `WF_ENABLE_FENNEL=1` | ~145 KB `.rodata` | shipping |
| JavaScript | `/` or `j` (TBD — `//` is comment) | QuickJS or duktape, embedded | `WF_ENABLE_JS=1` | ~500 KB text (QuickJS) | planned |
| WebAssembly | `\0asm` magic in the script bytes | wasm3 or wasmi, embedded | `WF_ENABLE_WASM=1` | ~300 KB (wasm3) | planned |

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
- `wftools/wf_viewer/stubs/fennel.lua` — vendored Fennel 1.6.1.
- `scripts/minify_lua.py` — Lua source minifier (used on `fennel.lua`).
- `scripts/patch_snowgoons_lua.py` — TCL → Lua byte-preserving patcher.
- `scripts/patch_snowgoons_fennel.py` — Lua → Fennel byte-preserving patcher.
- `docs/plans/2026-04-13-lua-interpreter-spike.md` — Lua spike plan.
- `docs/plans/2026-04-14-fennel-on-lua.md` — Fennel-on-Lua spike plan.
