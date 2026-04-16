# Plan: Optional QuickJS / JerryScript scripting engines

**Date:** 2026-04-14
**Status:** landed 2026-04-14 (QuickJS v0.14.0, JerryScript v3.0.0). The
plug is being renamed from the free-function `JsRuntimeInit / JsRunScript
/ JsAddConstantArray / JsRuntimeShutdown` shape into a `js_engine`
namespace (`Init / RunScript / AddConstantArray / DeleteConstantArray /
Shutdown`) as part of the
`docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md` sweep, to
match `lua_engine` and every engine that comes after. Other deviations
from the as-designed plan are captured inline below under *"As built:"* call-outs.
**Depends on:** Lua spike (landed); `docs/plans/2026-04-14-fennel-on-lua.md` (concurrent, owns Lua vendoring).
**Source investigation:** `docs/investigations/2026-04-14-scripting-language-replacement.md`

**Framing note (clarification, 2026-04-14):** an earlier draft of this
plan described JS as plugging into an always-on Lua host. That was wrong.
Every scripting engine (Lua, Fennel, QuickJS, JerryScript, wasm3) is an
independent compile-time opt-in. A build may ship **JS-only** (no Lua,
no Fennel), **wasm3-only**, **Lua-only**, or any combination. Fennel is
the sole exception: it compiles to Lua, so `WF_ENABLE_FENNEL=1` requires
Lua to also be compiled in. Below, phrases like "today's Lua-only build"
describe today's default configuration, not a permanent prerequisite.

## Context

Lua 5.4 is the default engine **in today's build**; the Lua spike (landed)
and the Fennel plan cover its own vendoring and composition. **This plan
is strictly about adding JavaScript as an independent, opt-in engine.**
Two JS runtimes were called out in the investigation as the strongest JS
candidates:

- **QuickJS** — ~500–700 KB code, up to ~1 MB heap, MIT, modern ES2020.
- **JerryScript** — ~60–100 KB code, ~40–80 KB baseline, Apache-2.0, smallest serious JS engine.

The user's constraints for this plan:

1. **Compile-time language subset.** A game build selects 1..N languages from the menu `{lua, fennel-on-lua, javascript}`. Lua/Fennel is independently on/off from JS; the two dimensions don't interact. *Multiple implementations of the same language are forbidden* — so within "javascript", the choice is `none | quickjs | jerryscript`, never both.
2. **No runtime filesystem** (CD / console target). Everything statically linked, no `dlopen`, no `fopen` of script assets — scripts live only inside IFF.
3. **Zero footprint when a language isn't selected.** If JS is off: no JS sources compile, no JS-only constant tables, no JS chunks left in shipped IFF. Binary/asset delta vs. the Lua-only default is zero. The symmetric rule holds the other way: a JS-only build omits all Lua sources and link deps.

Every engine works independently of every other (modulo Fennel→Lua). A JS-only build has no Lua, no Fennel, no wasm3 — just JS.

**Supersedes** the investigation's §"Multiple languages per game?" (l. 914–933), which landed at *"one language per game is almost certainly the right ceiling."* That verdict is revised: compile-time 1..N subset with sigil dispatch, zero-footprint for unselected languages. The original costs (binary size, mental tax, toolchain fragmentation) are eaten intentionally; the zero-footprint guarantee caps the binary-size cost.

Valid matrix (this plan only adds the right-hand column):

| Lua   | Fennel | JS engine      | Result                             |
|-------|--------|----------------|------------------------------------|
| off   | off    | none           | NullInterpreter only (scriptless)  |
| on    | off    | none           | **today's build**                  |
| on    | on     | none           | Fennel plan                        |
| on    | off    | quickjs        | new                                |
| on    | on     | quickjs        | new                                |
| on    | off    | jerryscript    | new                                |
| on    | on     | jerryscript    | new                                |
| off   | —      | quickjs        | new, JS-only game                  |
| off   | —      | jerryscript    | new, JS-only game                  |

## Approach

### 1. Compile-time switches

