# Plan — wfcrdt C++ RAII wrapper

**Date:** 2026-05-19
**Status:** Done 2026-05-19 (~1 h vs ~2–3 d estimate). Five implementation steps committed (`dbfbe99..e6e4a03`); `wfcrdt_wrapper_test` is green at 9/9, the C smoke stays green at 5/5, and both binaries are clean under `-DWF_ASAN=ON -DCMAKE_BUILD_TYPE=Debug`. One yffi-behaviour discovery: observers don't fire on the txn that registered them — found via a failing first run of `test_observer_fires`, restructured to mirror the C smoke's "register, commit, mutate-in-fresh-txn" pattern.
**Scope:** Thin C++ wrapper around the Yrs C ABI ([libyrs.h](../../wftools/y-crdt/tests-ffi/include/libyrs.h)) so the editor's CRDT bridge can use `wfcrdt::Doc` / `Map` / `Array` / `Transaction` / `Output` / `Subscription` instead of raw `YDoc*` / `YTransaction*` / `Branch*` / `YOutput*` handles.
**Estimate:** ~2–3 d per the [parent plan](2026-05-18-yrs-c-abi-binding.md). Likely ~2 h at the [recent vendor-and-glue pace](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_duration_tracking.md).

---

## Context

The [Yrs C ABI binding](2026-05-18-yrs-c-abi-binding.md) (landed 2026-05-19, commits `dd7c093..fe4439c`) exposes `libwfcrdt.a` wrapping `libyrs.a` — but it's surfaced as the raw C ABI today. The smoke test ([engine/crdt/wfcrdt_smoke.c](../../engine/crdt/wfcrdt_smoke.c)) demonstrates the four lifetime patterns callers will have to manage:

1. **Doc** — `ydoc_new` → `ydoc_destroy`.
2. **Transaction** — `ytransaction_new` → `ytransaction_commit`.
3. **Output** — `ymap_get` / `yarray_get` returns a `YOutput*` the caller must `youtput_destroy`.
4. **Subscription** — `ymap_observe` / `yarray_observe` returns a `subscription_id` the caller must `ymap_unobserve` / `yarray_unobserve`.

Every editor-side consumer is going to repeat this lifetime plumbing by hand without a wrapper, which means leaks the first time someone forgets a destroy. RAII makes it the compiler's problem.

`Branch*` (the type behind `Map`/`Array`/`Text`) is **not owned by the caller** — its lifetime is tied to the `Doc`, and the C ABI's `ymap_destroy`/`yarray_destroy` only release the temporary handle, not the underlying data. So `Map`/`Array` wrappers are **borrowed views**, not owners — they hold a raw `Branch*` and a back-pointer to the active `Transaction`.

---

## Decisions resolved this plan

| Decision | Choice | Reason |
|---|---|---|
| Header layout | Single `engine/crdt/wfcrdt.hpp` for the public API | Keeps the editor's include surface to one line. Wrapper is small enough not to warrant per-class headers. |
| Implementation | Single `engine/crdt/wfcrdt.cpp` | Same — small surface, single TU. |
| Namespace | `wfcrdt::` | Matches the `libwfcrdt.a` artefact name and stays out of `wf::` (engine code). The wrapper is editor-side, not engine-side. |
| Copyability | Move-only across the board | Raw handles aren't copyable — copying a `Doc` would be a double-free waiting to happen. |
| Transaction commit | RAII auto-commit on destruction; explicit `commit()` and `cancel()` provided | Mirrors `std::lock_guard`. Cancel is rare but unambiguous. |
| Error reporting | `std::optional<T>` from getters; exceptions only for ctor failures (OOM) | Most "errors" in the Yrs C ABI are "type mismatch on read" — natural fit for optional. Allocation failures stay rare and fatal. |
| Observer callback storage | Heap-allocated `std::function` lifetime managed by the returned `Subscription` | The C ABI takes a `void*` userdata + function pointer; pack the `std::function` into a small struct, pass its address as userdata, free it when the subscription destructs. |
| Span vs vector for state-sync buffers | `std::span<const uint8_t>` for inputs, `std::vector<uint8_t>` for outputs | Inputs may come from arbitrary buffers; outputs need to own the heap allocation Yrs hands back (replacing `ybinary_destroy` with vector dtor). |
| C++ standard | C++17 (matches engine) | `std::span` is C++20 — fall back to a `(const uint8_t*, size_t)` pair or roll a 5-line `Bytes` view. **Choice: 5-line internal `wfcrdt::ByteView` so we don't drag in `<span>` headers conditionally.** |
| Smoke-test port | New C++ test file `wfcrdt_wrapper_test.cc` exercising the wrapper through the same 5 scenarios | Keeps the C smoke test as the lower-level oracle; wrapper test asserts behavioural parity through the higher-level API. |

