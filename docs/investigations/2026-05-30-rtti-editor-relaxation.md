# Investigation — Should we relax `-fno-rtti` for the editor?

**Date:** 2026-05-30
**Trigger:** Aftermath of the [C++ exception-usage audit](2026-05-30-cpp-exceptions-audit.md). The audit conclusion noted that the new `TerminateHandler` in `engine/wf_edit/main.cc` dropped its originally-planned `typeid(e).name()` line because `-fno-rtti` is inherited from `wfengine` (`CMakeLists.txt:701`). The exceptions relaxation paid for itself (JSON, libdatachannel, the handler itself need them); the user asked whether a parallel RTTI relaxation for the editor is also worth it, **with explicit concern about leakage into the engine and near-identical implementations replacing shared code.**

This investigation answers: **no, not worth it**, and shows the cost-vs-benefit shape so the answer can be revisited if future demand changes.

## What the relaxation would buy

| Use site | Concrete need today |
|---|---|
| `TerminateHandler` `typeid(e).name()` | Marginal — one diagnostic line on top of `e.what()` + the backtrace, whose `[1]` frame already names the throw site (libgcc demangles without RTTI). |
| `dynamic_cast` in the editor's Doc / Outliner / Properties dispatch | **Zero.** All dispatch is via string keys (CRDT leaf paths) or `kind()` / `EActorKind` (engine pattern). No editor code is asking for it. |
| Future ImGui-side widget dispatch | **Zero.** Widgets are picked by OAD `ButtonType × showAs`, table-driven. |
| Better backtraces | **No.** `backtrace_symbols_fd()` demangles via libgcc's own machinery; doesn't depend on `-frtti`. |

→ Net win: one diagnostic line. The exception relaxation enabled an entire class of code (JSON parsing, libdatachannel send guards, the terminate handler itself); the RTTI relaxation would enable, today, *zero* working code.

## What the relaxation would cost

### 1. The flag is the enforcement

Today `-fno-rtti` on `wfengine` (and inherited by `wf_edit`) is a load-bearing guarantee: convention can't drift because the compiler refuses `typeid` / `dynamic_cast`. Flip it off on the editor and "is this RTTI? is this editor-only?" becomes a code-review job, exactly the policy shape exceptions have today — **but worse**, because exceptions surface as `try`/`catch`/`throw` in greps (auditable on demand, as we just did), whereas `dynamic_cast<T*>` looks like a plain cast at a glance. PR creep is near-certain over time.

The compile-flag enforcement is the same property `feedback_check_existing_constants` relies on for `Vector3::one`/etc.: an unenforceable convention degrades.

### 2. Dispatch-pattern divergence (the user's main concern)

The engine's pattern is **`kind()` / `EActorKind` discriminated dispatch** (`project_no_rtti_architectural_constraint`, `project_actor_kind_vs_capability`). The editor today reuses that — the Properties walker and OAD-driven panel both look up by string key or `kind()`, never by C++ type.

Once RTTI is available, the natural editor PR is "smarter walker using `dynamic_cast<Foo*>` instead of the verbose `kind()` switch." That creates **two dispatch paths for the same hierarchy**: engine keeps `kind()` for the device target, editor uses `dynamic_cast` for the same lookups. Each new actor class then has to be plumbed into both.

This is exactly the "near-identical implementations instead of sharing/reusing code" the user called out, and the `typeid()` cliff is currently the thing that prevents it.

### 3. Mixed-vtable ODR foot-gun (minor)

A class that ends up in both engine-target TUs (`-fno-rtti`) and editor-target TUs (`-frtti`) gets vtable + typeinfo emitted differently across translation units. GCC/Clang linkers tolerate it in practice (one wins), but it's a quiet footgun — a difference in vtable layout (e.g. typeinfo pointer slot) at some future compiler version becomes a load-bearing bug. Not a blocker by itself, but a tax we don't need to pay for one diagnostic line.

## What we lose from not having `typeid(e).name()`

The `TerminateHandler` as shipped already does:

1. Rethrow `std::current_exception()` + catch `std::exception&` → log `e.what()`.
2. `backtrace()` + `backtrace_symbols_fd()` → 64-frame demangled trace.
3. `std::abort()` → ASan / cores still trigger.

`e.what()` is the human message; the backtrace's `[1]` / `[2]` frames identify the throw site (e.g. `nlohmann::json::parse_error::create(…)`), which carries the C++ type name embedded in the symbol. In practice that's enough to triangulate every `terminate`-class bug we've seen.

If we ever genuinely need the C++ type without `-frtti`, GCC provides `abi::__cxa_current_exception_type()` returning a `std::type_info*` — but that's RTTI infrastructure under a different spelling, and the *actual* fix for a recurring `terminate` is almost always the throw site, not its type name in the handler.

## Recommendation

**Keep `-fno-rtti` on the editor.** Specifically:

- Do not relax the flag on `wf_edit` / `wfengine`.
- Leave the `TerminateHandler` as shipped (`e.what()` + backtrace + `abort()`).
- If a future use case actually demands C++ type identity (not just diagnostics), prefer **adding the discriminator to the data** (`kind()` extension, OAD tag, CRDT leaf key) over relaxing the flag — that keeps the editor and engine on one dispatch model.

## When to revisit

The answer would change if **any** of these become true:

- The editor needs to dispatch over a third-party C++ class hierarchy that doesn't carry its own discriminator (none currently — Yrs is C-ABI; libdatachannel handlers are typed callbacks; ImGui is procedural).
- A repeating `terminate` lands where `e.what()` + backtrace genuinely don't identify the type. (We don't have one; we'd need to see the handler fire and **fail to diagnose** at least twice before the cost makes sense.)
- The exception type-identity question moves from diagnostic to load-bearing — e.g. a feature that has to recover differently per exception type at runtime. Not on any plan.

Until then, the `typeid()` cliff is doing useful work as a hard wall against `dynamic_cast`-based editor PRs.

## Related

- [C++ exception-usage audit](2026-05-30-cpp-exceptions-audit.md) — the parent investigation.
- [`project_no_rtti_architectural_constraint`](../../../.claude/projects/-home-will-WorldFoundry/memory/project_no_rtti_architectural_constraint.md) — original policy memory.
- [`project_actor_kind_vs_capability`](../../../.claude/projects/-home-will-WorldFoundry/memory/project_actor_kind_vs_capability.md) — the dispatch model the editor shares with the engine.
- [`project_cpp_exceptions_editor_only`](../../../.claude/projects/-home-will-WorldFoundry/memory/project_cpp_exceptions_editor_only.md) — exceptions are editor-only; RTTI is *not* getting the same carve-out, and this doc is why.