`engine/build_game.sh` grows two orthogonal selectors (Lua/Fennel toggles belong to their own plans; shown here for completeness):

```bash
WF_JS_ENGINE="${WF_JS_ENGINE:-none}"   # none | quickjs | jerryscript
# (Lua/Fennel owned by their plans; expected values on|off, default on for Lua)
```

`WF_JS_ENGINE` is validated against the three literal values — a mistyped "quick" or "both" fails the build with a clear message, closing the "two JS engines at once" footgun. The selected value becomes `-DWF_JS_ENGINE_NONE`, `-DWF_JS_ENGINE_QUICKJS`, or `-DWF_JS_ENGINE_JERRYSCRIPT` exported to all TUs. JS-off and Lua-off are independent: if both dimensions are off you get a scriptless NullInterpreter build.

### 2. Extensible per-script dispatch via sigil table

Today `LuaInterpreter::RunScript` receives a raw source string. The Fennel plan introduces sigil-sniffing (`;` = Fennel). We're going to add more languages after JS, so bake in an extensible registry now rather than hand-rolling another `if/else` arm per language.

Introduce `scripting_dispatch.cc` + `scripting_dispatch.hp`. It owns a small static array, one entry per compiled-in language:

```cpp
struct LangHandler {
    const char* sigil;                                       // e.g. "//", ";", ...
    size_t      sigilLen;
    Scalar    (*run)(const char* src, int objectIndex);      // engine entry point
};

Scalar DispatchScript(const char* src, int objectIndex);     // the only entry from game code
```

Each engine TU registers itself **at compile time** via a `LANG_HANDLER(...)` macro that appends to the table using the link-time-ordered-init trick or (simpler) a central `dispatch_table.inc` `#include` guarded by engine `#define`s:

```cpp
// dispatch_table.inc
#ifdef WF_JS_ENGINE_QUICKJS
    LANG_HANDLER("//", RunQuickJsScript)
#endif
#ifdef WF_JS_ENGINE_JERRYSCRIPT
    LANG_HANDLER("//", RunJerryScript)
#endif
#ifdef WF_WITH_FENNEL
    LANG_HANDLER(";",  RunFennelScript)
#endif
#ifdef WF_FUTURE_LANG_XYZ              // placeholder for the language-after-JS
    LANG_HANDLER("…",  RunXyzScript)
#endif
#ifdef WF_ENABLE_LUA
    // Lua is the fallthrough when compiled in — no sigil, matched last.
#endif
```

Routing rule: skip leading whitespace, match the longest sigil; if nothing matches, fall through to the build's **fallthrough engine**. Today the fallthrough is Lua (when compiled in); if Lua is *not* compiled in, the build needs a `WF_DEFAULT_ENGINE` knob (follow-up) to pick another fallthrough, or the dispatcher logs and no-ops unsigilled scripts. Unselected languages contribute **no entry** to the table — the branch doesn't exist in the binary. Sigils must be Lua-syntax errors *only when Lua is compiled in*; with Lua off they just need to be distinct from each other.

**As built (JS landing, 2026-04-14):** the dispatch registry was *not* extracted into a separate `scripting_dispatch.{hp,cc}` for the JS landing — there are still only two non-Lua sigils (`;` for Fennel, `//` for JS), and the existing inline `#ifdef` pattern in `scripting_stub.cc::LuaInterpreter::RunScript` carried them. A new header `wftools/engine/stubs/scripting_js.hp` declares the JS plug ABI (`JsRuntimeInit`, `JsAddConstantArray`, `JsRunScript`, …) and is included by `scripting_stub.cc` under `#ifdef WF_WITH_JS`.

**As built (ScriptRouter refactor, 2026-04-15):** `LuaInterpreter` is gone. `scripting_stub.cc` now contains a file-scope `lua_engine` namespace (pure Lua + optional Fennel sub-dispatch, using module-level globals instead of member variables) and a `ScriptRouter : public ScriptInterpreter` class that owns all engine lifecycles as peers. `ScriptInterpreterFactory` returns a `ScriptRouter`. The sigil dispatch, `AddConstantArray` broadcast, and shutdown sequencing all live in `ScriptRouter`; no engine initialises any other. Fennel remains a sub-dispatch within `lua_engine` (it compiles to Lua and shares the `lua_State`), so it does not appear at the router level.