---

## API surface (full sketch)

```cpp
// engine/crdt/wfcrdt.hpp
#pragma once
#include <functional>
#include <optional>
#include <string>
#include <vector>
#include <cstdint>

struct YDoc;
struct YTransaction;
struct Branch;
struct YOutput;
struct YMapEvent;
struct YArrayEvent;

namespace wfcrdt {

struct ByteView { const std::uint8_t* data; std::size_t len; };

class Output;
class Map;
class Array;
class Subscription;

class Transaction {
public:
    ~Transaction();
    Transaction(Transaction&&) noexcept;
    Transaction& operator=(Transaction&&) noexcept;
    Transaction(const Transaction&) = delete;

    void commit();
    void cancel();

    Map map(const char* name);
    Array array(const char* name);

    std::vector<std::uint8_t> stateVector() const;
    std::vector<std::uint8_t> stateDiff(ByteView remoteStateVector) const;
    void apply(ByteView diff);

    YTransaction* raw() const { return _txn; }
private:
    friend class Doc;
    explicit Transaction(YDoc* doc);
    YTransaction* _txn;
};

class Doc {
public:
    Doc();
    ~Doc();
    Doc(Doc&&) noexcept;
    Doc& operator=(Doc&&) noexcept;
    Doc(const Doc&) = delete;

    Transaction begin();
    YDoc* raw() const { return _doc; }
private:
    YDoc* _doc;
};

class Output {
public:
    ~Output();
    Output(Output&&) noexcept;
    Output(const Output&) = delete;

    std::optional<long long>   readLong()   const;
    std::optional<std::string> readString() const;
    std::optional<double>      readFloat()  const;
    bool valid() const { return _out != nullptr; }
private:
    friend class Map;
    friend class Array;
    explicit Output(YOutput* out);
    YOutput* _out;
};

class Map {
public:
    void insert(const char* key, long long value);
    void insert(const char* key, const char* value);
    void insert(const char* key, double value);
    Output get(const char* key) const;
    int len() const;

    Subscription observe(std::function<void(const YMapEvent*)> cb);
private:
    friend class Transaction;
    Map(Branch* branch, YTransaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    YTransaction* _txn;
};

class Array {
public:
    void insertLong(int index, long long value);
    void insertRange(int index, const long long* values, int count);
    Output get(int index) const;
    int len() const;

    Subscription observe(std::function<void(const YArrayEvent*)> cb);
private:
    friend class Transaction;
    Array(Branch* branch, YTransaction* txn) : _branch(branch), _txn(txn) {}
    Branch* _branch;
    YTransaction* _txn;
};

enum class SubKind { Map, Array };

class Subscription {
public:
    ~Subscription();
    Subscription(Subscription&&) noexcept;
    Subscription& operator=(Subscription&&) noexcept;
    Subscription(const Subscription&) = delete;
private:
    friend class Map;
    friend class Array;
    Subscription(Branch* target, unsigned int subId, SubKind kind, void* heapCb);
    Branch* _target;
    unsigned int _subId;
    SubKind _kind;
    void* _heapCb;
};

} // namespace wfcrdt
```

The full `YInput` value taxonomy (bool, binary, JSON array, JSON map, nested types) is **out of scope** for this phase — the editor's first consumer needs long/string/float scalars. Other input types are an additive extension when their use case lands.

---

## Implementation steps

Each step is its own commit per [feedback_commit_after_each_phase](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md).

1. **`wfcrdt.hpp` skeleton + `wfcrdt.cpp` Doc/Transaction impl + smoke compiles.** Implements the lifetime spine: `Doc`, `Transaction`, auto-commit, explicit `commit()`/`cancel()`. No `Map`/`Array`/`Output`/`Subscription` yet — they'll be empty forward decls so the header parses. CMake target gains the new `.cpp`. Smoke test stays C, so build succeeds with the wrapper present but unused.

2. **`Output` + `Map` insert/get/len** — first half of the CRUD surface. Insert overloads for `long long`, `const char*`, `double`. `Output::readLong/readString/readFloat` return `std::optional`. Add `engine/crdt/wfcrdt_wrapper_test.cc` exercising map round-trip; one CMake target + run.

3. **`Array` insert/get/len** — symmetric to Map. Extend the wrapper test.

