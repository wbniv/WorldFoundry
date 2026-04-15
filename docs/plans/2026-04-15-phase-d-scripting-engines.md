# Phase D — Implement pending scripting engines

## Context

After Phase A (drop-dead-renderers, done) and Phase B (LOC reduction / dead
code cleanup, in progress), Phase D lands all pending scripting engines.

Pluggable scripting ABI:
- `wftools/wf_viewer/stubs/scripting_stub.cc` — `ScriptRouter::RunScript` dispatch
- `wftools/wf_viewer/stubs/scripting_js.hp` — plug ABI header template

Current dispatch order: `//` → JS, `#b64\n` → wasm3, fallthrough → Lua/Fennel.

**Definition of done for each engine:** code compiles, snowgoons player +
director smoke test passes, `docs/scripting-languages.md` updated (engine row,
sigil, compile switch, binary cost, status → "shipping"), snowgoons reference
scripts added to the doc.

---

## Pending engines

### 1. Lua fixes (#1–#6) — `2026-04-15-lua-engine-fixes.md`

No new vendor. All changes in `scripting_stub.cc` (`lua_engine` namespace).

| Fix | Risk | Effort |
|-----|------|--------|
| #4 Gate debug `fprintf` behind `WF_SCRIPT_DEBUG` | zero | 5 min |
| #5 Sandbox stdlib (remove `io`/`os` from `luaL_openlibs`) | zero | 15 min |
| #1 Script compilation cache (`luaL_ref` + `unordered_map`) | medium | 1 h |
| #2 Per-actor environment tables | medium | 2 h |
| #3 Fennel pre-compilation cache (`fennel.compileString`) | medium | 1 h |
| #6 Multi-tick coroutine continuations (`lua_resume`) | high | half-day — land separately after #1–#5 |

Land order: #4+#5 → #1+#2+#3 together → #6 separately.

**Doc updates:** update the Lua + Fennel rows in `docs/scripting-languages.md`
to note the fixes landed (status footnote). No new sigil or switch.

---

### 2. JerryScript smoke test

Build path landed; vendor at `wftools/vendor/jerryscript-v3.0.0/`;
`scripting_jerryscript.cc` exists. Not yet smoke-tested.

Implementation steps:
1. Build: `WF_JS_ENGINE=jerryscript bash wftools/wf_engine/build_game.sh`
2. Run snowgoons player + director; fix any bugs
3. Verify behavior matches QuickJS

**Doc updates:**
- `docs/scripting-languages.md`: change JerryScript status from
  "landed (build path); not yet smoke-tested" → "shipping"
- Add JerryScript snowgoons player + director reference scripts to the doc

**Effort:** half-day.

---

### 3. Forth — `2026-04-14-forth-scripting-engine.md`

**All 6 vendor dirs already in tree.** Default engine: **zForth** (4 KB, MIT).

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