One `cd.iff` can therefore mix Lua, Fennel, JS, and whatever-comes-next; language is a property of the script body, and the dispatch cost is a short `for`-loop over the compiled-in subset.

**Sigil registry.** Sigils must be Lua-syntax errors so the fallthrough never misroutes real Lua. Reserve them up front:

| Sigil | Language        | Status |
|-------|-----------------|--------|
| `;`   | Fennel (Lisp)   | taken by Fennel plan |
| `//`  | JavaScript      | this plan |
| `#`   | WebAssembly     | **reserved** — confirmed as the next language; likely wasm3 or WAMR hosting AssemblyScript / Rust / C (see investigation §Tier 7 WebAssembly, l. 441–681) |
| `@`   | *reserved*      | available for future |

Claim one per language as it's added; document the reservation in `scripting_dispatch.hp`.

### 3. JS engine implementation

New files, each compiled **only** when its flag is set:

- `wftools/engine/stubs/scripting_quickjs.cc` — QuickJS implementation.
- `wftools/engine/stubs/scripting_jerryscript.cc` — JerryScript implementation.

Each exposes a single function (no new class, no factory re-plumbing):

```cpp
// Called from LuaInterpreter's dispatch when sigil == "//".
Scalar RunJsScript(MailboxesManager& mgr, const char* src, int objectIndex);
// Lifetime helpers — called from LuaInterpreter ctor / dtor.
void   JsRuntimeInit(MailboxesManager& mgr);
void   JsRuntimeShutdown();
```

`scripting_lua.cc` calls these through a thin header guarded by `#if !defined(WF_JS_ENGINE_NONE)`; under `none` the header provides inline no-op stubs, so there's no link-time dependency at all.

The JS runtime registers the same callbacks Lua has — `read_mailbox`, `write_mailbox` — and the same `INDEXOF_*` / `JOYSTICK_BUTTON_*` integer constants as JS globals. Constant source of truth is the existing tables in `scripting_common.cc` (or the Lua-side file post-refactor); the JS TU includes that header and walks the same arrays.

**Cross-language parity (TODO).** Before any more languages land — and ideally before this plan's implementation is merged — audit the predefined constant and callback surface across every compiled-in engine. Same names, same values, same calling convention in Lua, Fennel (inherits Lua), QuickJS, JerryScript, and the eventual WASM host. Sources of truth:

- `mailbox/mailbox.inc` — `INDEXOF_*` via macro expansion (already canonical).
- `scripting_common.cc` — `joystickArray[]` for `JOYSTICK_BUTTON_*` (hardcoded; needs a better home).
- `read_mailbox` / `write_mailbox` signatures.
- Future: the typed-accessor set flagged in the investigation's §"What the engine SDK should provide" (l. 877–895) — `read_actor`, `read_fixed`, `read_color`, `read_flags`, `read_bool`, `read_int`. These don't exist in Lua yet, but when they do, every other engine must grow them in lockstep.

Write one canonical list (header or IDL-ish `.inc` file) and generate each engine's bindings from it rather than maintaining parallel hand-written tables. Failure mode to avoid: Lua gets `read_actor` shipped in a sprint, JS still only has `read_mailbox`, and level scripts silently diverge by language.

Specifics:

- **QuickJS**: `JS_NewRuntime` / `JS_NewContext`; `JS_NewCFunctionData` binds callbacks (pass `this` via the data array — no statics); `JS_SetPropertyStr` + `JS_NewInt32` for constants; `JS_Eval(..., JS_EVAL_TYPE_GLOBAL)`; `JS_IsException` / `JS_GetException` for error logging; `JS_ToFloat64`; `JS_FreeValue` / `JS_FreeContext` / `JS_FreeRuntime`.
- **JerryScript**: `jerry_init(JERRY_INIT_EMPTY)`; `jerry_create_external_function`; `jerry_set_object_native_pointer(global, this, &native_info)` so callbacks fetch the mailbox manager; `jerry_set_property` + `jerry_create_number` for constants; `jerry_eval(src, len, JERRY_PARSE_NO_OPTS)`; `jerry_value_is_error`, `jerry_value_to_number` / `jerry_get_number_value`; `jerry_release_value`; `jerry_cleanup`. Single-context per init is fine.

