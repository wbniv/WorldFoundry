# JerryScript v3.0.0 — GCC 14 Build Fixes

**Date:** 2026-04-15  
**Vendor path:** `engine/vendor/jerryscript-v3.0.0/`  
**GCC version:** GCC 14 (Ubuntu 24.04 default)  
**Build profile:** `wf-minimal.profile` (no BigInt, no Realms, no debugger,
no RegExp, no TypedArray, no Container builtins)

---

## Background

JerryScript v3.0.0 was released in 2023 against GCC ≤ 12. GCC 14 tightened
several diagnostics to errors that were previously warnings or silent.

The `wf-minimal` profile (`JERRY_BUILTINS=0`, with a small allow-list of
essential builtins) triggers **seven distinct build failures** that are all
rooted in one systemic problem: **JerryScript's upstream CI always builds with
all features enabled**. The disabled-feature code paths were never compiled
with GCC 14, so the bugs accumulated unseen.

### Why the upstream project doesn't see this

JerryScript v3.0.0 was tested on GCC 9-10 (Ubuntu 20.04). Under those
compilers, most of these diagnostics were warnings, not errors, or were
suppressed. The project has had essentially no commits since mid-2023 and
appears to be in maintenance-only mode. No upstream profile disables
`JERRY_BUILTINS` the way our `wf-minimal` profile does.

---

## All seven bugs and their fixes

### Bug 1 — `ecma_op_same_value_zero` declaration guarded

**Files:** `jerry-core/ecma/operations/ecma-conversion.h` (declaration),
`jerry-core/ecma/operations/ecma-conversion.c` (definition)  
**Symptom:** `error: implicit declaration of function 'ecma_op_same_value_zero'`

**Root cause:** Both the declaration (in `.h`) and definition (in `.c`) were
guarded by `#if JERRY_BUILTIN_CONTAINER`. But `Array.prototype.includes`
(`ecma-builtin-array-prototype.c`) calls `ecma_op_same_value_zero`
unconditionally.

**Fix:**  
- `ecma-conversion.h`: remove `#if JERRY_BUILTIN_CONTAINER` guard from the
  declaration  
- `ecma-conversion.c`: remove `#if JERRY_BUILTIN_CONTAINER` guard from the
  definition

---

### Bug 2 — Pointer/integer type mismatch in `JERRY_ASSERT`

**File:** `jerry-core/vm/opcodes.c`,
`opfunc_lexical_scope_has_restricted_binding`, `!JERRY_BUILTIN_REALMS` branch  
**Symptom:** `error: comparison between pointer and integer`

**Root cause:** `frame_ctx_p->this_binding` is `ecma_value_t` (tagged
integer). `ecma_builtin_get_global()` returns `ecma_object_t*` (pointer).
GCC 14 errors on the implicit pointer↔integer comparison. The
`JERRY_BUILTIN_REALMS` branch correctly compares two `ecma_value_t` fields.

**Fix:**
```c
// BEFORE:
JERRY_ASSERT (frame_ctx_p->this_binding == ecma_builtin_get_global ());
// AFTER:
JERRY_ASSERT (frame_ctx_p->this_binding == ecma_make_object_value (ecma_builtin_get_global ()));
```

---

### Bug 3 — Forward use of undeclared variable `global_obj_p`

**File:** `jerry-core/vm/opcodes.c`, same function as Bug 2  
**Symptom:** `error: 'global_obj_p' undeclared`

**Root cause:** `global_obj_p` is declared *eight lines later* in the same
function. Used before declaration in the `!JERRY_BUILTIN_REALMS` branch.
The `JERRY_BUILTIN_REALMS` branch correctly uses
`(ecma_object_t *) JERRY_CONTEXT (global_object_p)`.

**Fix:**
```c
// BEFORE:
ecma_object_t *const global_scope_p = ecma_get_global_scope (global_obj_p);
// AFTER:
ecma_object_t *const global_scope_p = ecma_get_global_scope (ecma_builtin_get_global ());
```

---

### Bug 4 — Unused parameter `cp` in `lit_char_fold_to_lower/upper`

**File:** `jerry-core/lit/lit-char-helpers.c`  
**Symptom:** `error: unused parameter 'cp' [-Werror=unused-parameter]`

