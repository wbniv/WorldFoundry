# Investigation: Forth compile vs. run separation in scripting_zforth.cc

**Date:** 2026-04-29
**Conclusion:** Compile/run separation is correctly handled. One actionable improvement: a pre-compile pass at level load to eliminate first-frame jitter.

---

## How RunScript handles compile vs. run

`scripting_zforth.cc::RunScript()` ([source](https://github.com/wbniv/WorldFoundry/blob/2026-new-level/engine/stubs/scripting_zforth.cc)):

1. On first call with a given `src` pointer:
   - Scans for the **last `;`** in the script to find the boundary between word definitions and the call body
   - Evals the definitions part (`src` … last `;`) directly into `g_ctx` — compiled once, never re-evaluated
   - Wraps the call body (everything after last `;`) in a named word `_wfsN` (where N = cache size at compile time)
   - Stores `src → "_wfsN"` in `g_scriptCache`
2. On all subsequent calls: looks up the cached word name and evals it (just executes the pre-compiled word)

Scripts with no definitions (no `;` at all) have their entire body wrapped in `_wfsN`.

This is correct Forth embedding. The compile/run distinction is maintained because:
- All `:` … `;` definitions are compiled at first-call time
- Immediate words (`if`, `else`, `fi`, `begin`, `until`, `do`, `loop`) are immediate only during compilation — wrapping the call body in `: _wfsN … ;` means they compile correctly on first call and execute correctly on all subsequent calls

---

## Constants: inline literals, not `constant`

`AddConstantArray` defines each constant as:

```forth
: INDEXOF_INPUT 3024 ;
```

rather than the standard Forth form `3024 constant INDEXOF_INPUT`. The comment explains why:

> `constant` (r> + postpone literal) is compile-time-only and broken at runtime in zForth's embedding model.

The inline literal form is equivalent for read-only constants and avoids the issue entirely. This is correct.

---

## Issues found

### 1. First-frame jitter (shared with Lua/JS)

Compilation is lazy: the first time each actor's script executes, it compiles. For a level with 50 actors all running Forth scripts, the first frame does 50 compilations. Lua and JS have the same issue.

**Fix:** expose a `CompileScript(const char* src)` entry point in `scripting_forth.hp` and call it for each unique script pointer during level load (before the first frame). Since `g_ctx` already persists for the engine lifetime, this is just a scheduling change — no architectural work needed.

### 2. Last-`;` split heuristic

The definition/call-body split uses "find the last `;`". This fails if:
- The call body contains a `;` (e.g. inside a string literal or comment)
- Definitions are interleaved with call-body code (unusual but valid Forth style)

In practice, WF Forth scripts follow a simple pattern (`definitions then calls`) and don't embed `;` in strings/comments, so this is not a current problem. Worth documenting as a constraint on script style.

### 3. Append-only dictionary grows unbounded

`DeleteConstantArray` is a no-op — zForth dictionaries cannot shrink. Every unique compiled script word (`_wfs0`, `_wfs1`, …) lives for the engine lifetime. Constants defined via `AddConstantArray` also persist.

At current scale (small levels, ~20 actors) this is fine. For a large level with hundreds of unique scripts, dictionary memory could become a concern. zForth's `g_ctx` is a fixed-size memory block (`ZF_DICT_SIZE` in `wf_zfconf.h`) — if it fills up, `zf_eval` returns an error.

**Mitigation:** `ZF_DICT_SIZE` is set to 32 KB in `zfconf.h` (comment: "comfortably holds all INDEXOF_* constants + scripts"). Monitor if script count grows.

---

## Pre-compile pass: verdict

Feasible, worthwhile, low effort. The dictionary (`g_ctx`) already persists across frames. Implementation:

```cpp
// scripting_forth.hp — add to forth_engine namespace:
void CompileScript(const char* src);

// scripting_zforth.cc — implementation:
void forth_engine::CompileScript(const char* src) {
    // Same logic as the "cache miss" path in RunScript, without executing.
    // Called once per unique script at level load.
}
```

Level loading code iterates all objects, reads their script fields, and calls `CompileScript` for each unique pointer. First frame then hits only cache hits.

This is a quality-of-life improvement, not a correctness fix. Defer until first-frame hitching is actually observed.
