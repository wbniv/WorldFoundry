# Plan: encode scripting language in OAS/OAD; drop runtime sigil detection

**Date:** 2026-04-16
**Status:** planned

## Context

`ScriptRouter::RunScript` currently determines which scripting engine to invoke by
sniffing the leading byte(s) of the script body:

```
\       → Forth
//wren\n → Wren
//      → JS
#b64\n  → Wasm
;       → Fennel (inside lua_engine)
else    → Lua
```

This couples the language choice to the script text and makes it impossible to author
a plain Lua script that happens to start with `//`. It also means the engine must carry
dispatch logic that belongs in the authoring tool.

**Goal:** move the language tag out of the script body and into the OAD attribute that
describes the actor's script field. Drop sigil sniffing from `ScriptRouter` entirely.
The Blender plugin keeps autodetect as a UI convenience but writes an explicit language
value to the OAD — the runtime never guesses.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Where language lives | **New `int32 ScriptLanguage` field in `common.inc`** next to `Script` | OAD already carries per-field metadata; int32 dropmenu is the established pattern |
| Runtime dispatch | **Enum passed through `EvalScript` → `RunScript`** | No string sniff in the hot path |
| Sigil handling | **Strip sigils from existing scripts** | The corpus is small. Remove the leading sigil byte(s) from each script file after setting the explicit `ScriptLanguage` field in its OAD. Cleaner than leaving dead text. |
| Default for old OAD files | **0 = Lua** | Most existing scripts are Lua; the field is absent in old binary OADs, so the OAD reader returns 0 for unset int32 fields |
| Autodetect in plugin | **Keep as plugin-only UI hint** | Plugin reads the first line and pre-fills the dropdown; user can override. Autodetect value is never written to OAD — the plugin always writes an explicit language int. |
| `ScriptLanguage` enum values | 0 = `lua`, 1 = `fennel`, 2 = `wren`, 3 = `forth`, 4 = `js`, 5 = `wasm` | Lua=0 fixed (absent fields default correctly); Fennel paired next to Lua (same runtime); lightest-to-heaviest otherwise |

## OAS change

**File:** `wfsource/source/oas/common.inc` — the only hand-edited file in this subsystem.

Add **after** the existing `Script` XDATA entry (and before `ScriptControlsInput`):

```
TYPEENTRYINT32(Script Language,ScriptLanguage,0,5,0,"Lua|Fennel|Wren|Forth|JavaScript|WebAssembly",SHOW_AS_DROPMENU)
```

`common.ht` (the game-code struct header) and `common.pp` (the preprocessed C
source used to compile the binary `.oad`) are both **generated from `common.oas` +
`common.inc`** by `prep` / `oas2oad-rs`. They carry a "DO NOT MODIFY" banner.
After editing `common.inc`, rebuild with `oas2oad-rs` to regenerate them.

**Layout note:** placing `ScriptLanguage` after `Script` appends a new field at a
higher offset, so old binary IFF files (built before this change) simply return 0
for the absent field — which maps to Lua, the correct default. No level rebuild
required for existing levels to continue working.

## `EvalScript` / `RunScript` signature change

**File:** `wfsource/source/game/level.hp` / `level.cc`

```cpp
// Before:
void Level::EvalScript(const void* script, int objectIndex);

// After:
void Level::EvalScript(const void* script, int objectIndex, int language);
```

**File:** `wfsource/source/scripting/scriptinterpreter.hp`

```cpp
// Before:
virtual Scalar RunScript(const void* script, int objectIndex) = 0;

// After:
virtual Scalar RunScript(const void* script, int objectIndex, int language) = 0;
```

**Call site** in `actor.cc`:

```cpp
// Before:
theLevel->EvalScript(_nonStatPlat->_pScript, GetActorIndex());

// After:
theLevel->EvalScript(_nonStatPlat->_pScript, GetActorIndex(),
                     GetCommonBlockPtr()->ScriptLanguage);
```

The shell/SHELL script path in `level.cc` (line ~597) also calls `EvalScript`
directly — pass `0` (Lua) there since the shell script is always Lua.

## `ScriptRouter::RunScript` change

**File:** `wftools/wf_viewer/stubs/scripting_stub.cc`

Replace the sigil-sniff block with a language-enum dispatch:

```cpp
Scalar ScriptRouter::RunScript(const void* script, int objectIndex, int language)
{
    using RunFn = float(*)(const char*, int);
    static const RunFn kDispatch[6] = {
#ifdef WF_ENABLE_LUA
        /* 0 lua    */ lua_engine::RunScript,
#else
        /* 0 lua    */ nullptr,
#endif
#ifdef WF_ENABLE_FENNEL
        /* 1 fennel */ fennel_engine::RunScript,
#else
        /* 1 fennel */ nullptr,
#endif
#ifdef WF_ENABLE_WREN
        /* 2 wren   */ wren_engine::RunScript,
#else
        /* 2 wren   */ nullptr,
#endif
#ifdef WF_ENABLE_FORTH
        /* 3 forth  */ forth_engine::RunScript,
#else
        /* 3 forth  */ nullptr,
#endif
#if defined(WF_JS_ENGINE_QUICKJS) || defined(WF_JS_ENGINE_JERRYSCRIPT)
        /* 4 js     */ js_engine::RunScript,
#else
        /* 4 js     */ nullptr,
#endif
#if defined(WF_WASM_ENGINE_WAMR) || defined(WF_WASM_ENGINE_WASM3)
        /* 5 wasm   */ wasm3_engine::RunScript,
#else
        /* 5 wasm   */ nullptr,
#endif
    };
    RangeCheck(0, language, 6);
    AssertMsg(kDispatch[language] != nullptr, "no dispatch entry for language " << language);
    return Scalar::FromFloat(kDispatch[language](static_cast<const char*>(script), objectIndex));
}
```

