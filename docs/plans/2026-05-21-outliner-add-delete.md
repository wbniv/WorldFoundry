# Plan — Outliner add/delete actor (`wf-edit`: structural editing)

**Date:** 2026-05-21
**Status:** **DONE 2026-05-21 (~1.5 h actual vs ~3–4 day estimate) — actor add/delete + save shipped.** Scope approved by Will: ship layers 1 + the Outliner UI, handle the crux the safe way (suspend field→viewport propagation after a structural edit). Fast vs estimate because the identity-map crux — the estimate's "real work" — was handled with the **suspend-propagation guard** (D3) rather than the full live-sync (deferred); estimate stays on the average-programmer scale ([feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md)). Two follow-ups logged ([TODO.md](../../TODO.md)): live structural sync (`wfmut::Spawn`/`RemoveActor`) + a stable-id identity map. The consumer the [lossless Doc schema](2026-05-21-lossless-doc-schema.md) unblocked. **M1** ✓: `wfcrdt::Array::remove` (wraps yffi `yarray_remove_range`, bounds-guarded); `level_doc` `DeleteActor`/`DuplicateActor` (clone via `DocChunkToInput`); headless `WF_EDIT_STRUCT_TEST` proof — snowgoons 36 → `dup=0` → **37** (re-parses; House count 2 = faithful clone) → `del=3` → **35**, ASan-clean. **M2** ✓: Outliner Duplicate/Delete buttons + Del key; a structural edit sets `structural_dirty` → field→viewport propagation suspended (D3 guard) with a toast; [screenshot](../../tests/screenshots/wfedit_outliner_struct.png) (37 actors, the duplicated House selected). Save persists the new count (lossless schema). The `wfcrdt::Array::remove` round-trip is covered end-to-end by the structural-save proof (a dedicated wrapper unit test was skipped as redundant). Next: **M3** — docs + the live-sync / stable-id follow-ups.
**Estimate:** ~3–4 days on the average-programmer scale ([feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md)) — small UI + a wrapper primitive, but the identity-map interaction (D3) is the real work.
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Screenshots

**The Outliner's Duplicate / Delete buttons** appear above the actor list when an actor is selected (qbert_practice, 66 actors):

![Outliner with Duplicate / Delete buttons over the actor list](../../tests/screenshots/qbert_editor_load.png)

**M2 — after a duplicate** (snowgoons 36 → 37; the cloned House selected; field→viewport propagation suspended with a toast until reload):

![Outliner after duplicating the House — 37 actors](../../tests/screenshots/wfedit_outliner_struct.png)

---

## Context

The editor can read/edit/preview/save (field edits). The [lossless Doc schema](2026-05-21-lossless-doc-schema.md) made `content` an arbitrary-length array the save walks faithfully, so **adding/deleting actors in the `Doc` now persists by construction**. This plan wires the Outliner ([main.cc:230](../../engine/wf_edit/main.cc)) to do it.

Three layers, in rising difficulty:

1. **Doc + save** (easy, fully enabled): delete = remove `content[i]`; add = duplicate the selected actor's chunk subtree and push. Save emits the new count. Needs one new primitive — `wfcrdt::Array::remove` (the wrapper has `push`/`insert` but no remove; yffi has [`yarray_remove_range`](../../wftools/y-crdt/yffi/src/lib.rs)).
2. **The bridge's identity map** (the crux): the [CRDT→engine bridge](2026-05-20-crdt-engine-bridge.md) maps `content[i]` → engine actor `i+1` **positionally** (`DocActorToEngineIdx`). A structural Doc edit shifts `content` but **not** the live engine actors, so after a delete/add, field-edit propagation would mutate the **wrong** engine actor. This must be handled or the bridge silently corrupts edits.
3. **Live-viewport reflection** (hardest): for the add/delete to *show* in the viewport, route through `wfmut::SpawnActor`/`RemoveActor`. `RemoveActor` is confirmed (deferred deletion); **`SpawnActor`'s runtime path is committed-but-unconfirmed** (aborts on some templates — [engine mutation API](2026-05-19-engine-mutation-api.md)).

