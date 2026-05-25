# Plan — Confirm SpawnActor → Live Structural Sync → OAD kPropMap Codegen

**Date:** 2026-05-21  
**Status:** DONE — M1/M2/M3 all landed (commits `addb4a57`, `b5be8492`, `1effceec`); SpawnActor live structural sync + 77-field generated map shipped.
**Owner:** Claude (Will reviewing)  
**Branch:** `2026-new-level`

---

## Context

The Outliner add/delete landed (2026-05-21, [plan](../../WorldFoundry.2026-new-level/docs/plans/2026-05-21-outliner-add-delete.md)) with a `structural_dirty` guard that suspends the bridge's field→viewport propagation after any structural edit, because the positional `content[i]↔engine i+1` map goes stale. Three follow-ups were explicitly deferred:

1. **Confirm SpawnActor's runtime path** — the Jolt position-sync fix (commit `0adf1d4`) was committed but never exercised on a real spawn against a real level.
2. **Live structural sync** — make Outliner add/delete reflect in the live viewport without a reload.
3. **OAD codegen for `kPropMap`** — the bridge only drives 15 hand-curated fields; any other OAD field is a `NoOp` at the engine.

The three milestones are sequential: M1 unlocks M2 (need confirmed SpawnActor to wire live add); M2 restores field-propagation continuity through structural edits, which makes M3's full-field-coverage actually useful in a live session.

---

## Key architectural facts (from code reading)