Every `RunScript` has exactly the signature `float(const char*, int)` — the function name
decays directly to a `RunFn` pointer; no lambda wrapper needed.

`fennel_engine::RunScript` is a thin wrapper that uses the Lua VM internally — the
`gFennelEvalRef` path is unchanged, just reached via `fennel_engine` rather than a
boolean flag passed into `lua_engine`.

The `NullInterpreter` stub also grows the `language` parameter (ignored).

## Blender plugin change

**File:** `wf_blender/` (wherever the common block panel is rendered)

1. Add a `ScriptLanguage` integer property bound to `object["ScriptLanguage"]`
   (or whatever the OAD field accessor is), displayed as an `EnumProperty` with
   items `[("lua",…,0), ("fennel",…,1), ("wren",…,2), ("forth",…,3), ("js",…,4), ("wasm",…,5)]`.
2. On script-text change (or on a "Detect" button press): scan the **full script text**
   and pre-fill the dropdown by looking for unambiguous markers anywhere in the body:
   - Contains base64-only characters (no spaces/keywords) → WebAssembly
   - Contains `(defn`, `(let [`, `(fn `, `(var ` → Fennel (Lisp s-expressions)
   - Contains `class `, `Fiber.`, `.new()` → Wren
   - Contains `: ` word defs, `VARIABLE`, `CREATE` in all-caps → Forth
   - Contains `function `, `const `, `let `, `=>` → JavaScript
   - else → Lua (fallthrough default)
3. User can always override the auto-filled value before export.
4. On export, Blender always writes a concrete integer (0–5) to the OAD field.
   There is no "auto" value; the runtime never has to guess.
5. After migration: run each level and confirm behaviour is identical to the pre-change sigil-based run.

## Migration

Existing `.iff` and `cd.iff` files built before this change have no `ScriptLanguage`
field in the OAD binary. The CommonBlock reader returns `0` for any unset int32 field,
which maps to Lua — correct for all existing Lua scripts.

The entire migration can be driven as a headless Blender Python script
(`blender --background --python migrate_script_language.py`). The exporter is
schema-driven, so once `ScriptLanguage` is in the rebuilt OAD it is exported
automatically. The migration script needs to:

1. Iterate all objects with a `Script` property.
2. Detect language by scanning the full script text (same heuristics as the UI autodetect).
3. Set `wf_ScriptLanguage` to the detected enum value.
4. Strip the leading sigil from the script text.
5. Re-export each affected level.

Scripts without a sigil (plain Lua) are unaffected. The corpus is small; this is a
one-time pass, not an ongoing concern.

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/oas/common.inc` | Add `TYPEENTRYINT32(Script Language, …)` after `Script` |
| `wfsource/source/oas/common.ht` | **Generated** — rebuilt by `oas2oad-rs`; do not hand-edit |
| `wfsource/source/oas/common.pp` | **Generated** — rebuilt by `oas2oad-rs`; do not hand-edit |
| `wfsource/source/game/level.hp` | Add `language` param to `EvalScript` |
| `wfsource/source/game/level.cc` | Thread `language` through; shell script passes 0 |
| `wfsource/source/game/actor.cc` | Pass `GetCommonBlockPtr()->ScriptLanguage` |
| `wfsource/source/scripting/scriptinterpreter.hp` | Add `language` param to `RunScript` |
| `wftools/wf_viewer/stubs/scripting_stub.cc` | Replace sigil sniff with enum dispatch |
| `wf_blender/` | Add `ScriptLanguage` enum dropdown + full-text autodetect hint |

## Verification

1. Default build: Lua-only level (`ScriptLanguage=0`) runs snowgoons identically.
2. Each compiled-in engine: set `ScriptLanguage=N` in snowgoons; confirm player + director
   behaviour matches the pre-change run.
3. Old IFF (no `ScriptLanguage` field): boots and runs; `ScriptLanguage` reads 0 (Lua) — correct for all existing Lua scripts.
4. Blender autodetect: open a script with Fennel syntax; confirm dropdown pre-fills to Fennel.
5. `grep -n 'p\[0\]\|sigil\|\*p ==' wftools/wf_viewer/stubs/scripting_stub.cc` returns nothing.

## Follow-ups

- `tool.oas` has a separate `Activation Script` XDATA field — add `Activation Script Language`
  there too, with the same enum.
- `levelobj.oas` has `Startup Script` (via `DEFAULT_SCRIPTNAME`) — covered by `common.inc`.
- The Blender exporter should guard against writing a sigil that was accidentally left
  in the script text after the migration pass (warn or strip on export).
- **Tool class rearchitect** — `tool.cc` / `toolshld.cc` / `toolngun.cc` currently pass `language=0`
  hardcoded for `ActivationScript`. These classes share a lot of structure; consider consolidating
  them (and `ActivationScriptLanguage`) as part of the `tool.oas` follow-up rather than patching
  each one individually.