### 4. Vendoring (no filesystem at runtime)

Matches the `engine/vendor/<name>-<version>/` convention from the Fennel plan; hashes appended to `engine/vendor/README.md`.

```
engine/vendor/
  quickjs-<version>/     quickjs.{c,h} cutils.{c,h}
                         libregexp.{c,h} libunicode.{c,h}
                         libbf.{c,h} quickjs-atom.h
                         quickjs-opcode.h libunicode-table.h
  jerryscript-<version>/ (full upstream tree + build/ populated on first build)
```

Both are statically linked — no `.so`, no `dlopen`, no filesystem touch at runtime. Fine under a CD / embedded target.

Build-script branches:

- `WF_JS_ENGINE=none` — nothing from `engine/vendor/` compiles; `scripting_quickjs.cc` / `scripting_jerryscript.cc` are skipped; no JS link deps.
- `WF_JS_ENGINE=quickjs` — compile `scripting_quickjs.cc` + `quickjs-<version>/{quickjs,cutils,libregexp,libunicode,libbf}.c` with `-DCONFIG_VERSION='"<version>"' -Wno-sign-compare -Wno-unused-parameter`.
- `WF_JS_ENGINE=jerryscript` — size-optimised profile (see below). One-shot CMake into `engine/vendor/jerryscript-<version>/build/` (idempotent: skip if `libjerry-core.a` is fresher than sources):

  ```bash
  cmake -S engine/vendor/jerryscript-<version> \
        -B engine/vendor/jerryscript-<version>/build \
    -DJERRY_CMDLINE=OFF \
    -DJERRY_PROFILE=wf-minimal        `# custom profile file, see below` \
    -DJERRY_ERROR_MESSAGES=OFF \
    -DJERRY_LINE_INFO=OFF \
    -DJERRY_LOGGING=OFF \
    -DJERRY_DEBUGGER=OFF \
    -DJERRY_MEM_STATS=OFF \
    -DJERRY_PARSER_DUMP_BYTE_CODE=OFF \
    -DJERRY_SNAPSHOT_EXEC=OFF \
    -DJERRY_SNAPSHOT_SAVE=OFF \
    -DJERRY_VM_HALT=OFF \
    -DJERRY_VM_THROW=OFF \
    -DENABLE_LTO=ON -DENABLE_STRIP=ON
  cmake --build engine/vendor/jerryscript-<version>/build
  ```

  Compile `scripting_jerryscript.cc` with the jerry-core/jerry-port includes. Link `libjerry-core.a libjerry-port-default.a`.

**Profile choice — "gameplay-minimum" (`wf-minimal.profile`).** JerryScript ships three stock profiles: `es5.1` (default, ~100 KB), `es.next` (~180 KB), `minimal` (~60 KB, strips *everything* non-VM). We check in a fourth, `engine/vendor/jerryscript-<version>/jerry-core/profiles/wf-minimal.profile`, derived from stock `minimal` and re-enabling exactly the builtins gameplay scripts cannot reasonably live without.

Enabled in `wf-minimal` on top of stock `minimal`:

- `JERRY_BUILTIN_ARRAY` — array methods (`push`, `pop`, `indexOf`, `forEach`, `map`); WF scripts will keep lists of actors/triggers/choices, and forcing every list op through host callbacks poisons authoring.
- `JERRY_BUILTIN_STRING` — string methods (`split`, `slice`, `indexOf`, `replace`); dialogue and debug logging are real uses.
- `JERRY_BUILTIN_NUMBER` — `Number.parseInt`/`parseFloat`/`toFixed`; required for any numeric parsing of mailbox/config values.
- `JERRY_BUILTIN_MATH` — `Math.floor`/`sqrt`/`min`/`max`/`abs`/`PI`; fixed-point and geometry math is inescapable in gameplay code.
- `JERRY_BUILTIN_ERRORS` — `Error` / `TypeError` / `RangeError` constructors; scripts need to throw structured failures the host can pretty-print.
- `JERRY_BUILTIN_BOOLEAN` — Boolean wrapper; trivial weight, avoids oddities around `new Boolean()`.
- `JERRY_BUILTIN_GLOBAL_THIS` — `globalThis` binding; cheap, makes the constant-registration path from our side uniform.

**Deliberately left off** (and why):

- `JERRY_ESNEXT` — the whole ES2015+ surface (classes, `let`/`const`, arrows, templates, destructuring, `Promise`, `async`/`await`, `Map`/`Set`/`Symbol`, modules). Adds ~80 KB and is *exactly* what someone picking QuickJS is paying for. Keeping it off here is the flavor's reason to exist.
- `JERRY_BUILTIN_JSON` — no inline data tables (~5 KB). If needed later, inline data becomes a host-side deserializer.
- `JERRY_BUILTIN_REGEXP` — regex is ~20 KB and gameplay code almost never needs it; string `indexOf`/`slice` cover the 80% case.
- `JERRY_BUILTIN_DATE` — timers are host-owned (frame counters, `read_mailbox(INDEXOF_FRAME_TIME)`), not `new Date()`.
- `JERRY_BUILTIN_BIGINT` / `DATAVIEW` / `TYPEDARRAY` / `PROMISE` / `PROXY` / `REFLECT` / `MAP`/`SET` / `WEAKREF` / `SYMBOL` / `REALMS` — all gated on `JERRY_ESNEXT`; moot with ESNEXT off.
- `JERRY_MODULE_SYSTEM` — ESNEXT-only in JerryScript, and scripts live inline in IFF not on a filesystem; modules would be a fake convenience.
- `JERRY_ERROR_MESSAGES` / `JERRY_LINE_INFO` / `JERRY_LOGGING` / `JERRY_DEBUGGER` — pure shipping-build flags. Error messages become numeric codes; line numbers are absent. Acceptable because the JerryScript flavor is the ship-size flavor. Debug-build variant (see verification) turns `JERRY_ERROR_MESSAGES` + `JERRY_LINE_INFO` back on to keep authors sane during development; shipping flips them off.

**Target size:** ~80–90 KB library + bindings, vs. ~60 KB for pure `minimal` and ~100 KB for stock `es5.1`. The ~20 KB premium over pure `minimal` buys back the authoring floor (`Array`, `Math`, `String`, `Error`) without inviting the ES.NEXT cliff.

**What this profile does *not* buy you** — spelled out so the trade is explicit and future-me doesn't misremember:

| Feature | Status | Script-author consequence |
|---------|--------|---------------------------|
| `let` / `const`, arrow fns, classes, templates, destructuring | **off** | Author in ES5.1 syntax: `var`, `function`, string concat with `+`, manual object literals. |
| `Promise` / `async`/`await` | **off** | Sequencing is callback-based or frame-polled via mailboxes. |
| `Map` / `Set` | **off** | Use plain objects (`{}`) as string-keyed maps; duplicates acceptable for WF's scale. |
| `JSON` | **off** | No inline data tables; host exposes a decoder or ship data as separate IFF chunks. |
| `RegExp` | **off** | String matching via `indexOf` / manual walk. |
| `Proxy` / `Reflect` | **off** | Typed-mailbox wrappers are hand-written getter/setter objects (see cross-language parity TODO in §3). |
| `?.` / `??` | **off** | `x && x.y` and `x != null ? x : default` patterns. |

**If a specific game needs even smaller (~60 KB):** follow-up `WF_JS_ENGINE=jerryscript-nano` using stock `minimal`, host-side everything. Not in this plan.

**If a specific game needs ES2015+:** the answer is `WF_JS_ENGINE=quickjs`. That's the whole reason both engines coexist.

### 5. Asset / CD footprint when JS engine is `none`

When JS is off, a CD shipped with that build has zero JS weight anywhere. Rules:

- **Binary**: JS TUs and vendor sources don't compile → zero code. The inline no-op stubs in the dispatch header are a single `if-constexpr`-ish branch that compiles out completely.
- **Constants**: `INDEXOF_*` / `JOYSTICK_BUTTON_*` tables are shared across every compiled-in engine; no JS-only copies. Zero delta.
- **IFF assets**: a `none`-JS build does not ship JS script bodies in `cd.iff`. Enforce this with an IFF pre-flight check in the build (or at game boot, in debug builds) that scans OAS script fields and fails if any begin with `//` when `WF_JS_ENGINE_NONE` is defined. Keeps stray JS scripts out of the disc image. The same per-sigil check applies symmetrically — a Lua-off build should reject sigil-less scripts, a Fennel-off build should reject `;`-prefixed scripts, and so on.

