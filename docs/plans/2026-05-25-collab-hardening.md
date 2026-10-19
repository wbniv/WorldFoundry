# Collab-hardening — leaf-granular, drag-aware engine propagation

**Status:** ✅ DONE 2026-05-25 (~1 h actual). Both fixes shipped; `wfcrdt_wrapper_test` 14/14 under
ASan+UBSan (strengthened `test_deep_observer` pins the path shape); the `WF_EDIT_DRAGLOCK_TEST`
harness PASSes — a remote non-transform edit *and* a remote Position edit both leave an actively
dragged actor put, and propagation resumes on release.
**Date:** 2026-05-25
**Scope:** wf-edit CRDT→engine bridge. Closes [code-review](../investigations/2026-05-25-wf-edit-code-review.md)
finding #2.
**Estimate:** ~half a day (average programmer familiar with the bridge): ~35 LOC in
[`engine_bridge.cc`](../../engine/wf_edit/engine_bridge.cc), a one-line call-site change, a unit-test
extension, and a headless proof harness.

## Context

The deep-observer bridge ([observe-deep plan](2026-05-25-observe-deep-bridge.md)) made *every* Doc
writer — local panel, remote peer, undo, replay, DAP — drive the live engine through one path:
`DrainEngineSync` ([`engine_bridge.cc:260`](../../engine/wf_edit/engine_bridge.cc)). But that path is
**whole-actor granular**: the deep observer queues only the touched actor's *index*
([`engine_bridge.cc:232-236`](../../engine/wf_edit/engine_bridge.cc) — `s_pending_resync` is a
`std::unordered_set<int>`), discarding the field the path already carries, and `DrainEngineSync`
then re-reads and re-applies **all ~90 fields** of that actor
([`engine_bridge.cc:284-285`](../../engine/wf_edit/engine_bridge.cc)).

That over-application is review finding #2. It's idempotent in the common case but breaks one
real collab scenario:

```
A user is mid-drag moving actor 5 with the gizmo. The gizmo writes the engine LIVE
each frame (ApplyGizmoToEngine) and does NOT write the Doc until mouse-release
(CommitGizmoToDoc) — main.cc:1024-1037.

Frame N, top:  DrainEngineSync runs (main.cc:590) BEFORE the gizmo block.
               A peer's SYNC edited actor 5's Mass.  The observer queued {5}.
               DrainEngineSync re-reads ALL of actor 5 and re-pushes the STALE
               pre-drag Position/Orientation from the Doc → the gizmo's reference
               matrix is rebuilt from the stale pose → the actor jumps mid-gesture.
On release:    CommitGizmoToDoc writes only Position/Orientation (gizmo.cc:124-150),
               so the peer's Mass survives — but the visible jump already happened.
```

Two independent weaknesses feed it: (a) a *non-transform* edit needlessly re-pushes the transform,
and (b) even a legitimately concurrent transform edit yanks an in-progress local drag. We fix both.

## Design

Two coordinated, complementary changes in [`engine_bridge.cc`](../../engine/wf_edit/engine_bridge.cc).

### Fix A — leaf-granular propagation (queue the changed field, not just the actor)

The deep path is already precise enough. For a field-leaf edit the path relative to `content` is
`[ {index: actor}, {key:"items"}, {index: fieldChunk}, … ]` — `path[2]` is the field's position in
the actor's `items[]`, i.e. exactly the `child_index` that [`ReadActorFields`](../../engine/wf_edit/level_doc.cc)
stamps onto every `ActorField` and that survives into `PropField.child_index`. (Confirmed by
`test_deep_observer` and the lossless v2 chunk schema; verified during this plan.)

Change the queue to carry which fields changed, with a whole-actor fallback for ambiguous paths:

```cpp
struct PendingActor {
    bool all = false;                       // ambiguous path → re-apply every field
    std::unordered_set<int> children;       // specific items[] child indices
};
static std::unordered_map<int, PendingActor> s_pending_resync;
```

Observer ([`engine_bridge.cc:232`](../../engine/wf_edit/engine_bridge.cc)) extracts the field index
when the path matches the field shape, else marks the actor `all` (so we never *under*-propagate):

```cpp
for (const auto& p : evs) {
    if (p.empty() || !p[0].isIndex) continue;            // structural → s_content_sub rebuilds
    PendingActor& pa = s_pending_resync[(int)p[0].index];
    if (p.size() >= 3 && !p[1].isIndex && p[1].key == "items" && p[2].isIndex)
        pa.children.insert((int)p[2].index);
    else
        pa.all = true;                                    // can't isolate the leaf
}
```

`DrainEngineSync` filters to the changed children (the `s_resync_all` structural-rebuild branch
keeps its full re-propagate by marking every actor `all`):

```cpp
for (const auto& pf : ResolveProperties(ReadActorFields(doc, idx))) {
    if (!pa.all && !pa.children.count(pf.child_index)) continue;   // unchanged field
    if (idx == drag_locked_doc_idx && IsTransformField(pf.name)) continue;   // Fix B
    PropagateToEngine(idx, pf);
}
```

