# Code review — wf-edit deep observer, gizmo keys/snap, Markdown chat

**Date:** 2026-05-25
**Status:** Review complete. No severe bugs found. **Findings #1, #3, #4 fixed
2026-05-25.** #1 (frame ordering) — `UpdateBridgeMap` now runs after `CollabDrain`
([`main.cc:556-575`](../../engine/wf_edit/main.cc)). #3 (S hotkey selection guard) and
#4 (snap-step min clamp) — one-line polish, applied. **#2 and #5 remain open**, deferred
to the collab-hardening and live-reload follow-ups respectively.
**Reviewer:** Claude (3-angle finder sweep + direct source verification of every load-bearing claim).

## Scope

Today's four **editor-only** commits (game/level/SMB changes excluded per request):

| Commit | What |
|--------|------|
| [`6f9d5d45`](https://github.com/wbniv/WorldFoundry/commit/6f9d5d45) | deep Doc observer drives all engine propagation |
| [`16258a46`](https://github.com/wbniv/WorldFoundry/commit/16258a46) | verify deep-observer path; fix matched-guard dropping transforms |
| [`cdb9b999`](https://github.com/wbniv/WorldFoundry/commit/cdb9b999) | gizmo G/R/W mode keys + snap (viewport-gizmo Phase 4) |
| [`2c09fe36`](https://github.com/wbniv/WorldFoundry/commit/2c09fe36) | render chat as Markdown (vendor imgui_markdown) |

Files: [`engine/crdt/wfcrdt.cpp`](../../engine/crdt/wfcrdt.cpp)/[`.hpp`](../../engine/crdt/wfcrdt.hpp),
[`engine/wf_edit/engine_bridge.cc`](../../engine/wf_edit/engine_bridge.cc)/[`.h`](../../engine/wf_edit/engine_bridge.h),
[`level_doc.cc`](../../engine/wf_edit/level_doc.cc)/[`.h`](../../engine/wf_edit/level_doc.h),
[`main.cc`](../../engine/wf_edit/main.cc). The vendored `third_party/imgui_markdown/imgui_markdown.h` (1177 lines, MIT drop) was excluded from line-by-line but its integration in `main.cc` was checked.

Related plans: [observe-deep bridge](../plans/2026-05-25-observe-deep-bridge.md),
[viewport gizmo](../plans/2026-05-22-viewport-gizmo.md),
[realtime co-editing](../plans/2026-05-21-realtime-coediting.md).

## Method

Three independent finder angles (line-by-line, removed-behavior, cross-file tracer) surfaced
~15 raw candidates. Every candidate that drove a severity claim was then **verified directly
against the source** rather than trusted from the finder — which refuted four of them
(including the highest-severity one). The findings below are what survived.

## Findings (ranked)

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | **Medium** | `engine_bridge.cc` ordering vs `main.cc:559-567` | Combined structural+field remote edit mistargets the engine for one frame |
| 2 | Low-Med | `engine_bridge.cc:284` | A single-field resync re-applies the actor's *whole* transform, fighting an in-progress local gizmo drag |
| 3 | Low ✅ fixed | `main.cc:815` | `S` snap-toggle hotkey fires with no actor selected (unguarded, unlike Delete) |
| 4 | Low ✅ fixed | `main.cc:950,952` | Snap step accepts `0`/negative → snapping silently disabled while the checkbox still reads "on" |
| 5 | Low / latent | `engine_bridge.cc:50,245,262` | Bridge state is process-global with no reset path; a future in-session level reload would propagate against a stale map |

---

### 1. Frame-ordering: a combined structural+field remote edit mistargets for one frame — *Medium*

**Location:** per-frame loop [`main.cc:558-567`](../../engine/wf_edit/main.cc); mechanism in
`UpdateBridgeMap`/`DrainEngineSync` ([`engine_bridge.cc:243-287`](../../engine/wf_edit/engine_bridge.cc)).

The frame loop runs:

```
558  InitBridgeMap(doc)        // once
559  UpdateBridgeMap(doc)      // IF s_needs_rebuild: rebuild map, clear queue, set s_resync_all
562  CollabDrain(c)            // apply incoming relay SYNC  →  fires the observers
567  DrainEngineSync(doc)      // flush queued edits into the engine
```

The deep observer ([`engine_bridge.cc:232-236`](../../engine/wf_edit/engine_bridge.cc)) queues a
touched actor by its **post-edit** `content[]` index; the content observer
([224-226](../../engine/wf_edit/engine_bridge.cc)) sets `s_needs_rebuild`. The R2 safeguard that
protects against shifted indices — drop the queue + `s_resync_all = true`
([251-252](../../engine/wf_edit/engine_bridge.cc)) — only fires *inside* `UpdateBridgeMap`.

But `UpdateBridgeMap` runs at line 559, **before** `CollabDrain` applies the SYNC at 562. So for
a SYNC that arrives this frame, `s_needs_rebuild` is still false when `UpdateBridgeMap` runs (no-op),
the SYNC then fires both observers, and `DrainEngineSync` at 567 drains the new index against the
**stale, not-yet-rebuilt** `s_doc_to_engine` map with `s_resync_all` still false.

**Failure scenario:** a peer sends one update that, in a single commit, inserts an actor at
`content[2]` *and* edits `content[5].Position`. The observer queues `{5}` (post-insert index);
`DrainEngineSync` maps `5` through the old map and moves the actor that *was* at index 5 (the wrong
one), or — if the queued index is now past the old array end —
`DocActorToEngineIdx` returns 0 and the edit is silently dropped this frame
([278](../../engine/wf_edit/engine_bridge.cc)). It **self-heals next frame**: `UpdateBridgeMap`
finally rebuilds and sets `s_resync_all`, so `DrainEngineSync` re-propagates *every* actor.

**Reachability:** each local gesture is its own Doc commit, so field and structural edits normally
arrive as *separate* SYNCs in separate frames (no co-occurrence). It requires one update carrying
both — i.e. a late-joiner's initial full-state sync, Yjs-coalesced updates, or a multi-part undo.
Impact is a sub-frame (~16 ms) wrong-actor flicker that corrects itself.

**Note:** the comment at [`main.cc:564-566`](../../engine/wf_edit/main.cc) ("Must run after
UpdateBridgeMap so it reads the rebuilt doc→engine map") is misleading — `UpdateBridgeMap` runs
*before* `CollabDrain`, so for the just-applied SYNC the map is **not** rebuilt this frame.

**Fix options:** (a) move `UpdateBridgeMap` to *after* `CollabDrain` (rebuild reflects the SYNC the
same frame); or (b) re-check `s_needs_rebuild` at the top of `DrainEngineSync` and force `s_resync_all`
if a rebuild is still pending. Either makes a same-frame structural+field SYNC correct.

**✅ Fixed 2026-05-25** — applied option (a). The loop is now `InitBridgeMap` → `CollabDrain` →
`UpdateBridgeMap` → `DrainEngineSync` ([`main.cc:556-575`](../../engine/wf_edit/main.cc)). A SYNC's
structural change is rebuilt the same frame it arrives, which forces `s_resync_all` so the field
edit re-propagates against the fresh map. Verified safe: `ReSyncAfterDocChange` (called inside
`CollabDrain`) only refreshes UI caches — it never reads the bridge map — and `InitBridgeMap` stays
first so the observers are registered before the SYNC fires them. Local structural edits (Outliner
UI, runs later in the frame) are still picked up next frame exactly as before. `wf_edit` rebuilt
and relinked clean.

### 2. A single-field resync re-applies the whole actor transform — *Low-Medium*

**Location:** [`engine_bridge.cc:284-285`](../../engine/wf_edit/engine_bridge.cc).

`DrainEngineSync` re-reads and re-propagates **every** field of a touched actor
(`ResolveProperties(ReadActorFields(doc, idx))`), not just the leaf that changed. This is
deliberate and idempotent for the common case, but it re-pushes `Position`/`Orientation` even when
only an unrelated field changed.

**Failure scenario:** the user is mid-drag rotating actor 5 with the gizmo — the engine is updated
live each frame via `ApplyGizmoToEngine` with **no Doc write until release**
([`main.cc:995-997`](../../engine/wf_edit/main.cc)). A peer (or a local undo) edits actor 5's
`Mass`. The deep observer queues `{5}`; `DrainEngineSync` re-reads *all* of actor 5's fields and
re-applies the **stale pre-drag** `Position`/`Orientation` from the Doc, snapping the actor back
mid-gesture until the user moves the mouse again. On release, `CommitGizmoToDoc`
([`main.cc:1003`](../../engine/wf_edit/main.cc)) overwrites with the drag result (last-writer-wins
silently clobbers the peer's edit). Requires concurrent same-actor editing — uncommon but real in
collab.

**Fix:** propagate only the changed leaf (the deep path already carries the field key segment), or
skip `Position`/`Orientation` re-push for the actor currently under an active gizmo drag
(`c->gizmo_active`).

### 3. `S` snap-toggle hotkey is unguarded by selection — *Low*

**Location:** [`main.cc:815-816`](../../engine/wf_edit/main.cc).

The G/R/W/S gizmo hotkeys are gated only on `!typing && !KeyCtrl`
([807](../../engine/wf_edit/main.cc)). Delete is additionally gated on `c->selected >= 0`
([792](../../engine/wf_edit/main.cc)); `S` is not, so pressing `S` with nothing selected (gizmo not
even rendered) still flips `c->gizmo_snap` and that state then persists to `identity.json` on exit
([1594-1596](../../engine/wf_edit/main.cc)). Harmless but surprising. Trivial fix: add the same
selection guard, or accept it as a global preference toggle.

**✅ Fixed 2026-05-25** — added `c->selected >= 0` to the G/R/W/S hotkey block guard
([`main.cc:830`](../../engine/wf_edit/main.cc)). The gizmo isn't rendered without a selection, so
none of the mode/snap keys act when nothing is selected, and `gizmo_snap` can no longer be toggled
into `identity.json` with an empty selection.

> A finder also posited a Ctrl+S-vs-`S` race (release Ctrl a frame before S). **Refuted:**
> `IsKeyPressed(…, /*repeat=*/false)` fires only on the press edge, and line 790 requires `KeyCtrl`
> while 807 requires `!KeyCtrl` — mutually exclusive on the same frame.

### 4. Snap step accepts `0`/negative — *Low (UX only)*

**Location:** [`main.cc:950,952`](../../engine/wf_edit/main.cc) — the `deg`/`units` `InputFloat`s
have no min clamp.

Entering `0` (or clearing the field) sets `gizmo_snap_trans`/`gizmo_snap_rot` to 0, which is passed
to `ImGuizmo::Manipulate`. **This does not freeze or corrupt anything**: ImGuizmo's `ComputeSnap`
guards `if (snap <= FLT_EPSILON) return;` ([`ImGuizmo.cpp:1248-1250`](../../third_party/imguizmo/ImGuizmo.cpp)),
so a 0/negative step silently disables snapping. The only wart is that the "Snap" checkbox still
reads on while nothing snaps. Optional fix: clamp the input to a small positive minimum.

> Originally flagged as a NaN-corruption-on-save bug (`fmodf(delta, 0)` → NaN model matrix →
> `CommitGizmoToDoc` persists NaN to the `.lev`). **Refuted** by reading the vendored ImGuizmo: the
> `<= FLT_EPSILON` guard makes it a no-op. This is why the snap value never reaches a divide.

**✅ Fixed 2026-05-25** — clamp each stored snap step to a small positive minimum right after its
`InputFloat` ([`main.cc:973-979`](../../engine/wf_edit/main.cc)): rotation floored at `1.0` deg
(format is `%.0f`), translation at `0.01` units (format is `%.2f`). Snapping is now always
effective whenever the "Snap" checkbox reads on, and the clamped value is what persists.

### 5. Bridge state is process-global with no reset — *Low / latent*

**Location:** file-statics at [`engine_bridge.cc:41-52`](../../engine/wf_edit/engine_bridge.cc);
`InitBridgeMap` early-returns once `s_bridge_ready`; `DrainEngineSync` early-returns on `!theLevel`
([262](../../engine/wf_edit/engine_bridge.cc)) without clearing the queue.

`s_doc_to_engine`, `s_eid_to_engine`, `s_pending_resync`, `s_deep_sub`, `s_bridge_ready` assume
**one Doc / one level for the whole process** and have no teardown. Not reachable today (wf-edit
loads one level per process and never rebuilds `c->doc`), so this is a *latent* hazard, not a live
bug. It becomes real if an in-session level reload or a second viewport is added — both are on the
roadmap ([editor what's-next #5, HAL decomposition](../plans/2026-05-22-editor-whats-next.md)):
the new Doc would never get a deep observer (early return), and queued edits could propagate against
a stale map. Flagged now because the follow-up that triggers it is already committed. Fix when that
lands: a `ResetBridge()` that drops the subscriptions and clears the maps.

## Candidates verified as NOT bugs

Recording these so the next reviewer doesn't re-chase them:

- **`pf.matched` guard removal** ([`engine_bridge.cc:279-285`](../../engine/wf_edit/engine_bridge.cc)) —
  **correct.** `Position`/`Orientation` are per-instance transform fields not in the OAD
  (`matched=false`); a `matched` guard would drop exactly the viewport-moving edits. Unmapped fields
  become `NoOp` and `PropagateToEngine` ignores them. The fix in `16258a46` is right.
- **Latency on local panel edits** — documented as "by design" at
  [`main.cc:907-908`](../../engine/wf_edit/main.cc) (local and remote edits share the single
  propagation path), **but it is eliminable** and the user asked to remove it. It is actually a
  *structural* ~2-frame lag: `RunEditor` ([`game.cc:471-476`](../../wfsource/source/game/game.cc))
  renders the 3D scene (`StepFrame`) at the *top* of the loop, before `editor_frame` builds the
  panels and drains, so the edit is rendered two `StepFrame`s later. See the follow-up plan
  [zero-latency local edits](../plans/2026-05-25-wf-edit-zero-latency-local-edits.md) — the fix
  reorders so the render happens after the UI build + drain.
- **yffi / Yrs C-ABI usage** ([`wfcrdt.cpp` `decode_event_path`](../../engine/crdt/wfcrdt.cpp)) —
  **correct.** Tag constants (`Y_ARRAY`/`Y_MAP`/`Y_TEXT`), union member names, `YPathSegment`
  key/index access, and `ypath_destroy(segs, len)` ownership release all match `libyrs.h`. The
  no-transaction-in-observer rule is honored (the callback only inserts into a set).
- **Observer lifetime** — **fine** for the single-Doc design: the branch comes from the doc-owned
  root cache (outlives the registration txn), the lambda captures nothing (all file-statics), and the
  callback runs synchronously on the frame thread. (The single-Doc *assumption* is finding #5.)
- **Markdown chat null-callbacks** — **safe.** `imgui_markdown`'s default `formatCallback` is valid;
  link/tooltip callbacks are NULL-guarded; heading-level indexing is bounds-checked.
- **Signature change `WriteFieldLeaf(..., bool remote=false)`** — **safe.** Defaulted, so all ~9
  existing callers compile unchanged.

## Conclusion

The editor work is in good shape. The deep-observer refactor (`6f9d5d45`) is the architecturally
correct move — collapsing local-panel, remote, undo, and replay edits onto one propagation path —
and the C-ABI / lifetime / guard-removal details are right. The one substantive issue is the
**frame-loop ordering** (finding #1): `UpdateBridgeMap` should run *after* `CollabDrain` so a
same-frame structural+field SYNC rebuilds before it drains. It self-heals in one frame today, so
it's a correctness-hygiene fix, not a fire. Findings #2–#5 are minor or latent.

Findings #1 (reorder + comment), #3 (selection guard), and #4 (snap-step clamp) are **applied**
(2026-05-25). Remaining: #2 and #5 are deferred to the collab-hardening / live-reload follow-ups.