4. **`Transaction::stateVector` / `stateDiff` / `apply`** — sync surface, returns `std::vector<uint8_t>` (owns the buffer; dtor replaces `ybinary_destroy` call). Wrapper test gets the two-Doc parity assertion ported from the C smoke.

5. **`Subscription` + `Map::observe` / `Array::observe`** — heap-allocated `std::function` packed into a trampoline struct, passed as `void*` userdata to the C ABI. Subscription dtor frees the trampoline and calls the right `_unobserve`. Wrapper test verifies the observer fires exactly once on a commit. **Note:** this is the only step where lifetime is non-trivial — the heap `std::function` outlives the `observe()` call but is destroyed before the `_unobserve` call inside `~Subscription`.

6. **Docs.** Plan Status → Done with time, [wf-status.md](../../wf-status.md) prepend + Active row, [TODO.md](../../TODO.md) entry retired if the wrapper's first consumer (the editor shell) is ever skipped, [editor design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) Tier 2 entry: "C++ RAII wrapper landed; editor bridge can now consume it."

---

## Verification

1. **`task build-editor` still green.** Existing C smoke test (`wfcrdt_smoke`) keeps passing — the wrapper is additive, the C ABI is untouched.

2. **Wrapper test passes.** New `wfcrdt_wrapper_test` (C++17) exercises the same five scenarios as the C smoke, but through the wrapper API. Runs as a CTest entry alongside the existing smoke.

3. **Leak-free under ASan.** Build with `-DWF_ENABLE_CRDT=ON -DWF_ASAN=ON`, run both smoke binaries. Zero leaks reported. This is the real win — RAII is meant to make leaks structurally impossible, ASan is the proof.

4. **Move semantics behave.** A specific test in `wfcrdt_wrapper_test.cc` move-constructs and move-assigns a `Doc` and a `Transaction`, asserts the source is left in a valid-but-empty state (subsequent operations are no-ops or yield `valid() == false`).

5. **Observer subscription lifetime.** Test that destroying the `Subscription` BEFORE the next commit prevents the callback from firing. Asserts the `_unobserve` path works.

---

## Out of scope (deferred)

- **Full `YInput` taxonomy** — bool, binary, JSON-array, JSON-map, XML types. Add when a consumer needs them.
  - **Nested types — DONE 2026-05-20** (triggered by the editor's read-only Y.Doc population, [editor-app-shell M4](2026-05-20-editor-app-shell.md)). Added `wfcrdt::Input` (a pure-C++ prelim builder: `str`/`lng`/`dbl`/`boolean`/`map`/`array` + `set`/`push`) plus `Map::insert(key, Input)`, `Array::insert/push(Input)`, and the read side `Output::asMap()`/`asArray()`. `wfcrdt_wrapper_test` now 10/10 (incl. `test_nested_array_of_maps`), clean under ASan/UBSan. **yffi bug found:** prefilled `yinput_ymap` infinite-loops in `<YInput as Prelim>::integrate` ([`yffi/src/lib.rs:1795`](../../wftools/y-crdt/yffi/src/lib.rs) — `let i = 0` never incremented); the wrapper materializes maps via empty-container-then-populate to dodge it (upstream patch: [`docs/patches/yrs-0.9.3-yinput-ymap-integrate-loop.patch`](../patches/yrs-0.9.3-yinput-ymap-integrate-loop.patch); [TODO](../../TODO.md) § Collaborative Editor).
- **Iterators** — `yarray_iter` / map iter. Editor doesn't need them yet.
- **`yobserve_deep`** — nested observation. Editor bridge will start with flat top-level observation; deep observation is a v2 line item.
- **`YText`** — separate type with its own rich-text op model. Not in v1 schema.
- **Exception type hierarchy** — single `std::runtime_error` from ctor on alloc failure; no custom hierarchy until a caller needs to discriminate.

---

## Cross-references

- [Parent plan: Yrs C ABI binding (landed)](2026-05-18-yrs-c-abi-binding.md)
- [Editor design doc § Tier 2 Engine↔CRDT bridge](../investigations/2026-05-18-collaborative-level-editor-design.md)
- [feedback_plan_duration_tracking](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_duration_tracking.md) — note implementation time on completion
- [feedback_commit_after_each_phase](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md) — each of the 6 steps is its own commit
- External: [libyrs.h C ABI](https://github.com/y-crdt/y-crdt/blob/v0.9.3/tests-ffi/include/libyrs.h), [Yrs project](https://github.com/y-crdt/y-crdt)