**Root cause:** Both `lit_char_fold_to_lower` and `lit_char_fold_to_upper`
use `cp` only inside `#if JERRY_UNICODE_CASE_CONVERSION`. With
`JERRY_UNICODE_CASE_CONVERSION=0` (wf-minimal profile), the parameter
is never referenced, triggering `-Werror=unused-parameter`.

**Fix:** Add `(void) cp;` in each `#else` branch before the `return`
statement.

---

### Bug 5 — `ecma_object_is_regexp_object` declaration guarded

**File:** `jerry-core/ecma/operations/ecma-objects.h` (declaration),
`jerry-core/ecma/operations/ecma-objects.c` (definition)  
**Symptom:** `error: implicit declaration of function 'ecma_object_is_regexp_object'`

**Root cause:** The declaration was guarded by `#if JERRY_BUILTIN_REGEXP`,
but `ecma_op_is_regexp` calls `ecma_object_is_regexp_object` unconditionally
after a Symbol.match check.

**Fix:**  
- `ecma-objects.h`: remove the `#if JERRY_BUILTIN_REGEXP` guard from the
  declaration  
- `ecma-objects.c`: keep the function outside the guard, but make its body
  conditional — return `false` immediately when `JERRY_BUILTIN_REGEXP=0`

---

### Bug 6 — Container-specific functions defined without feature guard

**File:** `jerry-core/ecma/builtin-objects/ecma-builtin-intrinsic.c`  
**Symptom:** `error: implicit declaration of function 'ecma_op_container_get_object'`
and `'ecma_op_container_create_iterator'`; `error: 'ECMA_BUILTIN_ID_MAP_ITERATOR_PROTOTYPE'
undeclared`; and `defined but not used` warnings for the two static functions.

**Root cause:** `ecma_builtin_intrinsic_map_prototype_entries` and
`ecma_builtin_intrinsic_set_prototype_values` are static helper functions
that call container-specific APIs. They are properly *called* under
`#if JERRY_BUILTIN_CONTAINER` in the dispatch switch, but the function
*definitions* have no such guard, so they compile (and fail) unconditionally.

**Fix:** Wrap both function definitions in `#if JERRY_BUILTIN_CONTAINER` /
`#endif`.

---

### Bug 7 — RegExp string iterator function depends on disabled types

**File:** `jerry-core/ecma/builtin-objects/ecma-builtin-regexp-string-iterator-prototype.c`  
**Symptom:** Multiple errors: `unknown type name 'ecma_regexp_string_iterator_t'`,
`'ECMA_OBJECT_CLASS_REGEXP_STRING_ITERATOR' undeclared`, `'RE_FLAG_GLOBAL'
undeclared`, `error: implicit declaration of function 'ecma_op_regexp_exec'`.

Additionally in `jerry-core/ecma/operations/ecma-iterator-object.c`:  
`'ECMA_OBJECT_CLASS_REGEXP_STRING_ITERATOR' undeclared` in an assert.

**Root cause:** The `ecma_builtin_regexp_string_iterator_prototype_object_next`
function (and the dispatch assert in `ecma-iterator-object.c`) use types and
constants defined only when `JERRY_BUILTIN_REGEXP=1`. The JerryScript cmake
build compiles all source files unconditionally — there is no CMakeLists.txt
guard to skip this file when REGEXP is disabled.

**Fix:**  
- `ecma-builtin-regexp-string-iterator-prototype.c`: wrap the real function
  body in `#if JERRY_BUILTIN_REGEXP`; provide a stub in `#else` that returns
  `ecma_raise_type_error` so the dispatch table (generated by the
  `BUILTIN_INC_HEADER_NAME` template mechanism) can still link.  
- `ecma-iterator-object.c`: wrap the
  `ECMA_OBJECT_CLASS_REGEXP_STRING_ITERATOR` branch of the assert in
  `#if JERRY_BUILTIN_REGEXP`.

**Note on the typedarray path in `ecma-builtin-array-iterator-prototype.c`:**
The same pattern applies to lines ~95–105, where `ecma_object_is_typedarray`,
`ecma_typedarray_get_arraybuffer`, `ecma_arraybuffer_is_detached`, and
`ecma_typedarray_get_length` are called without a `JERRY_BUILTIN_TYPEDARRAY`
guard. Fixed by wrapping the entire `if (ecma_object_is_typedarray(...)) { }`
block in `#if JERRY_BUILTIN_TYPEDARRAY`.

---

## Files changed