Implementation steps:
1. `wftools/wf_viewer/stubs/scripting_forth.hp` — shared plug ABI header
2. `scripting_zforth.cc` — zForth default backend
3. Dispatch block in `scripting_stub.cc` (`\` sigil, before `//`)
4. `WF_FORTH_ENGINE=zforth` + `WF_ENABLE_FORTH` in `build_game.sh`
5. Smoke test with zForth
6. `scripts/patch_snowgoons_forth.py` — patch snowgoons IFF with `\`-sigil scripts
7. Remaining backends: `scripting_{ficl,atlast,embed,libforth,pforth}.cc`
   (same ABI shape as zForth; one at a time)

**Doc updates:**
- `docs/scripting-languages.md`: add Forth section — one row per backend,
  sigil `\`, `WF_FORTH_ENGINE` / `WF_ENABLE_FORTH` switches, binary cost per
  engine, status
- Add snowgoons player + director examples in Forth (valid for all backends
  since they share the same word definitions)

**Effort:** 1–2 days.

---

### 4. Wren — `2026-04-14-wren-scripting-engine.md`

**Plan is stale** — references `LuaInterpreter::` methods; must be refreshed
to `ScriptRouter` plug ABI before implementation. Vendor (Wren 0.4.0
single-file amalgamation) not yet in tree.

Sigil: `//wren\n` (checked before generic `//` to avoid false dispatch to JS).

Implementation steps:
1. Refresh `2026-04-14-wren-scripting-engine.md` — replace all `LuaInterpreter::`
   references with `ScriptRouter` plug ABI
2. Vendor Wren 0.4.0 amalgamation under `wftools/vendor/wren-0.4.0/`
3. `scripting_wren.hp` + `scripting_wren.cc`
4. Dispatch block in `scripting_stub.cc` (before `//` JS check)
5. `WF_ENABLE_WREN=1` in `build_game.sh`
6. Smoke test
7. `scripts/patch_snowgoons_wren.py`

**Doc updates:**
- `docs/scripting-languages.md`: add Wren row — sigil `//wren\n`,
  `WF_ENABLE_WREN`, binary cost (~100 KB), status, foreign-class mailbox bridge
  note (`Env.read_mailbox` / `Env.write_mailbox`)
- Add snowgoons player + director examples in Wren

**Effort:** 1–2 days (includes plan refresh + vendor).

---

### 5. WAMR — `2026-04-14-wamr-dev-aot-ship.md`

Nothing in tree yet. Sigil: `#b64\n` (shared with wasm3; `WF_WASM_ENGINE`
switch selects between them). AOT path is a stretch goal.

Implementation steps (Phase 1 — interp only):
1. Vendor WAMR classic interpreter under `wftools/vendor/wamr-*/`
2. `wftools/wf_viewer/stubs/scripting_wamr.hp` + `scripting_wamr.cc`
3. Extend `WF_WASM_ENGINE=wamr` in `build_game.sh`
4. Re-author snowgoons WAT sources to use WAMR const-import host globals
   (`import "consts" "INDEXOF_INPUT" (global i32)` at instantiate time)
5. Recompile `.wasm` and re-patch snowgoons IFF via `scripts/patch_snowgoons_wasm.py`
6. Smoke test

**Doc updates:**
- `docs/scripting-languages.md`: add WAMR row — `WF_WASM_ENGINE=wamr`,
  binary cost, status, note that WAMR supports const-import globals (unlike
  wasm3 which requires baked literals)
- Update wasm3 row to clarify it remains as `WF_WASM_ENGINE=wasm3`

**Effort:** 2–3 days (largest lift).

---

## Full dispatch order after Phase D

```
1. `\`        → Forth     (if WF_ENABLE_FORTH)
2. `//wren\n` → Wren      (if WF_ENABLE_WREN)
3. `//`       → JS        (QuickJS or JerryScript, if WF_WITH_JS)
4. `#b64\n`   → Wasm      (wasm3 or WAMR, if WF_WITH_WASM)
5. `;`        → Fennel    (inside Lua, if WF_ENABLE_FENNEL)
6. fallthrough → Lua
```

---

## Recommended implementation order

1. **Lua fixes #4+#5** — zero risk; 20 min total
2. **JerryScript smoke test** — closes out the JS chapter; half-day
3. **Lua fixes #1–#3** — hardening pass; land together
4. **Forth (zForth first)** — vendors in tree, plan clean; 1–2 days
5. **Wren** — after plan refresh + vendor; 1–2 days
6. **WAMR** — last; largest lift; 2–3 days
7. **Lua fix #6** — separate, after everything else stable

---

## Critical files

| Path | Role | Status |
|------|------|--------|
| `wftools/wf_viewer/stubs/scripting_stub.cc` | Dispatch + `lua_engine` | exists |
| `wftools/wf_viewer/stubs/scripting_js.hp` | Plug ABI template | exists |
| `wftools/wf_viewer/stubs/scripting_jerryscript.cc` | JerryScript impl | exists, untested |
| `wftools/vendor/jerryscript-v3.0.0/` | JerryScript vendor | exists |
| `wftools/vendor/zforth-41db72d1/` (+ 5 others) | Forth vendors | exists |
| `wftools/wf_engine/build_game.sh` | Build flags | exists |
| `docs/scripting-languages.md` | **Updated for every engine that lands** | exists |
| `2026-04-14-wren-scripting-engine.md` | **Needs plan refresh before impl** | stale |
