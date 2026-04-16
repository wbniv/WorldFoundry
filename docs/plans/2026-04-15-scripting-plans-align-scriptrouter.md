# Plan: align scripting-engine plans with ScriptRouter convention

**Date:** 2026-04-15
**Status:** complete 2026-04-16 — all phases (A, A′, B, C, D.1–D.5, E) complete; all engine smoke tests passed 2026-04-16 (JerryScript, WAMR, Wren, zForth)
**Scope:** docs-only pass over `docs/plans/2026-04-{13,14,15}-*` scripting-engine plans.

## Context

The 2026-04-15 ScriptRouter refactor (captured in `docs/plans/2026-04-15-lua-engine-fixes.md` and the "As built" callout in `docs/plans/2026-04-14-pluggable-scripting-engine.md`) changed the shape of every scripting engine in `wftools/engine/stubs/scripting_stub.cc`:

- `LuaInterpreter` is gone. A `ScriptRouter : public ScriptInterpreter` owns every engine's lifecycle as a peer.
- Each engine lives as a file-scope `<engine>_engine` namespace with module-level globals (not a class, not member variables), exposing `Init(mgr) / Shutdown() / AddConstantArray(list) / DeleteConstantArray(list) / RunScript(src, objectIndex)`.
- Sigil dispatch, constant-array broadcast, and shutdown sequencing live in `ScriptRouter`; no engine initialises another.
- Fennel remains a sub-dispatch **inside** `lua_engine` (it compiles to Lua and shares the `lua_State`) — it is *not* a router-level peer.

The currently-landed JS (`JsRuntimeInit / JsRunScript / …`) and wasm3 (`Wasm3RuntimeInit / Wasm3RunScript / …`) plugs still use the earlier free-function `VerbNoun` style. The newer `lua_engine` namespace style is the convention going forward.

The older scripting plans (Lua spike, Fennel, JS, wasm3) describe a `LuaInterpreter` class that no longer exists. Pending plans (WAMR, Wren, Forth) describe hooking into `LuaInterpreter::RunScript` / ctor / dtor — those hooks don't exist either. This plan updates every doc in one sweep so the next person reading them doesn't have to mentally retarget every code snippet.

## Current status of each scripting plan