Net effect: a JS-off build has zero JS delta vs. the same configuration without this plan.

### 6. Authoring JS scripts in the IFF

IFF OAS script fields are already plain-text bodies. To add a JS script, author it with `// ` as the first line:

```javascript
// snowgoons player
write_mailbox(INDEXOF_INPUT, read_mailbox(INDEXOF_HARDWARE_JOYSTICK1_RAW));
```

No parallel `cd.iff` needed. A Lua→JS converter is follow-up work (mirroring `scripts/tcl_to_lua_in_dump.py`), but for the JS spike we hand-port one snowgoons script and patch it in via the existing byte-preserving patcher.

## Critical files

Modify:
- `engine/build_game.sh` — add `WF_JS_ENGINE` selection, conditional compile/link.
- `wftools/engine/stubs/scripting_lua.cc` (or wherever sigil sniff lives after the Fennel plan) — add `//` branch that calls `RunJsScript` when any JS engine is compiled, else falls through.

Create:
- `wftools/engine/stubs/scripting_dispatch.{hp,cc}` — the sigil registry and `DispatchScript` entry point. Future languages add themselves by editing `dispatch_table.inc`, nothing else.
- `wftools/engine/stubs/scripting_quickjs.cc` — QuickJS implementation, contributes `RunQuickJsScript` + lifetime hooks.
- `wftools/engine/stubs/scripting_jerryscript.cc` — JerryScript implementation, contributes `RunJerryScript` + lifetime hooks.
- `engine/vendor/quickjs-<version>/` — vendored source. *As built:* `quickjs-v0.14.0` (quickjs-ng fork). The plan's `cutils.{c,h}` and `libbf.{c,h}` lists are stale for this fork — `cutils.h` is header-only (no `.c`) and `libbf` was dropped from quickjs-ng. Core link set is `quickjs.c libregexp.c libunicode.c dtoa.c`.
- `engine/vendor/jerryscript-<version>/` — vendored source. *As built:* `jerryscript-v3.0.0`. CMake build is run by `build_game.sh` into `jerry-core/`'s sibling `build/` directory; `libjerry-core.a` + `libjerry-port.a` link in. The build also keeps `JERRY_ERROR_MESSAGES` + `JERRY_LINE_INFO` on by default — this is the dev-target build, the shipping toggle (§ Follow-ups) is still TODO.
- `engine/vendor/jerryscript-<version>/jerry-core/profiles/wf-minimal.profile` — new JerryScript feature profile (stock `minimal` + `ARRAY`/`STRING`/`NUMBER`/`MATH`/`ERRORS`/`BOOLEAN`/`GLOBAL_THIS`). Rationale spelled out in §4.
- `engine/vendor/README.md` — append QuickJS + JerryScript versions and SHA256s (file created by Fennel plan).
- Optional: `scripts/check_iff_no_js.py` — fails if any OAS script body starts with `//` (used by the `none` build for asset-footprint verification). *As built:* deferred — no JS scripts have been authored into `cd.iff` yet, so the asset check has nothing to fail on. Add when the first JS script lands.

