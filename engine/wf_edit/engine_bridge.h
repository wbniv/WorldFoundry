//=============================================================================
// engine/wf_edit/engine_bridge.h — CRDT->engine bridge (Option C).
//
// Propagates Doc edits into the live engine via wfmut:: so the viewport
// reflects them. M1: identity mapping (Doc content[] index -> engine 1-based
// wfmut::ActorIdx) + a verification dump. M2 adds field translation; M3 wires
// the panel commit through to wfmut.
//
// EDITOR-ONLY (WF_ENABLE_EDITOR / wf_edit target). The engine stays untouched —
// this consumes the existing wfmut:: surface (engine/mutation/wfmut.hpp). See
// plan docs/plans/2026-05-20-crdt-engine-bridge.md.
//=============================================================================
#pragma once

#include <string>

namespace wfcrdt { class Doc; }

namespace wfedit {

struct PropField;  // property_panel.h — a Doc field after OAD correlation

// Map a Doc content[] index (0-based — what the Outliner selects, i.e.
// EditorCtx::selected) to the engine's 1-based actor index (Actor::GetActorIndex
// / BaseObjectList slot, the same id wfmut::ActorIdx uses). Returns 0 (an
// invalid actor index) when there is no live level, the index is out of range,
// or the actor has no live engine counterpart (non-templated duplicate sentinel).
//
// M2: backed by an explicit stable map (InitBridgeMap) rather than a positional
// formula, so structural edits (BridgeNotifyDelete/Duplicate) don't invalidate
// surviving actors.
int DocActorToEngineIdx(int doc_index);

// Call once when both the Doc and the live engine level are first available
// (first frame after level load). Populates the stable eid→engine map from each
// actor's `_eid` key (stamped by LoadLevelTreeIntoDoc) and registers a
// content-array observer that sets a dirty flag on structural changes.
void InitBridgeMap(wfcrdt::Doc& doc);

// Call every frame (immediately after InitBridgeMap). If the content-array
// observer has flagged a structural change since the last call, re-reads the
// Doc's content array, diffs against the eid→engine map, and calls
// wfmut::RemoveActor / wfmut::SpawnActor as needed. No-op when nothing changed.
void UpdateBridgeMap(wfcrdt::Doc& doc);

// Call every frame (immediately after UpdateBridgeMap). Flushes Doc field edits
// queued by the deep observer (in InitBridgeMap) into the live engine via
// PropagateToEngine. This is the SINGLE engine-propagation path for every Doc
// writer — local panel commits, remote collaborator SYNCs, undo/redo, replay,
// and DAP edits all reach the viewport here, not just the selected actor. Reads
// the Doc (opens short read txns) — must run at frame top with no live txn.
void DrainEngineSync(wfcrdt::Doc& doc);

// Verification (WF_EDIT_BRIDGE_DEBUG): print, for every Doc actor, its
// doc_index -> mapped engine_idx -> engine currentPos() alongside the Doc's own
// Position leaf, flagging any mismatch. Called once when the live level is
// available (the global `theLevel`). Reads only — no mutation.
void DumpIdentityMap(wfcrdt::Doc& doc);

// ── M2: field translation ────────────────────────────────────────────────────
// The engine write a Doc field maps to. v1 covers transform (Position/
// Orientation) + the 15 wfmut kPropMap scalar/enum fields (D4); everything else
// is `None` (the Doc still holds the edit — the viewport just won't change).
struct EngineWrite {
    enum Kind {
        NoOp,       // no engine mapping in v1 (`NoOp` not `None` — Xlib #defines None 0L)
        Pos,        // wfmut::SetActorPos(vec)
        Orient,     // wfmut::SetActorOrientation(vec, revolutions)
        FieldFloat, // wfmut::SetActorField(path, d)   — fixed-point fields
        FieldInt,   // wfmut::SetActorField(path, i)   — int / enum / bool fields
    } kind = NoOp;
    std::string        path;          // "block.field" for FieldFloat/FieldInt
    float              vec[3] = {0, 0, 0};   // Pos / Orient (Orient in revolutions)
    double             d = 0.0;       // FieldFloat
    long long          i = 0;         // FieldInt (enum -> index, bool -> 0/1)
};

// Translate one OAD-correlated Doc field into the engine write that mirrors it.
// Pure (no live engine, no mutation) — M3 dispatches the result through wfmut.
// Coercion preserves WF conventions: Orientation stays in revolutions; float
// fields pass a double (wfmut applies the fixed-point scale); enum/bool fields
// pass the index/flag as an int. Returns kind==NoOp for the unmapped long tail.
EngineWrite TranslateField(const PropField& f);

// WF_EDIT_BRIDGE_DEBUG: resolve a Doc actor's fields and print each field's
// TranslateField result (name -> kind/path/value), so the mapping + coercion is
// visible on real level data. Reads only — no mutation.
void DumpTranslations(wfcrdt::Doc& doc, int doc_index);

// ── M3: propagate a Doc edit into the live engine ────────────────────────────
// Translate `f` and dispatch the result through wfmut on the live level
// (`theLevel`), mapping the Doc actor at `doc_index` to its engine actor idx.
// No-op when there's no live level / no engine actor / the field is unmapped
// (NoOp). Call from the game thread (the editor frame callback) — wfmut's
// contract. The next StepFrame re-renders the mutated actor, so the viewport
// reflects the edit on the following frame.
void PropagateToEngine(int doc_index, const PropField& f);

// WF_EDIT_BRIDGE_TEST headless proof: edit one field's DATA leaf on the
// `doc_index` actor (as the panel's commit would), propagate it through
// PropagateToEngine, and log the engine actor's position before/after so the
// full Doc->bridge->wfmut path is visible without UI interaction. A following
// --screenshot captures the moved actor.
void RunBridgeTest(wfcrdt::Doc& doc, int doc_index,
                   const std::string& field_name, const std::string& new_data);

// WF_EDIT_REMOTE_TEST headless proof for the deep-observer path: edits actor
// `docB`'s Position via a REMOTE-origin txn (Doc::beginRemote — a peer/replay/DAP
// edit), then flushes via DrainEngineSync — WITHOUT any direct PropagateToEngine
// call. Asserts the engine actor moved, so only the deep observer can have driven
// it. `selectedA` is the locally-selected actor (must differ from docB — the
// regression was that a remote edit only reached the *selected* actor). Logs
// "[remote-test] PASS" / "FAIL". Leaves the actor moved so --screenshot captures it.
void RunRemoteSyncTest(wfcrdt::Doc& doc, int selectedA, int docB,
                       const std::string& new_pos);

// WF_EDIT_SPAWN_CONFIRM_TEST headless proof (two parts):
// A) Scans the live level's template table via HasTemplate and logs the first
//    non-null entry. Does NOT attempt to spawn it — Room/Level/Tool templates
//    abort via terminate() in the OAS constructor; Actor-kind confirmation is
//    deferred until a level with safe spawnable templates is available.
// B) Finds the first startup-constructed actor (HasTemplate=false + live engine
//    slot), calls RemoveActor on it, and confirms the deferred-deletion path.
//    Prints "[spawn-test] PASS" on success or "[spawn-test] FAIL" on failure.
void RunSpawnConfirmTest();

}  // namespace wfedit
