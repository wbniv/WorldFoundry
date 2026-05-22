# Upgrade Yrs (0.9.3 → 0.26.0) + Native Undo/Redo for wf-edit

**Status:** Phase A DONE 2026-05-22 (upgraded to v0.26.0, not 0.23.5 — newest stable, identical UndoManager C API); Phase B (native undo) in progress

> **Phase A result:** vendored Yrs bumped 0.9.3 → **v0.26.0** (newest stable; web-search said 0.23.5 was latest but the repo already had up to 0.26.0 with a byte-identical `yundo_manager_*` C API + committed `libyrs.h`, so newest was the better debt payoff). `wfcrdt` re-threaded for the read/write txn split + owned-`YSubscription` observers; a real **root-resolution deadlock** (`ymap/yarray(doc,name)` open their own internal write txn) was fixed with **lazy txn acquisition** — root branches resolve at the `Doc` (cached) before any write lock, the yffi txn opens only on the first data op — keeping the public wrapper API and all ~16 call sites unchanged (3 multi-root sites reordered to fetch both roots before the first op). Verified: `wfcrdt_smoke` 5/5, `wfcrdt_wrapper_test` 10/10, `wfcrdt_sync` 4/4, relay smoke 3/3, and `wf-edit` loads snowgoons (36 actors, bridge map OK).

## Context

The wf-edit level editor has **no undo** today — every field edit, gizmo move, and add/delete is irreversible. The editor's data model is a [Yrs](https://crates.io/crates/yrs) CRDT document (`wfcrdt::Doc`), and modern Yrs ships a native [`UndoManager`](https://docs.yjs.dev/api/undo-manager) that makes every transaction reversible for free — the right primitive for this feature.

The catch: the vendored Yrs (`wftools/y-crdt`, a git submodule) is pinned to **v0.9.3 — a June 2022 release** (commit `9f52142`), added 2026-05-19 (commit `dd7c0939`, plan [2026-05-18-yrs-c-abi-binding.md](2026-05-18-yrs-c-abi-binding.md)). That plan said "pin to the latest tagged release," but 0.9.3 was chosen — an under-specified pin, most likely because 0.9.3's [`yffi`](https://lib.rs/crates/yffi) crate ships a pre-generated `libyrs.h` C header. **0.9.3 predates the `UndoManager`** (added upstream ~0.16+).

We could fake undo with a C++ compensating-write stack on top of 0.9.3, but that code is **throwaway** — it gets deleted the moment we adopt the native `UndoManager`. Rather than write undo twice and keep accreting debt on a 4-year-old CRDT, the decision (2026-05-22) is to **bite the bullet: upgrade Yrs first, then wire the native UndoManager.**