```
engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/operations/ecma-conversion.h
  - Remove #if JERRY_BUILTIN_CONTAINER guard around ecma_op_same_value_zero declaration

engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/operations/ecma-conversion.c
  - Remove #if JERRY_BUILTIN_CONTAINER guard around ecma_op_same_value_zero definition

engine/vendor/jerryscript-v3.0.0/jerry-core/vm/opcodes.c
  - ecma_builtin_get_global() → ecma_make_object_value(ecma_builtin_get_global()) in assert
  - global_obj_p → ecma_builtin_get_global() in ecma_get_global_scope call

engine/vendor/jerryscript-v3.0.0/jerry-core/lit/lit-char-helpers.c
  - Add (void) cp; in #else branches of lit_char_fold_to_lower and lit_char_fold_to_upper

engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/operations/ecma-objects.h
  - Remove #if JERRY_BUILTIN_REGEXP guard around ecma_object_is_regexp_object declaration

engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/operations/ecma-objects.c
  - Remove #if JERRY_BUILTIN_REGEXP guard from function definition
  - Make body conditional: JERRY_BUILTIN_REGEXP=0 returns false immediately

engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/builtin-objects/ecma-builtin-intrinsic.c
  - Wrap ecma_builtin_intrinsic_map_prototype_entries and ..._set_prototype_values
    in #if JERRY_BUILTIN_CONTAINER / #endif

engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/builtin-objects/ecma-builtin-regexp-string-iterator-prototype.c
  - Wrap real function body in #if JERRY_BUILTIN_REGEXP
  - Provide stub implementation in #else that returns type error

engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/builtin-objects/ecma-builtin-array-iterator-prototype.c
  - Wrap typedarray-dependent block in #if JERRY_BUILTIN_TYPEDARRAY

engine/vendor/jerryscript-v3.0.0/jerry-core/ecma/operations/ecma-iterator-object.c
  - Wrap ECMA_OBJECT_CLASS_REGEXP_STRING_ITERATOR assert branch in #if JERRY_BUILTIN_REGEXP
```

---

## Upstream status and how to report

The upstream project is at `github.com/jerryscript-project/jerryscript`.
The v3.0.0 tag is the last release (2023); the project is in maintenance-only
mode with sparse activity.

**These bugs are almost certainly not yet reported or fixed upstream.** The
root cause — no CI coverage for minimal profiles on GCC 14 — means nobody
with upstream access has seen them.

**To file a bug:**

1. Search `github.com/jerryscript-project/jerryscript/issues` for "GCC 14",
   "same_value_zero", "global_obj_p", "unused parameter cp".
2. If no open issue covers the full set, file one issue titled something like:
   > "Build failures on GCC 14 with JERRY_BUILTINS=0 (7 bugs in minimal profile)"  
   Include the reproducer:
   ```bash
   # Minimum repro (ubuntu 24.04):
   cmake -S . -B build -DJERRY_BUILTINS=0 -DJERRY_BUILTIN_ARRAY=1 \
         -DJERRY_BUILTIN_ERRORS=1
   cmake --build build -j
   ```
   Reference this investigation file for the full patch list.
3. A consolidated PR with the 10 changed files would be a clean contribution.
   All fixes are in `#if`/`#else` branches — they are purely additive,
   zero risk to the default (full-features) build.

**Prioritized upstreaming order** (most broadly useful first):
1. Bugs 1, 2, 3 — single-line fixes, clearly correct, affect any minimal profile
2. Bug 5 — 2 files, widely useful
3. Bug 4 — cosmetic `-Werror=unused-parameter` fix
4. Bugs 6, 7 — more invasive; container/regexp users only

---

## Verification

After applying all patches, build with:

```bash
cd engine
WF_JS_ENGINE=jerryscript bash build_game.sh
```

The JerryScript cmake sub-build runs first (idempotent once libs exist),
then links into `wf_game`. Expect no errors — only a `tmpnam` deprecation
warning from unrelated INI parser code.

Smoke test — run snowgoons with JS scripts:
```bash
# Patch snowgoons.iff with JS scripts:
python3 scripts/patch_snowgoons_js.py

# Launch:
cd wfsource/source/game
DISPLAY=:0 /path/to/wf_game -Lwflevels/snowgoons.iff
```
Player movement and camera cuts confirm JerryScript is dispatching and
executing the JS mailbox scripts end-to-end.