Reuse:
- `ScriptInterpreter` ABI in `wfsource/source/scripting/scriptinterpreter.hp:42` — unchanged.
- `mailboxIndexArray` / `joystickArray` from `scripting_stub.cc` (or its post-split home) — same tables feed JS globals.

## Verification

1. **Default build unchanged**:
   - `bash engine/build_game.sh` (no env var) → same `wf_game` as today's default (Lua on, JS off). Binary-size delta vs. main: 0 bytes (±link-order noise).
2. **QuickJS build (mixed with Lua)**:
   - `WF_JS_ENGINE=quickjs bash engine/build_game.sh` links clean.
   - Smoke test (debug-only, runs at first `RunScript`): `// return 1+2` → `3.0`; `// write_mailbox(0,42); read_mailbox(0)` → `42.0`.
   - Snowgoons end-to-end with the JS-ported player script: joystick moves character; camshot still works (director remains Lua).
3. **QuickJS-only build (no Lua)**:
   - `WF_ENABLE_LUA=0 WF_JS_ENGINE=quickjs bash engine/build_game.sh` links clean; no Lua link deps, no Lua TUs compiled.
   - Snowgoons with all scripts authored as JS (player + director both prefixed `//`): plays identically to the mixed build.
   - Sigil-less scripts in the iff fail the pre-flight check or no-op cleanly at runtime (choice deferred to the `WF_DEFAULT_ENGINE` follow-up).