| # | Plan doc | Language / runtime | Status | Vendor present | Plug file present | Uses new convention |
|---|----------|--------------------|--------|----------------|-------------------|---------------------|
| 1 | `2026-04-13-lua-interpreter-spike.md` | Lua 5.4 | **landed** | `engine/vendor/lua-5.4.8/` | `scripting_stub.cc` (`lua_engine` ns) | yes (canonical) |
| 2 | `2026-04-14-vendor-lua.md` | Lua 5.4 (vendoring) | **landed** | `engine/vendor/lua-5.4.8/` | n/a | yes |
| 3 | `2026-04-14-fennel-on-lua.md` | Fennel | **landed** | `wftools/engine/stubs/fennel.lua` | sub-dispatch in `lua_engine` ns | yes (sub-engine, not router peer) |
| 4 | `2026-04-14-pluggable-scripting-engine.md` | QuickJS / JerryScript | **landed** (status marker present) | `quickjs-v0.14.0/`, `jerryscript-v3.0.0/` | `scripting_quickjs.cc`, `scripting_jerryscript.cc` | partial — uses `JsRuntimeInit/JsRunScript` free-fn style; should migrate to `js_engine` namespace |
| 5 | `2026-04-14-wasm3-scripting-engine.md` | wasm3 | **landed** (no status marker) | `wasm3-v0.5.0/`, `wasm3-v0.5.0-wf/` | `scripting_wasm3.cc` | partial — uses `Wasm3RuntimeInit/Wasm3RunScript`; should migrate to `wasm3_engine` namespace |
| 6 | `2026-04-14-wamr-dev-aot-ship.md` | WAMR (interp + AOT) | **landed 2026-04-15** (interp phase 1; WAT compiled; needs smoke test) | `wamr-2.2.0/`, `wamr-2.2.0-wf/` (incl. compiled `.wasm`) | `scripting_wamr.hp`, `scripting_wamr.cc` | yes — `wamr_engine` namespace |
| 7 | `2026-04-14-wren-scripting-engine.md` | Wren | **landed 2026-04-15** (needs smoke test) | `wren-0.4.0/` | `scripting_wren.hp`, `scripting_wren.cc` | yes — `wren_engine` namespace |
| 8 | `2026-04-14-forth-scripting-engine.md` | zForth/ficl/Atlast/embed/libforth/pForth (pluggable) | **landed 2026-04-15** (zForth default; needs smoke test) | `zforth-*/`, `ficl-*/`, etc. | `scripting_forth.hp`, `scripting_zforth.cc` | yes — `forth_engine` namespace |
| 9 | `2026-04-15-lua-engine-fixes.md` | Lua (fixes #1–#6) | **landed 2026-04-15** (#1–#5 shipped; #6 coroutines landed, needs smoke test) | n/a | n/a | yes — defines the convention |

A row-for-row version of this table should also land at the top of `docs/scripting-languages.md` (user-visible status reference). That is included in Phase C below.

## Approach

### Phase A — Mark landed plans with a status block and retarget their code

For each **landed** plan (rows 1–5) add (if missing) a top-of-file `**Status:** landed YYYY-MM-DD (<notes>)` line identical in shape to the one already in the JS plan. Then edit the body so that:

- All references to `LuaInterpreter` / `LuaInterpreter::ctor` / `LuaInterpreter::RunScript` become `ScriptRouter` / `ScriptRouter::RunScript` / `<engine>_engine::Init` as appropriate.
- Code snippets that show member variables (`int _fennelEvalRef` etc.) become file-scope statics inside the relevant `<engine>_engine` namespace.
- Dispatch snippets that live in `LuaInterpreter::RunScript` move to `ScriptRouter::RunScript` (with the sigil match + `<engine>_engine::RunScript(src, objectIndex)` call).
- "As built" callouts capture any remaining deviation, but only the deviation — not the whole plan body.

**Plans 1 + 2 (Lua spike + vendor Lua):** add status blocks pointing at the current `lua_engine` namespace; flip "new file `luainterpreter.{cc,hp}`" language to "file-scope `lua_engine` namespace in `scripting_stub.cc`". Delete the "factory swap" section (it landed as `ScriptInterpreterFactory` returning `ScriptRouter`). Keep the hand-ported snowgoons snippets — they are still accurate.

**Plan 3 (Fennel):** call out that `_fennelEvalRef` lives as a module-level static inside `lua_engine`, not a `LuaInterpreter` member; the sigil dispatch is inside `lua_engine::RunScript` before the plain-Lua path; the compilation-cache improvements from `2026-04-15-lua-engine-fixes.md` fix #3 supersede the `fennel.eval` path described here.

**Plan 4 (pluggable / JS):** status marker already present. The existing "As built (ScriptRouter refactor, 2026-04-15)" callout at line ~107 already captures the refactor; promote the `//` arm to `ScriptRouter::RunScript`.

**Plan 5 (wasm3):** add a `**Status:** landed <date>` line (date from `git log` for `scripting_wasm3.cc` — commit `cfa739c`, 2026-04-14). Flip all "add the `#` arm in `scripting_stub.cc` next to the `;` and `//` branches" to "`ScriptRouter::RunScript` already contains the arm".

### Phase A′ — Rename landed engines into the `<engine>_engine` namespace

Code change, not just docs. Bring JS and wasm3 into the convention so
every engine has the same five-function shape:

- `scripting_js.hp` + `scripting_quickjs.cc` / `scripting_jerryscript.cc`:
  rename `JsRuntimeInit / JsRuntimeShutdown / JsRunScript /
  JsAddConstantArray / JsDeleteConstantArray` → `js_engine::Init /
  Shutdown / RunScript / AddConstantArray / DeleteConstantArray`. Update
  `ScriptRouter` call sites.
- `scripting_wasm3.hp` + `scripting_wasm3.cc`: rename `Wasm3RuntimeInit /
  Wasm3RuntimeShutdown / Wasm3RunScript / Wasm3AddConstantArray /
  Wasm3DeleteConstantArray` → `wasm3_engine::Init / Shutdown / RunScript
  / AddConstantArray / DeleteConstantArray`. Update `ScriptRouter` call
  sites.

Verify by rebuilding each flavour (`WF_JS_ENGINE=quickjs`,
`WF_JS_ENGINE=jerryscript`, `WF_WASM_ENGINE=wasm3`) and re-running the
snowgoons player + director ports.

### Phase B — Retarget pending plans onto the new convention

For each pending plan (rows 6–8) rewrite every snippet that names `LuaInterpreter` so it instead:

- Declares a file-scope namespace `<engine>_engine` inside a sibling TU `scripting_<name>.cc` (matching JS/wasm3; keeps `scripting_stub.cc` from becoming unbounded). Expose the five-function ABI via a `scripting_<name>.hp`. The namespace name inside the `.cc` file matches the engine name for consistency with `lua_engine`.
- Adds `<engine>_engine::Init(mgr)` to `ScriptRouter::ScriptRouter` next to the existing `lua_engine::Init / JsRuntimeInit / Wasm3RuntimeInit` calls (guarded by the plan's `WF_ENABLE_<X>` / `WF_<X>_ENGINE` macro).
- Adds `<engine>_engine::Shutdown()` to `~ScriptRouter` in reverse order.
- Adds `<engine>_engine::AddConstantArray(list)` to `ScriptRouter::AddConstantArray`.
- Adds the sigil match arm to `ScriptRouter::RunScript` **in the correct priority order** (longer/more-specific sigils first): `\` → Forth, `//wren\n` → Wren, `//` → JS, `#b64\n` / `#aot\n` → wasm (wasm3 **or** WAMR depending on switch), `;` → Fennel (inside `lua_engine`), else → `lua_engine::RunScript` (fallthrough).

**Plan 6 (WAMR):** reuses the `#` sigil already claimed by wasm3. Clarify that `WF_WASM_ENGINE` selects exactly one of `{none, wasm3, wamr, wamr-aot, w2c2}` and the dispatch arm in `ScriptRouter::RunScript` is a single `#`-prefix branch that calls whichever `<impl>_engine::RunScript` is compiled in. The "Phase 1 step 2: `scripting_wamr.{hp,cc}` — same shape as `scripting_wasm3.cc`" instruction stands but should explicitly name the namespace `wamr_engine`.

**Plan 7 (Wren):** rewrite Phase 4 ("Dispatch in `scripting_stub.cc`"). Instead of hooking `LuaInterpreter::LuaInterpreter()` ctor/dtor/AddConstantArray, hook `ScriptRouter::ScriptRouter() / ~ScriptRouter() / AddConstantArray`. The new Phase 4 reads as four insertions into `ScriptRouter`, each guarded by `#ifdef WF_ENABLE_WREN`, matching the existing JS/wasm3 insertions. The `//wren\n` sigil check goes into `ScriptRouter::RunScript` **before** the `//` JS check.

**Plan 8 (Forth):** same retargeting — the `\` dispatch arm goes into `ScriptRouter::RunScript` first (it's the most specific one-byte sigil for a backslash). Phase 6 ("Integrate into `scripting_stub.cc`") becomes "add `forth_engine::Init / Shutdown / AddConstantArray` calls into `ScriptRouter` and the `\` arm into `ScriptRouter::RunScript`". Keep the backend-selection mechanism (`WF_FORTH_ENGINE=zforth|ficl|…`) unchanged — each selected backend compiles into a single `forth_engine` namespace with the chosen implementation.

### Phase C — Add a unified status table to `docs/scripting-languages.md`

Prepend a **Status** table (the one in this plan) to `docs/scripting-languages.md`. Each pending row links to its plan; each landed row links to the plan **and** to the source file in `wftools/engine/stubs/`.

### Phase D — Implement pending scripting engines

**Definition of done for each engine:** code compiles, snowgoons player + director smoke test passes, `docs/scripting-languages.md` updated (engine row, sigil, compile switch, binary cost, status → "shipping"), snowgoons reference scripts added to the doc.

#### D.1 Lua fixes (#1–#6) — see `2026-04-15-lua-engine-fixes.md`

No new vendor. All changes in `scripting_stub.cc` (`lua_engine` namespace).

| Fix | Risk | Effort |
|-----|------|--------|
| #4 Gate debug `fprintf` behind `WF_SCRIPT_DEBUG` | zero | 5 min |
| #5 Sandbox stdlib (remove `io`/`os` from `luaL_openlibs`) | zero | 15 min |
| #1 Script compilation cache (`luaL_ref` + `unordered_map`) | medium | 1 h |
| #2 Per-actor environment tables | medium | 2 h |
| #3 Fennel pre-compilation cache (`fennel.compileString`) | medium | 1 h |
| #6 Multi-tick coroutine continuations (`lua_resume`) | high | half-day — land separately after #1–#5 |

Land order: #4+#5 → #1+#2+#3 together → #6 separately. Update Lua + Fennel rows in `docs/scripting-languages.md` with a status footnote once fixes land. No new sigil or switch.

#### D.2 JerryScript smoke test

Build path landed; vendor at `engine/vendor/jerryscript-v3.0.0/`; `scripting_jerryscript.cc` exists. Not yet smoke-tested.

1. Build: `WF_JS_ENGINE=jerryscript bash engine/build_game.sh`
2. Run snowgoons player + director; fix any bugs
3. Verify behavior matches QuickJS

**Doc updates:** flip JerryScript status from "landed (build path); not yet smoke-tested" → "shipping". Add JerryScript snowgoons player + director reference scripts.

**Effort:** half-day.

#### D.3 Forth — see `2026-04-14-forth-scripting-engine.md`

All 6 vendor dirs already in tree. Default engine: **zForth** (4 KB, MIT).

| Vendor dir | Engine | Size | License |
|-----------|--------|------|---------|
| `zforth-41db72d1/` | zForth | 4 KB | MIT |
| `ficl-3.06/` | ficl | ~100 KB | BSD-2 |
| `atlast-08ff0e1a/` | Atlast | ~30 KB | Public domain |
| `embed-154aeb2f/` | embed | ~5 KB VM | MIT |
| `libforth-b851c6a2/` | libforth | ~50 KB | MIT |
| `pforth-63d4a418/` | pForth | ~120 KB | 0-BSD |
| `nanoforth-3b9c3aab/` | nanoFORTH | — | not yet a `WF_FORTH_ENGINE` option |

Sigil: `\` (Forth line-comment; dispatch before `//`).

1. `wftools/engine/stubs/scripting_forth.hp` — shared plug ABI header
2. `scripting_zforth.cc` — zForth default backend (`forth_engine` namespace)
3. Dispatch arm in `ScriptRouter::RunScript` (`\` sigil, before `//`)
4. `WF_FORTH_ENGINE=zforth` + `WF_ENABLE_FORTH` in `build_game.sh`
5. Smoke test with zForth
6. `scripts/patch_snowgoons_forth.py` — patch snowgoons IFF with `\`-sigil scripts
7. Remaining backends: `scripting_{ficl,atlast,embed,libforth,pforth}.cc` (same ABI, one at a time)

**Doc updates:** add Forth section to `docs/scripting-languages.md` — one row per backend, sigil `\`, `WF_FORTH_ENGINE` / `WF_ENABLE_FORTH` switches, binary cost per engine, status. Add snowgoons player + director examples in Forth (valid for all backends — shared word definitions).

**Effort:** 1–2 days.

#### D.4 Wren — see `2026-04-14-wren-scripting-engine.md`

Plan already refreshed to ScriptRouter convention in Phase B. Vendor (Wren 0.4.0 single-file amalgamation) not yet in tree.

Sigil: `//wren\n` (checked before generic `//` to avoid false dispatch to JS).

1. Vendor Wren 0.4.0 amalgamation under `engine/vendor/wren-0.4.0/`
2. `scripting_wren.hp` + `scripting_wren.cc` (`wren_engine` namespace)
3. Dispatch arm in `ScriptRouter::RunScript` (before `//` JS check)
4. `WF_ENABLE_WREN=1` in `build_game.sh`
5. Smoke test
6. `scripts/patch_snowgoons_wren.py`

**Doc updates:** add Wren row to `docs/scripting-languages.md` — sigil `//wren\n`, `WF_ENABLE_WREN`, binary cost (~100 KB), status, foreign-class mailbox bridge note (`Env.read_mailbox` / `Env.write_mailbox`). Add snowgoons player + director examples in Wren.

**Effort:** 1–2 days.

#### D.5 WAMR — see `2026-04-14-wamr-dev-aot-ship.md`

**Landed 2026-04-15 (phase 1 — interp; needs smoke test).**

Phase 1 (interp only) — all steps complete:
1. ✓ Vendor WAMR 2.2.0 classic interpreter under `engine/vendor/wamr-2.2.0/`
2. ✓ `wftools/engine/stubs/scripting_wamr.hp` + `scripting_wamr.cc` (`wamr_engine` namespace, wasm-C-API)
3. ✓ Extend `WF_WASM_ENGINE=wamr` in `build_game.sh`; CMake block builds `libvmlib.a` (~519 KB at MinSizeRel)
4. ✓ Re-authored snowgoons WAT sources in `wamr-2.2.0-wf/` using `(import "consts" "INDEXOF_*" (global i32))` host globals
5. ✓ Compiled WAT → `.wasm` via `wat2wasm` (director 158 B, player 159 B); `scripts/patch_snowgoons_wamr.py` prefers these over the wasm3 fallback
6. ⬜ Smoke test — blocked on HAL cleanup (other branch)

AOT path (phase 2) deferred.

#### Full dispatch order after Phase D

```
1. `\`        → Forth     (if WF_ENABLE_FORTH)
2. `//wren\n` → Wren      (if WF_ENABLE_WREN)
3. `//`       → JS        (QuickJS or JerryScript, if WF_WITH_JS)
4. `#b64\n`   → Wasm      (wasm3 or WAMR, if WF_WITH_WASM)
5. `;`        → Fennel    (inside Lua, if WF_ENABLE_FENNEL)
6. fallthrough → Lua
```

#### Recommended land order

1. **Lua fixes #4+#5** — zero risk; 20 min total
2. **JerryScript smoke test** — closes out the JS chapter; half-day
3. **Lua fixes #1–#3** — hardening pass; land together
4. **Forth (zForth first)** — vendors in tree, plan clean; 1–2 days
5. **Wren** — vendor + impl; 1–2 days
6. **WAMR** — last; largest lift; 2–3 days
7. **Lua fix #6** — separate, after everything else stable

### Phase E — Reference scripts in `docs/scripting-languages.md`

`docs/scripting-languages.md` carries the canonical player + director
snowgoons scripts for every engine WF supports.  The doc currently has
working, committed scripts for **Lua**, **Fennel**, **QuickJS**, and
**wasm3**.  Phase E extends it with the remaining engines.

**JerryScript** — no new block needed; JerryScript shares the `//` sigil
with QuickJS and the authored source is byte-for-byte identical.  Add a
one-line note under the existing QuickJS block:

> **JavaScript (JerryScript):** scripts are identical to the QuickJS
> block above. Both engines use the `//` sigil; `WF_JS_ENGINE` picks
> which runtime is compiled in.

**Forth** (after D.3 lands) — add after the existing wasm3 block.
`read-mailbox` and `write-mailbox` are hyphenated host words with stack
signatures `( idx -- val )` and `( val idx -- )` respectively.
`INDEXOF_*` constants are loaded into the dictionary at `Init`.
The same source runs on every backend (zForth, ficl, Atlast, embed,
libforth, pForth) — backend selection is compile-time only.

*Player:*
```forth
\ snowgoons player
INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox
```

*Director:*
```forth
\ snowgoons director
: ?cam ( mb -- ) read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then ;
100 ?cam   99 ?cam   98 ?cam
```

Note: on PC dev mailbox values are float; embed truncates to 16-bit int.
On the real fixed-point target all engines use integer-valued mailboxes
so this is correct.

**Wren** (after D.4 lands) — add after the Forth block.
`INDEXOF_*` constants are injected as module-level `var` declarations in
a preamble built at `wren_engine::Init`; they are bare names in scripts.
Mailbox access is through the foreign class `Env` — Wren has no
top-level functions.

*Player:*
```wren
//wren
Env.write_mailbox(INDEXOF_INPUT, Env.read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW))
```

*Director:*
```wren
//wren
var v
v = Env.read_mailbox(100); if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
v = Env.read_mailbox(99);  if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
v = Env.read_mailbox(98);  if (v != 0) Env.write_mailbox(INDEXOF_CAMSHOT, v)
```

**WAMR WAT** (after D.5 lands) — add a note under the existing wasm3 WAT
block.  The `.wat` source differs from wasm3 only in how constants are
imported: WAMR supports host-supplied `(global …)` imports so
`INDEXOF_*` are declared as global imports rather than baked literals.

*Player WAT (WAMR):*
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

*Director WAT (WAMR):*
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

Unlike wasm3, WAMR resolves `INDEXOF_CAMSHOT` from the host globals table
at instantiate time — no baked literals in the module body.

#### Phase E verification

For each engine block added:
1. Script source is copy-pasted from the doc into the patching script (or
   run manually) and the iff is re-patched.
2. `wf_game` runs snowgoons: player moves, director cuts cameras.
3. Status in the doc's engine table updated to "shipping".

### Phase F — Smoke test all engines in `wf_game`

**Definition of done:** `wf_game -Lwflevels/snowgoons.iff` runs with the given engine
compiled in, player moves under joystick input, director cuts cameras on trigger.
Once passed, flip the engine's status to "shipping" in `docs/scripting-languages.md`.

| Engine | Build switch | Status |
|--------|-------------|--------|
| Lua 5.4 | `WF_ENABLE_LUA=1` | ✓ done |
| Fennel | `WF_ENABLE_FENNEL=1` | ✓ done |
| JavaScript (QuickJS) | `WF_JS_ENGINE=quickjs` | ✓ done |
| WebAssembly (wasm3) | `WF_WASM_ENGINE=wasm3` | ✓ done |
| JavaScript (JerryScript) | `WF_JS_ENGINE=jerryscript` | ⬜ build path landed; never run |
| WebAssembly (WAMR) | `WF_WASM_ENGINE=wamr` | ⬜ blocked on HAL cleanup (other branch) |
| Forth (zForth) | `WF_FORTH_ENGINE=zforth` | ⬜ landed 2026-04-15; needs smoke test |
| Wren | `WF_ENABLE_WREN=1` | ⬜ landed 2026-04-15; needs smoke test |

## Critical files

**Docs (Phases A, B, C):**
- `docs/plans/2026-04-13-lua-interpreter-spike.md`
- `docs/plans/2026-04-14-vendor-lua.md`
- `docs/plans/2026-04-14-fennel-on-lua.md`
- `docs/plans/2026-04-14-pluggable-scripting-engine.md`
- `docs/plans/2026-04-14-wasm3-scripting-engine.md`
- `docs/plans/2026-04-14-wamr-dev-aot-ship.md`
- `docs/plans/2026-04-14-wren-scripting-engine.md`
- `docs/plans/2026-04-14-forth-scripting-engine.md`
- `docs/plans/2026-04-15-lua-engine-fixes.md` (cosmetic cross-reference)
- `docs/scripting-languages.md` — host for the unified status table + per-engine rows and snowgoons reference scripts.

**Code (Phase A′ — rename):**
- `wftools/engine/stubs/scripting_js.hp` — wrap decls in `namespace js_engine { ... }`
- `wftools/engine/stubs/scripting_wasm3.hp` — wrap decls in `namespace wasm3_engine { ... }`
- `wftools/engine/stubs/scripting_quickjs.cc`, `scripting_jerryscript.cc` — rename defs to `js_engine::*`
- `wftools/engine/stubs/scripting_wasm3.cc` — rename defs to `wasm3_engine::*`
- `wftools/engine/stubs/scripting_stub.cc` — rename call sites

**Code (Phase D — new engines / lua fixes):**
- `wftools/engine/stubs/scripting_stub.cc` (lua_engine fixes, dispatch arms)
- new: `scripting_forth.hp`, `scripting_zforth.cc` (+ other Forth backends)
- new: `scripting_wren.hp`, `scripting_wren.cc`
- new: `scripting_wamr.hp`, `scripting_wamr.cc`
- new vendor dirs: `engine/vendor/wren-0.4.0/`, `engine/vendor/wamr-*/`
- new patchers: `scripts/patch_snowgoons_{forth,wren}.py`
- `engine/build_game.sh` — new `WF_ENABLE_FORTH` / `WF_FORTH_ENGINE` / `WF_ENABLE_WREN` / `WF_WASM_ENGINE=wamr` flags

**Reference (canonical shape):**
- `wftools/engine/stubs/scripting_stub.cc` — `ScriptRouter` + `lua_engine` namespace.

## Verification

1. Each landed plan clearly says `**Status:** landed <date>` at the top.
2. `grep -n LuaInterpreter docs/plans/2026-04-*-scripting*.md 2026-04-14-fennel*.md 2026-04-14-wamr*.md 2026-04-14-wren*.md 2026-04-14-forth*.md` returns either zero hits, or only hits inside historical "As built" callouts or code-archaeology notes (explicitly flagged as pre-refactor).
3. Every pending plan's "Integrate into `scripting_stub.cc`" / "Dispatch" section names `ScriptRouter`, not `LuaInterpreter`.
4. Status table in `docs/scripting-languages.md` (or `docs/plans/README.md`) lists all nine plans with correct status; cross-links resolve.
5. Sigil priority in the pending plans matches: `\` > `//wren\n` > `//` > `#…\n` > `;` > fallthrough.
6. Phase A′ code rename (JS + wasm3 plugs → `js_engine` / `wasm3_engine` namespaces) builds clean under both `WF_JS_ENGINE=quickjs` and `WF_WASM_ENGINE=wasm3`; snowgoons still runs. Phase D engine implementations carry their own per-engine verification (see D.1–D.5).