- `_templateObjects[i]` is **only non-null** for actors explicitly flagged as runtime-spawnable in the level binary. Regular startup-constructed actors (Houses, platforms, Rooms) have `_templateObjects[i] = null`, so `HasTemplate(i)` returns false and `SpawnActor` cannot duplicate them.
- Runtime-spawned temp actors land at slots `[objectCount..]`, separate from startup actors `[1..objectCount-1]`. The positional map `content[i] → i+1` covers startup actors only.
- `RemoveActor` (deferred via `SetPendingRemove`) works on **any** actor regardless of template status.
- Actor indices are never compacted after removal — the slot stays null until overwritten by a new spawn in that same slot (which doesn't happen; temp actors use the overflow slots).
- kPropMap uses C `offsetof()` against three generated structs (`_Common`, `_Movement`, `_Mesh`) from `common.ht`, `movebloc.ht`, `mesh.ht`. The `.oad` binary carries field metadata (name, type, UI hints) but not offsets; those must stay compile-time.

---

## M1 — Confirm SpawnActor via headless proof

**Outcome**: A `WF_EDIT_SPAWN_CONFIRM_TEST` env-var test (mirror of the existing `WF_EDIT_STRUCT_TEST` pattern) that loads snowgoons, finds the first non-null template entry via `HasTemplate` scan, spawns it inside a known room, asserts a valid ActorIdx is returned, and verifies `GetActorPos` returns approximately the requested position. ASan-clean.

**Steps**:
1. In `engine/wf_edit/main.cc` (or a new `engine/wf_edit/spawn_test.cc`), add the `WF_EDIT_SPAWN_CONFIRM_TEST` path, mirroring the existing `WF_EDIT_STRUCT_TEST` block:
   - After `LoadLevel`, scan `i=1..` calling `wfmut::HasTemplate(*theLevel, i)` (expose if not already — `level.HasTemplate(i)` is on Level, wfmut needs to forward it or the test calls it directly).
   - Use position from `wfmut::GetActorPos(*theLevel, 1)` (the Level root) + a small Z offset (safe inside the root room).
   - `parentIdx = 1` (the Level root actor; `parentIdx=0` asserts in the engine).
   - Assert `SpawnActor` returns a value and `GetActorPos(new_idx)` ≈ requested pos.
2. Add `wfmut::HasTemplate(Level&, int templateIdx)` forwarding wrapper if not present (trivial: calls `level.HasTemplate(templateIdx)`).
3. Gate: ASan-clean, test exits 0.

**Expose `HasTemplate` in wfmut if missing**: `engine/mutation/wfmut.{h,cpp}`.  
**Test location**: env-var block in `engine/wf_edit/main.cc` or a new `spawn_test.cc` linked into `wf_edit`.

**Commit separately** (M1 is its own commit).

---

## M2 — Explicit stable-id map + live structural sync

**Replaces** the positional formula `doc_index + 1` in `engine_bridge.cc` with an explicit `std::vector<int> doc_to_engine_` map. `PropagateToEngine` becomes a map lookup; structural edits maintain the map instead of setting `structural_dirty`.

### Map lifecycle

**At `wfedit::InitBridge` / level load** (`engine_bridge.cc`):  
Fill `doc_to_engine_` with `{1, 2, ..., N}` (same as current formula). Clear `structural_dirty`.

**On `DoDelete(doc_i)`** (`main.cc` → bridge):
```
old_engine_idx = doc_to_engine_[doc_i]
DeleteActor(doc, doc_i)                      // remove from Doc
wfmut::RemoveActor(*theLevel, old_engine_idx) // deferred engine removal
doc_to_engine_.erase(begin + doc_i)          // shift map down
// structural_dirty stays clear — map is valid again immediately
```
Delete always works (no template needed); propagation continues for surviving actors.

**On `DoDuplicate(doc_i)`** (`main.cc` → bridge):
```
src_engine_idx = doc_to_engine_[doc_i]
new_doc_i = DuplicateActor(doc, doc_i)       // clone Doc entry (appended at end)
if HasTemplate(*theLevel, src_engine_idx):
    pos = GetActorPos(src_engine_idx) + Vector3(0, 0, 0.5)  // small offset avoids col check
    new_idx = SpawnActor(*theLevel, src_engine_idx, pos, parentIdx=1)
    doc_to_engine_.push_back(new_idx.value())
    // structural_dirty stays clear — live preview works
else:
    doc_to_engine_.push_back(0)              // sentinel: no live engine actor
    structural_dirty = true                  // guard stays; toast: "non-templated actor — reload to see in viewport"
```

### Bridge API additions

Add to `engine_bridge.{h,cc}`:
- `void BridgeNotifyDelete(int doc_i)` — erases entry, calls `RemoveActor`
- `void BridgeNotifyDuplicate(int doc_i, int new_doc_i)` — spawns if templated, pushes idx
- `DocActorToEngineIdx(int doc_i)` — becomes `doc_to_engine_[doc_i]` (0 = no live actor = skip)

Remove `structural_dirty` from the delete path entirely. Keep it only for the non-templated-duplicate fallback.

### Parent index

Use `parentIdx = 1` for all `SpawnActor` calls. This is the Level root actor and safe for all tested levels. A `wfmut::GetActorParentIdx` API can be added later if actor hierarchy matters (not a blocker for v1 live sync).

### Verification
- Delete: remove a House in the Outliner → it disappears from the viewport; surviving actors' field edits still propagate live. ASan-clean.
- Duplicate a templated actor (e.g. a coin or enemy in snowgoons): appears live in the viewport. Field edits to the duplicate propagate immediately.
- Duplicate a non-templated actor (House): shows the toast; save + reload shows it. No bridge corruption.
- Screenshot of each (bridge screenshot op).

**Commit separately** (M2 is its own commit).

---

## M3 — OAD codegen for `kPropMap`

**Replaces** the 15 hand-curated entries in `engine/mutation/wfmut.cpp:183–202` with an auto-generated include covering all fields in the three supported blocks.

### Codegen pipeline addition

Add a `gen-kpropmap` step to `wfsource/source/oas/regen-headers.sh`, running after each `.ht` file is produced:
- For each of `{common, movebloc, mesh}`:
  - Parse the `.ht` struct: regex `^\s+(\w+)\s+(\w+);` → `(ctype, member_name)`
  - `is_fixed32` = (`ctype == "fixed32"`)
  - Emit one `kPropMap` entry:
    ```cpp
    {"common.member", {PropInfo::COMMON, offsetof(_Common, member), true/false}},
    ```
- Output: `engine/mutation/kpropmap_generated.inc` (committed, not gitignored)

In `wfmut.cpp`, replace the hand-curated block:
```cpp
static const std::unordered_map<std::string, PropInfo> kPropMap = {
#include "kpropmap_generated.inc"
};
```

The file is regenerated by `task gen-oas-headers`; the `.inc` is committed so a checkout without the OAS toolchain still builds.

### Scope

Only the three blocks wired in `get_block()` — COMMON, MOVEBLOC, MESH. Other blocks (COLBLOC, CAMBLOC, etc.) are out of scope until `get_block()` supports them.

### Coverage increase

~15 fields → ~45–50 fields (all members of the three structs). Any panel widget for common/movement/mesh fields now propagates live.

### Verification
- `task gen-oas-headers` runs without error; `kpropmap_generated.inc` changes (if .oas changed) or stays identical (idempotent).
- Build succeeds with the generated include.
- A field outside the original 15 (e.g. `common.Poof` or `movebloc.StepSize`) editable in the panel now propagates to the engine (observe actor change in viewport).
- All existing bridge tests still pass; ASan-clean.

**Commit separately** (M3 is its own commit, with updated `regen-headers.sh` + `kpropmap_generated.inc` + `wfmut.cpp` change).

---

## Estimates (average-programmer scale)

| Milestone | Estimate |
|-----------|----------|
| M1 Confirm SpawnActor | 2–4 h |
| M2 Stable-id map + live sync | ~1 day |
| M3 OAD codegen | 3–5 h |

---

## Critical files

| Milestone | Files |
|-----------|-------|
| M1 | `engine/wf_edit/main.cc`, `engine/mutation/wfmut.{h,cpp}` (`HasTemplate` wrapper) |
| M2 | `engine/wf_edit/engine_bridge.{h,cc}` (map + new bridge notify fns), `engine/wf_edit/main.cc` (DoDelete/DoDuplicate → bridge calls), `engine/wf_edit/level_doc.{h,cc}` (unchanged), `engine/mutation/wfmut.{h,cpp}` (unchanged) |
| M3 | `wfsource/source/oas/regen-headers.sh`, `engine/mutation/kpropmap_generated.inc` (new), `engine/mutation/wfmut.cpp` (replace hand-curated block) |

---

## Out of scope

- Blank/templated "Add" actor (needs a class picker + OAD default population — separate plan)
- Undo for structural edits (needs a general undo stack)
- `GetActorParentIdx` wfmut API (deferred; parentIdx=1 is safe for v1)
- Blocks beyond COMMON/MOVEBLOC/MESH in kPropMap (needs `get_block()` extension)
- Live multi-user CRDT sync of structural edits (out of v1 scope)

---

## Cross-references

- Preceding plan: [outliner-add-delete](../../WorldFoundry.2026-new-level/docs/plans/2026-05-21-outliner-add-delete.md) (D3/D4 follow-ups)
- Engine bridge: [crdt-engine-bridge](../../WorldFoundry.2026-new-level/docs/plans/2026-05-20-crdt-engine-bridge.md)
- Mutation API: [engine-mutation-api](../../WorldFoundry.2026-new-level/docs/plans/2026-05-19-engine-mutation-api.md) (SpawnActor/RemoveActor)
- OAS codegen: [ht-codegen-repair](../../WorldFoundry.2026-new-level/docs/plans/2026-05-20-ht-codegen-repair.md) (`task gen-oas-headers`, `regen-headers.sh`)