4. **JerryScript builds**: same as QuickJS, with `WF_JS_ENGINE=jerryscript`.
5. **Mixed languages in one IFF**: patch the player script to JS, leave director as Lua (or Fennel if compiled in). Both run in the same level tick.
6. **Size deltas**: report stripped `wf_game` size for each mode. Targets: QuickJS ≈ +350 KB; JerryScript (`wf-minimal` profile) ≈ +80–90 KB (lib only) / ~+100 KB including bindings; `none` = 0 KB vs. today. A JS-only build subtracts the Lua lib (~150-200 KB) from the total; don't mistake that for a regression.
7. **Asset footprint**: run the asset check in a JS-off build against a JS-containing dev `cd.iff` and confirm it fails loudly; against the same-config-without-JS `cd.iff` it passes.

## Follow-ups (out of scope)

- **Update `docs/scripting-languages.md`** with the QuickJS port of every script in the snowgoons level — paired side-by-side with the existing Lua / Fennel rows so authors can see the same gameplay logic in all three languages. Source of truth is whatever `tcl_to_lua_in_dump.py` produces from the snowgoons IFF; convert each by hand (no `lua_to_js_in_dump.py` yet — see next bullet).
- `scripts/lua_to_js_in_dump.py` — bulk Lua→JS converter mirroring `tcl_to_lua_in_dump.py`.
- Wire selection into `Taskfile.yml` (`task build`, `task build:quickjs`, `task build:jerryscript`).
- **Debug vs. shipping JerryScript builds.** The `wf-minimal` profile turns off `JERRY_ERROR_MESSAGES` and `JERRY_LINE_INFO` because this flavor exists to be the smallest JS option. Add a `WF_JS_DEBUG_BUILD=1` toggle that flips those two flags back on (adds ~10–15 KB) so authors have readable stack traces during development; shipping builds stay lean.
- **`WF_JS_ENGINE=jerryscript-nano`** — pure stock `minimal` profile (~60 KB), with gameplay utilities host-side. Deferred until a specific game demands the extra ~20 KB.
- **WASM is next.** Add wasm3 (or WAMR) as the next dispatch registry entry under sigil `#`, with AssemblyScript / Rust / C as its source-language tier. Reuse the same mailbox + constants surface (audit item above); exploit WASM's determinism and sandboxing per investigation §Tier 7.
- **Mailbox / constants cross-language audit** (called out in §3 above) — not separable from this plan but tracked as a standing item until the canonical IDL exists.