**Why the upgrade is bounded, not a swamp:** our C++ wrapper (`engine/crdt/wfcrdt.cpp`) couples to only **~30 yffi functions**, the Rust relay touches **3 yrs call sites**, and the [Yjs v1 update wire format is version-stable](https://docs.yjs.dev/api/document-updates) — so the collab relay protocol and on-disk `.ydoc` snapshots survive the upgrade untouched. The one genuinely mechanical change is the post-0.9.3 **read/write transaction split**, which we absorb *inside* `wfcrdt.cpp` so the `wfcrdt.hpp` public API and every editor file above it stay unchanged.

**Outcome:** wf-edit runs on Yrs 0.23.5; Ctrl+Z / Ctrl+Y reverse and replay every edit (field, gizmo, add/delete) via the native `UndoManager`; undo is local-only in a collab session.

---

## Phase A — Upgrade vendored Yrs 0.9.3 → 0.23.5

Goal: get the engine + relay building and passing existing tests on Yrs 0.23.5, with **no behavior change** (undo comes in Phase B). Commit at the end of the phase.

1. **Bump the submodule.** `cd wftools/y-crdt && git fetch --tags && git checkout v0.23.5` (or the exact latest tag); update the gitlink + `.gitmodules` comment. Confirm `yffi/tests-ffi/include/libyrs.h` exists at that tag — if the committed header is gone, generate it with the repo's `cbindgen` config (`yffi/cbindgen.toml`) into the same path the build references (`wftools/y-crdt/tests-ffi/include/libyrs.h`).
2. **Toolchain check.** 0.23.5 needs a newer Rust edition/MSRV than 0.9.3's edition-2018. Verify the project toolchain (`rust-toolchain.toml` / CI) satisfies it; bump if needed. Rebuild the static lib: `cargo build --release -p yffi --manifest-path wftools/y-crdt/Cargo.toml` → `libyrs.a`. Corrosion (the `cmake/Corrosion` submodule) drives this from CMake; confirm no CMake target rename is needed.
3. **Re-thread `engine/crdt/wfcrdt.cpp` for the new ABI.** This is the bulk of the work. The public `wfcrdt.hpp` types (`Doc`, `Transaction`, `Map`, `Array`, `Output`, `Input`, `Subscription`) stay; only the `.cpp` bodies change:
   - **Transaction split:** `Doc::begin()` now calls `ydoc_write_transaction(doc, 0, nullptr)` (write-capable; reads work on it too) instead of the 0.9.3 `ytransaction_new`. Keep the single RAII `Transaction` type so callers are unaffected. `Transaction::commit()` → `ytransaction_commit`.
   - **Mutators/readers take an explicit txn ptr:** update the ~30 call sites — `ymap_insert(branch, txn, …)`, `ymap_get(branch, txn, key)`, `ymap_len(branch, txn)`, `yarray_insert_range(branch, txn, …)`, `yarray_get(branch, txn, idx)`, `yarray_len(branch, txn)`, `yarray_remove_range(branch, txn, …)`. Root-type accessors: `ymap(doc, name)` / `yarray(doc, name)`. The `Map`/`Array` views already carry a `YTransaction*` (`_txn`) — thread it through.
   - **Observer API:** `ymap_observe` / `yarray_observe` / `ydoc_observe_updates_v1` now return an owned `YSubscription*` freed by `yunobserve(sub)` (replacing the 0.9.3 integer-id + `ymap_unobserve(branch, id)` model). Rework `Subscription`'s internals (store `YSubscription*`, free in dtor); keep its move-only public shape.
   - **Constraint to honor:** modern Yrs forbids a second concurrent write txn and forbids opening a txn inside an observer callback. The editor's txns are short-lived and sequential, but audit `observeUpdates` / map/array observers to ensure no callback opens a new `doc.begin()`.
4. **Rust relay diff (small).** In `wftools/wf_collab/src/bin/relay.rs` (and `tests/relay_smoke.rs`): `doc.transact()` → `doc.transact_mut()` for the write sites, and adjust `apply_update` / `insert` to the new signatures. `cargo update -p yrs` in `wf_collab/Cargo.toml`.
5. **Build + regression.** `task build` (verify the `wf_game` / `wf_edit` binary timestamps advance — pipe-through-grep hides failures). Run the existing CRDT wrapper tests (`engine/crdt/wfcrdt_wrapper_test.cc`) and the relay smoke test. Confirm wf-edit still loads snowgoons, the Outliner populates, field edits + gizmo + delete/duplicate still work, and a two-instance relay session still syncs (Yjs-v1 wire compat means no protocol change).

**Critical files (Phase A):** `wftools/y-crdt` (submodule pointer), `.gitmodules`, `engine/crdt/wfcrdt.cpp` (the ~30-call re-thread + observer rework), `engine/crdt/wfcrdt.hpp` (only if a signature genuinely must change — aim for none), `wftools/wf_collab/src/bin/relay.rs` + `Cargo.toml`, possibly `rust-toolchain.toml` / `CMakeLists.txt` (Corrosion target).

---

## Phase B — Native UndoManager binding + wf-edit wiring

Goal: Ctrl+Z / Ctrl+Y reverse/replay every edit, local-only in collab. Commit at the end of the phase.

1. **Expose `UndoManager` in the C++ wrapper** (`wfcrdt.hpp` / `wfcrdt.cpp`) — a thin RAII class over the `yundo_manager_*` C ABI:
   ```cpp
   class UndoManager {
   public:
       explicit UndoManager(Doc& doc);          // yundo_manager(doc, default options)
       ~UndoManager();                           // yundo_manager_destroy
       void addScope(const Array& root);         // yundo_manager_add_scope — track "content"
       void addScope(const Map& root);           //   (and "meta" if we ever edit it)
       bool undo();                              // yundo_manager_undo  → true if something undone
       bool redo();                              // yundo_manager_redo
       bool canUndo() const;                     // yundo_manager_can_undo
       bool canRedo() const;                     // yundo_manager_can_redo
       void clear();                             // yundo_manager_clear
       // optional: stopCapturing() to break coalescing between discrete edits
   };
   ```
   Confirm exact signatures against the regenerated `libyrs.h`. Default `UndoManager` options coalesce edits within a ~500 ms window into one undo step — good for typing/gizmo-drag (one Ctrl+Z reverses a whole drag); call `stopCapturing()` after structural ops if we want delete/duplicate to be their own discrete steps.
2. **Local-only-in-collab via tracked origins.** Yrs `UndoManager` only reverts transactions whose **origin** is in its tracked-origins set. Tag this editor's *local* edits with a per-instance origin and remote applies with none (or a different one):
   - In `Doc::begin()` (or a new `Doc::beginLocal()`), pass a stable local origin to `ydoc_write_transaction(doc, origin_len, origin)`. The `UndoManager` is constructed tracking that origin.
   - `CollabDrain` (main.cc ~340) applies remote SYNC updates via `txn.apply(...)`; ensure that path uses a transaction with **no** (or a non-tracked) origin so remote edits never enter our undo history. This realizes "local-only undo" with zero per-edit bookkeeping — strictly cleaner than the C++-stack design's `_eid`-anchoring.
3. **Wire into the editor** (`engine/wf_edit/main.cc`):
   - Add `std::optional<wfcrdt::UndoManager> undo;` to `EditorCtx`; construct it right after the Doc is populated (main() ~944), `addScope(content array)`.
   - Add `DoUndo(c)` / `DoRedo(c)`: call `c->undo->undo()/redo()`, then run the same post-apply refresh `CollabDrain` already does (main.cc 343-352) — `RefreshActorList`, re-`ResolveProperties` for the selection, `PropagateToEngine` for each matched field — plus a toast ("undo" / "nothing to undo"). The native manager mutates the Doc directly; the engine/UI just need to re-sync from it.
   - **Keybindings** (main.cc ~637-642, beside Ctrl+S/Delete, guarded by `!typing`): Ctrl+Z → `DoUndo`; Ctrl+Shift+Z **and** Ctrl+Y → `DoRedo` (gate the plain-Z undo on `!io.KeyShift` so one Z press can't fire both).
   - **Edit menu** in the main menu bar (~620): `Undo  Ctrl+Z` / `Redo  Ctrl+Y`, each `enabled` from `canUndo()`/`canRedo()` so they grey out when empty:

     ```
     ┌─ File ─┬─ Edit ──────────┬─ View ─┐
     │        │ Undo      Ctrl+Z │        │   ← greyed when canUndo()==false
     │        │ Redo      Ctrl+Y │        │   ← greyed when canRedo()==false
     │        └──────────────────┘        │
     ```
4. **Nothing else changes** — no `undo.cc`, no `_eid` anchoring, no `DocChunkToInput` capture, no `WriteFieldLeaf`/`property_panel.cc`/`gizmo.cc` signature changes. The native manager reverses whatever transactions hit the tracked scope, regardless of which code path (panel, gizmo, structural) produced them.

**Critical files (Phase B):** `engine/crdt/wfcrdt.hpp` + `wfcrdt.cpp` (UndoManager class + local-origin txn), `engine/wf_edit/main.cc` (EditorCtx member, DoUndo/DoRedo, keybindings, Edit menu, refresh).

---

## Risks & watch-items

- **Transaction nesting (HIGH).** Modern Yrs panics on a second concurrent write txn or a txn opened inside an observer callback. Audit all `doc.begin()` scopes and observer callbacks during Phase A; `yundo_manager_undo/redo` open their own txn internally, so `DoUndo`/`DoRedo` must run at frame top with no txn live (they do).
- **Header regeneration (MEDIUM).** If v0.23.5 no longer commits `libyrs.h`, we must generate it via the upstream `cbindgen.toml`. Verify before assuming the path exists.
- **Rust toolchain bump (MEDIUM).** 0.23.5 MSRV may exceed what CI/dev pins; bump `rust-toolchain.toml` and re-verify Android/iOS Rust builds aren't broken.
- **Wire/snapshot compat (LOW, but verify).** Yjs v1 update format is stable across versions; the relay's `0x01 SYNC` bytes and `.ydoc` snapshots should interop. Smoke-test a fresh-instance + existing-snapshot session after the upgrade to confirm.
- **Coalescing granularity (LOW).** Tune via `stopCapturing()` so a gizmo drag = one undo step but two unrelated field edits aren't merged. Confirm visually.

---

## Verification

1. **Phase A regression (no new behavior):** existing `wfcrdt_wrapper_test` + relay smoke pass on 0.23.5; wf-edit loads snowgoons, Outliner populates, a field edit / gizmo move / duplicate / delete each still works; two-instance relay session syncs an edit both ways.
2. **Phase B undo logic — env-gated headless harness** (model on the existing `WF_EDIT_TEST_SET` / `WF_EDIT_STRUCT_TEST` blocks in `main.cc` ~963/996): `WF_EDIT_UNDO_TEST="field:Mass|DATA|2.5;undo;redo;dup:0;undo;del:1;undo"` drives edits + `c->undo->undo()/redo()` against the Doc, re-reading via `ReadActorFields`/`ReadActorNames` after each step and asserting: after `edit;undo` the original value/actor-count is restored; after `edit;undo;redo` the edited state returns; `dup;undo` restores the count; `del;undo` restores the actor. Print `[undo] all PASS`; wire a `wf_edit_undo` CTest beside `wf_edit_spawn_confirm`.
3. **Phase B screenshot proof** (per house rule — visual proof for gameplay/UI features): `WF_EDIT_UNDO_UI=del wf_edit --select=1 --frames 5 --leveltree=<snowgoons.lev> --screenshot out.ppm` performs an edit then one `DoUndo`, capturing the Outliner/Properties back in their pre-edit state + the "undo" toast. Note the `--screenshot PATH` space-not-`=` gotcha and run-in-background per the screenshot-capture practice.
4. **Manual collab check:** two wf-edit instances on a relay; instance A edits, instance B's Ctrl+Z does **nothing** to A's edit (local-only); A's Ctrl+Z reverses A's own edit and B sees the revert.

---

## Execution notes

- Commit after Phase A and after Phase B (each independently builds + passes its tests).
- **Estimate (average-programmer scale):** Phase A ≈ 1–1.5 days (the wfcrdt.cpp re-thread + observer rework + toolchain/header shake-out dominate); Phase B ≈ 0.5 day (native UndoManager makes the wiring small). ~2 days total.
- Supersedes the deferred-TODO from the earlier "C++ undo stack" discussion; that throwaway approach is explicitly not taken.