This alone fixes the review's primary scenario (a peer's *Mass* edit no longer re-pushes the
transform) and is a real per-frame cost win (one field vs. ~90). `UpdateBridgeMap`'s
`s_pending_resync.clear()` and the `s_resync_all` path work unchanged on the new container type.

### Fix B — active-drag transform lock

Fix A still leaves the case where a peer edits the *same* transform field that's under an active
local drag. Guard it: while the local gizmo is dragging, the engine transform of the dragged actor
is owned by the drag until release, so `DrainEngineSync` must not overwrite it.

- Add a small `IsTransformField(name)` helper (`Position` / `Orientation` — the two by-name
  transform fields `CommitGizmoToDoc` writes).
- Give `DrainEngineSync` a defaulted param: `DrainEngineSync(wfcrdt::Doc&, int drag_locked_doc_idx = -1)`
  ([declaration in `engine_bridge.h`](../../engine/wf_edit/engine_bridge.h)).
- The single call site ([`main.cc:590`](../../engine/wf_edit/main.cc)) passes
  `c->gizmo_active ? c->selected : -1` (the flag already exists at
  [`main.cc:211`](../../engine/wf_edit/main.cc) and brackets the drag exactly). On release,
  `CommitGizmoToDoc` writes the final pose and the lock is gone, so the next frame propagates
  normally.

The guard sits inside the per-field loop so it also protects the `s_resync_all` full-resync path
(a structural rebuild mid-drag won't yank the drag either).

## Critical files

- [`engine/wf_edit/engine_bridge.cc`](../../engine/wf_edit/engine_bridge.cc) — `s_pending_resync`
  type, the `observeDeep` callback (~232), `DrainEngineSync` (~260), new `IsTransformField`.
- [`engine/wf_edit/engine_bridge.h`](../../engine/wf_edit/engine_bridge.h) — `DrainEngineSync`
  signature + the proof-harness declaration.
- [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) — call site at ~590; new env-gated proof
  harness alongside the existing `WF_EDIT_REMOTE_TEST` (~640).
- [`engine/crdt/wfcrdt_wrapper_test.cc`](../../engine/crdt/wfcrdt_wrapper_test.cc) — extend
  `test_deep_observer`.

## Verification

1. **Unit (wfcrdt):** extend `test_deep_observer` to assert the path contract Fix A relies on —
   for the nested-leaf edit, `path[1]` is the `"items"` key and `path[2].isIndex` is the field's
   `items[]` index. This pins the wfcrdt side so a future yffi bump can't silently break the
   extraction. Run `cmake --build cmake-build-editor --target wfcrdt_wrapper_test` (the Release
   tree per [build-path memory](../../CLAUDE.md)) under the default ASan+UBSan; expect all tests
   green (currently 14/14).
2. **Headless bridge proof** (env-gated, modelled on `WF_EDIT_REMOTE_TEST`): `WF_EDIT_DRAGLOCK_TEST`
   — select actor A, set `gizmo_active` + move A's engine pose to a drag pose, apply a **remote**
   (`Doc::beginRemote`) edit to A — first a non-transform field (proves Fix A: A doesn't move), then
   a `Position` edit (proves Fix B: A still doesn't move while locked) — then clear the lock and
   confirm the next `DrainEngineSync` propagates normally. Build the `wf_edit` target
   (`cmake --build build-editor --target wf_edit`); confirm the binary timestamp advanced.
3. **Visual proof — degenerate here, so log-based instead.** The property under test is the
   *absence* of motion (the dragged actor must NOT move), which a static before/after pair can't
   convey the way the [observe-deep](2026-05-25-observe-deep-bridge.md) movement screenshots could.
   The deterministic `[draglock-test] … PASS` stderr line (drag-pose held through both remote edits,
   then moved on release) plus the unit test are the honest proof; no screenshot captured.

**As-run result:** `[draglock-test] A=1 (eng 2) drag-pose (11.000 22.000 33.000) | (1) remote
'Global Bounding Box' edit held | (2) locked Position edit held | (3) released Position edit ->
(4.000 5.000 6.000) moved ==> PASS`.

## Scope decisions (what this plan deliberately excludes)

- **Finding #5** (process-global bridge state, no `ResetBridge`) — routed by the review to the
  **live-reload** follow-up, not collab; it's latent until in-session reload / a 2nd viewport
  exists ([editor what's-next](2026-05-22-editor-whats-next.md)). Left there.
- **Last-writer-wins on the *same transform field*** — inherent CRDT behaviour; once Fix B protects
  the in-progress drag and `CommitGizmoToDoc` only touches the transform leaves, the residual is a
  legitimate concurrent-Position tie that Yjs resolves deterministically. No conflict UI in scope.
- **Live two-instance collab-undo check** ([TODO.md](../../TODO.md)) and **presence/awareness
  races** — separate items; not triggered by finding #2.

## Tracking

On completion: flip this **Status**, sync the matching wf-status.md row, mark finding #2 ✅ in the
[code review](../investigations/2026-05-25-wf-edit-code-review.md), and check off the COLLABORATIVE
EDITOR TODO entry.