---

## Decisions

| # | Decision | Choice | Reason |
|---|----------|--------|--------|
| D1 | The missing primitive | Add **`wfcrdt::Array::remove(int index, int count = 1)`** wrapping `yarray_remove_range` (mirror `Array::insert`'s yffi pattern, [wfcrdt.cpp](../../engine/crdt/wfcrdt.cpp)). | The wrapper lacks element removal; it's the one piece structural editing needs that doesn't exist. Small + reusable. |
| D2 | Add semantics | **Duplicate the selected actor** (clone its chunk subtree, append to `content`), not "insert a blank actor". | A blank actor needs a class/template + sensible field defaults (a bigger design); duplicating an existing one is immediately useful and reuses the actor's full subtree. Build the clone by reading `content[i]` back into a `wfcrdt::Input` (a `DocActorToInput` deep-copy) and `push`-ing it. |
| D3 | **Identity-map stability (the crux)** | **v1: structural edits invalidate the bridge's positional map; field→viewport propagation is *guarded* (suspended) until the next load/save-reload.** The Doc + save stay correct; only the *live preview* of subsequent field edits is paused after a structural edit (the viewport still shows the pre-edit engine state until reload). | The positional `content[i]↔engine i+1` map is only valid while the two are in lockstep; a Doc-only structural edit breaks it. Keeping them in lockstep (D4) needs `SpawnActor` (unconfirmed) + an answer to whether the engine **compacts** actor indices on removal — unknowns too big for v1. Guarding propagation is the safe minimum that ships structural editing without corrupting field edits. The proper fix (stable-id mapping or full live re-sync) is the **live-structural-sync follow-up**. |
| D4 | Live-viewport structural reflection | **Deferred.** v1's viewport reflects add/delete on **reload** (open the saved `.lev`), not live. | `SpawnActor` is unconfirmed; `RemoveActor` is confirmed but raises the index-compaction question (D3). Wiring live `Spawn`/`Remove` + re-syncing the identity map is its own milestone — gate it behind confirming `SpawnActor` (the SMB Gold work was to settle that). |
| D5 | Undo | **Out of scope** for v1 (no undo for add/delete). | The editor has no undo stack yet; structural undo is a general-undo concern, not this feature's. |

---

## Milestones (each its own commit, [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md))

### 1. `wfcrdt::Array::remove` + the deferred structural-save proof — ✅ DONE 2026-05-21
- **Outcome:** `Array::remove` (bounds-guarded) + `DeleteActor`/`DuplicateActor` (+ `DocChunkToInput` deep-copy) in `level_doc`; `WF_EDIT_STRUCT_TEST` proves dup/del → save → correct OBJ count, re-parses, ASan-clean. The remove round-trip is covered by this end-to-end proof (the standalone wrapper unit test was skipped as redundant).
- Add `Array::remove(index, count=1)` to [wfcrdt.hpp/.cpp](../../engine/crdt/wfcrdt.cpp) (wraps `yarray_remove_range`); extend `wfcrdt_wrapper_test` with a remove round-trip.
- Land the lossless-plan's deferred M2 proof: headless `WF_EDIT_STRUCT_TEST` removes `content[N]` (and duplicates one), saves → `.lev` re-parses with the right OBJ count, survivors byte-identical.
- **Gate:** wrapper test green; structural save proof passes; ASan-clean.

### 2. Outliner add/delete UI + identity-map guard — ✅ DONE 2026-05-21
- **Outcome:** Outliner Duplicate/Delete buttons + Del key → `DoDuplicate`/`DoDelete` → `RefreshAfterStructural` (re-read names, clamp selection, force props re-resolve, set `structural_dirty`). The guard suspends `PropagateToEngine` while `structural_dirty`. Headless `WF_EDIT_STRUCT_UI=dup|del` drives the UI path for the [screenshot](../../tests/screenshots/wfedit_outliner_struct.png). ASan-clean.
- Outliner ([main.cc](../../engine/wf_edit/main.cc)): a delete affordance (Del key / right-click "Delete") on the selected actor → `Array::remove`; an "Add (duplicate)" button → `DocActorToInput(selected)` + `push`. Re-read `actor_names`; fix up `selected`.
- **Identity-map guard (D3):** a `structural_dirty` flag set on any add/delete; `PropagateToEngine` becomes a no-op while set (with a one-time toast: "structural edit — reload to resume live preview"). Cleared on (re)load.
- **Gate:** add/delete in the Outliner updates the list + persists on save ([screenshot](../../tests/screenshots/wfedit_outliner_struct.png) of the Outliner after the duplicate + the saved `.lev` diff); a field edit *after* a structural edit does **not** mutate the wrong actor (guard verified). ASan-clean; runtime byte-unchanged.

### 3. Docs + status sync — ✅ DONE 2026-05-21
- Plan Status → Done w/ actuals; [wf-status.md](../../wf-status.md) row → Done; the TODO Outliner-add/delete entry updated (Doc-level done; remaining = live sync + stable-id map); design-doc structural-editing note; the **live-structural-sync** (D4) + **stable-id identity map** (D3 proper fix) follow-ups logged in [TODO.md](../../TODO.md).

---

## Verification

1. **`Array::remove`** round-trips (wrapper test).
2. **Structural save** — add/delete → saved `.lev` has the right OBJ count, survivors byte-identical, re-parses (the lossless-plan M2 proof, now landed here).
3. **Bridge not corrupted** — a field edit after a structural edit is guarded (no wrong-actor mutation); identity map valid again after reload.
4. **No regression** — field-edit→viewport (bridge), save round-trip, panel render all still pass when no structural edit has happened.
5. **ASan/UBSan/LSan clean**; runtime byte-unchanged (editor-only).

---

## Critical files

**Modify:** [`engine/crdt/wfcrdt.{hpp,cpp}`](../../engine/crdt/wfcrdt.cpp) (`Array::remove`), [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) (Outliner UI + `structural_dirty` guard), [`engine/wf_edit/level_doc.{h,cc}`](../../engine/wf_edit/level_doc.cc) (`DocActorToInput` clone; `WF_EDIT_STRUCT_TEST`), [`engine/wf_edit/engine_bridge.{h,cc}`](../../engine/wf_edit/engine_bridge.cc) (propagation guard), `engine/crdt/wfcrdt_wrapper_test`, [wf-status.md](../../wf-status.md), [TODO.md](../../TODO.md).
**Reuse:** `wfmut::RemoveActor`/`SpawnActor` (only when D4's live-sync follow-up lands).

---

## Out of scope (each its own later plan)

- **Live-viewport structural sync (D4)** — `wfmut::Spawn`/`RemoveActor` + identity-map re-sync so add/delete shows live. Gated on confirming `SpawnActor`'s runtime path + answering whether the engine compacts actor indices on removal.
- **Stable-id identity map (D3 proper fix)** — replace the positional `content[i]↔i+1` map with a per-actor stable id ↔ engine idx lookup, so structural edits don't invalidate field propagation. The robust replacement for v1's guard.
- **Blank/templated add** — insert a new actor of a chosen class with defaults (vs. duplicate). Needs a class picker + OAD-default population.
- **Undo** (D5) — general editor undo stack.

---

## Cross-references

- Parent: [lossless Doc schema](2026-05-21-lossless-doc-schema.md) (unblocked this; deferred its M2 proof here), [CRDT→engine bridge](2026-05-20-crdt-engine-bridge.md) (the identity map this perturbs), [save round-trip](2026-05-21-editor-save-roundtrip.md), [engine mutation API](2026-05-19-engine-mutation-api.md) (`Spawn`/`RemoveActor`; SpawnActor unconfirmed).
- Memory: [feedback_estimate_average_programmer_scale](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_estimate_average_programmer_scale.md), [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md), [project_followup_mailbox_999_crash](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_followup_mailbox_999_crash.md), [project_wf_edit_build_path](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_wf_edit_build_path.md).
