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

namespace wfcrdt { class Doc; }

namespace wfedit {

// Map a Doc content[] index (0-based — what the Outliner selects, i.e.
// EditorCtx::selected) to the engine's 1-based actor index (Actor::GetActorIndex
// / BaseObjectList slot, the same id wfmut::ActorIdx uses). Returns 0 (an
// invalid actor index) when there is no live level or the index is out of range.
//
// v1 is positional with a verified constant offset: the Doc and the engine load
// the same .lev source, so content[i] corresponds to engine actor
// (i + kDocToEngineIdx). DumpIdentityMap is the proof it holds (plan M1).
int DocActorToEngineIdx(int doc_index);

// Verification (WF_EDIT_BRIDGE_DEBUG): print, for every Doc actor, its
// doc_index -> mapped engine_idx -> engine currentPos() alongside the Doc's own
// Position leaf, flagging any mismatch. Called once when the live level is
// available (the global `theLevel`). Reads only — no mutation.
void DumpIdentityMap(wfcrdt::Doc& doc);

}  // namespace wfedit
